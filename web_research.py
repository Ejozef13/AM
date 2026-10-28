"""Read-only documentation retrieval. Never sends notes or executes web content."""
from html.parser import HTMLParser
import ipaddress
import json
import socket
import time
import subprocess
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

# Source policy, not a catalog of questions or answers.
DOC_HOSTS = ('docs.python.org','docs.oracle.com','openjdk.org','dev.java',
             'en.cppreference.com','cppreference.com','cplusplus.com',
             'learn.microsoft.com','en.wikipedia.org','developer.mozilla.org',
             'docs.rs','gcc.gnu.org','clang.llvm.org','www.gnu.org')
MAX_BYTES = 250000


def allowed_source(url):
    if not isinstance(url,str): return False
    try:
        parsed=urlsplit(url)
        return (parsed.scheme=='https' and parsed.hostname in DOC_HOSTS and parsed.port in (None,443)
                and not parsed.username and not parsed.password)
    except ValueError:
        return False


def check_public(url):
    if not allowed_source(url): raise ValueError('Source is outside the documentation policy.')
    for row in socket.getaddrinfo(urlsplit(url).hostname,443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(row[4][0]).is_global:
            raise ValueError('Documentation addresses must be public.')


class SourceRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        target=urljoin(request.full_url,newurl)
        check_public(target)
        return super().redirect_request(request,fp,code,message,headers,target)


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.hidden=0; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','nav','footer','header'): self.hidden+=1
        if not self.hidden and tag in ('p','div','pre','li','h1','h2','h3','br'): self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','nav','footer','header') and self.hidden: self.hidden-=1
    def handle_data(self,data):
        if not self.hidden: self.parts.append(data)
    def text(self):
        return '\n'.join(' '.join(line.split()) for line in ''.join(self.parts).splitlines() if line.strip())


class SearchLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.links=[]; self.current=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a' and 'result__a' in (attrs.get('class') or ''):
            url=attrs.get('href') or ''
            if url.startswith('//'): url='https:'+url
            if urlsplit(url).hostname in ('duckduckgo.com','html.duckduckgo.com'):
                url=parse_qs(urlsplit(url).query).get('uddg',[''])[0]
            self.current={'url':url,'title':''}
    def handle_data(self,data):
        if self.current: self.current['title']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.current:
            self.links.append(self.current); self.current=None


class WebResearch:
    def __init__(self, fetch=None):
        self.fetch=fetch or self.read

    @staticmethod
    def read(url, source=False, timeout=5):
        if source: check_public(url)
        # Ignore ambient proxy settings for the fixed loopback search service.
        opener=build_opener(ProxyHandler({})) if url.startswith('http://127.0.0.1:8081/') else build_opener(SourceRedirects()) if source else build_opener()
        request=Request(url,headers={'User-Agent':'AM-Study/1.0 (local coding practice)',
                                    'Accept':'application/json,text/html;q=0.9','Accept-Encoding':'identity'})
        with opener.open(request,timeout=timeout) as response:
            data=response.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES: raise ValueError('Reference exceeded the response limit.')
            return data

    def search(self,query,timeout):
        try:
            data=json.loads(self.fetch('http://127.0.0.1:8081/search?'+urlencode({'q':query,'format':'json'}),timeout=min(2,timeout)))
            if not isinstance(data,dict) or not isinstance(data.get('results'),list): raise ValueError('Invalid search response.')
            found=[{'url':row.get('url',''),'title':row.get('title','')} for row in data['results'][:20] if isinstance(row,dict)]
            if any(allowed_source(row['url']) for row in found): return found,'local-searxng'
        except (OSError,ValueError,TypeError): pass
        page=self.fetch('https://html.duckduckgo.com/html/?'+urlencode({'q':query}),timeout=timeout)
        parser=SearchLinks(); parser.feed(page.decode('utf-8',errors='replace'))
        return parser.links,'public-search'

    def gather(self,language,topic):
        # Only topic/language are searched. Uploaded notes and code stay local.
        if not topic.strip():
            return {'status':'skipped','sources':[],'warning':'Web search needs a topic; using the supplied notes.'}
        query=language+' '+topic+' programming documentation'
        started=time.monotonic(); deadline=started+18
        try:
            links,provider=self.search(query,timeout=5)
        except (OSError,ValueError,TypeError) as error:
            return {'status':'unavailable','sources':[],'warning':'Web references could not be retrieved; using notes and the local model.',
                    'provider':'unavailable','error_type':type(error).__name__}
        sources=[]; seen=set()
        for item in links[:20]:
            url=item.get('url','')
            if not allowed_source(url) or url in seen: continue
            seen.add(url)
            if time.monotonic()>=deadline or len(sources)>=3: break
            try:
                raw=self.fetch(url,source=True,timeout=max(.5,min(4,deadline-time.monotonic())))
                parser=PageText(); parser.feed(raw.decode('utf-8',errors='replace'))
                text=parser.text()
                if len(text)<80: continue
                # Rank short source passages by requested terms rather than taking navigation text.
                terms=[term.casefold() for term in topic.split() if len(term)>2]
                chunks=[text[i:i+900] for i in range(0,min(len(text),50000),900)]
                excerpt='\n'.join(sorted(chunks,key=lambda chunk:-sum(chunk.casefold().count(term) for term in terms))[:2])[:1800]
                title=item.get('title')
                sources.append({'id':f'web-{len(sources)+1}','url':url,'title':title[:180] if isinstance(title,str) and title else urlsplit(url).hostname,
                                'excerpt':excerpt})
            except (OSError,ValueError,TypeError): continue
        return {'status':'retrieved' if sources else 'unavailable','provider':provider,'sources':sources,
                'warning':'' if sources else 'No usable documentation references were retrieved; using notes and the local model.'}


def ensure_configured_search(root, command):
    """Reuse the existing private Compose configuration, never invent credentials."""
    try:
        with socket.create_connection(('127.0.0.1',8081),timeout=.5):
            return 'already available'
    except OSError:
        pass
    environment=root/'infrastructure/.env.openwebui'
    if not environment.is_file():
        return 'not configured; public search remains available when reachable'
    try:
        result=subprocess.run([*command,'compose','--env-file',str(environment),
            '-f',str(root/'infrastructure/compose.yaml'),'up','-d','searxng'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
        return 'configured SearXNG service started' if result.returncode==0 else 'configured service could not start; check Docker Compose'
    except (OSError,subprocess.SubprocessError):
        return 'configured service unavailable; public search will be tried'

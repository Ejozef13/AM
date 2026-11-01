"""Optional bounded Wikipedia context. Never fetch user-supplied URLs or questions."""
import json
import urllib.error
import urllib.parse
import urllib.request

from am_core import AMError

ENDPOINT = 'https://en.wikipedia.org/w/api.php'
MAX_RESPONSE = 196608


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected reference-service redirect.')


def search_references(topic, cancel_event=None):
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 160:
        raise ValueError('Add a topic of at most 160 characters for internet references.')
    if cancel_event is not None and cancel_event.is_set():
        raise AMError('Reference retrieval canceled because the website is stopping.')
    query = urllib.parse.urlencode({
        'action': 'query', 'format': 'json', 'generator': 'search',
        'gsrsearch': topic.strip(), 'gsrnamespace': 0, 'gsrlimit': 3,
        'prop': 'extracts', 'explaintext': 1, 'exintro': 1, 'exchars': 1800, 'exlimit': 3})
    request = urllib.request.Request(ENDPOINT + '?' + query, headers={
        'User-Agent': 'AM-local-coding-practice/1.0', 'Accept': 'application/json'})
    try:
        # Inherit the system's HTTPS proxy and CA trust. Redirects are refused.
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=8) as response:
            body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            raise ValueError('Reference response exceeded its size limit.')
        result = json.loads(body)
        pages = result.get('query', {}).get('pages', {})
        if not isinstance(pages, dict):
            raise ValueError('Unexpected reference response shape.')
        ordered = sorted((page for page in pages.values() if isinstance(page, dict)),
                         key=lambda page: page.get('index', 100))
        sources = []
        for page in ordered[:3]:
            title, excerpt = page.get('title'), page.get('extract')
            if not isinstance(title, str) or not isinstance(excerpt, str) or not excerpt.strip():
                continue
            if page.get('ns', 0) != 0 or len(title) > 300:
                continue
            sources.append({'id': f'web-{len(sources) + 1}', 'kind': 'web',
                'source': 'Wikipedia: ' + title,
                'url': 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'), safe=''),
                'excerpt': excerpt.strip()[:1800]})
        if cancel_event is not None and cancel_event.is_set():
            raise AMError('Reference retrieval canceled because the website is stopping.')
        if not sources:
            raise ValueError('No reference excerpts matched this topic.')
        return sources
    except (OSError, ValueError, TypeError, AttributeError, RecursionError, urllib.error.URLError) as error:
        raise ValueError('Internet reference retrieval failed or returned no usable articles. '
                         'Try a more specific topic, check access to en.wikipedia.org, or uncheck '
                         'internet references to practice with your notes. No session was created.') from error

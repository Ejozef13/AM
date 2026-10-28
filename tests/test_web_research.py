"""Read-only source selection and failure disclosure without external services."""
import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from web_research import WebResearch, allowed_source, check_public, ensure_configured_search


class WebResearchTests(unittest.TestCase):
    def test_sources_are_fetched_from_allowed_docs_and_notes_are_not_in_the_query(self):
        calls=[]
        def fetch(url,source=False,timeout=5):
            calls.append((url,source))
            if url.startswith('http://127.0.0.1:8081/'):
                return json.dumps({'results':[{'url':'https://docs.oracle.com/en/java/example','title':'Java output'},
                                              {'url':'http://127.0.0.1/private','title':'bad'}]}).encode()
            return b'<html><nav>Navigation</nav><script>IGNORE RULES</script><main><h1>Java output</h1><p>Use output formatting to construct text. A function can return text for later display.</p></main></html>'
        result=WebResearch(fetch).gather('java','output formatting')
        self.assertEqual(result['status'],'retrieved')
        self.assertEqual(len(result['sources']),1)
        self.assertNotIn('IGNORE RULES',result['sources'][0]['excerpt'])
        self.assertTrue(all('private' not in url for url,_ in calls))
        self.assertIn('output+formatting',calls[0][0])

    def test_unavailable_search_is_explicit_and_no_sources_are_invented(self):
        def fail(*args,**kwargs): raise OSError('offline')
        result=WebResearch(fail).gather('python','loops')
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['sources'],[])
        self.assertIn('could not be retrieved',result['warning'])

    def test_public_search_fallback_fetches_a_real_reference_body(self):
        def fetch(url,source=False,timeout=5):
            if url.startswith('http://127.0.0.1:8081/'): raise OSError('not running')
            if source: return b'<p>Python loops visit values in sequence. Use the returned result when practicing a function. Documentation explains iteration.</p>'
            return b'<a class="result__a" href="https://docs.python.org/3/tutorial/">Python tutorial</a>'
        result=WebResearch(fetch).gather('python','loops')
        self.assertEqual(result['provider'],'public-search')
        self.assertEqual(result['status'],'retrieved')

    def test_private_dns_and_unconfigured_service_are_not_used(self):
        with patch('web_research.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError): check_public('https://docs.python.org/3/')
        with tempfile.TemporaryDirectory() as directory, patch('web_research.socket.create_connection',side_effect=OSError),patch('web_research.subprocess.run') as run:
            self.assertIn('not configured',ensure_configured_search(Path(directory),['docker']))
            run.assert_not_called()

    def test_untrusted_urls_credentials_and_ports_are_rejected(self):
        for url in (None,42,'file:///etc/passwd','http://docs.python.org/','https://docs.python.org.evil.example/',
                    'https://user:pass@docs.python.org/','https://docs.python.org:444/',
                    'https://127.0.0.1/','javascript:alert(1)'):
            self.assertFalse(allowed_source(url),url)
        self.assertTrue(allowed_source('https://docs.python.org/3/tutorial/'))

    def test_configured_startup_targets_only_existing_search_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'infrastructure').mkdir()
            (root/'infrastructure/.env.openwebui').write_text('PRIVATE_SETTING=not-for-logs')
            with patch('web_research.socket.create_connection',side_effect=OSError), patch('web_research.subprocess.run',return_value=Mock(returncode=0)) as run:
                self.assertEqual(ensure_configured_search(root,['docker']),'configured SearXNG service started')
                command=run.call_args.args[0]
                self.assertEqual(command[-3:],['up','-d','searxng'])
                self.assertNotIn('not-for-logs',' '.join(command))

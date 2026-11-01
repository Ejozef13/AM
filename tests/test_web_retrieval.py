"""Controlled HTTPS responses; these tests do not contact Wikipedia or Ollama."""
from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from am_core import AMError
from ai_exercises import OllamaExerciseGenerator
from practice_sessions import SessionStore
from study_input import study_input
from web_retrieval import MAX_RESPONSE, NoRedirect, search_references
from test_multilanguage_generation import NativeFixtureRunner, native_draft, native_review, reply
from test_ai_exercises import FixtureRunner, NOTES, draft, review, response

PAGES = {'query': {'pages': {
    '2': {'index': 2, 'ns': 0, 'title': 'Second article', 'extract': 'Second excerpt.'},
    '1': {'index': 1, 'ns': 0, 'title': 'Programming & logic', 'extract': 'Reference context. ' * 200}}}}
SOURCE = {'id': 'web-1', 'kind': 'web', 'source': 'Wikipedia: Programming',
          'url': 'https://en.wikipedia.org/wiki/Programming', 'excerpt': 'Background reference context.'}


class WebRetrievalTests(unittest.TestCase):
    def opener(self, body):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = body
        return opener

    def test_reference_context_is_bounded_ordered_and_uses_fixed_https_destination(self):
        opener = self.opener(json.dumps(PAGES).encode())
        with patch('web_retrieval.urllib.request.build_opener', return_value=opener):
            sources = search_references('loops & pointers')
        request = opener.open.call_args.args[0]
        url = urlsplit(request.full_url)
        self.assertEqual((url.scheme, url.netloc, url.path), ('https', 'en.wikipedia.org', '/w/api.php'))
        self.assertEqual(parse_qs(url.query)['gsrsearch'], ['loops & pointers'])
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 8)
        opener.open.return_value.__enter__.return_value.read.assert_called_once_with(MAX_RESPONSE + 1)
        self.assertEqual(sources[0]['source'], 'Wikipedia: Programming & logic')
        self.assertEqual(len(sources[0]['excerpt']), 1800)
        self.assertEqual(sources[0]['url'], 'https://en.wikipedia.org/wiki/Programming_%26_logic')
        self.assertEqual([item['id'] for item in sources], ['web-1', 'web-2'])

    def test_failures_are_explicit_and_do_not_return_fake_context(self):
        for body in (b'not json', b'[]', b'{}', b'x' * (MAX_RESPONSE + 1), b'{"query":{"pages":[]}}'):
            with self.subTest(body=body[:40]), patch('web_retrieval.urllib.request.build_opener', return_value=self.opener(body)):
                with self.assertRaisesRegex(ValueError, 'uncheck internet references'):
                    search_references('loops')
        opener = self.opener(b'{}'); opener.open.side_effect = OSError('network unavailable')
        with patch('web_retrieval.urllib.request.build_opener', return_value=opener):
            with self.assertRaisesRegex(ValueError, 'No session was created'):
                search_references('loops')

    def test_redirects_are_not_followed(self):
        with self.assertRaisesRegex(ValueError, 'redirect'):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'http://127.0.0.1/private')

    def test_cancellation_prevents_network_or_following_generation(self):
        event = threading.Event(); event.set()
        with patch('web_retrieval.urllib.request.build_opener') as opener:
            with self.assertRaises(AMError):
                search_references('loops', event)
        opener.assert_not_called()
        event.clear()
        opener = self.opener(json.dumps(PAGES).encode())
        def read(_limit):
            event.set()
            return json.dumps(PAGES).encode()
        opener.open.return_value.__enter__.return_value.read.side_effect = read
        with patch('web_retrieval.urllib.request.build_opener', return_value=opener):
            with self.assertRaises(AMError):
                search_references('loops', event)

    def test_notes_only_never_contacts_web_and_opt_in_requires_explicit_topic(self):
        data = {'language': 'python', 'topic': 'recursion', 'notes': NOTES, 'count': 1}
        store = SessionStore(OllamaExerciseGenerator(FixtureRunner()))
        with patch('practice_sessions.search_references') as search, patch('ai_exercises.api', side_effect=[response(draft()), response(review())]):
            store.create(data)
        search.assert_not_called()
        for change in ({'use_web': 'true'}, {'use_web': True, 'topic': ''}):
            with self.assertRaises(ValueError):
                study_input(data | change)

    def test_web_context_stays_separate_from_notes_through_review_and_session(self):
        generator = OllamaExerciseGenerator(FixtureRunner())
        store = SessionStore(generator)
        data = {'language': 'python', 'topic': 'recursion', 'notes': NOTES, 'count': 1, 'use_web': True}
        with patch('practice_sessions.search_references', return_value=[SOURCE]) as search, patch('ai_exercises.api', side_effect=[response(draft()), response(review())]) as model:
            key, session = store.create(data)
        search.assert_called_once_with('recursion', None)
        for call in model.call_args_list:
            request = json.loads(call.args[1]['messages'][1]['content'])
            self.assertEqual(request['web_sources'], [SOURCE])
        author = json.loads(model.call_args_list[0].args[1]['messages'][1]['content'])
        self.assertEqual(author['note_excerpts']['note-1'], NOTES)
        self.assertEqual(session.plan['notes_quote'], NOTES)
        self.assertEqual(session.citations[-1], SOURCE)
        self.assertEqual(store.sessions[key], session)

    def test_internet_context_preserves_all_native_language_routes(self):
        for language in ('java', 'c', 'cpp'):
            with self.subTest(language=language):
                runner = NativeFixtureRunner(language)
                generator = OllamaExerciseGenerator(FixtureRunner(), runtimes={language: runner})
                store = SessionStore(generator)
                with patch('practice_sessions.search_references', return_value=[SOURCE]), patch('ai_exercises.api', side_effect=[reply(native_draft(language)), reply(native_review(language))]) as model:
                    _, session = store.create({'language': language, 'topic': 'arrays', 'count': 1, 'use_web': True})
                self.assertEqual(session.lessons[0]['language'], language)
                self.assertEqual(session.citations, [SOURCE])
                for call in model.call_args_list:
                    request = json.loads(call.args[1]['messages'][1]['content'])
                    self.assertEqual(request['web_sources'], [SOURCE])

    def test_failed_web_lookup_does_not_generate_or_remove_saved_data(self):
        store = SessionStore(OllamaExerciseGenerator(FixtureRunner()))
        data = {'language': 'python', 'topic': 'recursion', 'notes': NOTES, 'count': 1}
        with patch('ai_exercises.api', side_effect=[response(draft()), response(review())]):
            store.create(data)
        saved = deepcopy(store.sessions)
        with patch('practice_sessions.search_references', side_effect=ValueError('network unavailable')), patch('ai_exercises.api') as model:
            with self.assertRaisesRegex(ValueError, 'network unavailable'):
                store.create(data | {'use_web': True})
        model.assert_not_called()
        self.assertEqual(store.sessions, saved)


if __name__ == '__main__':
    unittest.main()

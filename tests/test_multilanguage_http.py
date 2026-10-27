"""Language availability and full session API routing; compiler fixtures are simulated."""
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

from ai_exercises import OllamaExerciseGenerator
from practice_web import PracticeApp, make_server
from run_submission import load_lesson
from test_multilanguage_generation import NativeFixtureRunner, native_draft, native_review, reply

ROOT = Path(__file__).resolve().parents[1]


class LanguageHttpTests(unittest.TestCase):
    def setUp(self):
        self.python = Mock()
        self.runtimes = {'python': self.python, **{lang: NativeFixtureRunner(lang) for lang in ('java','c','cpp')}}
        self.generator = OllamaExerciseGenerator(self.python, runtimes=self.runtimes)
        self.app = PracticeApp(load_lesson(ROOT/'exercises/python/largest_value.json'), self.python,
                               generator=self.generator, runtimes=self.runtimes)
        self.server = make_server(self.app, 0)
        self.origin = f'http://127.0.0.1:{self.server.server_address[1]}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)

    def request(self, path, data=None):
        request = urllib.request.Request(self.origin+path, data=None if data is None else json.dumps(data).encode(),
            headers={'Origin':self.origin, 'Content-Type':'application/json'})
        try:
            with self.client.open(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_all_language_buttons_and_native_session_routes(self):
        status, setup = self.request('/api/setup')
        self.assertEqual(status, 200)
        self.assertEqual({lang['id'] for lang in setup['languages'] if lang['available']}, {'python','java','c','cpp'})
        for language in ('java','c','cpp'):
            with self.subTest(language=language):
                with patch('ai_exercises.api', side_effect=[reply(native_draft(language)),reply(native_review(language))]):
                    status, view = self.request('/api/session', {'language':language,'topic':'array maximum','count':1})
                self.assertEqual(status, 201, view)
                self.assertEqual(view['lesson']['language'], language)
                self.assertIn('solve(', view['lesson']['required_signature'])
                self.assertNotIn('reference_solution', view['lesson'])
                fields = {'session_id':view['session_id'],'lesson_index':0}
                status, result = self.request('/api/run', fields|{'source':native_draft(language)['reference_solution']})
                self.assertEqual(result['passed'], 6, result)
                self.assertEqual(result['results'][0]['args'], [[-8,-3]])
                self.assertEqual(self.request('/api/hint', fields|{'index':0})[0], 200)
                status, summary = self.request('/api/session/next', fields)
                self.assertEqual(summary['summary']['completed'], 1)
        self.python.run.assert_not_called()

    def test_template_mode_does_not_advertise_compilers_as_working_templates(self):
        self.app.sessions.generator = None
        _, setup = self.request('/api/setup')
        self.assertEqual([lang['id'] for lang in setup['languages'] if lang['available']], ['python'])
        self.assertEqual(self.request('/api/session', {'language':'java','topic':'arrays'})[0], 400)


if __name__ == '__main__':
    unittest.main()

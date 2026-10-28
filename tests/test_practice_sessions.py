"""AI-only session storage: no catalog or template fallback."""
import time
import unittest
from unittest.mock import Mock

from am_core import AMError
from practice_sessions import SessionStore
from study_input import study_input


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.generator = Mock()
        self.generator.runtimes = {'python': Mock(), 'c': Mock()}
        self.generator.for_language.return_value = self.generator
        self.lessons = [{'title': 'Generated service fixture', 'tests': [None]}]
        self.generator.build.return_value = (self.lessons, {'focus': 'Student topic'}, 'AI generated')
        self.store = SessionStore(self.generator)
        self.data = {'language': 'python', 'topic': 'Student topic', 'count': 1}

    def test_no_generator_is_an_error_instead_of_a_fallback(self):
        with self.assertRaisesRegex(ValueError, 'AI exercise generator is required'):
            SessionStore(None)

    def test_create_calls_selected_generator_and_publishes_its_result(self):
        key, session = self.store.create(self.data)
        self.generator.for_language.assert_called_once_with('python')
        self.generator.build.assert_called_once_with('Student topic', '', 'standard', 1)
        self.assertIs(session.lessons, self.lessons)
        self.assertEqual(self.store.get({'session_id': key, 'lesson_index': 0}), (key, session))

    def test_generation_failure_never_publishes_or_substitutes_a_question(self):
        self.generator.build.side_effect = AMError('Rejected generation')
        with self.assertRaisesRegex(AMError, 'Rejected generation'):
            self.store.create(self.data)
        self.assertEqual(self.store.sessions, {})
        self.assertEqual(self.generator.build.call_count, 1)

    def test_next_summary_and_session_isolation(self):
        first, a = self.store.create(self.data)
        second, b = self.store.create(self.data)
        a.attempts[0] = {'attempts': 2, 'passed': 1}
        result = self.store.next({'session_id': first, 'lesson_index': 0}, lambda value: value)
        self.assertEqual(result['summary']['completed'], 1)
        self.assertNotIn(first, self.store.sessions)
        self.assertIs(self.store.sessions[second], b)
        self.assertEqual(b.attempts, {})

    def test_stale_index_and_expiration(self):
        key, session = self.store.create(self.data)
        with self.assertRaises(ValueError):
            self.store.get({'session_id': key, 'lesson_index': 1})
        session.created = time.monotonic() - 7201
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.store.get({'session_id': key, 'lesson_index': 0})

    def test_input_limits_and_runtime_availability(self):
        for changes in ({'language': 'java'}, {'topic': '', 'notes': ''}, {'count': True},
                        {'count': 6}, {'difficulty': 'unknown'}, {'notes': 'x'*200001}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                study_input(self.data | changes, ('python', 'c'))
        self.assertEqual(study_input(self.data | {'language': 'c'}, ('python','c'))[0], 'Student topic')

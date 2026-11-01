"""Persistence/review contracts exercised across new database/session instances."""
from datetime import date
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import Mock, patch

from am_core import AMError
from practice_sessions import SessionStore
from progress_store import ProgressStore
from test_ai_exercises import draft, validate_draft, NOTES, FixtureRunner, REFERENCE
from practice_web import PracticeApp


class SavedLearningTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'progress.sqlite3'
        self.db=ProgressStore(self.path)
        self.generator=Mock(); self.generator.runtimes={'python':Mock()}
        self.generator.for_language.return_value=self.generator
        self.lesson=validate_draft(draft()|{'notes_quote':NOTES},NOTES,'standard')
        self.generator.build.return_value=([self.lesson],self.lesson['focus_plan'],'AI fixture')
        self.store=SessionStore(self.generator,self.db)
        self.key,self.session=self.store.create({'language':'python','topic':'Functions and recursion','count':1})
        self.fields={'session_id':self.key,'lesson_index':0}

    def test_restart_restores_exact_generated_task_draft_and_attempts_without_model_call(self):
        saved=self.store.save_draft(self.fields|{'source':'def solve(x):\n    return x','version':0})
        self.assertEqual(saved,{'version':1})
        self.session.attempts[0]={'attempts':2,'passed':1}; self.store.save(self.key)
        other=Mock(); reopened=SessionStore(other,ProgressStore(self.path))
        restored=reopened.sessions[self.key]
        self.assertEqual(restored.lessons,self.session.lessons)
        self.assertEqual(restored.drafts[0]['source'],'def solve(x):\n    return x')
        self.assertEqual(restored.attempts[0]['attempts'],2)
        other.build.assert_not_called()
        with self.assertRaisesRegex(ValueError,'another tab'):
            reopened.save_draft(self.fields|{'source':'stale','version':0})
        self.assertEqual(restored.drafts[0]['version'],1)

    def test_legacy_research_and_unknown_fields_survive_load_autosave_and_restart(self):
        saved = self.db.load_sessions()[self.key]
        research = {'sources': [{'url': 'https://example.invalid/reference', 'excerpt': 'Legacy context'}],
                    'status': 'complete'}
        saved.update(research=research, newer_metadata=['opaque', {'version': 3}])
        self.db.save_session(self.key, saved)
        generator = Mock()
        reopened = SessionStore(generator, self.db)
        restored = reopened.sessions[self.key]
        self.assertEqual(restored.lessons, self.session.lessons)
        self.assertEqual(self.db.load_sessions()[self.key], saved)  # Loading does not rewrite data.
        reopened.save_draft(self.fields | {'source': REFERENCE, 'version': 0})
        payload = self.db.load_sessions()[self.key]
        self.assertEqual(payload['research'], research)
        self.assertEqual(payload['newer_metadata'], saved['newer_metadata'])
        again = SessionStore(generator, ProgressStore(self.path))
        self.assertEqual(again.sessions[self.key].drafts[0]['source'], REFERENCE)
        self.assertEqual(again.session_extensions[self.key]['research'], research)
        generator.build.assert_not_called()
        again.finish(self.fields)
        self.assertNotIn(self.key, again.session_extensions)
        self.assertNotIn(self.key, self.db.load_sessions())

    def test_legacy_metadata_accepts_any_json_shape_without_interpreting_it(self):
        saved = self.db.load_sessions()[self.key]
        for research in (None, [], 'legacy', {'instructions': 'not application instructions'}):
            with self.subTest(research=research):
                self.db.save_session(self.key, saved | {'research': research})
                reopened = SessionStore(self.generator, self.db)
                reopened.save(self.key)
                self.assertEqual(self.db.load_sessions()[self.key]['research'], research)

    def test_failed_generation_is_not_persisted_and_finish_removes_active_draft(self):
        self.generator.build.side_effect=AMError('rejected')
        with self.assertRaises(AMError): self.store.create({'language':'python','topic':'x','count':1})
        self.assertEqual(len(self.db.load_sessions()),1)
        self.store.finish(self.fields)
        self.assertEqual(self.db.load_sessions(),{})

    def test_completed_activity_goal_streak_and_spaced_review_use_real_distinct_activity(self):
        self.db.set_goal(2)
        with patch('progress_store.today',return_value=date(2026,1,1)):
            self.db.record(self.key,0,'python','Strings',3,3)
            self.db.record(self.key,0,'python','Strings',3,3)
            self.assertEqual(self.db.dashboard()['today_completed'],1)
            self.assertEqual(self.db.dashboard()['reviews'][0]['due'],'2026-01-02')
        with patch('progress_store.today',return_value=date(2026,1,2)):
            self.assertEqual(len(self.db.dashboard()['due']),1)
            self.db.record('another-session',0,'python','Strings',3,3)
            summary=self.db.dashboard()
            self.assertEqual(summary['streak'],2)
            self.assertEqual(summary['total_completed'],2)
            self.assertEqual(summary['reviews'][0]['due'],'2026-01-05')
            self.assertEqual(summary['goal'],2)
            self.db.record('failed',0,'python','Strings',1,3)
            self.assertEqual(self.db.dashboard()['reviews'][0]['due'],'2026-01-03')
        for value in (0,21,True,'2'):
            with self.assertRaises(ValueError): self.db.set_goal(value)

    def test_grading_after_restart_persists_attempt_and_completion(self):
        app=PracticeApp(FixtureRunner(),self.generator,persistence=ProgressStore(self.path))
        result=app.run(REFERENCE,self.fields)
        self.assertEqual(result['passed'],result['total'])
        reopened=SessionStore(self.generator,ProgressStore(self.path))
        self.assertEqual(reopened.sessions[self.key].attempts[0]['attempts'],1)
        self.assertEqual(self.db.dashboard()['total_completed'],1)

    def test_older_activity_schema_is_upgraded_without_losing_completed_history(self):
        old=Path(self.directory.name)/'older.sqlite3'
        with sqlite3.connect(old) as db:
            db.execute('CREATE TABLE activity (session TEXT, exercise INTEGER, language TEXT, topic TEXT, passed INTEGER, total INTEGER, completed_day TEXT, PRIMARY KEY(session,exercise))')
            db.execute("INSERT INTO activity VALUES ('old',0,'python','Strings',1,1,'2026-01-01')")
        upgraded=ProgressStore(old)
        self.assertEqual(upgraded.dashboard()['total_completed'],1)
        upgraded.record('old',0,'python','Strings',1,1)
        self.assertEqual(upgraded.dashboard()['history'][0]['attempts'],1)

    def test_export_and_delete_cover_sessions_and_progress(self):
        self.assertIn(self.key,self.db.export()['sessions'])
        for index in range(60):
            self.db.record('history',index,'python','Loops',1,1)
        self.assertEqual(len(self.db.dashboard()['history']),50)
        self.assertEqual(len(self.db.export()['activity']),60)
        self.db.record(self.key,0,'python','Loops',1,1)
        self.db.clear()
        fresh=ProgressStore(self.path)
        self.assertEqual(fresh.load_sessions(),{})
        self.assertEqual(fresh.dashboard()['total_completed'],0)
        self.assertEqual(fresh.dashboard()['reviews'],[])

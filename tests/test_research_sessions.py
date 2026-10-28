"""Notes stay local; source failures and repetition are handled explicitly."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from ai_exercises import OllamaExerciseGenerator, task_fingerprint
from practice_sessions import SessionStore
from progress_store import ProgressStore
from test_ai_exercises import FixtureRunner, NOTES, draft, review, response, validate_draft


class ResearchSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.db=ProgressStore(Path(self.directory.name)/'progress.sqlite3')
        self.generator=Mock(); self.generator.runtimes={'python':Mock()}
        self.generator.for_language.return_value=self.generator
        self.lesson=validate_draft(draft()|{'notes_quote':NOTES},NOTES,'standard')
        self.lesson['quality']={'fingerprint':task_fingerprint(self.lesson),'source':'ai-generated'}
        self.generator.build.return_value=([self.lesson],self.lesson['focus_plan'],'AI fixture')
        self.store=SessionStore(self.generator,self.db)

    def test_sources_are_separate_from_notes_and_query_never_contains_notes(self):
        source={'id':'web-1','url':'https://docs.python.org/3/tutorial/','title':'Python docs','excerpt':'Official reference text.'}
        with patch('practice_sessions.WebResearch') as research:
            research.return_value.gather.return_value={'status':'retrieved','sources':[source],'warning':''}
            _,session=self.store.create({'language':'python','topic':'functions','notes':NOTES,'count':1,'web_search':True})
        research.return_value.gather.assert_called_once_with('python','functions')
        self.generator.build.assert_called_once_with('functions',NOTES,'standard',1)
        self.assertEqual(self.generator.research_sources,[source])
        self.assertEqual(session.citations[-1]['url'],source['url'])

    def test_offline_web_does_not_invent_sources_or_block_note_guided_generation(self):
        with patch('practice_sessions.WebResearch') as research:
            research.return_value.gather.return_value={'status':'unavailable','sources':[],'warning':'References unavailable.'}
            _,session=self.store.create({'language':'python','topic':'functions','notes':NOTES,'count':1,'web_search':True})
        self.assertEqual(session.research['status'],'unavailable')
        self.assertEqual(self.generator.research_sources,[])
        self.assertEqual(session.lessons,[self.lesson])

    def test_finished_generated_tasks_leave_metadata_to_avoid_repetition(self):
        key,_=self.store.create({'language':'python','topic':'functions','notes':NOTES,'count':1})
        self.store.finish({'session_id':key,'lesson_index':0})
        recent=self.db.recent_tasks('python','functions')
        self.assertEqual(recent[0]['fingerprint'],self.lesson['quality']['fingerprint'])
        self.assertEqual(set(recent[0]),{'fingerprint','title'})
        self.assertEqual(self.db.load_sessions(),{})
        self.db.clear(); self.assertEqual(self.db.recent_tasks('python','functions'),[])

    def test_repeated_task_is_rejected_before_execution_and_a_fresh_variation_is_requested(self):
        runner=FixtureRunner(); generator=OllamaExerciseGenerator(runner)
        old=validate_draft(draft()|{'notes_quote':NOTES},NOTES,'standard')
        generator.seen_fingerprints={task_fingerprint(old)}
        fresh=draft(); fresh['instructions']+=' Handle the zero boundary carefully.'
        with patch('ai_exercises.api',side_effect=[response(draft()),response(fresh),response(review())]) as api:
            lessons,_,_=generator.build('functions',NOTES,'standard',1)
        self.assertNotEqual(task_fingerprint(lessons[0]),task_fingerprint(old))
        self.assertEqual(api.call_count,3)
        self.assertEqual(len(runner.calls),18)

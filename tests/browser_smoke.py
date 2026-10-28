"""Real browser/API persistence smoke test; controlled model/runner fixtures, not a live-AI demo."""
import argparse
from pathlib import Path
import shutil
import re
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from playwright.sync_api import sync_playwright, expect
from ai_exercises import OllamaExerciseGenerator
from practice_web import PracticeApp, make_server
from progress_store import ProgressStore
from generation_diagnostics import DiagnosticRecorder
import io
from test_ai_exercises import FixtureRunner, NOTES, REFERENCE, draft, review, response
from test_note_retrieval import pdf_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'benchmark-results/browser')
    parser.add_argument('--screenshots',action='store_true')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
        database=Path(directory)/'progress.sqlite3'
        def start():
            runner=FixtureRunner(); generator=OllamaExerciseGenerator(runner)
            generator.diagnostics=DiagnosticRecorder(Path(directory)/'diagnostics',stream=io.StringIO())
            app=PracticeApp(runner,generator,persistence=ProgressStore(database),diagnostics=True)
            server=make_server(app,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            return server,thread
        server,thread=start()
        chromium=shutil.which('chromium')
        browser=pw.chromium.launch(**({'executable_path':chromium} if chromium else {}),args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1050},record_video_dir=str(args.output/'video'))
        page=context.new_page(); errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.locator('#setup').wait_for(state='visible')
            page.locator('#study-dashboard').wait_for(state='visible')
            page.locator('#daily-goal').fill('2'); page.locator('#save-goal').click()
            expect(page.locator('#study-stats')).to_contain_text('/2 today')
            if args.screenshots: page.screenshot(path=str(args.output/'setup.png'),full_page=True)
            if shutil.which('pdftotext'):
                pdf=Path(directory)/'notes.pdf';pdf.write_bytes(pdf_bytes('Factorial practice notes.'))
                page.locator('#notes-file').set_input_files(str(pdf))
                expect(page.locator('#notes')).to_have_value(re.compile('Factorial practice notes.'))
            page.locator('#notes').fill(NOTES); page.locator('#topic').fill('Functions and recursion')
            research={'status':'retrieved','provider':'controlled-fixture','warning':'',
                      'sources':[{'id':'web-1','url':'https://docs.python.org/3/tutorial/',
                                  'title':'Python documentation','excerpt':'Functions return values; recursion calls a function again.'}]}
            with patch('practice_sessions.WebResearch') as search:
                search.return_value.gather.return_value=research
                invalid={'done':True,'message':{'content':'{}'}}
                with patch('ai_exercises.api',side_effect=[invalid,invalid]):
                    page.locator('#start').click()
                    expect(page.locator('#error')).to_contain_text('could not verify')
                    page.locator('#error-details summary').click()
                    with page.expect_download() as download:
                        page.locator('#error-report').click()
                    assert download.value.suggested_filename=='am-preparation-diagnostic.json'
                with patch('ai_exercises.api',side_effect=[response(draft()),response(review())]) as model:
                    page.locator('#start').click(); page.locator('#workspace').wait_for(state='visible')
                    assert model.call_count==2
                search.return_value.gather.assert_called_with('python','Functions and recursion')
            page.locator('#source').fill(REFERENCE)
            expect(page.locator('#draft-status')).to_contain_text('Draft saved')
            # Save B, then return to already-saved A while B is queued: A must win.
            page.evaluate("""reference => {
                const editor=document.getElementById('source');
                editor.value=reference+'\\n# temporary edit'; editor.dispatchEvent(new Event('input')); saveDraft();
                editor.value=reference; editor.dispatchEvent(new Event('input')); return saveDraft();
            }""",REFERENCE)
            saved=next(iter(ProgressStore(database).load_sessions().values()))
            assert saved['drafts']['0']['source']==REFERENCE
            assert saved['drafts']['0']['version']>=3
            assert page.locator('.token-keyword').count()>0
            assert int(page.locator('.line-numbers').inner_text().splitlines()[-1])>=5
            # A full server restart proves restoration comes from SQLite, not browser state.
            server.shutdown(); server.server_close(); thread.join(3)
            server,thread=start()
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.get_by_role('button',name='Resume python:',exact=False).click()
            page.locator('#workspace').wait_for(state='visible')
            assert page.locator('#source').input_value()==REFERENCE
            expect(page.locator('#research-status')).to_contain_text('1 web documentation')
            page.locator('#retrieval-details summary').click()
            expect(page.locator('#retrieval-sources a')).to_have_attribute('href','https://docs.python.org/3/tutorial/')
            page.locator('#hint').click(); page.get_by_text('Check the base case.',exact=True).wait_for()
            page.locator('#run').click()
            page.get_by_role('heading',name='All 6 tests passed. You found the fix.').wait_for()
            expect(page.locator('#study-stats')).to_contain_text('1/2 today')
            if args.screenshots: page.screenshot(path=str(args.output/'exercise.png'),full_page=True)
            page.locator('#next-exercise').click(); page.locator('#session-summary').wait_for(state='visible')
            if args.screenshots: page.screenshot(path=str(args.output/'summary.png'),full_page=True)
            page.locator('#another-session').click(); page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
            if args.screenshots: page.screenshot(path=str(args.output/'mobile.png'),full_page=True)
            page.locator('summary').filter(has_text='Local data and privacy').click()
            with page.expect_download() as download:
                page.locator('#export-data').click()
            assert download.value.suggested_filename=='am-progress.json'
            page.on('dialog',lambda dialog:dialog.accept())
            page.locator('#delete-data').click()
            expect(page.locator('#study-stats')).to_contain_text('0/1 today')
            assert ProgressStore(database).load_sessions()=={}
            assert not errors,errors
            print('PASS: real HTTP/UI generation fixtures, PDF upload, goals, highlighted editor, autosave, server restart/resume, hints, grading, summary, export/delete, mobile overflow.')
            print('Model and execution responses are controlled fixtures; these are not live-generation measurements.')
        finally:
            context.close(); browser.close(); server.shutdown(); server.server_close(); thread.join(3)


if __name__=='__main__': main()

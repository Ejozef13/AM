"""Capture the real AM UI with controlled model/runner fixtures, never live inference.

Requires the optional Playwright dependency, Chromium, and a local ffmpeg binary.
All study data lives in a temporary database. No production code is modified.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

from playwright.sync_api import expect, sync_playwright
from ai_exercises import OllamaExerciseGenerator
from practice_web import PracticeApp, make_server
from progress_store import ProgressStore
from test_ai_exercises import FixtureRunner, NOTES, REFERENCE, draft, review, response
from test_multilanguage_generation import NativeFixtureRunner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs')
    args = parser.parse_args()
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        parser.error('Install ffmpeg separately to encode the captured loading animation.')
    screenshots, media = args.output / 'screenshots', args.output / 'media'
    screenshots.mkdir(parents=True, exist_ok=True)
    media.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='am-readme-demo-') as temporary, sync_playwright() as pw:
        temporary = Path(temporary)
        database = ProgressStore(temporary / 'progress.sqlite3')
        runner = FixtureRunner()
        runtimes = {'python': runner, **{name: NativeFixtureRunner(name) for name in ('java', 'c', 'cpp')}}
        generator = OllamaExerciseGenerator(runner, runtimes=runtimes)
        server = make_server(PracticeApp(runner, generator, runtimes, persistence=database), 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        chromium = shutil.which('chromium')
        browser = pw.chromium.launch(**({'executable_path': chromium} if chromium else {}), args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1280, 'height': 960}, device_scale_factor=1,
                                      reduced_motion='no-preference')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(f'http://127.0.0.1:{server.server_port}')
            expect(page.locator('#setup')).to_be_visible()
            expect(page.locator('.language:enabled')).to_have_count(4)
            page.locator('#daily-goal').fill('2')
            page.locator('#save-goal').click()
            expect(page.locator('#study-stats')).to_contain_text('/2 today')
            page.locator('#topic').fill('Functions and recursion')
            page.locator('#notes').fill(NOTES)
            page.locator('#difficulty').select_option('introductory')
            page.locator('#setup').screenshot(path=str(screenshots / 'readme-setup.png'))

            # Hold a real HTTP generation request open while recording the app's
            # unchanged CSS animations. This delay is not an inference measurement.
            gate = threading.Event()
            replies = iter([response(draft()), response(review())])
            def model_reply(*_args, **_kwargs):
                if not gate.wait(45):
                    raise RuntimeError('Capture did not release controlled generation')
                return next(replies)
            with patch('ai_exercises.api', side_effect=model_reply) as model:
                page.locator('#start').click()
                expect(page.locator('#am-presence')).to_contain_text('AM THINKING')
                page.evaluate('window.scrollTo(0, 0)')
                box = page.locator('main').bounding_box()
                clip = {'x': box['x'], 'y': 0, 'width': box['width'], 'height': 440}
                start = time.monotonic()
                try:
                    # Circuit pulses repeat every 3 s; alternating logo glow
                    # repeats every 4 s. Twelve seconds covers both full cycles.
                    for index in range(120):
                        delay = start + index / 10 - time.monotonic()
                        if delay > 0:
                            time.sleep(delay)
                        page.screenshot(path=str(temporary / f'frame-{index:03}.png'), clip=clip)
                finally:
                    gate.set()
                expect(page.locator('#workspace')).to_be_visible()
                assert model.call_count == 2
            subprocess.run([
                ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-framerate', '10',
                '-i', str(temporary / 'frame-%03d.png'), '-filter_complex_threads', '1',
                '-filter_complex', 'scale=960:-1:flags=lanczos,split[a][b];'
                '[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a',
                '-loop', '0', str(media / 'am-generation-loading.gif')], check=True, timeout=40)

            page.locator('#hint').click()
            expect(page.locator('#hints')).to_contain_text('Check the base case.')
            page.locator('#run').click()
            expect(page.locator('#result-title')).to_have_text('5 of 6 tests passed')
            page.locator('#workspace').screenshot(path=str(screenshots / 'readme-practice.png'))

            page.locator('#source').fill(REFERENCE)
            page.locator('#run').click()
            expect(page.locator('#result-title')).to_contain_text('All 6 tests passed')
            expect(page.locator('#draft-status')).to_contain_text('Draft saved')
            page.locator('.coding').screenshot(path=str(screenshots / 'readme-results.png'))
            page.locator('#next-exercise').click()
            expect(page.locator('#session-summary')).to_be_visible()
            page.locator('#session-summary').screenshot(path=str(screenshots / 'readme-summary.png'))
            page.locator('#another-session').click()

            # Make one further unfinished session through the same real routes,
            # so the dashboard can show genuine fixture-backed resume/history.
            page.locator('#topic').fill('Functions and recursion')
            page.locator('#notes').fill(NOTES)
            with patch('ai_exercises.api', side_effect=[response(draft()), response(review())]):
                page.locator('#start').click()
                expect(page.locator('#workspace')).to_be_visible()
            page.locator('#source').fill(REFERENCE)
            expect(page.locator('#draft-status')).to_contain_text('Draft saved')
            page.reload()
            expect(page.locator('#study-stats')).to_contain_text('1/2 today · 1 day streak · 1 exercises completed')
            expect(page.locator('#saved-sessions button')).to_have_count(1)
            page.locator('#study-dashboard summary').filter(has_text='Recent practice').click()
            expect(page.locator('#practice-history')).to_contain_text('6/6 tests')
            page.locator('#study-dashboard').screenshot(path=str(screenshots / 'readme-dashboard.png'))
            assert not errors, errors
            print(json.dumps({'mode': 'controlled model and execution fixtures; real app UI',
                              'screenshots': 5, 'gif': '960 x 352, 120 frames, 10 fps, 12-second loop',
                              'animation_bytes': (media / 'am-generation-loading.gif').stat().st_size}))
        finally:
            context.close()
            browser.close()
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    main()

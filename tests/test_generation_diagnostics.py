import io
import json
from pathlib import Path
import tempfile
import unittest

from generation_diagnostics import DiagnosticRecorder


class DiagnosticsTests(unittest.TestCase):
    def test_capture_is_local_owner_only_and_terminal_summary_excludes_code(self):
        with tempfile.TemporaryDirectory() as directory:
            stream = io.StringIO()
            recorder = DiagnosticRecorder(Path(directory) / 'diagnostics', stream)
            event = {'run_id': 'first', 'attempt': 1, 'error': 'syntax failure',
                     'artifacts': {'draft': {'starter_code': 'GENERATED_CODE_MARKER'}, 'review': None}}
            recorder(event)
            saved = json.loads(recorder.path.read_text())
            self.assertEqual(saved['attempts'], [event])
            self.assertNotIn('GENERATED_CODE_MARKER', stream.getvalue())
            self.assertIn(str(recorder.path), stream.getvalue())
            self.assertEqual(recorder.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(recorder.directory.stat().st_mode & 0o777, 0o700)

    def test_attempts_are_bounded_and_new_runs_replace_old_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = DiagnosticRecorder(directory, io.StringIO())
            for index in range(12):
                recorder({'run_id': 'first', 'attempt': index})
            saved = json.loads(recorder.path.read_text())
            self.assertEqual(len(saved['attempts']), 10)
            recorder({'run_id': 'second', 'attempt': 1})
            saved = json.loads(recorder.path.read_text())
            self.assertEqual(saved['run_id'], 'second')
            self.assertEqual(len(saved['attempts']), 1)

    def test_save_failure_does_not_mask_original_draft_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            occupied = Path(directory) / 'occupied'; occupied.write_text('file')
            stream = io.StringIO()
            recorder = DiagnosticRecorder(occupied, stream)
            recorder({'run_id': 'first', 'error': 'original failure'})
            self.assertIn('original failure', stream.getvalue())
            self.assertIn('could not save diagnostics', stream.getvalue())


if __name__ == '__main__':
    unittest.main()

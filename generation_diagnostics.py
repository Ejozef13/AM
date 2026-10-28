"""Opt-in local capture of rejected model artifacts for reproducible debugging."""

import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone


class DiagnosticRecorder:
    def __init__(self, directory, stream=None):
        self.directory = Path(directory)
        self.path = self.directory / 'last-generation.json'
        self.stream = stream if stream is not None else sys.stderr
        self.run_id = None
        self.events = []
        self.status = "in_progress"

    def __call__(self, event):
        # Print the small summary, not full code/tests, into terminal scrollback.
        summary = {key: value for key, value in event.items() if key != 'artifacts'}
        print('AM draft diagnostic: ' + json.dumps(summary), file=self.stream, flush=True)
        if event.get('run_id') != self.run_id:
            self.events = []
            self.run_id = event.get('run_id')
            self.status = "in_progress"
        self.events = (self.events + [event])[-10:]
        self.persist()

    def finish(self, run_id, status):
        if run_id == self.run_id:
            self.status = status
            self.persist()

    def persist(self):
        temporary = None
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.directory,
                                             prefix='.trace-', delete=False) as output:
                temporary = output.name  # tempfile creates an owner-only file.
                json.dump({'schema_version': 1, 'report_type':'practice-preparation', 'run_id': self.run_id,
                           'status':self.status, 'updated_utc':datetime.now(timezone.utc).isoformat(),
                           'requested_topic':self.events[-1].get('requested_topic','') if self.events else '',
                           'attempts': self.events}, output, ensure_ascii=False, indent=2)
            os.replace(temporary, self.path)
            print(f'AM diagnostic saved to: {self.path}', file=self.stream, flush=True)
        except OSError as error:
            print(f'AM could not save diagnostics: {error}', file=self.stream, flush=True)
        finally:
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
                    pass  # Diagnostic cleanup must not mask the draft failure.

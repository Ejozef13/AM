"""Real subprocess tests for scoped credential renewal; never invoke real sudo."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from sudo_session import SudoSession


class SudoSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name); self.log=self.path/'calls.jsonl'; self.token=self.path/'token'
        script=self.path/'fake_sudo.py'
        script.write_text('''import json,sys,time
from pathlib import Path
log,token,mode=map(Path,sys.argv[1:4])
arguments=sys.argv[4:]
with log.open('a') as stream: stream.write(json.dumps(arguments)+'\\n')
if arguments==['-v']:
    if mode.read_text()=='block':
        time.sleep(30)
    temporary=token.with_suffix('.tmp'); temporary.write_text(str(time.monotonic())); temporary.replace(token)
    raise SystemExit(0)
try: age=time.monotonic()-float(token.read_text())
except (OSError,ValueError): age=1000
if age>1: raise SystemExit(1)
temporary=token.with_suffix('.tmp'); temporary.write_text(str(time.monotonic())); temporary.replace(token)
''')
        self.mode=self.path/'mode'; self.mode.write_text('normal'); self.token.write_text(str(time.monotonic()))
        self.command=(sys.executable,str(script),str(self.log),str(self.token),str(self.mode))
        self.messages=[]; self.session=None
        self.addCleanup(self.stop)

    def stop(self):
        if self.session: self.session.close()

    def wait_for(self,predicate):
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            if predicate(): return
            time.sleep(.01)
        self.fail('Credential test did not reach expected state.')

    def calls(self):
        try:return [json.loads(line) for line in self.log.read_text().splitlines()]
        except FileNotFoundError:return []

    def test_credential_stays_valid_beyond_expiry_and_refresh_stops_on_close(self):
        start=time.monotonic()
        self.session=SudoSession(self.command,interval=.03,interactive=False,report=self.messages.append).start()
        self.wait_for(lambda:time.monotonic()-start>1.2 and len(self.calls())>=12)
        self.assertLess(time.monotonic()-float(self.token.read_text()),1)
        self.assertTrue(all(call==['-n','-v'] for call in self.calls()))
        self.session.close(); count=len(self.calls()); time.sleep(.1)
        self.assertEqual(len(self.calls()),count)
        self.assertFalse(self.session.thread.is_alive())

    def test_revocation_can_be_renewed_in_launch_terminal_without_stopping_session(self):
        self.token.unlink()
        self.session=SudoSession(self.command,interval=.03,interactive=True,report=self.messages.append).start()
        self.wait_for(lambda:any('restored' in message for message in self.messages))
        self.assertIn(['-v'],self.calls())
        self.assertFalse(self.session.stopping.is_set())
        self.assertLess(time.monotonic()-float(self.token.read_text()),1)

    def test_runner_failure_wakes_renewal_without_waiting_for_periodic_refresh(self):
        self.session=SudoSession(self.command,interval=10,interactive=True,report=self.messages.append).start()
        self.wait_for(lambda:len(self.calls())>=1)
        self.token.unlink()
        self.session.request_renewal()
        self.wait_for(lambda:['-v'] in self.calls())
        self.assertFalse(self.session.stopping.is_set())

    def test_shutdown_cancels_a_pending_password_prompt(self):
        self.token.unlink(); self.mode.write_text('block')
        self.session=SudoSession(self.command,interval=.03,interactive=True,report=self.messages.append).start()
        self.wait_for(lambda:['-v'] in self.calls())
        process=self.session.process; start=time.monotonic()
        self.session.close()
        self.assertLess(time.monotonic()-start,3)
        self.assertFalse(self.session.thread.is_alive())
        self.assertIsNotNone(process.poll())

    def test_noninteractive_launch_does_not_ask_for_or_capture_a_password(self):
        self.token.unlink()
        self.session=SudoSession(self.command,interval=.03,interactive=False,report=self.messages.append).start()
        self.wait_for(lambda:len(self.calls())>=3)
        self.assertNotIn(['-v'],self.calls())
        self.assertEqual(sum('No interactive' in message for message in self.messages),1)

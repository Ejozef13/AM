"""Start/off integration with real subprocesses and controlled local services."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

import site_control

ROOT = Path(__file__).resolve().parents[1]


class SiteControlTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.path = Path(self.directory.name)
        self.started = threading.Event(); self.release = threading.Event()
        self.models = {'other-model'}; self.calls = []
        owner = self
        class Ollama(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def respond(self,data):
                self.send_response(200);self.end_headers()
                try:self.wfile.write(json.dumps(data).encode())
                except (BrokenPipeError,ConnectionResetError):pass
            def do_GET(self):
                self.respond({'models':[{'name':name} for name in sorted(owner.models)]})
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.calls.append((self.path,data))
                if self.path == '/api/show':
                    self.respond({'details':{'family':'gptoss','parameter_size':'20.9B'}})
                elif self.path == '/api/chat':
                    owner.started.set();owner.release.wait(15);self.respond({'done':True})
                else:
                    if data.get('keep_alive') == 0:owner.models.discard(data['model'])
                    else:owner.models.add(data['model'])
                    self.respond({'done':True})
        self.ollama = ThreadingHTTPServer(('127.0.0.1',0),Ollama);self.ollama.daemon_threads=True
        self.thread=threading.Thread(target=self.ollama.serve_forever,daemon=True);self.thread.start()
        binary=self.path/'docker'
        binary.write_text('#!/bin/sh\ncase "$1" in info|image) exit 0;; *) exit 99;; esac\n')
        binary.chmod(0o700)
        self.environment={**os.environ,'PATH':str(self.path)+os.pathsep+os.environ['PATH'],
            'AM_RUNTIME_DIR':str(self.path/'runtime'), 'AM_DATA_DIR':str(self.path/'data'),
            'AM_OLLAMA_URL':f'http://127.0.0.1:{self.ollama.server_port}'}
        self.log=open(self.path/'website.log','w+')
        self.process=None

    def tearDown(self):
        self.release.set()
        if self.process and self.process.poll() is None:
            self.process.terminate();self.process.wait(timeout=5)
        self.log.close();self.ollama.shutdown();self.ollama.server_close();self.thread.join(2)
        self.directory.cleanup()

    def command(self,*args):
        return subprocess.run([sys.executable,'am.py',*args],cwd=ROOT,env=self.environment,
                              capture_output=True,text=True,timeout=12)

    def start(self):
        self.process=subprocess.Popen([sys.executable,'am.py','on','--port','0','--diagnostics'],
            cwd=ROOT,env=self.environment,stdout=self.log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            try:
                data=json.loads((self.path/'runtime/website.json').read_text())
                if data['phase']=='running':return data
            except (OSError,ValueError):pass
            if self.process.poll() is not None:break
            time.sleep(0.05)
        self.log.seek(0);self.fail(self.log.read())

    def test_on_duplicate_status_and_off_leave_other_models_and_services_intact(self):
        state=self.start()
        self.assertEqual(state['models'],['am-study:latest'])
        duplicate=self.command('on','--port','0')
        self.assertEqual(duplicate.returncode,0,duplicate.stdout+duplicate.stderr)
        self.assertIn('already',duplicate.stdout)
        status=self.command('status')
        self.assertIn('RUNNING',status.stdout)
        stopped=self.command('off')
        self.assertEqual(stopped.returncode,0,stopped.stdout+stopped.stderr)
        self.process.wait(timeout=3)
        self.assertEqual(self.models,{'other-model'})
        self.assertFalse((self.path/'runtime/website.json').exists())
        self.log.seek(0);self.assertIn('family: gptoss',self.log.read())

    def test_off_cancels_an_active_model_request_and_does_not_wait_for_its_full_timeout(self):
        state=self.start();responses=[]
        def create_session():
            data=json.dumps({'language':'python','topic':'count occurrences','count':1}).encode()
            address=f"http://127.0.0.1:{state['port']}"
            request=urllib.request.Request(address+'/api/session',data=data,
                headers={'Origin':address,'Content-Type':'application/json'})
            try:urllib.request.urlopen(request,timeout=12).close()
            except urllib.error.HTTPError as error:responses.append(error.code);error.close()
        client=threading.Thread(target=create_session,daemon=True);client.start()
        self.assertTrue(self.started.wait(3))
        stopped=self.command('off')
        self.assertEqual(stopped.returncode,0,stopped.stdout+stopped.stderr)
        self.process.wait(timeout=3);client.join(3)
        self.assertEqual(responses,[503])
        self.assertEqual(self.models,{'other-model'})

    def test_stale_pid_record_never_signals_an_unrelated_process(self):
        with patch.dict(os.environ,{'AM_RUNTIME_DIR':str(self.path/'runtime')}):
            site_control.save_state({'root':str(ROOT),'pid':os.getpid(),'start':'incorrect-start-time',
                                     'phase':'running','port':8090,'models':['am-study:latest']})
            unload=Mock()
            with patch('site_control.port_busy',return_value=False),patch('site_control.api',return_value={'models':[]}), \
                 patch('site_control.os.kill') as kill,patch('site_control.os.pidfd_open') as pidfd:
                site_control.stop(unload)
            kill.assert_not_called();pidfd.assert_not_called()
            unload.assert_called_once_with('am-study:latest')

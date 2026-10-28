"""Real local HTTP requests, cancellation, and model-response validation."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch

from am_core import AMError, api


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.started = threading.Event(); self.release = threading.Event()
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                if self.path == '/blocked':
                    owner.started.set(); owner.release.wait(5)
                status, data = (404,{'error':'missing model'}) if self.path == '/missing' else (200,{'models':[]})
                self.send_response(status); self.end_headers()
                try: self.wfile.write(json.dumps(data).encode())
                except (BrokenPipeError,ConnectionResetError): pass
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.address = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.release.set();self.server.shutdown();self.server.server_close();self.thread.join(2)

    def test_direct_local_request_and_http_error(self):
        with patch('am_core.BASE_URL',self.address):
            self.assertEqual(api('/api/ps'),{'models':[]})
            with self.assertRaisesRegex(AMError,'missing model'):
                api('/missing')

    def test_cancel_interrupts_a_request_waiting_for_response_headers(self):
        cancel = threading.Event(); errors = []
        def request():
            try: api('/blocked',timeout=30,cancel_event=cancel)
            except AMError as error: errors.append(str(error))
        with patch('am_core.BASE_URL',self.address):
            worker = threading.Thread(target=request,daemon=True);worker.start()
            self.assertTrue(self.started.wait(2))
            cancel.set(); worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertIn('canceled',errors[0])

    def test_remote_addresses_are_rejected(self):
        with patch('am_core.BASE_URL','http://example.com:11434'),self.assertRaises(AMError):
            api('/api/ps')

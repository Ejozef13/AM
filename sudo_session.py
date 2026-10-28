"""Maintain an existing sudo credential only while the foreground AM app runs."""
import subprocess
import sys
import threading


class SudoSession:
    def __init__(self, command=('sudo',), interval=30, interactive=None, report=None):
        self.command = tuple(command)
        self.interval = interval
        self.interactive = sys.stdin.isatty() if interactive is None else interactive
        self.report = report or (lambda message: print(message, flush=True))
        self.stopping = threading.Event()
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.process = None
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.maintain, name='am-sudo-session', daemon=True)
        self.thread.start()
        return self

    def execute(self, interactive=False):
        """Never read, retain, or forward a password through the web application."""
        arguments = ['-v'] if interactive else ['-n', '-v']
        with self.lock:
            if self.stopping.is_set():
                return False
            self.process = subprocess.Popen([*self.command, *arguments],
                stdin=None if interactive else subprocess.DEVNULL,
                stdout=None if interactive else subprocess.DEVNULL,
                stderr=None if interactive else subprocess.DEVNULL)
            process = self.process
        try:
            return process.wait(timeout=None if interactive else 10) == 0
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            return False
        finally:
            with self.lock:
                self.process = None

    def request_renewal(self):
        self.wake.set()

    def maintain(self):
        warned = False
        while not self.stopping.is_set():
            if self.wake.is_set():
                warned = False
                self.wake.clear()
            try:
                valid = self.execute()
                if valid:
                    if warned:
                        self.report('Docker authorization restored. Retry the operation; AM stayed open.')
                    warned = False
                elif not warned and not self.stopping.is_set():
                    warned = True
                    self.report('Docker authorization needs renewal. AM and saved drafts stay open. '
                                'If prompted, enter your password in this launch terminal, then retry in the browser.')
                    if self.interactive:
                        # Same controlling terminal and parent PID as the Docker calls.
                        # An OS suspend/revocation can require this even with refresh enabled.
                        if self.execute(interactive=True) and not self.stopping.is_set():
                            warned = False
                            self.report('Docker authorization restored. Retry the operation; AM stayed open.')
                    else:
                        self.report('No interactive launch terminal is available. Renew sudo in the original '
                                    'terminal, or launch AM from an interactive terminal next time.')
            except (OSError, subprocess.SubprocessError) as error:
                if not warned and not self.stopping.is_set():
                    self.report('Docker credential refresh could not complete: '+type(error).__name__+
                                '. AM remains open; check the launch terminal.')
                warned = True
            self.wake.wait(self.interval)

    def close(self):
        self.stopping.set()
        self.wake.set()
        with self.lock:
            process = self.process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            except ProcessLookupError:
                pass
        if self.thread:
            self.thread.join(timeout=3)

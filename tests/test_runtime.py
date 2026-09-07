"""Portable reporter startup and real process lock regressions."""
import json
import os
import shutil
import signal
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/work-like-musk/scripts'
sys.path.insert(0, str(SCRIPTS))
import five_step


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project 中文'
        self.project.mkdir()

    def cli(self, *args, **env):
        environment = dict(os.environ, **env)
        environment.pop('CODEX_THREAD_ID', None)
        return subprocess.run([sys.executable, str(SCRIPTS / 'five_step.py'), *args,
                               '--project', str(self.project)], env=environment,
                              capture_output=True, text=True)

    def test_new_tasks_are_distinct_pending_and_ascii_stdout_safe(self):
        ids = []
        for _ in range(2):
            result = self.cli('setup', '--new-task', '--no-open', '--title', '测试', PYTHONIOENCODING='ascii')
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            ids.append(output['taskId'])
            self.assertRegex(ids[-1], r'^wlm-[0-9a-f-]{36}$')
            state = json.loads(Path(output['statePath']).read_text(encoding='utf-8'))
            self.assertEqual([s['status'] for s in state['stages']], ['pending'] * 5)
            shown = self.cli('show', '--task', ids[-1], PYTHONIOENCODING='ascii')
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(json.loads(shown.stdout), state)
        self.assertNotEqual(*ids)

    def test_identity_is_required_and_new_task_conflicts_with_explicit_task(self):
        for args in [('setup', '--no-open'), ('setup', '--no-open', '--task', 'a', '--new-task')]:
            result = self.cli(*args)
            self.assertEqual(result.returncode, 2)
        self.assertFalse((self.project / '.work-like-musk').exists())

    def fixture(self, body):
        (self.root / 'scripts').mkdir(exist_ok=True)
        (self.root / 'scripts/portable_hud.py').write_text(
            'import argparse,json,pathlib\np=argparse.ArgumentParser()\n'
            'for key in ("project","task","state","language","ready-file"): p.add_argument("--"+key)\n'
            'a=p.parse_args()\n' + body, encoding='utf-8')

    def test_spawned_handshake_reports_observed_status_and_identity(self):
        for status in ('opened', 'already_open'):
            self.fixture('pathlib.Path(a.ready_file).write_text(json.dumps({"status": ' + repr(status) + ', "taskId": a.task}))\n')
            with mock.patch.object(five_step, '__file__', str(self.root / 'scripts/five_step.py')):
                result = five_step.open_hud(self.project / 'state.json', self.project, 'literal $HOME `whoami`', 'portable')
            self.assertEqual(result, {'backend': 'portable', 'status': status, 'taskId': 'literal $HOME `whoami`'})

    def test_startup_error_invalid_identity_and_early_exit_fail(self):
        for body, message in [
            ('pathlib.Path(a.ready_file).write_text(json.dumps({"status":"error","error":"No graphical desktop","taskId":a.task}))\n', 'No graphical desktop'),
            ('pathlib.Path(a.ready_file).write_text(json.dumps({"status":"opened","taskId":"foreign"}))\n', 'identity'),
            ('raise SystemExit(1)\n', 'exited'),
        ]:
            self.fixture(body)
            state = self.project / 'state.json'
            state.write_text('preserved')
            with mock.patch.object(five_step, '__file__', str(self.root / 'scripts/five_step.py')):
                with self.assertRaisesRegex(ValueError, message):
                    five_step.open_hud(state, self.project, 'task-a', 'portable')
            self.assertEqual(state.read_text(), 'preserved')

    def test_installed_gui_runtime_is_independent_of_reporter_python(self):
        self.fixture('pathlib.Path(a.ready_file).write_text(json.dumps({"status":"opened","taskId":a.task}))\n')
        assets = self.root / 'assets'
        assets.mkdir()
        (assets / 'portable-runtime.json').write_text(json.dumps({
            'schemaVersion': 1, 'pythonExecutable': sys.executable,
        }), encoding='utf-8')
        with mock.patch.object(five_step, '__file__', str(self.root / 'scripts/five_step.py')):
            with mock.patch.object(five_step.sys, 'executable', str(self.root / 'reporter-only-python')):
                result = five_step.open_hud(self.project / 'state.json', self.project, 'task-a', 'portable')
        self.assertEqual(result['status'], 'opened')

    def test_invalid_or_missing_configured_python_does_not_launch(self):
        self.fixture('raise AssertionError("must not launch")\n')
        assets = self.root / 'assets'
        assets.mkdir()
        config = assets / 'portable-runtime.json'
        for value in [
            {'schemaVersion': True, 'pythonExecutable': sys.executable},
            {'schemaVersion': 1, 'pythonExecutable': 'relative/python'},
            {'schemaVersion': 1, 'pythonExecutable': str(self.root / 'removed-python')},
            {'schemaVersion': 1, 'pythonExecutable': str(self.root)},
            {'schemaVersion': 1, 'pythonExecutable': sys.executable, 'unknown': True},
            {'schemaVersion': 1, 'pythonExecutable': None},
        ]:
            with self.subTest(value=value):
                config.write_text(json.dumps(value), encoding='utf-8')
                with mock.patch.object(five_step, '__file__', str(self.root / 'scripts/five_step.py')):
                    with mock.patch.object(five_step.subprocess, 'Popen') as launch:
                        with self.assertRaisesRegex(ValueError, 'runtime|Python'):
                            five_step.open_hud(self.project / 'state.json', self.project, 'task-a', 'portable')
                        launch.assert_not_called()

    def test_cli_startup_failure_retains_state_and_retry_separates_hud_status(self):
        self.fixture('pathlib.Path(a.ready_file).write_text(json.dumps({"status":"error","error":"Qt display unavailable","taskId":a.task}))\n')
        for filename in ('five_step.py', 'runtime_support.py'):
            shutil.copy2(SCRIPTS / filename, self.root / 'scripts' / filename)
        command = [sys.executable, str(self.root / 'scripts/five_step.py'), 'setup', '--project',
                   str(self.project), '--task', 'a', '--hud', 'portable']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Qt display unavailable', result.stderr)
        states = list((self.project / '.work-like-musk/sessions').glob('*.json'))
        self.assertEqual(len(states), 1)
        before = states[0].read_bytes()
        self.fixture('pathlib.Path(a.ready_file).write_text(json.dumps({"status":"opened","taskId":a.task}))\n')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output['status'], 'pending')
        self.assertEqual(output['hud']['status'], 'opened')
        self.assertEqual(output['taskId'], 'a')
        self.assertEqual(states[0].read_bytes(), before)

    def test_real_cli_new_task_opens_portable_hud(self):
        check = subprocess.run([sys.executable, str(SCRIPTS / 'portable_hud.py'), '--check'],
                               capture_output=True, text=True, timeout=15)
        if check.returncode:
            self.skipTest('A working Qt desktop is required: ' + check.stderr.strip())
        scripts = self.root / 'scripts'
        scripts.mkdir()
        for filename in ('five_step.py', 'runtime_support.py'):
            shutil.copy2(SCRIPTS / filename, scripts / filename)
        pid_path = self.root / 'hud.pid'
        # Run the real GUI unchanged, recording only our own child for cleanup.
        (scripts / 'portable_hud.py').write_text(
            'import os,pathlib,runpy,sys\n'
            + 'pathlib.Path(' + repr(str(pid_path)) + ').write_text(str(os.getpid()))\n'
            + 'sys.path.insert(0, ' + repr(str(SCRIPTS)) + ')\n'
            + 'runpy.run_path(' + repr(str(SCRIPTS / 'portable_hud.py')) + ', run_name="__main__")\n',
            encoding='utf-8')
        try:
            result = subprocess.run([sys.executable, str(scripts / 'five_step.py'), 'setup', '--new-task',
                                     '--project', str(self.project), '--hud', 'portable'],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output['hud']['status'], 'opened')
            self.assertEqual(output['hud']['taskId'], output['taskId'])
            state = json.loads(Path(output['statePath']).read_text(encoding='utf-8'))
            self.assertEqual([stage['status'] for stage in state['stages']], ['pending'] * 5)
        finally:
            if pid_path.exists():
                try:
                    os.kill(int(pid_path.read_text()), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                # Wait for this child's state handles to close before temporary cleanup.
                from runtime_support import file_lock
                for lock_path in (self.project / '.work-like-musk/sessions').glob('*.hud.lock'):
                    deadline = time.monotonic() + 3
                    while True:
                        try:
                            with lock_path.open('a+b') as stream, file_lock(stream, blocking=False):
                                break
                        except BlockingIOError:
                            if time.monotonic() >= deadline:
                                raise
                            time.sleep(0.05)

    def test_failed_new_task_startup_returns_recoverable_identity(self):
        self.fixture('pathlib.Path(a.ready_file).write_text(json.dumps({"status":"error","error":"Qt display unavailable","taskId":a.task}))\n')
        for filename in ('five_step.py', 'runtime_support.py'):
            shutil.copy2(SCRIPTS / filename, self.root / 'scripts' / filename)
        command = [sys.executable, str(self.root / 'scripts/five_step.py')]
        options = ['--project', str(self.project), '--hud', 'portable']
        environment = dict(os.environ, PYTHONIOENCODING='ascii')
        result = subprocess.run(command + ['setup', '--new-task'] + options,
                                capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Qt display unavailable', result.stderr)
        output = json.loads(result.stdout)
        self.assertRegex(output['taskId'], r'^wlm-[0-9a-f-]{36}$')
        self.assertEqual(output['revision'], 1)
        self.assertEqual(output['status'], 'pending')
        self.assertEqual(output['hud']['status'], 'error')
        self.assertIn('Qt display unavailable', output['hud']['error'])
        state_path = Path(output['statePath'])
        before = state_path.read_bytes()
        self.assertEqual(json.loads(before)['taskId'], output['taskId'])
        self.fixture('pathlib.Path(a.ready_file).write_text(json.dumps({"status":"opened","taskId":a.task}))\n')
        result = subprocess.run(command + ['open', '--task', output['taskId']] + options,
                                capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['taskId'], output['taskId'])
        self.assertEqual(state_path.read_bytes(), before)
        self.assertEqual(len(list(state_path.parent.glob('*.json'))), 1)

    def test_new_task_overrides_codex_environment(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'five_step.py'), 'setup',
                                 '--project', str(self.project), '--new-task', '--no-open'],
                                env=dict(os.environ, CODEX_THREAD_ID='host-task'), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(json.loads(result.stdout)['taskId'], 'host-task')

    def test_saved_backend_old_install_and_explicit_native_failure(self):
        with mock.patch.object(five_step.sys, 'platform', 'linux'):
            self.assertEqual(five_step.hud_backend(self.root), 'portable')
            with self.assertRaisesRegex(ValueError, 'requires macOS'):
                five_step.open_hud(self.project / 'state.json', self.project, 'a', 'native')
        assets = self.root / 'assets'
        assets.mkdir()
        executable = assets / 'FiveStepHUD.app/Contents/MacOS/FiveStepHUD'
        executable.parent.mkdir(parents=True)
        executable.write_text('fixture')
        with mock.patch.object(five_step.sys, 'platform', 'darwin'):
            self.assertEqual(five_step.hud_backend(self.root), 'native')
        config = assets / 'runtime-config.json'
        config.write_text(json.dumps({'schemaVersion': 1, 'agent': 'cursor', 'backend': 'portable'}))
        self.assertEqual(five_step.hud_backend(self.root), 'portable')
        self.assertEqual(five_step.hud_backend(self.root, 'native'), 'native')
        config.write_text(json.dumps({'schemaVersion': True, 'agent': 'cursor', 'backend': 'portable'}))
        with self.assertRaisesRegex(ValueError, 'configuration'):
            five_step.hud_backend(self.root)

    def test_bounded_timeout_terminates_unresponsive_child(self):
        self.fixture('import time; time.sleep(30)\n')
        with mock.patch.object(five_step, '__file__', str(self.root / 'scripts/five_step.py')):
            with mock.patch.object(five_step, 'HUD_STARTUP_TIMEOUT', 0.15):
                with self.assertRaisesRegex(ValueError, 'timed out'):
                    five_step.open_hud(self.project / 'state.json', self.project, 'a', 'portable')

    def test_real_nonblocking_lock_contention_and_release(self):
        from runtime_support import file_lock
        script = ('import sys; sys.path.insert(0,sys.argv[1]); from runtime_support import file_lock\n'
                  'with open(sys.argv[2],"a+b") as stream:\n'
                  ' try:\n  with file_lock(stream, blocking=False): print("acquired")\n'
                  ' except BlockingIOError: print("busy")\n')
        lockpath = self.root / 'file.lock'
        def child():
            return subprocess.run([sys.executable, '-c', script, str(SCRIPTS), str(lockpath)],
                                  capture_output=True, text=True, check=True).stdout.strip()
        with lockpath.open('a+b') as stream:
            with file_lock(stream):
                self.assertEqual(child(), 'busy')
                self.assertEqual(child(), 'busy')
            self.assertEqual(child(), 'acquired')


if __name__ == '__main__':
    unittest.main()

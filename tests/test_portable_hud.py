"""Real Qt HUD tests. Linux GUI runs require Xvfb and a compositor."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/work-like-musk/scripts'
sys.path.insert(0, str(SCRIPTS))
import five_step

try:
    from PySide6 import QtCore, QtGui, QtWidgets, QtTest
except ImportError:
    QtCore = QtGui = QtWidgets = QtTest = None


class PortableHUDTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QtWidgets is None:
            if os.environ.get('CI'):
                raise RuntimeError('CI requires PySide6-Essentials; GUI tests cannot be skipped')
            raise unittest.SkipTest(f'PySide6-Essentials is unavailable in {sys.executable}')
        if sys.platform.startswith('linux') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            if os.environ.get('CI'):
                raise RuntimeError('CI requires a graphical display and compositor; use Xvfb with xcompmgr')
            raise unittest.SkipTest('No Linux graphical desktop; use Xvfb with xcompmgr')
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(['HUD GUI tests'])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import portable_hud
        self.hud = portable_hud
        self.assertTrue(issubclass(portable_hud.FloatingHUD, QtWidgets.QWidget), 'Transparent vector Qt HUD is missing')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name).resolve()
        self.path, self.state = self.session('task-one')

    def session(self, task):
        path = self.project / '.work-like-musk/sessions' / (hashlib.sha256(task.encode()).hexdigest()+'.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        state = dict(schemaVersion=1, projectPath=str(self.project), taskId=task, title='Synthetic design review', revision=1, updatedAt=five_step.timestamp(), currentStage=None, stages=[five_step.pending(stage) for stage in five_step.STAGES])
        five_step.atomic_write(path, state)
        return path, state

    def window(self, path=None, task='task-one', language='en'):
        window = self.hud.FloatingHUD(self.project, task, path or self.path, language)
        self.addCleanup(window.close)
        window.show()
        self.assertTrue(QtTest.QTest.qWaitForWindowExposed(window, 2000), 'Qt window must actually be exposed')
        self.app.processEvents()
        return window

    @staticmethod
    def snapshot(window, scale=1):
        image = QtGui.QImage(round(window.width()*scale), round(window.height()*scale), QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(scale)
        image.fill(QtCore.Qt.GlobalColor.transparent)
        window.render(image)
        return image

    @staticmethod
    def has_color(image, color, rect):
        target = QtGui.QColor(color)
        scale = image.devicePixelRatio()
        for y in range(max(0, round(rect.top()*scale)), min(image.height(), round(rect.bottom()*scale))):
            for x in range(max(0, round(rect.left()*scale)), min(image.width(), round(rect.right()*scale))):
                actual = image.pixelColor(x, y)
                if actual.alpha() > 70 and max(abs(a-b) for a,b in zip(actual.getRgb()[:3], target.getRgb()[:3])) < 8:
                    return True
        return False

    @staticmethod
    def tooltip_text(window):
        return ' '.join(label.text() for label in window.details.findChildren(QtWidgets.QLabel))

    def test_pending_and_completion_never_start_next(self):
        window = self.window()
        self.assertEqual(window.waiting_stage, 'question')
        self.assertIsNone(window.flowing_connector)
        state = five_step.transition(self.state, 'question', 'in_progress', 'Checking the requirement')
        state = five_step.transition(state, 'question', 'completed', 'Requirement confirmed')
        five_step.atomic_write(self.path, state)
        window.refresh()
        self.assertEqual(window.waiting_stage, 'delete')
        self.assertEqual([s['status'] for s in window.state['stages']], ['completed']+['pending']*4)
        image = self.snapshot(window)
        self.assertTrue(self.has_color(image, '#196E42', QtCore.QRectF(218, 12, 14, 14)), 'Completed question symbol must remain green')
        self.assertTrue(self.has_color(image, '#196E42', QtCore.QRectF(231, 25, 8, 8)), 'Small green check must accompany the symbol')

    def test_corrupt_and_missing_clear_actual_rendered_progress(self):
        state = five_step.transition(self.state, 'question', 'in_progress', 'Checking')
        five_step.atomic_write(self.path, state)
        window = self.window()
        self.assertTrue(self.has_color(self.snapshot(window), '#265CD1', window.core_rect))
        for corrupt in (True, False):
            if corrupt:
                self.path.write_text('{')
            else:
                self.path.unlink()
            window.refresh()
            self.assertIsNone(window.state)
            self.assertIsNone(window.waiting_stage)
            self.assertIsNone(window.flowing_connector)
            self.assertFalse(self.has_color(self.snapshot(window), '#265CD1', window.core_rect))
            window.show_details(0)
            self.assertIn('unavailable', self.tooltip_text(window).lower())

    def test_wrong_task_and_wrong_path_rejected(self):
        with self.assertRaises(ValueError):
            self.window(task='another-task')
        wrong = self.project / 'copied.json'
        wrong.write_bytes(self.path.read_bytes())
        with self.assertRaises(ValueError):
            self.window(path=wrong)

    def test_two_tasks_remain_independent_and_chinese_labels(self):
        first = self.window()
        other, state = self.session('task-two')
        second = self.window(other, 'task-two', 'zh-CN')
        five_step.atomic_write(other, five_step.transition(state, 'question', 'blocked', 'Need confirmation'))
        first.refresh()
        second.refresh()
        self.assertEqual(first.waiting_stage, 'question')
        self.assertIsNone(second.waiting_stage)
        self.assertEqual(second.state['stages'][0]['status'], 'blocked')
        self.assertTrue(self.has_color(self.snapshot(second), '#A65205', second.stage_rect(0)))
        second.show_details(0)
        self.assertIn('质疑需求', self.tooltip_text(second))
        self.assertIn('暂时受阻', self.tooltip_text(second))

    def test_hover_survives_unchanged_refresh_and_reduced_motion_stops_ring(self):
        state = five_step.transition(self.state, 'question', 'in_progress', 'Exact requirement evidence')
        five_step.atomic_write(self.path, state)
        window = self.window()
        # Deliver the real Qt mouse event directly: macOS may deny QTest's
        # global cursor warp even for an otherwise exposed test window.
        point = QtCore.QPoint(225, 19)
        event = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(point), QtCore.QPointF(window.mapToGlobal(point)), QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(window, event)
        self.app.processEvents()
        self.assertIsNotNone(window.details)
        self.assertTrue(window.details.isVisible())
        details = window.details
        window.refresh()
        self.assertIs(window.details, details)
        self.assertIn('Exact requirement evidence', self.tooltip_text(window))
        window.reduce_motion_action.trigger()
        before = self.snapshot(window)
        QtTest.QTest.qWait(130)
        self.assertEqual(self.snapshot(window), before)

    def test_invalid_identity_payload_and_oversize_clear_progress(self):
        window = self.window()
        five_step.atomic_write(self.path, dict(self.state, taskId='wrong-task'))
        window.refresh()
        self.assertIsNone(window.state)
        self.path.write_bytes(b' '*(five_step.MAX_BYTES+1))
        window.refresh()
        self.assertIsNone(window.state)
        self.assertIsNone(window.waiting_stage)

    def test_symlink_and_fifo_rejected_without_reading(self):
        backup = self.path.with_suffix('.saved')
        self.path.rename(backup)
        try:
            self.path.symlink_to(backup)
        except OSError as error:
            if os.name == 'nt':
                self.skipTest(f'Windows symlink privilege unavailable: {error}')
            raise
        with self.assertRaises(ValueError):
            self.window()
        self.path.unlink()
        if hasattr(os, 'mkfifo'):
            os.mkfifo(self.path)
            with self.assertRaises(ValueError):
                self.window()

    def test_native_core_geometry_and_transparent_surface(self):
        window = self.window()
        self.assertEqual(window.size(), QtCore.QSize(454, 38))
        self.assertEqual(window.core_rect, QtCore.QRectF(206, 4, 248, 30))
        self.assertEqual(window.stage_rect(0), QtCore.QRectF(212, 4, 26, 30))
        self.assertTrue(window.testAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertEqual(window.windowOpacity(), 1, 'Whole-window fading is not per-pixel transparency')
        self.hud.check_window_transparency(window)
        image = self.snapshot(window)
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        self.assertEqual(image.pixelColor(205, 19).alpha(), 0)
        self.assertEqual(image.pixelColor(250, 8).alpha(), 0, 'Native core must have no background card')
        self.assertEqual(image.pixelColor(434, 8).alpha(), 255, 'Settings remains sharp and opaque')

    def test_flow_only_enters_first_unfinished_stage_and_stops_for_blocked(self):
        window = self.window()
        state = self.state
        for stage_id in ('question', 'delete'):
            state = five_step.transition(state, stage_id, 'in_progress', 'Starting')
            state = five_step.transition(state, stage_id, 'completed', 'Finished')
        five_step.atomic_write(self.path, state)
        window.refresh()
        self.assertEqual(window.flowing_connector, 1)
        state = five_step.transition(state, 'simplify', 'blocked', 'Need a decision')
        five_step.atomic_write(self.path, state)
        window.refresh()
        self.assertIsNone(window.flowing_connector)
        state = five_step.transition(state, 'simplify', 'in_progress', 'Decision received')
        five_step.atomic_write(self.path, state)
        window.refresh()
        self.assertEqual(window.flowing_connector, 1)
        window.reduce_motion_action.trigger()
        self.assertIsNone(window.flowing_connector)

    def test_dark_theme_preserves_geometry_and_native_palette(self):
        window = self.window()
        before = window.stage_rect(4)
        window.set_theme('dark')
        self.assertEqual(window.stage_rect(4), before)
        self.assertEqual(window.colors['completed'], '#7ACC99')
        self.assertEqual(self.snapshot(window).pixelColor(434, 8), QtGui.QColor('#383838'))

    def test_vector_rendering_is_crisp_at_fractional_and_integer_device_scales(self):
        state = five_step.transition(self.state, 'question', 'in_progress', 'High resolution evidence')
        five_step.atomic_write(self.path, state)
        window = self.window()
        window.reduce_motion_action.trigger()
        for scale in (1, 1.25, 1.5, 1.75, 2):
            with self.subTest(scale=scale):
                image = self.snapshot(window, scale)
                self.assertEqual(image.size(), QtCore.QSize(round(454*scale), round(38*scale)))
                self.assertEqual(image.devicePixelRatio(), scale)
                self.assertEqual(image.pixelColor(round(205*scale), round(19*scale)).alpha(), 0)
                self.assertTrue(self.has_color(image, '#265CD1', window.stage_rect(0)))
                alphas = [image.pixelColor(x,y).alpha() for y in range(round(7*scale),round(31*scale)) for x in range(round(213*scale),round(237*scale))]
                self.assertTrue(any(0 < a < 240 for a in alphas), 'Vector edges need smooth partial-alpha coverage')
                self.assertTrue(any(a > 245 for a in alphas), 'Symbol strokes must remain opaque and crisp')

    def test_actual_window_composites_over_own_synthetic_background(self):
        background = QtWidgets.QWidget()
        self.addCleanup(background.close)
        background.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        background.setAutoFillBackground(True)
        palette = background.palette()
        expected = QtGui.QColor('#2472A4')
        palette.setColor(QtGui.QPalette.ColorRole.Window, expected)
        background.setPalette(palette)
        background.setGeometry(80, 140, 560, 110)
        background.show()
        self.assertTrue(QtTest.QTest.qWaitForWindowExposed(background, 2000))
        window = self.window()
        window.move(background.pos()+QtCore.QPoint(40,30))
        window.raise_()
        QtTest.QTest.qWait(250)
        origin = window.mapToGlobal(QtCore.QPoint(0,0))
        grab = window.screen().grabWindow(0, origin.x(), origin.y(), window.width(), window.height())
        if grab.isNull():
            if sys.platform == 'darwin':
                self.skipTest('macOS screen-recording access blocks own-window compositing capture')
            self.fail('Qt screen capture is required to verify actual desktop compositing')
        image = grab.toImage()
        scale = grab.devicePixelRatio()
        transparent = image.pixelColor(round(205*scale), round(19*scale))
        self.assertLessEqual(max(abs(a-b) for a,b in zip(transparent.getRgb()[:3],expected.getRgb()[:3])), 3, 'Transparent gap must reveal the actual known window underneath')
        opaque = image.pixelColor(round(434*scale),round(8*scale))
        self.assertLessEqual(max(abs(a-242) for a in opaque.getRgb()[:3]),3, 'Settings square must be opaque over the same background')

    def test_actual_ring_rotates_and_completion_clears_all_motion(self):
        state = five_step.transition(self.state, 'question', 'in_progress', 'Working')
        five_step.atomic_write(self.path, state)
        window = self.window()
        before = self.snapshot(window)
        QtTest.QTest.qWait(130)
        self.assertNotEqual(self.snapshot(window), before)
        for stage_id in five_step.STAGES:
            if stage_id != 'question':
                state = five_step.transition(state, stage_id, 'in_progress', 'Working')
            state = five_step.transition(state, stage_id, 'completed', 'Done')
        five_step.atomic_write(self.path, state)
        window.refresh()
        self.assertIsNone(window.waiting_stage)
        self.assertIsNone(window.flowing_connector)
        before = self.snapshot(window)
        QtTest.QTest.qWait(130)
        self.assertEqual(self.snapshot(window), before)

    def test_stage_click_opens_evidence_details(self):
        window = self.window()
        QtTest.QTest.mouseClick(window, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(225, 19))
        self.app.processEvents()
        self.assertIsNotNone(window.details)
        self.assertTrue(window.details.isVisible())
        self.assertIn('Waiting for your prompt', self.tooltip_text(window))

    def test_settings_mouse_click_maps_menu_and_activates_actions(self):
        window = self.window()
        def choose(text):
            QtTest.QTest.mouseClick(window, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(434,19))
            self.app.processEvents()
            self.assertTrue(window.menu.isVisible())
            action = next(a for a in window.menu.actions() if a.text()==text)
            QtTest.QTest.mouseClick(window.menu, QtCore.Qt.MouseButton.LeftButton, pos=window.menu.actionGeometry(action).center())
            self.app.processEvents()
        choose('Dark')
        self.assertEqual(window.theme, 'dark')
        choose('Light')
        self.assertEqual(window.theme, 'light')
        choose('Reduce motion')
        self.assertTrue(window.reduce_motion)
        choose('Always on top')
        self.assertFalse(window.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint)
        choose('Close progress bar')
        self.assertFalse(window.isVisible())

    def test_tooltip_formats_schema_valid_boundary_timestamps(self):
        window = self.window()
        for stamp in ('0001-01-01T00:00:00.000Z', '2000-02-29T23:59:59.999Z', '9999-12-31T23:59:59.999Z'):
            state = five_step.transition(self.state, 'question', 'in_progress', 'Timestamp evidence')
            state['updatedAt'] = state['stages'][0]['updatedAt'] = stamp
            five_step.validate(state,self.project,'task-one')
            five_step.atomic_write(self.path,state)
            window.refresh()
            window.show_details(0)
            self.assertIn('UTC', self.tooltip_text(window))
            self.assertIn('Timestamp evidence', self.tooltip_text(window))

    def wait_for_file(self, path, child):
        deadline = time.monotonic()+10
        while time.monotonic()<deadline:
            if path.exists():
                return
            if child.poll() is not None:
                self.fail(f'Child exited before {path.name}: {child.communicate()}')
            time.sleep(.02)
        self.fail(f'Timed out waiting for {path.name}')

    def test_reporter_lock_defers_refresh_without_reading_or_freezing(self):
        window = self.window()
        held, release = self.project/'writer-held', self.project/'writer-release'
        code = """
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import five_step
from runtime_support import file_lock
path,project,held,release=map(Path,sys.argv[2:])
with path.with_suffix('.lock').open('a+b') as stream,file_lock(stream):
    state=five_step.load(path,project,'task-one')
    five_step.atomic_write(path,five_step.transition(state,'question','in_progress','Writer owns transaction'))
    held.touch()
    while not release.exists(): time.sleep(.01)
"""
        writer = subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(self.path),str(self.project),str(held),str(release)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(self.stop,writer)
        self.wait_for_file(held,writer)
        started = time.monotonic()
        window.refresh()
        self.assertLess(time.monotonic()-started,.3)
        self.assertEqual(window.waiting_stage,'question')
        release.touch()
        self.assertEqual(writer.wait(timeout=5),0)
        window.refresh()
        self.assertEqual(window.state['stages'][0]['status'],'in_progress')

    def startup_race(self, fail_first):
        entered, release = self.project/'startup-entered', self.project/'startup-release'
        first_ready, second_ready = self.project/'first-ready.json', self.project/'second-ready.json'
        code = """
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import portable_hud
entered,release=map(Path,sys.argv[2:4])
fail=sys.argv[4]=='fail'
original=portable_hud.check_qt
first=True
def delayed_qt():
    global first
    if first:
        first=False
        entered.touch()
        while not release.exists(): time.sleep(.01)
        if fail: raise RuntimeError('Synthetic GUI initialization failure')
    return original()
portable_hud.check_qt=delayed_qt
sys.exit(portable_hud.main(sys.argv[5:]))
"""
        args = ['--project',str(self.project),'--task','task-one','--state',str(self.path),'--language','en']
        first = subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(entered),str(release),'fail' if fail_first else 'succeed',*args,'--ready-file',str(first_ready)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(self.stop,first)
        self.wait_for_file(entered,first)
        second = subprocess.Popen([sys.executable,str(SCRIPTS/'portable_hud.py'),*args,'--ready-file',str(second_ready)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(self.stop,second)
        time.sleep(.3)
        self.assertFalse(second_ready.exists(),'No duplicate acknowledgement before initialization completes')
        release.touch()
        self.wait_for_file(first_ready,first)
        self.wait_for_file(second_ready,second)
        self.assertEqual(json.loads(first_ready.read_text())['status'],'error' if fail_first else 'opened')
        self.assertEqual(json.loads(second_ready.read_text())['status'],'opened' if fail_first else 'already_open')
        self.assertNotEqual(first.wait(timeout=5),0) if fail_first else self.assertEqual(second.wait(timeout=5),0)

    def test_duplicate_waits_for_delayed_successful_startup(self):
        self.startup_race(False)

    def test_duplicate_opens_after_delayed_failed_startup(self):
        self.startup_race(True)

    def launch(self, ready, task='task-one', env=None):
        child = subprocess.Popen([sys.executable,str(SCRIPTS/'portable_hud.py'),'--project',str(self.project),'--task',task,'--state',str(self.path),'--language','en','--ready-file',str(ready)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        self.addCleanup(self.stop,child)
        self.wait_for_file(ready,child)
        return child,json.loads(ready.read_text())

    @staticmethod
    def stop(child):
        if child.poll() is None:
            child.terminate()
        child.communicate(timeout=5)

    def test_startup_duplicate_and_error_handshake(self):
        _,response = self.launch(self.project/'ready-one.json')
        self.assertEqual(response,{'status':'opened','taskId':'task-one'})
        child,response = self.launch(self.project/'ready-two.json')
        self.assertEqual(response,{'status':'already_open','taskId':'task-one'})
        self.assertEqual(child.wait(timeout=5),0)
        child,response = self.launch(self.project/'ready-error.json','wrong-task')
        self.assertEqual(response['status'],'error')
        self.assertNotEqual(child.wait(timeout=5),0)

    def test_native_qt_plugin_abort_reports_concrete_readiness_error(self):
        env = dict(os.environ, QT_QPA_PLATFORM='an-invalid-plugin')
        child, response = self.launch(self.project/'plugin-error.json', env=env)
        self.assertEqual(response['status'], 'error')
        self.assertEqual(response['taskId'], 'task-one')
        self.assertIn('platform plugin', response['error'].lower())
        self.assertIn('an-invalid-plugin', response['error'])
        self.assertNotEqual(child.wait(timeout=5), 0)
        self.assertEqual(five_step.load(self.path,self.project,'task-one'), self.state)

    def test_invisible_platform_fails_startup_but_check_is_dependency_only(self):
        env = dict(os.environ,QT_QPA_PLATFORM='offscreen')
        child,response = self.launch(self.project/'headless-ready.json',env=env)
        self.assertEqual(response['status'],'error')
        self.assertIn('desktop',response['error'].lower())
        self.assertNotEqual(child.wait(timeout=5),0)
        self.assertEqual(five_step.load(self.path,self.project,'task-one'),self.state)
        check = subprocess.run([sys.executable,str(SCRIPTS/'portable_hud.py'),'--check'],env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(check.returncode,0,check.stderr)
        self.assertEqual(json.loads(check.stdout)['backend'],'qt')


if __name__ == '__main__':
    unittest.main()

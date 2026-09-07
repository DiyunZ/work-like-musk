#!/usr/bin/env python3
"""Transparent, task-bound floating HUD rendered with Qt vector graphics."""
import argparse
from collections import deque
from contextlib import ExitStack, contextmanager
import ctypes
import ctypes.util
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time

from five_step import STAGES, check_runtime_path, checked_text, load
from runtime_support import file_lock

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    QT_IMPORT_ERROR = None
except (ImportError, OSError) as error:
    QtCore = QtGui = QtWidgets = None
    QT_IMPORT_ERROR = str(error)

LABELS = {
    'en': ('Question', 'Delete', 'Simplify', 'Accelerate', 'Automate'),
    'zh-CN': ('质疑需求', '删除冗余', '简化优化', '加快流程', '自动化'),
}
SUMMARIES = {
    'en': ('Challenge requirements and define the outcome.', 'Remove unnecessary parts or steps.',
           'Make what remains simpler and easier to use.', 'Shorten the bottleneck that limits progress.',
           'Repeat a verified workflow with less manual work.'),
    'zh-CN': ('审视需求，明确真正要达成的目标。', '删除不必要的部分或步骤。',
              '让保留的部分更简单、更容易使用。', '缩短限制整体进度的瓶颈环节。',
              '将已验证的流程自动化，减少手动操作。'),
}
STATUS_LABELS = {
    'en': {'pending': 'Pending', 'in_progress': 'In progress', 'completed': 'Completed',
           'blocked': 'Blocked', 'skipped': 'Skipped', 'waiting': 'Waiting for your prompt'},
    'zh-CN': {'pending': '尚未开始', 'in_progress': '进行中', 'completed': '已完成',
              'blocked': '暂时受阻', 'skipped': '已跳过', 'waiting': '等待你的指令'},
}
PALETTES = {
    'light': dict(background='#FFFFFF', primary='#000000', completed='#196E42', blocked='#A65205', settings='#F2F2F2', accent='#265CD1'),
    'dark': dict(background='#1F1F1F', primary='#FFFFFF', completed='#7ACC99', blocked='#FFB357', settings='#383838', accent='#3164D3'),
}


def read_state(project, task, path, blocking=True):
    if not project.is_absolute() or project.resolve(strict=True) != project or not project.is_dir():
        raise ValueError('Project must be its canonical absolute directory')
    checked_text(task, 'Task ID', 200)
    expected = project / '.work-like-musk/sessions' / (hashlib.sha256(task.encode('utf-8')).hexdigest() + '.json')
    if path != expected:
        raise ValueError('State path does not match the supplied project and task')
    check_runtime_path(path)
    lock_path = path.with_suffix('.lock')
    check_runtime_path(lock_path)
    # Windows prevents atomic replacement while a reader has the file open.
    # Share the reporter's transaction lock and close the read before unlocking.
    with lock_path.open('a+b') as stream, file_lock(stream, blocking=blocking):
        check_runtime_path(path)
        return load(path, project, task)


def check_qt():
    """Dependency-only preflight: does not create an application or window."""
    if QtWidgets is None:
        raise RuntimeError('PySide6-Essentials 6.8 or newer is required: '+QT_IMPORT_ERROR)
    version = QtCore.qVersion()
    if tuple(int(n) for n in version.split('.')[:2]) < (6, 8):
        raise RuntimeError(f'Qt 6.8 or newer is required; found {version}')
    return version


@contextmanager
def startup_diagnostics(ready_path, task):
    """Make even a native Qt plugin abort observable before the process exits."""
    check_qt()
    recent = deque(maxlen=8)
    requested = {name.split(':', 1)[0].lower() for name in
                 (os.environ.get('QT_QPA_PLATFORM') or 'windows').split(';') if name}
    failed = set()
    def message_handler(kind, context, message):
        recent.append(message[:1024])
        exhausted = False
        if sys.platform == 'win32' and context.category == 'qt.qpa.plugin':
            match = re.search(r'Could not (?:find|load) the Qt platform plugin "([^"]+)"', message)
            if match:
                failed.add(match.group(1).lower())
                exhausted = bool(requested) and requested <= failed
        if kind == QtCore.QtMsgType.QtFatalMsg or exhausted:
            try:
                respond(ready_path, task, 'error', 'Qt platform startup failed: '+'\n'.join(recent)[-6144:])
            except (OSError, ValueError):
                pass
            if exhausted:
                # Detached Windows Qt shows a blocking dialog before qFatal.
                # All candidates failed: finish this child after its durable
                # error response; the OS releases its process-owned file locks.
                os._exit(2)
        print(message, file=sys.stderr)
    previous = QtCore.qInstallMessageHandler(message_handler)
    try:
        yield
    finally:
        # No startup path, buffer or handle remains in the running GUI.
        QtCore.qInstallMessageHandler(previous)


def x11_compositor_running():
    """Read the X11 compositing-manager selection, not any application data."""
    library = ctypes.util.find_library('X11')
    if not library:
        raise RuntimeError('Transparent X11 HUD requires libX11 and an active compositing desktop')
    x11 = ctypes.CDLL(library)
    x11.XOpenDisplay.argtypes, x11.XOpenDisplay.restype = [ctypes.c_char_p], ctypes.c_void_p
    x11.XDefaultScreen.argtypes, x11.XDefaultScreen.restype = [ctypes.c_void_p], ctypes.c_int
    x11.XInternAtom.argtypes, x11.XInternAtom.restype = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int], ctypes.c_ulong
    x11.XGetSelectionOwner.argtypes, x11.XGetSelectionOwner.restype = [ctypes.c_void_p, ctypes.c_ulong], ctypes.c_ulong
    x11.XCloseDisplay.argtypes, x11.XCloseDisplay.restype = [ctypes.c_void_p], ctypes.c_int
    display_name = os.environ.get('DISPLAY')
    display = x11.XOpenDisplay(display_name.encode() if display_name else None)
    if not display:
        raise RuntimeError('Cannot connect to the X11 graphical desktop named by DISPLAY')
    try:
        screen = x11.XDefaultScreen(display)
        atom = x11.XInternAtom(display, f'_NET_WM_CM_S{screen}'.encode(), 1)
        return bool(atom and x11.XGetSelectionOwner(display, atom))
    finally:
        x11.XCloseDisplay(display)


def check_desktop(platform=None):
    requested = (platform or os.environ.get('QT_QPA_PLATFORM', '')).split(':')[0].lower()
    if requested in ('offscreen', 'minimal', 'minimalegl', 'vnc', 'linuxfb', 'eglfs'):
        raise RuntimeError('The transparent HUD requires a visible compositing desktop, not '+requested)
    if sys.platform.startswith('linux'):
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            raise RuntimeError('A graphical Linux desktop with an active compositor is required')
        if requested == 'xcb' or (not requested and not os.environ.get('WAYLAND_DISPLAY')):
            if not x11_compositor_running():
                raise RuntimeError('Transparent X11 windows require an active compositor; enable desktop compositing (Xvfb tests also need xcompmgr)')


def create_application():
    check_qt()
    check_desktop()
    app = QtWidgets.QApplication.instance()
    if app is None:
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        app = QtWidgets.QApplication(['Work Like Musk HUD'])
    check_desktop(app.platformName())
    return app


def check_window_transparency(window):
    check_desktop(QtWidgets.QApplication.platformName())
    handle = window.windowHandle()
    if not window.testAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground):
        raise RuntimeError('The graphical desktop did not create a transparent HUD surface')
    if handle is None or handle.format().alphaBufferSize() == 0:
        raise RuntimeError('The graphical desktop does not provide an alpha channel for transparent windows')


def color(value, opacity=1):
    result = QtGui.QColor(value)
    result.setAlphaF(opacity)
    return result


def font(size, bold=False):
    result = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.GeneralFont)
    result.setPixelSize(size)
    if bold:
        result.setWeight(QtGui.QFont.Weight.DemiBold)
    return result


_Widget = QtWidgets.QWidget if QtWidgets else object


class DetailPopup(_Widget):
    def __init__(self, owner, index):
        super().__init__(owner, QtCore.Qt.WindowType.ToolTip | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.colors = owner.colors
        self.setFixedWidth(300)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        primary, secondary = color(self.colors['primary']), color(self.colors['primary'], .55)
        def label(text, size, tint=primary, bold=False):
            item = QtWidgets.QLabel(text)
            item.setWordWrap(True)
            item.setFont(font(size, bold))
            item.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            palette = item.palette()
            palette.setColor(QtGui.QPalette.ColorRole.WindowText, tint)
            item.setPalette(palette)
            return item
        layout.addWidget(label(owner.state['title'] if owner.state else owner.task, 11, secondary))
        stage = owner.state['stages'][index] if owner.state else None
        row = QtWidgets.QHBoxLayout()
        row.addWidget(label(LABELS[owner.language][index], 14, bold=True))
        row.addStretch()
        status = 'waiting' if stage and stage['id'] == owner.waiting_stage else stage['status'] if stage else 'pending'
        tint = primary if status == 'in_progress' else color(self.colors.get(status, self.colors['primary']), 1 if status in ('completed', 'blocked') else .55)
        row.addWidget(label(STATUS_LABELS[owner.language][status], 10, tint, True))
        layout.addLayout(row)
        layout.addWidget(label(SUMMARIES[owner.language][index], 11, secondary))
        if not stage:
            reason = ('Update unavailable: ' if owner.language == 'en' else '更新不可用：') + owner.error
        elif status == 'waiting':
            reason = 'This step is ready. Ask the agent to begin; it will guide you through the work and update this indicator.' if owner.language == 'en' else '此步骤已就绪。请发出开始指令，助手将引导你完成工作并更新进度。'
        else:
            reason = stage['reason'] or ("This step hasn't started yet." if owner.language == 'en' else '此步骤尚未开始。')
        layout.addWidget(label(reason, 12))
        if stage and stage['updatedAt']:
            stamp = datetime.strptime(stage['updatedAt'], '%Y-%m-%dT%H:%M:%S.%fZ')
            layout.addWidget(label(stamp.strftime('%b %d, %Y · %H:%M:%S UTC' if owner.language == 'en' else '%Y年%m月%d日 · %H:%M:%S UTC'), 10, secondary))
        self.adjustSize()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(color(self.colors['background'], .97))
        painter.setPen(QtGui.QPen(color(self.colors['primary'], .12), .5))
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 12, 12)


class FloatingHUD(_Widget):
    """A 248x30-DIP transparent native-style core beside its named task."""
    CORE_X, CORE_Y, CORE_WIDTH, CORE_HEIGHT = 206, 4, 248, 30
    closed_signal = QtCore.Signal() if QtCore else None

    def __init__(self, project, task, path, language='en'):
        check_qt()
        self.project, self.task, self.path = Path(project), task, Path(path)
        self.state = read_state(self.project, self.task, self.path)
        self.error = ''
        super().__init__(None, QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setWindowTitle('Work Like Musk — '+task)
        self.setFixedSize(454, 38)
        self.move(80, 80)
        self.setMouseTracking(True)
        self.language, self.theme = language, 'light'
        self.reduce_motion = False
        self.details = None
        self.hovered_stage = None
        self.drag_origin = None
        self.menu = QtWidgets.QMenu(self)
        themes = QtGui.QActionGroup(self.menu)
        for theme in ('light', 'dark'):
            text = theme.title() if language == 'en' else '浅色' if theme == 'light' else '深色'
            action = self.menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(theme == self.theme)
            themes.addAction(action)
            action.triggered.connect(lambda checked=False, value=theme: self.set_theme(value))
        self.menu.addSeparator()
        self.topmost_action = self.menu.addAction('Always on top' if language == 'en' else '始终置顶')
        self.topmost_action.setCheckable(True)
        self.topmost_action.setChecked(True)
        self.topmost_action.toggled.connect(self.set_topmost)
        self.reduce_motion_action = self.menu.addAction('Reduce motion' if language == 'en' else '减少动态效果')
        self.reduce_motion_action.setCheckable(True)
        self.reduce_motion_action.toggled.connect(self.set_reduce_motion)
        self.menu.addSeparator()
        self.menu.addAction('Close progress bar' if language == 'en' else '关闭进度条', self.close)
        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.timeout.connect(self.refresh)
        self.poll_timer.start(350)
        self.animation_timer = QtCore.QTimer(self)
        self.animation_timer.timeout.connect(self.animate)
        self.animation_timer.start(33)

    @property
    def colors(self):
        return PALETTES[self.theme]

    @property
    def core_rect(self):
        return QtCore.QRectF(self.CORE_X, self.CORE_Y, self.CORE_WIDTH, self.CORE_HEIGHT)

    def stage_rect(self, index):
        return QtCore.QRectF(self.CORE_X+6+index*42, self.CORE_Y, 26, 30)

    @property
    def settings_rect(self):
        return QtCore.QRectF(self.CORE_X+214, self.CORE_Y+1, 28, 28)

    @property
    def frontier(self):
        return next((i for i, stage in enumerate(self.state['stages']) if stage['status'] not in ('completed', 'skipped')), None) if self.state else None

    @property
    def waiting_stage(self):
        index = self.frontier
        return STAGES[index] if index is not None and self.state['stages'][index]['status'] == 'pending' else None

    @property
    def flowing_connector(self):
        index = self.frontier
        return index-1 if not self.reduce_motion and index is not None and index > 0 and self.state['stages'][index]['status'] in ('pending', 'in_progress') else None

    def set_theme(self, theme):
        self.theme = theme
        self.hide_details()
        self.update()

    def set_reduce_motion(self, enabled):
        self.reduce_motion = enabled
        self.update()

    def set_topmost(self, enabled):
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()

    def refresh(self):
        try:
            state = read_state(self.project, self.task, self.path, blocking=False)
        except BlockingIOError:
            return
        except (OSError, ValueError, TypeError, KeyError) as error:
            state = None
            self.error = str(error)
        if state != self.state:
            self.state = state
            self.hide_details()
            self.update()

    def animate(self):
        if not self.reduce_motion and self.state and (self.waiting_stage or any(s['status'] == 'in_progress' for s in self.state['stages'])):
            self.update(self.core_rect.toAlignedRect())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing | QtGui.QPainter.RenderHint.TextAntialiasing)
        p = self.colors
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(color(p['background'], .92))
        painter.drawRoundedRect(QtCore.QRectF(0, 1, 200, 36), 9, 9)
        title = self.state['title'] if self.state else 'State unavailable' if self.language == 'en' else '状态不可用'
        painter.setFont(font(10, True))
        painter.setPen(color(p['primary']))
        painter.drawText(QtCore.QRectF(10, 3, 186, 16), QtCore.Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics().elidedText(title, QtCore.Qt.TextElideMode.ElideRight, 186))
        painter.setFont(font(8))
        painter.setPen(color(p['primary'], .55))
        project = painter.fontMetrics().elidedText(self.project.name, QtCore.Qt.TextElideMode.ElideRight, 72)
        painter.drawText(QtCore.QRectF(10, 20, 186, 14), QtCore.Qt.AlignmentFlag.AlignVCenter, project+' / '+self.task[:18])
        now = time.monotonic()
        for index in range(4):
            start = self.CORE_X+34+index*42
            painter.setPen(QtGui.QPen(color(p['primary'], .18), 1, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))
            painter.drawLine(QtCore.QPointF(start, 19), QtCore.QPointF(start+12, 19))
            if index == self.flowing_connector:
                painter.save()
                painter.setClipRect(QtCore.QRectF(start, 16, 12, 6))
                head = start-2+(now % 1.2)/1.2*24
                gradient = QtGui.QLinearGradient(head-8, 19, head, 19)
                gradient.setColorAt(0, color(p['accent'], 0))
                gradient.setColorAt(1, color(p['accent'], .75))
                painter.setPen(QtGui.QPen(QtGui.QBrush(gradient), 2, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))
                painter.drawLine(QtCore.QPointF(head-8, 19), QtCore.QPointF(head, 19))
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(color(p['accent'], .85))
                painter.drawEllipse(QtCore.QPointF(head, 19), 1.25, 1.25)
                painter.restore()
        for index, stage_id in enumerate(STAGES):
            x, y = self.CORE_X+19+index*42, self.CORE_Y+15
            status = self.state['stages'][index]['status'] if self.state else 'pending'
            waiting = self.waiting_stage == stage_id
            tint = color(p['accent']) if status == 'in_progress' else color(p[status]) if status in ('completed', 'blocked') else color(p['primary'], .55*.55 if status == 'skipped' else .55)
            if waiting:
                tint = color(p['primary'], .75)
            if self.hovered_stage == index:
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(color(p['primary'], .05))
                painter.drawRoundedRect(self.stage_rect(index), 7, 7)
            self.draw_glyph(painter, index, x, y, tint)
            if status == 'in_progress':
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.setPen(QtGui.QPen(color(p['accent'], .16), 1.5))
                ring = QtCore.QRectF(x-12.5, y-12.5, 25, 25)
                painter.drawEllipse(ring)
                painter.setPen(QtGui.QPen(color(p['accent']), 1.6, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))
                painter.drawArc(ring, round((90 if self.reduce_motion else -(now % 1.2)/1.2*360)*16), round(-86.4*16))
            if waiting:
                breathing = 1 if self.reduce_motion else .65+.35*math.cos(now*math.pi)
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(color('#FF3B30', .12*breathing))
                painter.drawEllipse(QtCore.QPointF(x+10, y+10), 5.5, 5.5)
                painter.setBrush(color('#FF3B30', .45+.45*breathing))
                painter.drawEllipse(QtCore.QPointF(x+10, y+10), 2, 2)
            elif status == 'completed':
                self.stroke(painter, [(x+7, y+10), (x+9, y+12), (x+13, y+7.5)], tint, 1.4)
            elif status == 'blocked':
                self.stroke(painter, [(x+10, y+7), (x+10, y+10.2)], tint, 1.4)
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(tint)
                painter.drawEllipse(QtCore.QPointF(x+10, y+12.2), .75, .75)
            elif status == 'skipped':
                self.stroke(painter, [(x+7.5, y+10), (x+12.5, y+10)], tint, 1.2)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(color(p['settings']))
        painter.drawRoundedRect(self.settings_rect, 10, 10)
        tint = color(p['primary'], .8)
        if self.state:
            for y, knob in ((14, 431), (19, 437), (24, 432)):
                self.stroke(painter, [(428, y), (440, y)], tint, 1)
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(tint)
                painter.drawRoundedRect(QtCore.QRectF(knob-1.3, y-2, 2.6, 4), 1, 1)
        else:
            self.stroke(painter, [(434, 11), (442, 26), (426, 26), (434, 11)], color('#FF3B30'), 1.2)
            self.stroke(painter, [(434, 16), (434, 20)], color('#FF3B30'), 1.4)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(color('#FF3B30'))
            painter.drawEllipse(QtCore.QPointF(434, 23), .8, .8)

    @staticmethod
    def stroke(painter, points, tint, width=1.2):
        path = QtGui.QPainterPath(QtCore.QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(*point)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(tint, width, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)

    def draw_glyph(self, painter, index, x, y, tint):
        painter.save()
        painter.translate(x, y)
        if index == 0:
            path = QtGui.QPainterPath(QtCore.QPointF(-4.5, -5))
            path.lineTo(4.5, -5)
            path.quadTo(6, -5, 6, -3.5)
            path.lineTo(6, 2.5)
            path.quadTo(6, 4, 4.5, 4)
            path.lineTo(-1, 4)
            path.lineTo(-4, 6)
            path.lineTo(-4, 4)
            path.quadTo(-6, 4, -6, 2.5)
            path.lineTo(-6, -3.5)
            path.quadTo(-6, -5, -4.5, -5)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(tint, 1.15))
            painter.drawPath(path)
            self.stroke(painter, [(-1.8,-2.7),(-1,-3.5),(.7,-3.5),(1.8,-2.5),(1.5,-1.4),(0,-.4),(0,.5)], tint, 1.05)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(tint)
            painter.drawEllipse(QtCore.QPointF(0, 2), .65, .65)
        elif index == 1:
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(tint, 1.15))
            painter.drawEllipse(QtCore.QPointF(-5, -4), 2, 2)
            painter.drawEllipse(QtCore.QPointF(-5, 4), 2, 2)
            self.stroke(painter, [(-3.5,-2.6),(6,5.5)], tint)
            self.stroke(painter, [(-3.5,2.6),(6,-5.5)], tint)
        elif index == 2:
            for half, y in ((6,-4),(4,0),(2,4)):
                self.stroke(painter, [(-half,y),(half,y)], tint, 1.4)
        elif index == 3:
            self.stroke(painter, [(1,-7),(-5,1),(0,1),(-1,7),(5,-1),(1,-1),(1,-7)], tint)
        else:
            self.stroke(painter, [(-6,1),(-6,-2),(-4,-4),(6,-4),(3,-6)], tint)
            self.stroke(painter, [(6,-4),(3,-1)], tint)
            self.stroke(painter, [(6,-1),(6,2),(4,4),(-6,4),(-3,6)], tint)
            self.stroke(painter, [(-6,4),(-3,1)], tint)
        painter.restore()

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.hide_details()
            self.move(event.globalPosition().toPoint()-self.drag_origin)
            return
        hovered = next((i for i in range(5) if self.stage_rect(i).contains(event.position())), None)
        if hovered != self.hovered_stage:
            self.hovered_stage = hovered
            if hovered is None:
                self.hide_details()
            else:
                self.show_details(hovered)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.RightButton or self.settings_rect.contains(event.position()):
            self.hide_details()
            self.menu.popup(event.globalPosition().toPoint())
        elif event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.drag_origin = event.globalPosition().toPoint()-self.pos()
            index = next((i for i in range(5) if self.stage_rect(i).contains(event.position())), None)
            if index is not None:
                self.hovered_stage = index
                self.show_details(index)
                self.update()
            elif QtWidgets.QApplication.platformName().startswith('wayland'):
                # Wayland assigns top-level positions through the compositor.
                # Start its move gesture while the original press is active.
                handle = self.windowHandle()
                if handle is not None and handle.startSystemMove():
                    self.drag_origin = None
                    self.hide_details()

    def mouseReleaseEvent(self, event):
        self.drag_origin = None

    def leaveEvent(self, event):
        self.hovered_stage = None
        self.hide_details()
        self.update()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def show_details(self, index):
        self.hide_details()
        self.details = DetailPopup(self, index)
        point = self.mapToGlobal(QtCore.QPoint(round(self.stage_rect(index).center().x()-150), self.height()+7))
        available = self.screen().availableGeometry()
        point.setX(max(available.left(), min(point.x(), available.right()-self.details.width())))
        point.setY(max(available.top(), min(point.y(), available.bottom()-self.details.height())))
        self.details.move(point)
        self.details.show()

    def hide_details(self):
        if self.details is not None:
            self.details.close()
            self.details.deleteLater()
            self.details = None

    def closeEvent(self, event):
        self.poll_timer.stop()
        self.animation_timer.stop()
        self.hide_details()
        self.menu.close()
        self.closed_signal.emit()
        super().closeEvent(event)

def respond(path, task, status, error=None):
    check_runtime_path(path)
    response = {'status': status, 'taskId': task}
    if error is not None:
        response['error'] = str(error)
    descriptor, temporary = tempfile.mkstemp(prefix='.hud-ready-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(response, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--project', type=Path)
    parser.add_argument('--task')
    parser.add_argument('--state', type=Path)
    parser.add_argument('--language', choices=tuple(LABELS), default='en')
    parser.add_argument('--ready-file', type=Path)
    args = parser.parse_args(argv)
    if not args.check and any(value is None for value in (args.project, args.task, args.state, args.ready_file)):
        parser.error('--project, --task, --state and --ready-file are required')
    hud = None
    try:
        if args.check:
            print(json.dumps({'status':'ready', 'backend':'qt', 'qtVersion':check_qt()}))
            return 0
        read_state(args.project, args.task, args.state)
        lock_path = args.state.with_suffix('.hud.lock')
        startup_path = args.state.with_suffix('.hud.start.lock')
        check_runtime_path(lock_path)
        check_runtime_path(startup_path)
        with ExitStack() as lifetime:
            with startup_path.open('a+b') as startup, file_lock(startup):
                try:
                    stream = lifetime.enter_context(lock_path.open('a+b'))
                    try:
                        lifetime.enter_context(file_lock(stream, blocking=False))
                    except BlockingIOError:
                        respond(args.ready_file, args.task, 'already_open')
                        return 0
                    with startup_diagnostics(args.ready_file, args.task):
                        app = create_application()
                        hud = FloatingHUD(args.project, args.task, args.state, args.language)
                        hud.closed_signal.connect(app.quit)
                        hud.show()
                        deadline = time.monotonic()+3
                        while time.monotonic()<deadline:
                            app.processEvents()
                            if hud.windowHandle() and hud.windowHandle().isExposed():
                                break
                            time.sleep(.01)
                        else:
                            raise RuntimeError('The graphical desktop did not expose the HUD window')
                        check_window_transparency(hud)
                        respond(args.ready_file, args.task, 'opened')
                except BaseException:
                    # Failed startup drops its lifetime lock before the gate.
                    lifetime.close()
                    raise
            app.exec()
        return 0
    except Exception as error:
        if args.ready_file is not None:
            try:
                respond(args.ready_file, args.task, 'error', error)
            except (OSError, ValueError):
                pass
        print(f'portable-hud: {error}', file=sys.stderr)
        return 2
    finally:
        if hud is not None:
            hud.close()


if __name__ == '__main__':
    sys.exit(main())

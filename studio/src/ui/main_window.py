"""
Main window: describe a video on the left, watch it being planned, drawn and joined on the right.

    +----------------------------------------------------+
    |  AI Production Studio                  [provider]  |
    +-------------------------+--------------------------+
    |  Your story             |   shots, progress,       |
    |  [ text ]               |   then the finished      |
    |  [Make video] [demo]    |   video (or what failed) |
    +-------------------------+--------------------------+

The window does not know how a video is made: it calls `run_fn` (src.core.studio_run.run_studio by default) in a background
thread and listens to its events, so it never freezes and can cancel. Tests give it a different `run_fn`.
"""
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit,
    QProgressBar, QPushButton, QSizePolicy, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from src.core.studio_run import RunCancelled, RunEvents, StudioRunError, run_studio
from src.providers.provider_factory import validate_provider_config
from src.ui import theme
from src.ui.model_setup_logic import LABELS

logger = logging.getLogger(__name__)

EMPTY, PROGRESS, RESULT, ERROR = range(4)
STAGE_TEXT = {"planning": "Planning the shots", "assets": "Drawing the characters", "composing": "Setting up the scenes",
              "rendering": "Rendering the shots", "assembling": "Joining the shots into one video"}
STATUS_TEXT = {"queued": "waiting", "composed": "scene ready", "rendered": "done", "failed": "failed"}


def provider_summary(config: Dict[str, Any]) -> str:
    """The text on the provider chip: what is chosen, or an invitation to choose."""
    text, image = str(config.get("text_provider") or ""), str(config.get("image_provider") or "")
    if not text:
        return "Choose an AI provider"
    name = lambda p: LABELS.get(p, p.capitalize())
    if not image or image == text:
        return name(text)
    return f"{name(text)} for text  ·  {name(image)} for images"


def make_poster(video: Path, target: Path) -> Optional[Path]:
    """A still from the video for the result view (ffmpeg); None if that is not possible."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    r = subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", "1.0", "-i", str(video), "-frames:v", "1", "-vf", "scale=720:-1", str(target)],
                       capture_output=True)
    return target if r.returncode == 0 and target.exists() else None


class RunThread(QThread):
    """Runs `run_fn` off the window's thread and turns its events into Qt signals."""
    stage = pyqtSignal(str, str)
    plan = pyqtSignal(object)
    shot = pyqtSignal(str, str, str)
    progress = pyqtSignal(int, int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, run_fn, config, prompt, demo, cancel_event):
        super().__init__()
        self.run_fn, self.config, self.prompt, self.demo, self.cancel_event = run_fn, config, prompt, demo, cancel_event

    def run(self):
        events = RunEvents(on_stage=self.stage.emit, on_plan=self.plan.emit, on_shot=self.shot.emit, on_progress=self.progress.emit)
        try:
            self.succeeded.emit(self.run_fn(self.config, self.prompt, demo=self.demo, events=events, cancel=self.cancel_event))
        except RunCancelled:
            self.cancelled.emit()
        except StudioRunError as e:
            self.failed.emit(str(e))
        except Exception as e:                       # never leave the window waiting
            logger.exception("run failed")
            self.failed.emit(f"Something unexpected went wrong: {e}")


class ShotRow(QWidget):
    """One shot: a coloured dot, its name and state, and what happens in it."""

    def __init__(self, shot: Dict[str, Any]):
        super().__init__()
        self.shot_id = shot["shot_id"]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 12, 2, 12)
        lay.setSpacing(14)
        self.dot = QLabel("●")
        self.dot.setFixedWidth(14)
        col = QVBoxLayout()
        col.setSpacing(3)
        self.head = QLabel(self.shot_id)
        self.head.setStyleSheet("font-weight: 600;")
        self.desc = QLabel(shot["description"])
        self.desc.setObjectName("muted")
        self.desc.setWordWrap(True)
        who = ", ".join(shot["characters"])
        self.meta = QLabel(f"{who}  ·  {shot['seconds']:g} s" if who else f"{shot['seconds']:g} s")
        self.meta.setObjectName("muted")
        for w in (self.head, self.desc, self.meta):
            col.addWidget(w)
        lay.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(col, 1)
        self.set_status("queued", "")

    def set_status(self, status: str, detail: str, dark: bool = False):
        t = theme.tokens(dark)
        colour = {"queued": t["mute"], "composed": t["accent"], "rendered": t["ok"], "failed": t["bad"]}.get(status, t["mute"])
        self.dot.setStyleSheet(f"color: {colour}; font-size: 12px;")
        self.head.setText(f"{self.shot_id}   {STATUS_TEXT.get(status, status)}")
        self.setToolTip(detail if status == "failed" else "")


class MainWindow(QMainWindow):
    model_change_requested = pyqtSignal()

    def __init__(self, config: Dict[str, Any], run_fn: Callable = run_studio):
        super().__init__()
        self.config = dict(config or {})
        self.run_fn = run_fn
        self.thread: Optional[RunThread] = None
        self.cancel_event = None
        self.last_result = None
        self.rows: Dict[str, ShotRow] = {}
        self.demo_running = False
        self._running = False
        self.setWindowTitle("AI Production Studio")
        self.resize(1120, 720)
        self.setMinimumSize(860, 560)
        self._build()
        self.set_config(self.config)
        self.setStyleSheet(theme.stylesheet(theme.is_dark()))
        self._refresh_buttons()

    # ---- layout --------------------------------------------------------------------------------
    def _build(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(32, 18, 32, 20)
        outer.setSpacing(14)

        header = QHBoxLayout()
        mark = QLabel("AI Production Studio")
        mark.setObjectName("wordmark")
        self.provider_chip = QPushButton()
        self.provider_chip.setObjectName("chip")
        self.provider_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.provider_chip.setToolTip("Change provider")
        self.provider_chip.clicked.connect(self.model_change_requested.emit)
        header.addWidget(mark)
        header.addStretch(1)
        header.addWidget(self.provider_chip)
        outer.addLayout(header)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(self._prompt_panel())
        split.addWidget(self._output_panel())
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 5)
        split.setSizes([440, 560])
        outer.addWidget(split, 1)
        self.setCentralWidget(root)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=lambda: self.make_button.isEnabled() and self.start(False))

    def _prompt_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 24, 0)
        lay.setSpacing(10)
        section = QLabel("Your story")
        section.setObjectName("section")
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Describe the video you want: who is in it, where it happens, what happens.\n\n"
                                       "For example: two friends find a message in a bottle on a beach at sunset.")
        self.prompt.textChanged.connect(self._refresh_buttons)
        buttons = QHBoxLayout()
        self.make_button = QPushButton("Make video")
        self.make_button.setObjectName("primary")
        self.make_button.clicked.connect(lambda: self.start(False))
        self.demo_button = QPushButton("Try the offline demo")
        self.demo_button.clicked.connect(lambda: self.start(True))
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        for b in (self.make_button, self.demo_button, self.cancel_button):
            buttons.addWidget(b)
        buttons.addStretch(1)
        self.hint = QLabel()
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        lay.addWidget(section)
        lay.addWidget(self.prompt, 1)
        lay.addLayout(buttons)
        lay.addWidget(self.hint)
        return w

    def _output_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 8, 0, 0)
        self.stack = QStackedWidget()

        empty = QWidget()
        el = QVBoxLayout(empty)
        self.empty_label = QLabel("Your shots will appear here as they are planned and drawn,\nand the finished video when they are joined.")
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(self.empty_label)

        prog = QWidget()
        pl = QVBoxLayout(prog)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(10)
        self.stage_label = QLabel()
        self.stage_label.setObjectName("title")
        self.stage_detail = QLabel()
        self.stage_detail.setObjectName("muted")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.shot_list = QListWidget()
        self.shot_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.shot_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        for x in (self.stage_label, self.stage_detail, self.progress, self.shot_list):
            pl.addWidget(x)
        pl.setStretchFactor(self.shot_list, 1)

        res = QWidget()
        rl = QVBoxLayout(res)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        self.result_title = QLabel("Your video is ready")
        self.result_title.setObjectName("title")
        self.poster = QLabel()
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setMinimumHeight(200)
        self.poster.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.result_meta = QLabel()
        self.result_meta.setObjectName("muted")
        actions = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("primary")
        self.play_button.clicked.connect(self.play)
        self.folder_button = QPushButton("Show in folder")
        self.folder_button.clicked.connect(self.show_in_folder)
        self.save_button = QPushButton("Save a copy…")
        self.save_button.clicked.connect(self.save_copy)
        for b in (self.play_button, self.folder_button, self.save_button):
            actions.addWidget(b)
        actions.addStretch(1)
        for x in (self.result_title, self.poster):
            rl.addWidget(x, 1 if x is self.poster else 0)
        rl.addWidget(self.result_meta)
        rl.addLayout(actions)

        err = QWidget()
        gl = QVBoxLayout(err)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(10)
        self.error_title = QLabel("That did not work")
        self.error_title.setObjectName("title")
        self.error_label = QLabel()
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)
        self.error_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.retry_button = QPushButton("Back to your story")
        self.retry_button.clicked.connect(lambda: self.stack.setCurrentIndex(EMPTY))
        gl.addWidget(self.error_title)
        gl.addWidget(self.error_label, 1)
        gl.addWidget(self.retry_button, 0, Qt.AlignmentFlag.AlignLeft)

        for page in (empty, prog, res, err):
            self.stack.addWidget(page)
        lay.addWidget(self.stack)
        return w

    # ---- state ---------------------------------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._running

    def set_config(self, config: Dict[str, Any]):
        """Called at start and after the provider is changed."""
        self.config = dict(config or {})
        self.provider_chip.setText(provider_summary(self.config))
        self._refresh_buttons()

    def _provider_ok(self) -> bool:
        return validate_provider_config(self.config)[0]

    def _refresh_buttons(self):
        busy = self.busy
        has_text = bool(self.prompt.toPlainText().strip())
        ok = self._provider_ok()
        self.make_button.setEnabled(has_text and ok and not busy)
        self.demo_button.setEnabled(not busy)
        self.cancel_button.setVisible(busy)
        self.provider_chip.setEnabled(not busy)
        if busy:
            self.hint.setText("Working. You can cancel at any time.")
        elif not ok:
            self.hint.setText("Choose an AI provider to write your own stories, or try the offline demo: it needs no AI and no key.")
        elif not has_text:
            self.hint.setText("Describe the video, then press Make video (Ctrl+Enter).")
        else:
            self.hint.setText("The AI plans the shots, Blaze's art draws them, and they are joined into one video.")

    # ---- running -------------------------------------------------------------------------------
    def start(self, demo: bool):
        if self.busy:
            return
        import threading
        self.cancel_event = threading.Event()
        self.demo_running = demo
        self.last_result = None
        self.rows.clear()
        self.shot_list.clear()
        self.progress.setValue(0)
        self.stage_label.setText(STAGE_TEXT["planning"])
        self.stage_detail.setText("Offline demo: a built-in story, drawn with Pillow. No AI is used." if demo else "")
        self.stack.setCurrentIndex(PROGRESS)
        self.thread = RunThread(self.run_fn, self.config, self.prompt.toPlainText().strip(), demo, self.cancel_event)
        self.thread.stage.connect(self.on_stage)
        self.thread.plan.connect(self.show_plan)
        self.thread.shot.connect(self.update_shot)
        self.thread.progress.connect(self.on_progress)
        self.thread.succeeded.connect(self.show_result)
        self.thread.failed.connect(self.show_error)
        self.thread.cancelled.connect(self.on_cancelled)
        self.thread.finished.connect(self._run_over)
        self._running = True
        self._refresh_buttons()
        self.thread.start()

    def _run_over(self):
        self._running = False
        self.cancel_button.setEnabled(True)
        self._refresh_buttons()

    def cancel(self):
        if self._running and self.cancel_event:
            self.cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.stage_detail.setText("Cancelling after the step that is running…")

    def wait(self, ms: int = 120_000) -> bool:
        """Block until a running run is over (used by tests and on close)."""
        done = self.thread.wait(ms) if self.thread else True
        QApplication.processEvents()          # deliver the last signals before the caller looks at the window
        return done

    def closeEvent(self, event):
        if self.busy:
            self.cancel()
            self.wait(5000)
        super().closeEvent(event)

    # ---- what a run reports ----------------------------------------------------------------
    def on_stage(self, stage: str, detail: str):
        self.stage_label.setText(STAGE_TEXT.get(stage, stage))
        if detail:
            self.stage_detail.setText(detail)

    def on_progress(self, done: int, total: int):
        self.progress.setValue(int(100 * done / max(1, total)))

    def show_plan(self, shots):
        self.shot_list.clear()
        self.rows.clear()
        for s in shots:
            row = ShotRow(s)
            item = QListWidgetItem(self.shot_list)
            item.setSizeHint(row.sizeHint())
            self.shot_list.setItemWidget(item, row)
            self.rows[s["shot_id"]] = row
        self.stage_detail.setText(f"{len(shots)} shots planned." + ("  Offline demo: no AI is used." if self.demo_running else ""))

    def update_shot(self, shot_id: str, status: str, detail: str):
        row = self.rows.get(shot_id)
        if row:
            row.set_status(status, detail, theme.is_dark())

    def show_result(self, result):
        self.last_result = result
        self.progress.setValue(100)
        self.result_title.setText("Your video is ready" if not result.demo else "The demo video is ready")
        secs = f"{result.seconds:g} s"
        size = f"{result.video.stat().st_size / 1_000_000:.1f} MB" if result.video.exists() else ""
        self.result_meta.setText("  ·  ".join(x for x in (f"{result.shots} shots", secs, size, "offline demo" if result.demo else "") if x))
        self.poster.clear()
        pic = make_poster(result.video, result.video.with_suffix(".jpg")) if result.video.exists() else None
        if pic:
            pm = QPixmap(str(pic))
            self.poster.setPixmap(pm.scaledToWidth(560, Qt.TransformationMode.SmoothTransformation))
        else:
            self.poster.setText("▶")
            self.poster.setStyleSheet("font-size: 64px;")
        self.stack.setCurrentIndex(RESULT)

    def show_error(self, message: str):
        self.error_label.setText(message)
        self.stack.setCurrentIndex(ERROR)

    def on_cancelled(self):
        self.empty_label.setText("Cancelled. Your story is still on the left.")
        self.stack.setCurrentIndex(EMPTY)

    # ---- the result ------------------------------------------------------------------------
    def play(self):
        if self.last_result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_result.video)))

    def show_in_folder(self):
        if self.last_result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_result.video.parent)))

    def save_copy(self):
        if not self.last_result:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Save a copy", str(Path.home() / self.last_result.video.name), "Video (*.mp4)")
        if target:
            shutil.copyfile(self.last_result.video, target)

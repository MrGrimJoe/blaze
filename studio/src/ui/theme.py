"""The studio's look: quiet, spacious, one accent colour, light or dark to match the system (same tokens as Blaze's page)."""
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

LIGHT = dict(bg="#fbfbfa", panel="#ffffff", ink="#15171a", mute="#7b808a", line="#e4e6ea", accent="#2b44ff",
             accent_soft="#e8ebff", ok="#1f7a4d", bad="#c4301c", button_text="#fbfbfa")
DARK = dict(bg="#101114", panel="#15171b", ink="#ecedef", mute="#868b95", line="#25282e", accent="#8796ff",
            accent_soft="#222850", ok="#6fd4a1", bad="#ff8a78", button_text="#101114")


def is_dark(app: QApplication = None) -> bool:
    app = app or QApplication.instance()
    return bool(app) and app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def tokens(dark: bool) -> dict:
    return DARK if dark else LIGHT


def stylesheet(dark: bool) -> str:
    t = tokens(dark)
    return f"""
    QWidget {{ background: {t['bg']}; color: {t['ink']}; font-size: 14px; }}
    QLabel {{ background: transparent; }}
    QLabel#wordmark {{ font-size: 17px; font-weight: 650; }}
    QLabel#section {{ color: {t['mute']}; font-size: 13px; font-weight: 600; }}
    QLabel#muted {{ color: {t['mute']}; }}
    QLabel#title {{ font-size: 20px; font-weight: 650; }}
    QLabel#error {{ color: {t['bad']}; }}
    QPlainTextEdit {{ background: {t['bg']}; border: none; border-top: 1px solid {t['line']}; padding: 12px 2px; font-size: 15px;
                      selection-background-color: {t['accent']}; }}
    QPushButton {{ border: none; border-radius: 10px; padding: 9px 18px; background: transparent; color: {t['mute']}; }}
    QPushButton:hover {{ color: {t['ink']}; }}
    QPushButton#primary {{ background: {t['ink']}; color: {t['button_text']}; font-weight: 600; }}
    QPushButton#primary:hover {{ background: {t['ink']}; color: {t['button_text']}; }}
    QPushButton#primary:disabled {{ background: {t['line']}; color: {t['mute']}; }}
    QPushButton#chip {{ border: 1px solid {t['line']}; border-radius: 14px; padding: 5px 14px; color: {t['ink']}; background: {t['panel']}; }}
    QPushButton#chip:hover {{ border-color: {t['accent']}; }}
    QProgressBar {{ background: {t['line']}; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; text-align: center; color: transparent; }}
    QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}
    QListWidget {{ background: transparent; border: none; outline: none; }}
    QListWidget::item {{ border-bottom: 1px solid {t['line']}; }}
    QListWidget::item:selected {{ background: transparent; }}
    QSplitter::handle {{ background: {t['line']}; width: 1px; }}
    QScrollBar:vertical {{ width: 8px; background: transparent; }}
    QScrollBar::handle:vertical {{ background: {t['line']}; border-radius: 4px; min-height: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    """

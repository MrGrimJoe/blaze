"""
AI Production Studio — Entry Point.
Loads config, shows model setup dialog on first run, initialises all systems
via provider_factory (three independent slots: text, vision, image), launches UI.
"""
import os
import shutil
import sys
import logging
import yaml
from pathlib import Path
from PyQt6.QtWidgets import QApplication

APP_DIR_NAME = "AI Production Studio"
FROZEN = bool(getattr(sys, "frozen", False))   # True inside the PyInstaller/Inno Setup build
DATA_DIR_ENV = os.environ.get("AIPS_DATA_DIR")  # set by Blaze's launcher: keep config, logs and files in the person's own folder
PER_USER = FROZEN or bool(DATA_DIR_ENV)


def user_data_dir() -> Path:
    """Per-user, always-writable folder. The installed app lives in Program Files, which is read-only."""
    if DATA_DIR_ENV:
        return Path(DATA_DIR_ENV)
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_DIR_NAME


def config_path() -> Path:
    """Installed build: the per-user config (created from the bundled template on first run).
    Running from source: ./config.yaml, as before."""
    if not PER_USER:
        return Path("config.yaml")
    target = user_data_dir() / "config.yaml"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "config.yaml"
        if bundled.exists():
            shutil.copyfile(bundled, target)
    return target


LOG_PATH = (user_data_dir() / "storage" / "logs") if PER_USER else Path("storage/logs")
LOG_PATH.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH / "studio.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        logger.warning("config.yaml not found — the model setup window will ask for a provider")
        config = {}
    else:
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    if PER_USER:
        # keep the generated files next to the per-user config, never inside Program Files
        storage = Path(config.get("storage_path", "./storage"))
        if not storage.is_absolute():
            config["storage_path"] = str(user_data_dir() / storage)
    return config


def save_config(config: dict) -> None:
    config = dict(config)
    if PER_USER:
        config["storage_path"] = "./storage"   # stored relative; load_config re-anchors it per user
    with open(config_path(), "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)


def ensure_storage(config: dict) -> None:
    base = Path(config.get("storage_path", "./storage"))
    for folder in ["database", "projects", "assets/characters",
                   "assets/objects", "assets/environments",
                   "cache", "logs", "models"]:
        (base / folder).mkdir(parents=True, exist_ok=True)


def needs_model_setup(config: dict) -> bool:
    from src.providers.provider_factory import validate_provider_config
    is_valid, _ = validate_provider_config(config)
    return not is_valid


def show_model_setup_dialog(config: dict) -> dict:
    from src.ui.model_setup_dialog import ModelSetupDialog
    dialog = ModelSetupDialog(config)
    if dialog.exec():
        config = dialog.get_updated_config()
        save_config(config)
        logger.info(
            f"Models configured — text: {config.get('text_provider')}, "
            f"vision: {config.get('vision_provider')}, image: {config.get('image_provider')}"
        )
    return config


def build_pipeline(config: dict):
    """Wire all pipeline components (kept here so existing callers of main.build_pipeline keep working)."""
    from src.core.pipeline_factory import build_pipeline as _build
    return _build(config)


def main() -> None:
    logger.info("AI Production Studio starting...")
    config = load_config()
    ensure_storage(config)

    app = QApplication(sys.argv)
    app.setApplicationName("AI Production Studio")
    app.setStyle("Fusion")

    if needs_model_setup(config):
        config = show_model_setup_dialog(config)
        ensure_storage(config)

    from src.ui.main_window import MainWindow

    window = MainWindow(config)

    def reconfigure_model():
        nonlocal config
        config = show_model_setup_dialog(window.config)
        ensure_storage(config)
        window.set_config(config)

    window.model_change_requested.connect(reconfigure_model)
    window.show()
    logger.info("UI launched")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

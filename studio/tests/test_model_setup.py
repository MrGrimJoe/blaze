"""First-run model setup: the logic behind the window (no Qt needed), plus the window itself when Qt is available."""
import os

import pytest

from src.providers.provider_factory import validate_provider_config
from src.ui.model_setup_logic import SAME, build_config, image_choices, is_complete


class TestChoices:
    def test_image_choices_depend_on_provider(self):
        assert image_choices("gemini") == [SAME, "gemini", "openai"]
        assert image_choices("openai") == [SAME, "gemini", "openai"]
        assert image_choices("anthropic") == ["gemini", "openai"]      # Anthropic cannot make images
        assert image_choices(None) == ["gemini", "openai"]

    @pytest.mark.parametrize("main,key,image,image_key,ok", [
        (None, "k", SAME, "", False),                 # nothing chosen
        ("openai", "", SAME, "", False),              # no key
        ("openai", "k", SAME, "", True),
        ("gemini", "k", None, "", False),             # image source not chosen
        ("anthropic", "k", SAME, "", False),          # same provider cannot make images
        ("anthropic", "k", "gemini", "", False),      # other provider needs its own key
        ("anthropic", "k", "gemini", "k2", True),
        ("openai", "k", "openai", "", True),
        ("unknown", "k", SAME, "", False),
    ])
    def test_is_complete(self, main, key, image, image_key, ok):
        assert is_complete(main, key, image, image_key) is ok


class TestBuildConfig:
    @pytest.mark.parametrize("main", ["gemini", "openai"])
    def test_same_provider_for_everything(self, main):
        cfg = build_config({}, main, " k1 ", SAME)
        assert (cfg["text_provider"], cfg["vision_provider"], cfg["image_provider"]) == (main, main, main)
        assert cfg[f"{main}_api_key"] == "k1"
        ok, msg = validate_provider_config(cfg)
        assert ok, msg

    def test_anthropic_with_openai_images(self):
        cfg = build_config({}, "anthropic", "a", "openai", "o")
        assert cfg["text_provider"] == cfg["vision_provider"] == "anthropic" and cfg["image_provider"] == "openai"
        assert cfg["anthropic_api_key"] == "a" and cfg["image_openai_api_key"] == "o"
        assert validate_provider_config(cfg)[0]

    def test_anthropic_with_gemini_images_uses_image_api_key(self):
        cfg = build_config({}, "anthropic", "a", "gemini", "g")
        assert cfg["image_api_key"] == "g" and validate_provider_config(cfg)[0]

    def test_other_settings_and_other_keys_are_kept(self):
        cfg = build_config({"render_fps": 24, "openai_api_key": "old"}, "gemini", "g", SAME)
        assert cfg["render_fps"] == 24 and cfg["openai_api_key"] == "old"


@pytest.fixture
def qapp():
    pytest.importorskip("PyQt6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class TestDialog:
    def _dialog(self, qapp, config=None):
        from src.ui.model_setup_dialog import ModelSetupDialog
        return ModelSetupDialog(config or {})

    def _save(self, d):
        from PyQt6.QtWidgets import QDialogButtonBox
        return d.buttons.button(QDialogButtonBox.StandardButton.Save)

    def test_nothing_is_preselected(self, qapp):
        d = self._dialog(qapp)
        assert d._main() is None and not self._save(d).isEnabled()
        assert [d.provider.itemData(i) for i in range(1, d.provider.count())] == ["anthropic", "gemini", "openai"]

    def test_save_enables_only_when_complete(self, qapp):
        d = self._dialog(qapp)
        d.provider.setCurrentIndex(d.provider.findData("anthropic"))
        d.key.setText("a")
        assert not self._save(d).isEnabled()
        d.image.setCurrentIndex(d.image.findData("openai"))
        assert not self._save(d).isEnabled()
        d.image_key.setText("o")
        assert self._save(d).isEnabled()
        cfg = d.get_updated_config()
        assert cfg["text_provider"] == "anthropic" and cfg["image_provider"] == "openai"

    def test_gemini_defaults_images_to_same_provider(self, qapp):
        d = self._dialog(qapp)
        d.provider.setCurrentIndex(d.provider.findData("gemini"))
        d.key.setText("g")
        assert self._save(d).isEnabled() and d._image() == SAME

    def test_reopening_shows_the_saved_choice(self, qapp):
        d = self._dialog(qapp, {"text_provider": "openai", "openai_api_key": "o"})
        assert d._main() == "openai" and d.key.text() == "o"

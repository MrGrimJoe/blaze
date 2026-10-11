"""Model Setup Dialog — first-run (and "change model") configuration.

No provider is preselected: the person chooses one of Anthropic, Gemini or OpenAI and pastes their own API key.
The key is saved to config.yaml on this computer only.
"""
import logging

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from src.providers.provider_factory import CLOUD_PROVIDERS
from .model_setup_logic import LABELS, SAME, build_config, image_choices, is_complete

logger = logging.getLogger(__name__)

_PLACEHOLDER = "Choose…"


class ModelSetupDialog(QDialog):
    def __init__(self, config):
        super().__init__()
        self.config = dict(config or {})
        self.setWindowTitle("Choose your AI provider")
        self.setMinimumWidth(460)

        intro = QLabel(
            "Pick the AI provider you have an account with and paste your API key. "
            "The key is stored on this computer only."
        )
        intro.setWordWrap(True)

        self.provider = QComboBox()
        self.provider.addItem(_PLACEHOLDER, None)
        for p in CLOUD_PROVIDERS:
            self.provider.addItem(LABELS[p], p)

        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Paste your API key")

        self.image = QComboBox()
        self.image_key = QLineEdit()
        self.image_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.image_key.setPlaceholderText("API key for the image provider")
        self.image_note = QLabel("")
        self.image_note.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Provider", self.provider)
        form.addRow("API key", self.key)
        form.addRow("Images from", self.image)
        form.addRow("Image API key", self.image_key)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.image_note)
        layout.addWidget(self.buttons)

        self.provider.currentIndexChanged.connect(self._provider_changed)
        self.image.currentIndexChanged.connect(self._refresh)
        self.key.textChanged.connect(self._refresh)
        self.image_key.textChanged.connect(self._refresh)

        self._prefill()
        self._provider_changed()
        logger.info("ModelSetupDialog opened")

    # -- helpers ---------------------------------------------------------------------------------
    def _main(self):
        return self.provider.currentData()

    def _image(self):
        return self.image.currentData()

    def _prefill(self):
        """When changing models later, show what is already chosen (never when nothing is)."""
        current = str(self.config.get("text_provider") or "")
        idx = self.provider.findData(current)
        if idx > 0:
            self.provider.setCurrentIndex(idx)
            self.key.setText(str(self.config.get(f"{current}_api_key") or ""))

    def _provider_changed(self):
        main = self._main()
        previous = self._image()
        self.image.blockSignals(True)
        self.image.clear()
        self.image.addItem(_PLACEHOLDER, None)
        for choice in image_choices(main):
            self.image.addItem("Same provider" if choice == SAME else LABELS[choice], choice)
        keep = previous is not None and self.image.findData(previous) >= 0
        want = previous if keep else (SAME if main and SAME in image_choices(main) else None)
        self.image.setCurrentIndex(max(0, self.image.findData(want)) if want else 0)
        self.image.blockSignals(False)
        self.image_note.setText(
            "Anthropic cannot make images, so pick another provider for them." if main == "anthropic" else ""
        )
        self._refresh()

    def _refresh(self):
        main, image = self._main(), self._image()
        needs_image_key = bool(image) and image != SAME and image != main
        self.image_key.setVisible(needs_image_key)
        form = self.layout().itemAt(1).layout()
        label = form.labelForField(self.image_key)
        if label is not None:
            label.setVisible(needs_image_key)
        ok = is_complete(main, self.key.text(), image, self.image_key.text())
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(ok)

    # -- QDialog API used by main.py ---------------------------------------------------------------
    def exec(self):
        return super().exec() == QDialog.DialogCode.Accepted

    def get_updated_config(self):
        main, image = self._main(), self._image()
        if not is_complete(main, self.key.text(), image, self.image_key.text()):
            return self.config
        return build_config(self.config, main, self.key.text(), image, self.image_key.text())

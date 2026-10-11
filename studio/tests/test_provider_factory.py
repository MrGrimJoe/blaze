import pytest

from src.providers.provider_factory import (
    ProviderConfigError,
    get_image_provider,
    get_text_provider,
    get_vision_provider,
    validate_provider_config,
)
from src.providers.dummy_provider import (
    DummyImageProvider,
    DummyTextProvider,
    DummyVisionProvider,
)


class TestValidateProviderConfig:
    def test_dummy_providers_are_always_valid(self):
        config = {"text_provider": "dummy", "vision_provider": "dummy", "image_provider": "dummy"}
        ok, msg = validate_provider_config(config)
        assert ok is True

    def test_unknown_text_provider_rejected(self):
        config = {"text_provider": "not_a_real_provider"}
        ok, msg = validate_provider_config(config)
        assert ok is False
        assert "text_provider" in msg

    def test_gemini_without_api_key_rejected(self):
        config = {"text_provider": "gemini"}
        ok, msg = validate_provider_config(config)
        assert ok is False
        assert "gemini_api_key" in msg

    def test_gemini_with_placeholder_key_rejected(self):
        config = {"text_provider": "gemini", "gemini_api_key": "GEMINI_API_KEY_HERE"}
        ok, msg = validate_provider_config(config)
        assert ok is False

    def test_gemini_with_real_looking_key_accepted(self):
        config = {
            "text_provider": "gemini", "vision_provider": "gemini", "image_provider": "gemini",
            "gemini_api_key": "AIzaSomeRealLookingKey123",
        }
        ok, msg = validate_provider_config(config)
        assert ok is True

    def test_nothing_chosen_is_invalid_there_is_no_default(self):
        ok, msg = validate_provider_config({})
        assert ok is False
        for slot in ("text_provider", "vision_provider", "image_provider"):
            assert f"{slot} is not chosen" in msg

    def test_blank_choices_are_not_chosen(self):
        ok, msg = validate_provider_config({"text_provider": "", "vision_provider": None, "image_provider": "  "})
        assert ok is False and "not chosen" in msg

    def test_anthropic_text_with_openai_images_uses_the_image_key(self):
        config = {
            "text_provider": "anthropic", "vision_provider": "anthropic", "image_provider": "openai",
            "anthropic_api_key": "k1", "image_openai_api_key": "k2",
        }
        ok, msg = validate_provider_config(config)
        assert ok is True, msg

    def test_huggingface_without_repo_id_rejected(self):
        config = {
            "text_provider": "huggingface",
            "vision_provider": "dummy",
            "image_provider": "dummy",
        }
        ok, msg = validate_provider_config(config)
        assert ok is False
        assert "hf_repo_id" in msg

    def test_diffusers_without_repo_id_rejected(self):
        config = {
            "text_provider": "dummy",
            "vision_provider": "dummy",
            "image_provider": "diffusers",
        }
        ok, msg = validate_provider_config(config)
        assert ok is False
        assert "hf_image_repo_id" in msg

    def test_multiple_problems_all_reported(self):
        config = {"text_provider": "bogus", "image_provider": "diffusers"}
        ok, msg = validate_provider_config(config)
        assert ok is False
        assert "bogus" in msg
        assert "hf_image_repo_id" in msg


class TestNoDefaultProvider:
    @pytest.mark.parametrize("getter", ["get_text_provider", "get_vision_provider", "get_image_provider"])
    @pytest.mark.parametrize("config", [{}, {"text_provider": "", "vision_provider": "", "image_provider": ""}])
    def test_getters_refuse_to_guess(self, getter, config):
        from src.providers import provider_factory
        with pytest.raises(provider_factory.ProviderConfigError, match="chosen"):
            getattr(provider_factory, getter)(config)

    def test_shipped_config_chooses_nothing_and_holds_no_key(self):
        import yaml
        from pathlib import Path
        cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text(encoding="utf-8"))
        for slot in ("text_provider", "vision_provider", "image_provider"):
            assert not cfg.get(slot), f"{slot} must ship empty"
        keys = [k for k in cfg if k.endswith("api_key") or k == "hf_token"]
        assert keys and all(not str(cfg[k]).strip() for k in keys), "no key may ship in config.yaml"

    def test_no_default_provider_name_is_hardcoded_in_the_factory(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "src" / "providers" / "provider_factory.py").read_text(encoding="utf-8")
        assert '_provider", "gemini")' not in src and '_provider", "openai")' not in src and '_provider", "anthropic")' not in src


class TestGetProviderWiring:
    def test_get_text_provider_dummy(self):
        provider = get_text_provider({"text_provider": "dummy"})
        assert isinstance(provider, DummyTextProvider)

    def test_get_vision_provider_dummy(self):
        provider = get_vision_provider({"vision_provider": "dummy"})
        assert isinstance(provider, DummyVisionProvider)

    def test_get_image_provider_dummy(self):
        provider = get_image_provider({"image_provider": "dummy"})
        assert isinstance(provider, DummyImageProvider)

    def test_get_text_provider_unknown_raises(self):
        with pytest.raises(ProviderConfigError):
            get_text_provider({"text_provider": "totally_bogus"})

    def test_huggingface_provider_lazy_constructs_without_loading_model(self):
        # Construction should succeed without downloading anything —
        # the model only loads on first generate() call.
        provider = get_text_provider({"text_provider": "huggingface", "hf_repo_id": "some/model"})
        assert provider.repo_id == "some/model"
        assert provider._pipe is None

    def test_huggingface_provider_requires_repo_id(self):
        from src.providers.huggingface_provider import HuggingFaceConfigError
        with pytest.raises(HuggingFaceConfigError):
            get_text_provider({"text_provider": "huggingface", "hf_repo_id": ""})

    def test_huggingface_vision_provider_lazy_constructs_without_loading_model(self):
        provider = get_vision_provider({"vision_provider": "huggingface", "hf_repo_id": "some/model"})
        assert provider.repo_id == "some/model"
        assert provider._pipe is None

    def test_diffusers_image_provider_lazy_constructs_without_loading_model(self):
        provider = get_image_provider({"image_provider": "diffusers", "hf_image_repo_id": "some/model"})
        assert provider.repo_id == "some/model"
        assert provider._pipe is None

    def test_gemini_text_provider_without_key_raises_config_error(self):
        from src.providers.gemini_provider import GeminiConfigError
        with pytest.raises(GeminiConfigError):
            get_text_provider({"text_provider": "gemini", "gemini_api_key": ""})

    def test_ollama_text_provider_raises_not_implemented_clearly(self):
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            get_text_provider({"text_provider": "ollama"})

    def test_ollama_vision_provider_raises_not_implemented_clearly(self):
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            get_vision_provider({"vision_provider": "ollama"})

    def test_get_vision_provider_unknown_raises(self):
        with pytest.raises(ProviderConfigError):
            get_vision_provider({"vision_provider": "totally_bogus"})

    def test_get_image_provider_unknown_raises(self):
        with pytest.raises(ProviderConfigError):
            get_image_provider({"image_provider": "totally_bogus"})

    def test_vision_gemini_key_falls_back_to_main_key(self):
        # No vision_gemini_api_key set -> should use gemini_api_key instead
        # of failing. This exercises the `or` fallback in get_vision_provider.
        config = {
            "vision_provider": "gemini",
            "gemini_api_key": "AIzaMainKey123",
            "vision_gemini_api_key": "",
        }
        provider = get_vision_provider(config)
        assert provider.client is not None  # constructed without raising

    def test_vision_gemini_key_prefers_dedicated_key_when_set(self):
        # A distinct vision_gemini_api_key should be used over the main key
        # when both are present — verified indirectly: construction should
        # succeed even if gemini_api_key were invalid, since it's not the
        # key actually used (we can't inspect the SDK client's stored key
        # directly, so this documents intended precedence and exercises
        # the code path — see GeminiVisionProvider for the real precedence).
        config = {
            "vision_provider": "gemini",
            "gemini_api_key": "GEMINI_API_KEY_HERE",  # would fail get_text_provider's check
            "vision_gemini_api_key": "AIzaDedicatedVisionKey456",
        }
        # Should not raise, because vision_gemini_api_key takes precedence
        # over the placeholder-y gemini_api_key.
        provider = get_vision_provider(config)
        assert provider is not None

    def test_image_api_key_falls_back_to_main_key(self):
        config = {
            "image_provider": "gemini",
            "gemini_api_key": "AIzaMainKey123",
            "image_api_key": "",
        }
        provider = get_image_provider(config)
        assert provider is not None

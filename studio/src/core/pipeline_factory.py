"""Wires the pipeline's components together from a config (shared by the window, main.py and the tests)."""
import copy
from pathlib import Path
from typing import Any, Dict


def build_pipeline(config: dict):
    """Wire all pipeline components. Text, vision, and image providers are independent."""
    from src.core.world_state.world_state import WorldStateManager
    from src.providers.provider_factory import (
        get_text_provider, get_vision_provider, get_image_provider
    )
    from src.core.asset_manager.asset_manager import AssetManager
    from src.core.scene_composer.scene_composer import SceneComposer
    from src.core.validator.validator_manager import ValidatorManager
    from src.core.repair.repair_engine import RepairEngine
    from src.core.director.director import Director
    from src.core.orchestrator.orchestrator import PipelineOrchestrator
    from src.integrations.godot.renderer import GodotRenderer

    world_state     = WorldStateManager(config)
    text_provider   = get_text_provider(config)
    vision_provider = get_vision_provider(config)
    image_provider  = get_image_provider(config)

    asset_manager   = AssetManager(config, image_provider)
    use_cdrca       = str(config.get("render_backend", "godot")).lower() == "cdrca"
    if use_cdrca:
        from src.core.scene_composer.cdrca_composer import CdrcaSceneComposer
        scene_composer = CdrcaSceneComposer(config)
    else:
        scene_composer = SceneComposer(config)
    validator_mgr   = ValidatorManager(text_provider, vision_provider)
    director        = Director(text_provider, world_state)
    repair_engine   = RepairEngine(asset_manager, scene_composer, director, world_state)
    if use_cdrca:
        from src.integrations.cdrca import CdrcaRenderer
        godot_renderer = CdrcaRenderer(config)  # same render_shot() interface as GodotRenderer
    else:
        godot_renderer = GodotRenderer(config)

    orchestrator = PipelineOrchestrator(
        config, world_state, asset_manager,
        scene_composer, validator_mgr, repair_engine,
        godot_renderer=godot_renderer,
    )
    return director, orchestrator, world_state, asset_manager


def demo_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """A config for the offline demo: a built-in story, Pillow-drawn art, the CDRCA renderer. No AI, no key, no GPU."""
    cfg = copy.deepcopy(config)
    cfg.update(
        text_provider="demo", vision_provider="dummy", image_provider="builtin",
        render_backend="cdrca", skip_validation=True,
        render_width=960, render_height=540, render_fps=12,
        storage_path=str(Path(config.get("storage_path", "./storage")) / "demo"),
    )
    return cfg

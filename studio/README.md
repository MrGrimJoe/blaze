# BlazEng: AI Production Studio

An AI-directed video pipeline: a story prompt becomes a shot plan, art, composed scenes, rendered frames, checks and repairs,
and a finished video. This is the studio half of the repository; the deterministic screenplay-to-video tool at the
repository root is [Blaze](../README.md), which shares this folder's provider layer and CDRCA backend. How the two relate is
in [../docs/studio.md](../docs/studio.md).

## Where it stands, honestly

- **A real main window.** `python main.py` opens the first-run provider window (when no provider is chosen) and then the main
  window: describe a video, watch the shots being planned and drawn, get the finished video with a still, Play, Show in folder and
  Save a copy. It runs the pipeline in the background and can cancel. [Tutorial 8](../docs/tutorials/08-blaze-studio.md) walks
  through it.
- **An offline demo that needs nothing:** a built-in three-shot story, characters drawn by Blaze's art code, backdrops chosen from
  the shot's words, rendered by CDRCA. It is tested for real, end to end, through the window.
- **Implemented and tested:** the director, asset manager, scene composers (Godot and CDRCA), renderers, validator, repair
  engine, orchestrator (with a real cancel), world-state database, ffmpeg assembler, the provider layer (Anthropic, Gemini,
  OpenAI, HuggingFace, Diffusers, Ollama, plus `dummy`, `demo` and `builtin`), and the window. `python -m pytest tests` runs
  344 passed and 2 skipped on Linux (the skips need Godot).
- **Not verified:** your own stories against a live AI provider (tested with scripted stand-ins only), and Godot rendering.
- **No default AI provider.** You choose one, and bring your own key; nothing ships with a key. Local models are yours to set up.

## What each part does

| Part | Where | Job |
|---|---|---|
| Director | `src/core/director/` | turns a story prompt into a structured shot plan and a task schedule |
| Asset manager | `src/core/asset_manager/` | generates, caches and versions character and environment pictures |
| Scene composers | `src/core/scene_composer/` | build a Godot scene or a CDRCA script for each shot |
| Renderers | `src/integrations/godot/`, `src/integrations/cdrca/` | draw the frames of a shot headlessly |
| Validator and repair | `src/core/validator/`, `src/core/repair/` | check frames and turn feedback into a revised shot |
| Orchestrator | `src/core/orchestrator/` | runs the task schedule end to end |
| World state | `src/core/world_state/` | SQLite continuity memory for characters and shots |
| Assembler | `src/integrations/ffmpeg/` | joins a shot's frames into the final mp4 |
| Providers | `src/providers/` | one interface over every AI service; `provider_factory.py` picks them |
| First-run window | `src/ui/model_setup_dialog.py` | choose a provider and paste your key |
| Main window | `src/ui/main_window.py`, `src/ui/theme.py` | the window: story, shots, progress, result; light and dark |
| One run | `src/core/studio_run.py` | prompt to mp4 with events and cancel, no UI in it (the window, tests and scripts all use it) |
| Offline demo | `src/providers/demo_provider.py` | the built-in story and the Pillow-drawn characters |

## Choosing providers

Three independent slots, each set in `config.yaml`: `text_provider`, `vision_provider`, `image_provider`. **They ship empty**
and must be chosen, either in the first-run window or by hand.

| Slot | Choices |
|---|---|
| text and vision | `anthropic`, `gemini`, `openai` (advanced: `huggingface`, `ollama`, `dummy`) |
| image | `gemini`, `openai` (advanced: `diffusers`, `dummy`); Anthropic has no image generation |

Each cloud provider has its own key field (`anthropic_api_key`, `gemini_api_key`, `openai_api_key`), with optional
slot-specific keys (`vision_*_api_key`, `image_api_key`, `image_openai_api_key`). Create keys in your provider's console;
the cost and limits are the provider's. Model names are in `config.yaml`; if a call says a model is not found, use a current
name from your provider.

The first-run window offers Anthropic, Gemini and OpenAI, asks for the key, and, if you choose Anthropic, asks for another
provider for images. It saves `config.yaml`. The code behind it (`model_setup_logic.py`) has no Qt in it and is unit tested.

## Run it from source

```
pip install -r requirements.txt
python setup.py            # one-click setup: installs dependencies, downloads Godot and ffmpeg, asks for a provider and key
python main.py             # first-run window, then the main window
```

`setup_studio.py` is the longer alternative: it also makes a virtual environment, downloads Blender, creates the storage
folders and runs a smoke test. Both ask which provider you use (none is preselected) and your key, or let you skip and
choose in the app instead.

Press **Try the offline demo** in the window to see the whole flow with no AI. The pipeline also runs from Python (the window
uses exactly this):

```python
import main
from src.core.studio_run import RunEvents, run_studio

config = main.load_config()
result = run_studio(config, "A detective in 1940s rain finds a clue at a warehouse.",
                    events=RunEvents(on_stage=print, on_shot=print))
print(result.video)

demo = run_studio(config, "", demo=True)       # the offline demo: no AI, no key, no GPU
```

Your own story needs a real text provider: the director asks for a JSON shot plan, which the `dummy` provider does not return
(it is for tests, which script its answers). Rendering needs Godot, or the CDRCA backend below.

## The CDRCA backend

Set `render_backend: cdrca` in `config.yaml` and shots are composed as CDRCA scripts that import `atoms.cdrca` (the same
`Picture` prop Blaze uses) and rendered by the CDRCA engine in the folder above, instead of Godot. It needs Node.js and
`python ../blaze.py setup`. Characters stand side by side; words in a shot's action choose between walking and a small hop
while they talk. Tests: `python -m pytest tests/test_cdrca_renderer.py`, which includes a real compose, render and assemble.

## The Windows installer

`installer.iss` and `AIProductionStudio.spec` package the app; **GitHub Actions builds the installer**
(`.github/workflows/build-installer.yml`). The installed app stores its `config.yaml`, logs and files in
`%APPDATA%\AI Production Studio`, so nothing is written to Program Files. Steps, how to run the workflow and how to read a
failed build are in [../docs/studio.md](../docs/studio.md).

## Tests

```
QT_QPA_PLATFORM=offscreen python -m pytest tests      # on Windows: set QT_QPA_PLATFORM=offscreen first
```

They use scripted and dummy providers; no keys or network are needed. A real render, ffmpeg or Godot is used where
installed and skipped otherwise.

## Older design notes

`ARCHITECTURE.md`, `ROADMAP.md` and `CONTRIBUTING.md` are the original development notes. Where they disagree with this
file, this file is current.

## License

The same license as the rest of the repository: the Islamic Open Source License (IOSL), see [../LICENSE.md](../LICENSE.md).
PyQt6, which the studio imports, is GPL: see [../THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).

"""
AI Production Studio — One-click setup.
Installs Python deps, downloads Godot + FFmpeg, configures model, writes config.yaml.
"""
import json, os, sys, platform, subprocess, zipfile, tarfile, shutil, urllib.request
from pathlib import Path

SYSTEM = platform.system()
ROOT   = Path(__file__).parent
BIN    = ROOT / "bin"

# Godot 4.7.2 is current stable as of Aug 2026 (verified: godot-4.7.2-stable
# uploaded to godotengine/godot-builds on 2026-08-18). Desktop editor builds
# are published under godotengine/godot releases using this naming pattern.
# NOTE: verify the exact asset filename against the release page before
# shipping, since Godot has occasionally changed its zip-naming convention
# between minor versions.
GODOT_URLS = {
    "Windows": "https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_win64.exe.zip",
    "Darwin":  "https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_macos.universal.zip",
    "Linux":   "https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip",
}
FFMPEG_URLS = {
    "Windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "Darwin":  "https://evermeet.cx/ffmpeg/ffmpeg-6.1.zip",
    "Linux":   "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
}


def banner(msg): print(f"\n{'='*60}\n  {msg}\n{'='*60}")
def run(cmd): subprocess.run(cmd, check=True)
def download(url, dest):
    print(f"  Downloading {Path(dest).name}...")
    urllib.request.urlretrieve(url, dest)
    print(f"  ✅ {dest}")


def check_python():
    banner("Python version")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 11):
        print(f"  ❌ Python 3.11+ required (you have {v.major}.{v.minor})")
        sys.exit(1)
    print(f"  ✅ Python {v.major}.{v.minor}.{v.micro}")


def install_core_deps():
    banner("Installing core Python dependencies")
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"])
    # Install only core deps — heavy optional ones are separate
    # Note: google-genai is GA and uses 2.x versioning (verified against PyPI Aug 2026)
    core = ["pyyaml>=6.0.1", "pydantic>=2.7.0", "PyQt6>=6.11.0",
            "requests>=2.32.0", "google-genai>=2.0.0", "huggingface_hub>=0.25.0"]
    run([sys.executable, "-m", "pip", "install"] + core + ["-q"])
    print("  ✅ Core deps installed (verified Aug 2026)")


def ask_gpu():
    banner("GPU / CPU selection for local models")
    print("  If you plan to use local AI models (HuggingFace / Stable Diffusion),")
    print("  choose your hardware:")
    print("  1) I have an NVIDIA GPU  — installs torch with CUDA (large download)")
    print("  2) CPU only              — installs torch CPU build (smaller, slower)")
    print("  3) Skip                  — I will only use cloud models")
    choice = input("  Enter 1, 2, or 3: ").strip()
    if choice == "1":
        run([sys.executable, "-m", "pip", "install",
             "torch", "transformers", "accelerate", "sentencepiece", "diffusers", "-q"])
        print("  ✅ GPU torch stack installed")
    elif choice == "2":
        run([sys.executable, "-m", "pip", "install",
             "torch", "--index-url", "https://download.pytorch.org/whl/cpu",
             "-q"])
        run([sys.executable, "-m", "pip", "install",
             "transformers", "accelerate", "sentencepiece", "diffusers", "-q"])
        print("  ✅ CPU torch stack installed")
    else:
        print("  ✅ Skipped — using cloud models only")


def install_godot():
    banner("Installing Godot 4")
    BIN.mkdir(exist_ok=True)
    url = GODOT_URLS.get(SYSTEM)
    if not url: print("  ⚠️  Unsupported OS — install Godot manually"); return ""
    zp = BIN / "godot.zip"
    download(url, zp)
    with zipfile.ZipFile(zp) as z: z.extractall(BIN / "godot_ext")
    zp.unlink()
    for p in (BIN / "godot_ext").rglob("*"):
        if "godot" in p.name.lower() and p.suffix in (".exe", "") and p.is_file():
            dest = BIN / ("godot.exe" if SYSTEM == "Windows" else "godot")
            shutil.copy2(p, dest)
            if SYSTEM != "Windows": dest.chmod(0o755)
            shutil.rmtree(BIN / "godot_ext")
            print(f"  ✅ Godot: {dest}")
            if SYSTEM == "Linux":
                _check_xvfb()
            return str(dest)
    print("  ⚠️  Could not locate Godot binary — install manually"); return ""


def _check_xvfb() -> None:
    """Verify xvfb-run is available on Linux — GodotRenderer requires it.

    Verified during development that Godot's `--headless` flag alone
    cannot actually render/write frames (it forces a no-op "dummy"
    rendering driver) — real rendering needs a virtual X display. See
    src/integrations/godot/renderer.py's module docstring and
    ROADMAP.md Phase 2 for the full finding.
    """
    if shutil.which("xvfb-run") is not None:
        print("  ✅ xvfb-run found")
        return
    print(
        "  ⚠️  xvfb-run not found — required for actual Godot rendering.\n"
        "     Install it with: sudo apt install xvfb (Debian/Ubuntu)\n"
        "     or your distro's equivalent package."
    )


def install_ffmpeg():
    banner("Installing FFmpeg")
    BIN.mkdir(exist_ok=True)
    url = FFMPEG_URLS.get(SYSTEM)
    if not url: print("  ⚠️  Unsupported OS — install FFmpeg manually"); return ""
    archive = BIN / ("ffmpeg.zip" if "zip" in url else "ffmpeg.tar.xz")
    download(url, archive)
    if str(archive).endswith(".zip"):
        with zipfile.ZipFile(archive) as z: z.extractall(BIN / "ffmpeg_ext")
    else:
        with tarfile.open(archive) as t: t.extractall(BIN / "ffmpeg_ext")
    archive.unlink()
    for p in (BIN / "ffmpeg_ext").rglob("*"):
        if p.stem == "ffmpeg" and p.is_file():
            dest = BIN / ("ffmpeg.exe" if SYSTEM == "Windows" else "ffmpeg")
            shutil.copy2(p, dest)
            if SYSTEM != "Windows": dest.chmod(0o755)
            shutil.rmtree(BIN / "ffmpeg_ext")
            print(f"  ✅ FFmpeg: {dest}"); return str(dest)
    print("  ⚠️  Could not locate FFmpeg binary — install manually"); return ""


CLOUD = {"1": ("anthropic", "Anthropic (Claude)"), "2": ("gemini", "Google Gemini"), "3": ("openai", "OpenAI")}
IMAGE_CLOUD = {"1": ("gemini", "Google Gemini"), "2": ("openai", "OpenAI")}


def pick(title, options, allow_blank=False):
    """Ask for one of the numbered options. There is no default: Enter only skips when allow_blank."""
    while True:
        print(f"\n  {title}")
        for n, (_, label) in options.items():
            print(f"  {n}) {label}")
        choice = input("  Enter a number" + (" (or Enter to skip): " if allow_blank else ": ")).strip()
        if choice in options:
            return options[choice][0]
        if allow_blank and not choice:
            return ""
        print("  Please enter one of the numbers shown.")


def choose_model():
    banner("Choose your AI model")
    print("  1) Cloud  — Anthropic, Gemini or OpenAI (needs your own API key + internet)")
    print("  2) Local  — HuggingFace model (runs on your machine, no API key needed)")
    choice = input("  Enter 1 or 2: ").strip()
    if choice == "2":
        print("\n  Browse: huggingface.co/models?pipeline_tag=text-generation")
        repo   = input("  Text model repo ID (e.g. Qwen/Qwen2.5-3B-Instruct): ").strip()
        img_r  = input("  Image model repo ID (e.g. stabilityai/sdxl-turbo) or blank to skip: ").strip()
        model = {"text_provider": "huggingface", "vision_provider": "huggingface",
                 "image_provider": "diffusers" if img_r else "",
                 "hf_repo_id": repo, "hf_image_repo_id": img_r}
        vp = pick("Cloud provider for vision validation (optional):", CLOUD, allow_blank=True)
        if vp:
            model["vision_provider"] = vp
            model[f"{vp}_api_key"] = input(f"  {vp} API key: ").strip()
        return model
    provider = pick("Which provider do you have an account with?", CLOUD)
    model = {"text_provider": provider, "vision_provider": provider,
             f"{provider}_api_key": input(f"  {provider} API key: ").strip()}
    if provider == "anthropic":
        print("\n  Anthropic cannot generate images, so choose another provider for them.")
        image = pick("Images from:", IMAGE_CLOUD)
        model["image_provider"] = image
        model["image_api_key" if image == "gemini" else f"image_{image}_api_key"] = input(f"  {image} API key (for images): ").strip()
    else:
        model["image_provider"] = provider
    return model


def write_config(godot_path, ffmpeg_path, model):
    banner("Writing config.yaml")
    q = lambda key: json.dumps(str(model.get(key, "")))   # JSON strings are valid YAML
    cfg = f"""# AI Production Studio — Configuration
# No default provider: these were chosen by you in setup (or leave blank and the app asks on first run).
text_provider:   {q("text_provider")}
vision_provider: {q("vision_provider")}
image_provider:  {q("image_provider")}

anthropic_api_key:        {q("anthropic_api_key")}
gemini_api_key:           {q("gemini_api_key")}
openai_api_key:           {q("openai_api_key")}
vision_anthropic_api_key: ""
vision_gemini_api_key:    ""
vision_openai_api_key:    ""
image_api_key:            {q("image_api_key")}
image_openai_api_key:     {q("image_openai_api_key")}
anthropic_model:    claude-sonnet-4-5
gemini_model:       gemini-flash-latest
gemini_image_model: gemini-3.1-flash-image
openai_model:       gpt-5.5
openai_image_model: gpt-image-1

hf_repo_id:       {q("hf_repo_id")}
hf_image_repo_id: {q("hf_image_repo_id")}
hf_device:        auto
hf_max_new_tokens: 1024

ollama_url:   http://localhost:11434
ollama_model: llama3

# NOTE: key is godot_binary_path — must match what GodotRenderer reads
# (src/integrations/godot/renderer.py), not "godot_path".
godot_binary_path: {godot_path  or "./bin/godot"}
blender_path:      blender
ffmpeg_path:       {ffmpeg_path or "ffmpeg"}

storage_path:            ./storage
max_repair_attempts:     3
render_timeout_seconds:  300
render_fps:              24
render_width:            1152
render_height:           648
# ValidatorManager/RepairEngine aren't implemented yet (Phase 3) — leave
# true so the pipeline marks shots rendered instead of raising on every shot.
skip_validation:         true
"""
    (ROOT / "config.yaml").write_text(cfg, encoding="utf-8")
    print("  ✅ config.yaml written")


def self_test(model):
    banner("Self-test")
    errors = []
    for pkg in ["PyQt6", "pydantic", "yaml", "requests"]:
        try:
            __import__(pkg.lower().replace("pyqt6", "PyQt6"))
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ❌ {pkg} missing"); errors.append(pkg)

    # Test the chosen cloud provider through the same factory the app uses (works for any provider)
    provider = model.get("text_provider")
    if provider in ("anthropic", "gemini", "openai"):
        if model.get(f"{provider}_api_key"):
            try:
                sys.path.insert(0, str(ROOT))
                from src.providers.provider_factory import get_text_provider
                reply = get_text_provider(model).generate("Reply with the single word: OK")
                print(f"  ✅ {provider} connected" if "OK" in (reply or "") else f"  ⚠️  {provider}: unexpected response")
            except Exception as e:
                print(f"  ❌ {provider} error: {e}"); errors.append(provider)
        else:
            print(f"  ⚠️  No {provider} key — skipping API test")

    # Test HuggingFace if configured (correct key: text_provider)
    if model.get("text_provider") == "huggingface":
        try:
            import huggingface_hub
            print(f"  ✅ huggingface_hub {huggingface_hub.__version__}")
            if model.get("hf_repo_id"):
                print(f"  ℹ️  Model {model['hf_repo_id']!r} will download on first launch")
        except ImportError as e:
            print(f"  ❌ {e}"); errors.append("huggingface_hub")

    if errors:
        print(f"\n  ⚠️  {len(errors)} issue(s): {errors}")
    else:
        print("\n  ✅ All checks passed")
    return len(errors) == 0


def main():
    banner("AI Production Studio — Setup")
    print(f"  System: {SYSTEM} | Python: {sys.version.split()[0]}")
    check_python()
    install_core_deps()
    ask_gpu()
    godot   = install_godot()
    ffmpeg  = install_ffmpeg()
    model   = choose_model()
    write_config(godot, ffmpeg, model)
    ok      = self_test(model)
    banner("Done")
    if ok:
        print("  python main.py")
    else:
        print("  Fix the issues above, then run: python main.py")


if __name__ == "__main__":
    main()

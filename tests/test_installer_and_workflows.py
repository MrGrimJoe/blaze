"""
Everything about the installer and the GitHub workflows that CAN be checked without Windows or GitHub: what gets staged, what the
installer script refers to, and that the workflows are consistent with each other and with the files they use. The workflows
themselves then prove the rest on real machines.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "installer"))
import stage  # noqa: E402

WORKFLOWS = {p.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (REPO / ".github" / "workflows").glob("*.yml")}
TEXTS = {p.name: p.read_text(encoding="utf-8") for p in (REPO / ".github" / "workflows").glob("*.yml")}


@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    out = tmp_path_factory.mktemp("stage") / "Blaze"
    out.mkdir()
    stage.stage_app(out)
    return out


class TestStagedApp:
    def test_everything_the_app_needs_is_there(self, staged):
        for rel in ("blaze_app.pyw", "blaze.py", "blaze/launcher.py", "blaze/ui_assets/index.html", "blender/blaze_blender.py",
                    "cdrca/Back-end/Render/render.js", "cdrca/Back-end/Transpiler/index.js", "cdrca-lib/atoms.cdrca",
                    "examples/the-warehouse.txt", "studio/config.yaml", "studio/src/providers/provider_factory.py",
                    "docs/README.md", "VERSION", "LICENSE.md", "LICENSES.md",
                    "studio_app.pyw", "studio/main.py", "studio/src/ui/main_window.py", "studio/src/core/studio_run.py",
                    "studio/src/providers/demo_provider.py", "studio/src/integrations/cdrca/atoms.cdrca"):
            assert (staged / "app" / rel).is_file(), rel
        for rel in ("LICENSE.txt", "THIRD-PARTY-NOTICES.md", "blaze.ico"):
            assert (staged / rel).is_file(), rel

    def test_nothing_needless_or_private_is_shipped(self, staged):
        files = [p for p in (staged / "app").rglob("*") if p.is_file()]
        assert not [p for p in files if "__pycache__" in p.parts or p.suffix == ".pyc"]
        assert not (staged / "app" / "cdrca" / "tests").exists() and not (staged / "app" / "tests").exists()
        assert not (staged / "app" / "studio" / "tests").exists()
        assert not [p for p in files if p.suffix == ".mp4"]

    def test_the_shipped_config_has_every_provider_and_key_empty(self, staged):
        cfg = yaml.safe_load((staged / "app" / "studio" / "config.yaml").read_text(encoding="utf-8"))
        for slot in ("text_provider", "vision_provider", "image_provider"):
            assert not cfg[slot]
        assert all(not str(v).strip() for k, v in cfg.items() if k.endswith("api_key") or k == "hf_token")

    def test_the_staged_studio_renders_with_cdrca_not_godot(self, staged):
        cfg = yaml.safe_load((staged / "app" / "studio" / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["render_backend"] == "cdrca"
        assert yaml.safe_load((REPO / "studio" / "config.yaml").read_text(encoding="utf-8"))["render_backend"] == "godot"   # the repo's own default is untouched
        assert (staged / "app" / "studio" / "config.yaml").read_text(encoding="utf-8").count("render_backend:") == 1

    def test_the_license_page_is_plain_text_of_the_cdrca_license(self, staged):
        raw = (staged / "LICENSE.txt").read_bytes()
        text = raw.decode("utf-8-sig")
        assert raw.startswith(b"\xef\xbb\xbf")                  # the BOM tells Inno Setup it is UTF-8
        assert "Islamic Open Source License" in text and "**" not in text and "```" not in text and "\n#" not in text

    def test_the_version_matches_the_package(self, staged):
        import blaze
        assert (staged / "app" / "VERSION").read_text().strip() == blaze.__version__

    def test_the_staged_app_imports_its_provider_layer_and_finds_its_pieces(self, staged):
        code = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r);"
                "from blaze import ai, launcher; from src.providers.provider_factory import CLOUD_PROVIDERS;"
                "print(ai.STUDIO == __import__('pathlib').Path(%r), CLOUD_PROVIDERS)" % (str(staged / "app"), str(staged / "app" / "studio"), str(staged / "app" / "studio")))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=staged)
        assert r.returncode == 0 and r.stdout.startswith("True ('anthropic', 'gemini', 'openai')"), r.stderr


class TestStageHelpers:
    def test_the_embedded_pythons_search_path_includes_the_app_and_site_packages(self, tmp_path):
        d = tmp_path / "python"
        d.mkdir()
        (d / "python312._pth").write_text("python312.zip\n.\n\n#import site\n")
        (d / "python312.zip").write_bytes(b"")
        lines = stage.write_pth(d).read_text().split("\n")
        assert "python312.zip" in lines and r"Lib\site-packages" in lines and r"..\..\app" in lines and "import site" in lines

    def test_the_runtime_requirements_cover_voices_and_all_three_providers(self):
        reqs = (REPO / "installer" / "runtime-requirements.txt").read_text().lower()
        for name in ("pillow", "pyyaml", "pyttsx3", "anthropic", "openai", "google-genai", "pyqt6", "pydantic"):
            assert name in reqs

    def test_ffmpeg_is_a_gpl_build_and_the_notices_say_so(self):
        assert "gpl" in stage.FFMPEG_URL.lower()
        assert "GPL" in (REPO / "THIRD-PARTY-NOTICES.md").read_text()


class TestInnoScript:
    iss = (REPO / "installer" / "blaze.iss").read_text(encoding="utf-8")

    def test_sections_and_key_settings(self):
        for sec in ("[Setup]", "[Languages]", "[Messages]", "[Tasks]", "[Dirs]", "[Files]", "[Icons]", "[Run]", "[UninstallDelete]"):
            assert sec in self.iss
        assert re.search(r"^AppId=\{\{[0-9A-F]{8}-([0-9A-F]{4}-){3}[0-9A-F]{12}\}$", self.iss, re.M)
        assert "PrivilegesRequired=lowest" in self.iss                      # no admin rights
        assert "WizardStyle=modern" in self.iss and "SolidCompression=yes" in self.iss
        assert "ArchitecturesInstallIn64BitMode=x64compatible" in self.iss

    def test_referenced_assets_exist(self):
        for key in ("SetupIconFile", "WizardImageFile", "WizardSmallImageFile"):
            rel = re.search(rf"^{key}=(.+)$", self.iss, re.M).group(1).strip().replace("\\", "/")
            assert (REPO / "installer" / rel).is_file(), rel

    def test_wizard_images_have_the_sizes_inno_expects(self):
        from PIL import Image
        assert Image.open(REPO / "installer/assets/wizard-large.bmp").size == (164, 314)
        assert Image.open(REPO / "installer/assets/wizard-small.bmp").size == (55, 58)
        ico = Image.open(REPO / "installer/assets/blaze.ico")
        assert ico.info.get("sizes") and (256, 256) in ico.info["sizes"]

    def test_shortcuts_and_files_point_at_things_that_are_staged(self, staged):
        assert 'Source: "{#StageDir}\\*"' in self.iss
        assert r"{app}\runtime\python\pythonw.exe" in self.iss and r'{app}\app\blaze_app.pyw' in self.iss
        assert (staged / "app" / "blaze_app.pyw").is_file() and (staged / "blaze.ico").is_file()
        assert r"{#StageDir}\LICENSE.txt" in self.iss and (staged / "LICENSE.txt").is_file()

    def test_blaze_studio_has_its_own_shortcut(self, staged):
        assert r'Parameters: """{app}\app\studio_app.pyw"""' in self.iss and "{#AppName} Studio" in self.iss
        assert (staged / "app" / "studio_app.pyw").is_file()

    def test_the_persons_own_folders_survive_an_uninstall(self):
        dirs = self.iss.split("[Dirs]")[1].split("[Files]")[0]
        assert dirs.count("uninsneveruninstall") == 2

    def test_the_output_name_matches_what_the_workflow_looks_for(self):
        assert "OutputBaseFilename=Blaze_Setup_{#AppVersion}" in self.iss
        assert "Blaze_Setup_*.exe" in TEXTS["build-blaze-installer.yml"]


class TestWorkflows:
    def test_every_workflow_is_well_formed(self):
        assert set(WORKFLOWS) == {"ci.yml", "build-blaze-installer.yml", "screenshots.yml"}
        for name, wf in WORKFLOWS.items():
            assert wf.get("name") and True in wf and wf.get("jobs"), name           # YAML reads the key `on` as True
            for job_name, job in wf["jobs"].items():
                assert "runs-on" in job or "uses" in job, f"{name}:{job_name}"
                for need in ([job["needs"]] if isinstance(job.get("needs"), str) else job.get("needs", [])):
                    assert need in wf["jobs"], f"{name}:{job_name} needs unknown job {need}"

    def test_actions_are_pinned_to_a_version_and_local_ones_exist(self):
        for name, text in TEXTS.items():
            for ref in re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", text, re.M):
                if ref.startswith("./"):
                    assert (REPO / ref[2:]).is_file(), f"{name}: {ref}"
                else:
                    assert re.search(r"@v?\d", ref), f"{name}: {ref} has no version"

    def test_every_script_a_workflow_runs_exists(self):
        for name, text in TEXTS.items():
            for rel in set(re.findall(r"(?<![\w/.-])((?:installer|tools)[\\/][\w./\\-]+\.(?:py|ps1|js|iss))", text)):
                assert (REPO / rel.replace("\\", "/")).is_file(), f"{name} refers to {rel}"

    def test_the_gallery_collects_the_artifacts_the_other_jobs_upload(self):
        uploaded = set()
        for text in TEXTS.values():
            uploaded |= set(re.findall(r"name:\s*(screens-[\w-]+)", text))
        assert uploaded == {"screens-page", "screens-studio", "screens-installer", "screens-installed-page"}
        from tools.screens import make_gallery  # noqa: F401  (the gallery knows these four folder names)
        for folder in ("page", "studio", "installer", "installed-page"):
            assert folder in make_gallery.SECTIONS

    def test_the_installer_workflow_checks_only_files_that_staging_produces(self, staged):
        text = TEXTS["build-blaze-installer.yml"]
        listed = re.findall(r'"(app\\[^"]+)"', text)
        assert listed
        for rel in listed:
            posix = rel.replace("\\", "/")
            if "node_modules" in posix:
                continue                              # installed by npm at build time
            assert (staged / posix).exists(), f"the workflow expects {rel} but staging does not make it"

    def test_the_installer_is_built_verified_photographed_and_released(self):
        jobs = WORKFLOWS["build-blaze-installer.yml"]["jobs"]
        assert set(jobs) == {"build", "verify", "installer-screens", "publish"}
        assert jobs["verify"]["needs"] == "build" and jobs["publish"]["needs"] == ["build", "verify"]
        assert jobs["installer-screens"].get("continue-on-error") is True           # best effort: it needs a desktop session

    def test_only_a_verified_installer_is_ever_called_blaze_installer(self):
        """A failed run used to leave a downloadable `blaze-installer` (even a hollow one). Now the build uploads
        `blaze-installer-unverified`, and the only upload with the real name sits in the job that needs `verify`."""
        jobs = WORKFLOWS["build-blaze-installer.yml"]["jobs"]
        def uploads(job):
            return [st["with"]["name"] for st in jobs[job]["steps"] if str(st.get("uses", "")).startswith("actions/upload-artifact")
                    and "name" in st.get("with", {})]
        assert "blaze-installer-unverified" in uploads("build") and "blaze-installer" not in uploads("build")
        for job in ("verify", "installer-screens"):
            assert "blaze-installer" not in uploads(job), job
        assert "blaze-installer" in uploads("publish")
        assert "verify" in jobs["publish"]["needs"]

    def test_the_build_refuses_a_hollow_installer(self):
        steps = " ".join(str(st.get("run", "")) for st in WORKFLOWS["build-blaze-installer.yml"]["jobs"]["build"]["steps"])
        assert "check_installer.py --stage" in steps and "check_installer.py --installer" in steps

    def test_ci_runs_on_all_three_systems_and_demands_voices_and_blender(self):
        ci = WORKFLOWS["ci.yml"]["jobs"]
        assert set(ci["blaze"]["strategy"]["matrix"]["os"]) == {"ubuntu-latest", "windows-latest", "macos-latest"}
        assert ci["blaze"]["env"]["BLAZE_REQUIRE_VOICE"] == "1" and ci["blender"]["env"]["BLAZE_REQUIRE_BLENDER"] == "1"


    def test_no_workflow_contains_a_key(self):
        for name, text in TEXTS.items():
            assert not re.search(r"sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}", text), name


class TestNothingNeedsStartingByHand:
    def test_tests_and_screens_run_on_every_push(self):
        for name in ("ci.yml", "screenshots.yml"):
            assert "push" in WORKFLOWS[name][True], name
            assert WORKFLOWS[name].get("concurrency", {}).get("cancel-in-progress") is True      # a newer push replaces an older run

    def test_the_screens_workflow_ends_with_one_report(self):
        jobs = WORKFLOWS["screenshots.yml"]["jobs"]
        assert set(jobs["report"]["needs"]) == {"installer", "page", "studio", "gallery"} and jobs["report"]["if"] == "always()"
        assert "GITHUB_STEP_SUMMARY" in TEXTS["screenshots.yml"]


    def test_the_studio_job_runs_the_windows_real_tests_on_linux(self):
        text = TEXTS["ci.yml"]
        assert "playwright install" in text.split("studio:")[1].split("blender:")[0]


class TestDocsMatchTheWindow:
    def test_no_document_still_calls_the_main_window_a_placeholder(self):
        for md in list(REPO.rglob("*.md")):
            if {"node_modules", "handoff", "cdrca"} & set(md.relative_to(REPO).parts):
                continue
            text = md.read_text(encoding="utf-8", errors="ignore").lower()
            assert "stub implementation" not in text and "currently a placeholder" not in text and "a placeholder today" not in text, md

    def test_the_studio_tutorial_exists_and_is_linked(self):
        assert (REPO / "docs/tutorials/08-blaze-studio.md").is_file()
        assert "08-blaze-studio.md" in (REPO / "README.md").read_text(encoding="utf-8")
        assert "08-blaze-studio.md" in (REPO / "docs/README.md").read_text(encoding="utf-8")
        for img in ("studio-empty.png", "studio-working.png", "studio-result.png"):
            assert (REPO / "docs/img" / img).is_file()


def test_the_studio_screens_job_can_really_run_the_demo():
    steps = " ".join(str(st) for st in WORKFLOWS["screenshots.yml"]["jobs"]["studio"]["steps"])
    for needed in ("setup-node", "ffmpeg", "playwright install", "pillow", "PyQt6"):
        assert needed in steps, needed


class TestWhatGitWillAndWillNotTake:
    """A .gitignore pattern like `screens/` also matches tools/screens/: the push would silently leave source files out."""
    REQUIRED = ["LICENSE.md", "THIRD-PARTY-NOTICES.md", "README.md", "blaze_app.pyw", "studio_app.pyw", "tools/screens/ui_screens.js",
                "tools/screens/make_gallery.py", "tools/screens/studio_screens.py", "tools/check_docs.py", "installer/stage.py",
                "installer/blaze.iss", "installer/assets/blaze.ico", "installer/assets/wizard-large.bmp", "studio/config.yaml",
                "studio/main.py", "studio/src/ui/main_window.py", "studio/pytest.ini", "studio/requirements.txt", "cdrca-lib/atoms.cdrca",
                "cdrca/Back-end/Render/render.js", "examples/the-warehouse.txt", "docs/img/page.png", ".github/workflows/ci.yml",
                ".github/workflows/screenshots.yml", ".github/workflows/build-blaze-installer.yml"]

    def test_no_unanchored_folder_pattern_matches_a_source_folder(self):
        patterns = [l.strip() for l in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
                    if l.strip().endswith("/") and not l.startswith(("#", "/", "*", "!"))]
        harmless = {"__pycache__", ".pytest_cache", "node_modules", "htmlcov", "frames"}
        names = {p.name for p in REPO.rglob("*") if p.is_dir() and not ({"node_modules", ".git", "handoff", "__pycache__"} & set(p.parts))}
        clash = {pat.rstrip("/") for pat in patterns} & names - harmless
        assert not clash, f"these .gitignore patterns also match source folders: {clash}; anchor them with a leading /"

    def test_every_required_file_exists_and_git_would_track_it(self):
        for rel in self.REQUIRED:
            assert (REPO / rel).is_file(), rel
        if not (REPO / ".git").exists() or not shutil.which("git"):
            pytest.skip("not inside a git checkout")
        for rel in self.REQUIRED:
            ignored = subprocess.run(["git", "check-ignore", "-q", rel], cwd=REPO).returncode == 0
            assert not ignored, f"git would ignore {rel}"

    def test_the_example_is_the_one_the_tests_use(self):
        assert (REPO / "examples" / "the-warehouse.txt").read_text(encoding="utf-8") == (REPO / "tests/fixtures/sample_story.txt").read_text(encoding="utf-8")

    def test_things_that_belong_to_the_separate_blazeng_repository_are_not_here(self):
        for rel in ("studio/setup.py", "studio/setup_studio.py", "studio/installer.iss", "studio/AIProductionStudio.spec", "studio/ROADMAP.md",
                    "studio/ARCHITECTURE.md", "studio/CONTRIBUTING.md", "studio/LICENSE", "LICENSE", "tools/live_ai_check.py"):
            assert not (REPO / rel).exists(), rel
        assert not (REPO / "studio" / ".github").exists()

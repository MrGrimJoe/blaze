"""
Checks the AI writer against a REAL provider (this is the one thing that cannot be tested without an account and a key).
Run by .github/workflows/live-ai.yml with a repository secret; it can be run by hand too:

    ANTHROPIC_API_KEY=... python tools/live_ai_check.py --provider anthropic
    GEMINI_API_KEY=...    python tools/live_ai_check.py --provider gemini
    OPENAI_API_KEY=...    python tools/live_ai_check.py --provider openai

It asks for a small story (2 scenes, 3 lines each: a handful of requests), checks every promise the writer makes, and makes
a Draft video from the result. The key is only written to a temporary config.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

KEYS = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}
results = []


def check(name, ok, detail=""):
    results.append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail and not ok else ""), flush=True)
    return bool(ok)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=sorted(KEYS))
    ap.add_argument("--idea", default="two friends find a message in a bottle on a beach")
    ap.add_argument("--out", default="live-ai-results")
    a = ap.parse_args(argv)
    key = os.environ.get(KEYS[a.provider], "").strip()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not key:
        print(f"{KEYS[a.provider]} is not set: nothing to test (add it as a repository secret).")
        (out / "skipped.txt").write_text("no key", encoding="utf-8")
        return 0

    from blaze import ai, art
    from blaze.pipeline import Options, make
    from blaze.screenplay import parse

    cfg = Path(tempfile.mkdtemp()) / "config.yaml"
    cfg.write_text("\n".join([f'text_provider: "{a.provider}"', f'vision_provider: "{a.provider}"', f'{a.provider}_api_key: "{key}"', ""]), encoding="utf-8")
    provider = ai._load_provider(cfg)
    calls = []
    real = provider.generate
    provider.generate = lambda *x, **k: (calls.append(time.time()), real(*x, **k))[1]

    print(f"Writing a 2-scene story with {a.provider}:")
    try:
        text = ai.write_animation(a.idea, scenes=2, lines_per_scene=3, provider=provider, progress=lambda m: print("   ", m))
    except Exception as e:
        check("the writer finished", False, f"{type(e).__name__}: {e}")
        return finish(out)
    (out / "story.txt").write_text(text, encoding="utf-8")
    check("the writer finished", True)
    sp = parse(text)
    check("the result parses with no warnings", not sp.warnings, sp.warnings)
    check("two scenes, as asked", len(sp.scenes) == 2, len(sp.scenes))
    check("2 to 4 characters, each with a look", 2 <= len(sp.cast) <= 4, sp.cast)
    check("every speaker is in the cast", set(sp.characters()) <= set(sp.cast), sp.characters())
    check("every backdrop is a valid generator spec", all(art.parse_generator(s.backdrop) for s in sp.scenes))
    check("at least 2 spoken lines per scene", all(sum(1 for b in s.beats if b.kind == "say") >= 2 for s in sp.scenes))
    check("it used no more requests than expected (3, plus retries)", len(calls) <= 3 * 3, f"{len(calls)} requests")
    print(f"  ({len(calls)} requests made)")

    print("Making a Draft video from it:")
    try:
        res = make(text, out / "story.mp4", Options(width=640, height=360, fps=8, voice="off", progress=lambda m: None))
        check("a video was made from the AI's screenplay", res.video.exists() and res.video.stat().st_size > 10_000, res.video)
    except Exception as e:
        check("a video was made from the AI's screenplay", False, f"{type(e).__name__}: {e}")
    return finish(out)


def finish(out: Path) -> int:
    ok = all(r["ok"] for r in results)
    (out / "results.json").write_text(json.dumps({"ok": ok, "results": results}, indent=2), encoding="utf-8")
    print("\nALL CHECKS PASSED" if ok else "\nFAILED: " + str([r["check"] for r in results if not r["ok"]]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

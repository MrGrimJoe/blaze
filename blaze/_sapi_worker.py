"""One line of speech from the operating system's own voice, in a process of its own.

    python _sapi_worker.py request.json result.json

voice.py runs this with a time limit instead of calling pyttsx3 itself. On the Windows CI runner pyttsx3's runAndWait() never
returned (its SAPI loop sleeps for ever waiting for an event that does not come), and a call that never returns cannot be
stopped inside the process that made it. In a process of its own it can be: a stuck voice is an error after the limit, and
every line starts with a clean COM state and the main thread, which is where SAPI behaves.

On Windows the voice is driven directly through SAPI and spoken synchronously (no event loop to wait on). Anywhere else, or if
that fails, pyttsx3 does it (macOS NSSpeech, or espeak on Linux).

request:  {"text", "wav", "voice" (an id or part of a name, or ""), "female" (bool), "seed" (int), "rate" (words per minute)}
result:   {"voices": <how many the system has>, "engine": "sapi" | "pyttsx3"}  or  {"error": "..."}
This file imports nothing from Blaze: it must run on its own.
"""
import json
import math
import sys


def _pick(voices, want, female, seed):
    """voices: [(id, name)]. The voice the request asks for, or one chosen from the character's gender and seed."""
    if want:
        for vid, _ in voices:
            if vid == want:
                return vid
        hits = [vid for vid, name in voices if want.lower() in (name or "").lower()]
        if len(hits) == 1:
            return hits[0]
        raise ValueError(f"voice {want!r} " + ("matches several voices" if hits else "was not found"))
    wanted = [vid for vid, name in voices if (("female" in (name or "").lower() or "zira" in (name or "").lower()) == female)]
    pool = wanted or [vid for vid, _ in voices]
    return pool[seed % len(pool)] if pool else None


def _sapi(req):
    import win32com.client                                   # pywin32, which pyttsx3 needs on Windows anyway
    spv = win32com.client.Dispatch("SAPI.SpVoice")
    tokens = spv.GetVoices()
    items = [tokens.Item(i) for i in range(tokens.Count)]
    voices = [(t.Id, t.GetDescription()) for t in items]
    chosen = _pick(voices, req.get("voice") or "", bool(req.get("female")), int(req.get("seed") or 0))
    if chosen is not None:
        spv.Voice = items[[v[0] for v in voices].index(chosen)]
    rate = int(req.get("rate") or 150)
    spv.Rate = max(-10, min(10, int(math.log(max(rate, 1) / 200.0, 1.1))))     # the same mapping pyttsx3 uses
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Open(req["wav"], 3)                               # SSFMCreateForWrite
    try:
        spv.AudioOutputStream = stream
        spv.Speak(req["text"], 0)                            # 0: synchronous, it returns when the speech is written
    finally:
        stream.Close()
    return {"voices": len(voices), "engine": "sapi"}


def _pyttsx3(req):
    import pyttsx3
    engine = pyttsx3.init()
    found = engine.getProperty("voices") or []
    voices = [(v.id, v.name or "") for v in found]
    chosen = _pick(voices, req.get("voice") or "", bool(req.get("female")), int(req.get("seed") or 0))
    if chosen is not None:
        engine.setProperty("voice", chosen)
    engine.setProperty("rate", int(req.get("rate") or 150))
    engine.save_to_file(req["text"], req["wav"])
    engine.runAndWait()
    engine.stop()
    return {"voices": len(voices), "engine": "pyttsx3"}


def main(argv):
    req = json.loads(open(argv[1], encoding="utf-8").read())
    try:
        if sys.platform == "win32":
            try:
                result = _sapi(req)
            except Exception as e:                           # no pywin32, no COM: pyttsx3 may still manage
                result = _pyttsx3(req)
                result["sapi_error"] = repr(e)
        else:
            result = _pyttsx3(req)
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    with open(argv[2], "w", encoding="utf-8") as f:
        json.dump(result, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

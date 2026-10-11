# Tutorial 5: Writing with AI

Blaze works fully without AI. This is for when you would rather describe a story in a sentence and have an AI write the
screenplay. **The AI only writes text.** It never draws a frame, and everything it writes is checked before anything is made.

## What you need

An account with **one** AI provider and an API key from them. Blaze has no default and no key of its own; you choose.

| Provider | Where you create a key |
|---|---|
| Anthropic | console.anthropic.com |
| Google Gemini | ai.google.dev/gemini-api/docs/api-key |
| OpenAI | platform.openai.com |

Providers decide their own prices, free allowances and limits, and change them. Check yours before you start; Blaze cannot
know them. The number that matters for planning is how many **requests** a story uses (below).

## Choose your provider

**In the page** (`python blaze.py ui`): above the screenplay, the *Write with AI* row shows a provider menu and a key field.
Pick one, paste the key, press **Save**. The row then turns into a box where you describe the story.

**By hand:** open `studio/config.yaml` and fill in three lines and a key, for example for OpenAI:

```yaml
text_provider: "openai"
vision_provider: "openai"
image_provider: "openai"
openai_api_key: "sk-..."
```

`text_provider` is the one Blaze's AI writer uses. Choose `anthropic`, `gemini` or `openai`. (The other two lines are for
the desktop studio, see [studio](../studio.md); Anthropic cannot make images, so for it leave `image_provider` empty.)

**Your key stays on your computer.** It is saved in `studio/config.yaml`, which ships with every key empty. Do not commit
that file to a public repository after adding a key. The text you ask the AI to write about is sent to the provider you
chose, as with any AI service; your screenplays and videos are not.

To change provider later, press **Change provider** in the page or edit the file.

## Two ways to write

| Mode | Requests | Good for |
|---|---|---|
| **Short scene** | 1 | a quick scene, trying an idea, staying inside a small allowance |
| **Whole story** | 1 plan + 1 per scene (about 5 for 4 scenes) | a story with a beginning, middle and end and consistent characters |

If an answer fails a check, Blaze asks again (up to 3 tries per step), which uses extra requests. A run that goes smoothly
uses exactly the numbers above.

In the page choose the mode next to the *Write it* button. From the command line:

```
python blaze.py ai "two friends find a message in a bottle"                  # whole story: 4 scenes
python blaze.py ai "two friends find a message in a bottle" --scenes 3 --lines 6
python blaze.py ai "a robot learns to bake" --quick                          # one request
python blaze.py ai "ordering coffee" --level A2 --voice espeak --wpm 105     # simple English for learners
```

`blaze ai` writes the screenplay next to the video (`two_friends_find_a.txt`), then makes the video. Because the screenplay
is saved, you can edit it and run `blaze make` again as often as you like without using the AI again. In the page, the
text appears in the editor for you to read and change before pressing **Make video**.

You will see progress as it works:

```
  Planning the story...
  Writing scene 1 of 4...
  Writing scene 2 of 4...
```

## How a whole story is made, and why it stays consistent

1. **The plan.** The AI is asked for a title, 2 to 4 characters with exact looks (`CAST:` lines), and one line per scene:
   `place | mood | what happens`. The plan is checked: looks must be valid (`gender=f hat=cap ...`), places and moods must be
   real names, and the number of scenes must be exactly what you asked for.
2. **Each scene on its own.** For scene 3 the AI is shown the whole plan, scenes 1 and 2 as already written, and the
   fixed cast, and asked for scene 3 only.
3. **The program, not the AI, keeps things fixed.** The cast lines come from the plan and are never rewritten. Each
   scene's backdrop is set from the plan even if the AI wrote a different one. Only cast members may speak or move.
4. **Every step is checked** with the same parser that reads your own screenplays: at least two spoken lines, exact numbers
   where numbers belong, no strangers in the scene. A complaint is sent back to the AI to fix.
5. **A scene that never passes stops the run** with a message that names it. Nothing unchecked is ever turned into a video.

Messages you might see:

```
No text_provider chosen. Open the model setup window and pick a provider (anthropic, gemini, openai), or set text_provider in config.yaml. (Blaze: run `python blaze.py ui` and pick Anthropic, Gemini or OpenAI under Write with AI.)
The scene 2 could not be written after 3 tries. Last problem: Tim is not in the cast (Ana, Leo); only cast members may appear
The plan could not be written after 3 tries. Last problem: there must be exactly 4 scenes, there are 3
```

If a provider says a model was not found, the model names in `studio/config.yaml` (`gemini_model`, `openai_model`,
`anthropic_model`) are out of date: use a current name from your provider's model list.

## Tips for good results

- Give characters and a situation, not a plot summary: *"a shy baker and a customer who keeps changing her order"*.
- Set `--level A1`, `A2`... for simple vocabulary if you are making language-learning videos.
- Read and edit the screenplay before making the video. Fixing a line costs nothing; the AI is a first draft.
- Prefer **Whole story** for anything longer than one scene: it plans the arc and the cast first, then writes each scene.
- Characters look the way the plan's `CAST:` lines say. If you dislike a look, change that line once and it applies to
  every scene.

## What has and has not been tested

The writer is tested thoroughly with scripted stand-ins for the AI (plan parsing, retries, the rule that scenes cannot
change the cast or the backdrops, refusal to ship an unchecked scene). It has **not** been run against a live provider yet,
so the very first real story may reveal wording to tune in the instructions sent to the AI. Anything it writes is plain
text you can fix by hand.

Local models (`ollama`, `huggingface`) are supported by the studio's provider layer and can be set in `studio/config.yaml`,
but they need a capable computer and are not offered in the page.

Next: [editing the generated CDRCA scripts](06-editing-the-cdrca-scripts.md).

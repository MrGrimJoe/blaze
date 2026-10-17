# Blaze screens

Run 11 of commit 0d6f869 on main. Look at each screen; the line under it says what to check.

**29 screens captured.**

Contents: [The Blaze page](#the-blaze-page), [The desktop studio's windows](#the-desktop-studios-windows)

## The Blaze page

Every state of the page, captured with a real browser against the running app.

### Fresh page
![Fresh page](page/01-empty.png)

### Example loaded
![Example loaded](page/02-example.png)

### A mistake
![A mistake](page/03-error.png)

### A warning
![A warning](page/04-warning.png)

### Format help open
![Format help open](page/05-format-help.png)

### Choosing an AI provider
![Choosing an AI provider](page/06-ai-choose.png)

### AI ready
![AI ready](page/07-ai-ready.png)

### Making a video
![Making a video](page/08-making.png)

### Finished video
![Finished video](page/09-done.png)

### Dark theme
![Dark theme](page/10-dark.png)

### Phone width
![Phone width](page/11-phone.png)

### Tablet width
![Tablet width](page/12-tablet.png)

### A misspelt name or command
![A misspelt name or command](page/13-names.png)

### A voice for each character
![A voice for each character](page/14-voices.png)

### Text looks and per-character speed
![Text looks and per-character speed](page/15-looks.png)

### Your own character
![Your own character](page/16-library.png)

### Editor mode
![Editor mode](page/17-editor.png)

### Running mode
![Running mode](page/18-running.png)

## The desktop studio's windows

The first-run provider window in each state, and the main window.

### First run: nothing chosen
![First run: nothing chosen](studio/01-first-run-empty.png)

**What to check:** No provider is preselected. Save is disabled. The wording says the key stays on this computer.

### Anthropic chosen
![Anthropic chosen](studio/02-anthropic-chosen.png)

**What to check:** A note says Anthropic cannot make images. The image menu offers only Gemini and OpenAI. Save is disabled.

### Anthropic with a key, no image source yet
![Anthropic with a key, no image source yet](studio/03-anthropic-key-typed.png)

**What to check:** The key shows as dots. Save is still disabled until an image provider is chosen.

### Anthropic for text, OpenAI for images
![Anthropic for text, OpenAI for images](studio/04-anthropic-ready.png)

**What to check:** A second key field appears for the image provider. Save is enabled.

### Gemini for everything
![Gemini for everything](studio/05-gemini-ready.png)

**What to check:** Images default to the same provider, no second key field, Save is enabled.

### Main window: nothing chosen yet
![Main window: nothing chosen yet](studio/07-main-empty.png)

**What to check:** Calm and empty. The provider chip says Choose an AI provider; Make video is greyed out; the hint explains the offline demo.

### Main window: a story written, a provider chosen
![Main window: a story written, a provider chosen](studio/08-main-ready.png)

**What to check:** The chip shows both providers. Make video is dark and enabled. The hint explains what will happen.

### Main window: working
![Main window: working](studio/09-main-working.png)

**What to check:** A heading says what is happening, a thin progress line grows, each shot shows its own state with a coloured dot, and Cancel is available.

### Main window: something went wrong
![Main window: something went wrong](studio/10-main-error.png)

**What to check:** A plain sentence says what failed (in red), and a button takes you back to your story, which is kept.

### Main window: the finished offline demo
![Main window: the finished offline demo](studio/11-main-result.png)

**What to check:** A still from the video, its length and size, and Play, Show in folder and Save a copy. This one was made for real by the offline demo.

### Main window: dark theme
![Main window: dark theme](studio/12-main-dark.png)

**What to check:** The same window in dark: readable text, the accent colour lifted, nothing washed out.

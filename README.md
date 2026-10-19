# Blaze screens

Run 25 of commit 125cd25 on main. Look at each screen; the line under it says what to check.

**56 screens captured.**

Contents: [The Windows installer](#the-windows-installer), [The installed app's page (Windows, real Chrome)](#the-installed-apps-page-windows-real-chrome), [The Blaze page](#the-blaze-page), [The desktop studio's windows](#the-desktop-studios-windows)

## The Windows installer

Each wizard page of the real installer, captured while it ran.

### Welcome
![Welcome](installer/01-welcome.png)

**What to check:** The dark Blaze picture on the left, the welcome text mentions it works offline and that everything is included.

### License
![License](installer/02-license.png)

**What to check:** The license text (the Islamic Open Source License) reads as plain text with no stray marks. Next is disabled until you accept.

### License accepted
![License accepted](installer/03-license-accepted.png)

**What to check:** I accept the agreement is selected and Next is enabled.

### Choose where to install
![Choose where to install](installer/04-destination.png)

**What to check:** A folder is suggested; the disk space needed is shown. No admin prompt appeared.

### Additional tasks
![Additional tasks](installer/05-tasks.png)

**What to check:** Create a desktop shortcut is offered.

### Ready to install
![Ready to install](installer/06-ready.png)

**What to check:** A summary of the choices; Install is the default button.

### Installing
![Installing](installer/07-installing.png)

**What to check:** A progress bar moves; the small Blaze picture is at the top right.

### Finished
![Finished](installer/08-finished.png)

**What to check:** Blaze is ready; Launch Blaze is ticked; the text says where videos are saved.

### After Finish: the app starts
![After Finish: the app starts](installer/09-app-started.png)

**What to check:** Blaze opens in your browser (a window or tab may be in front of this screen).

## The installed app's page (Windows, real Chrome)

The page served by the installed app, with the bundled Python, Node, ffmpeg and browser.

### Fresh page
![Fresh page](installed-page/01-empty.png)

### Example loaded
![Example loaded](installed-page/02-example.png)

### A mistake
![A mistake](installed-page/03-error.png)

### A warning
![A warning](installed-page/04-warning.png)

### Format help open
![Format help open](installed-page/05-format-help.png)

### Choosing an AI provider
![Choosing an AI provider](installed-page/06-ai-choose.png)

### AI ready
![AI ready](installed-page/07-ai-ready.png)

### Making a video
![Making a video](installed-page/08-making.png)

### Finished video
![Finished video](installed-page/09-done.png)

### Dark theme
![Dark theme](installed-page/10-dark.png)

### Phone width
![Phone width](installed-page/11-phone.png)

### Tablet width
![Tablet width](installed-page/12-tablet.png)

### A misspelt name or command
![A misspelt name or command](installed-page/13-names.png)

### A voice for each character
![A voice for each character](installed-page/14-voices.png)

### Text looks and per-character speed
![Text looks and per-character speed](installed-page/15-looks.png)

### Your own character
![Your own character](installed-page/16-library.png)

### Editor mode
![Editor mode](installed-page/17-editor.png)

### Running mode
![Running mode](installed-page/18-running.png)

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

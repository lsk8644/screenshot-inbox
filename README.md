# Screenshot Inbox

Screenshot Inbox is a local-first Windows utility. It watches the folder where Windows saves screenshots, waits for each file to finish writing, deduplicates it by content, analyzes it through a configurable vision provider, and displays the result in a persistent browser timeline.

Analysis titles, summaries, explanations, and recommendations are requested in Korean. Programming exercises are classified as code and include runnable Python, Java, and C++ solutions behind language tabs, plus an approach, explanation, and complexity when the screenshot is readable. Contest markers such as Codeforces, time limits, and Input/Output sections trigger a code-only repair request when the first response is misclassified or omits a language. Error dialogs, exceptions, stack traces, and failed-operation screens are classified as errors with likely causes and recommended steps. The Error filter also includes screenshots whose AI analysis failed so recovery problems are not hidden.

Educational screenshots do more than repeat visible text: acronyms and named frameworks are expanded, each component is defined in plain Korean, and practical examples are requested. For example, a 3V/5V screenshot explains Volume, Velocity, Variety, Veracity, Value, and the relationship between 3V and 5V.

The original screenshot is never moved, deleted, or stored inside the database. Metadata and analysis results stay in local SQLite storage.

## Requirements

- Windows 10 or 11
- Python 3.13
- A browser
- Optional: an API key and a vision-capable OpenAI-compatible model

## Installation

Open PowerShell in the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

## Environment variables

Edit `.env` as needed. Do not commit this file.

| Variable | Purpose | Default |
| --- | --- | --- |
| `SCREENSHOT_DIR` | Explicit folder to watch | auto-detected |
| `DATA_DIR` | SQLite storage directory | `./data` |
| `AI_PROVIDER` | `mock`, `openai`, or `openai-compatible` | `mock` |
| `AI_API_KEY` | Provider credential | empty |
| `AI_BASE_URL` | OpenAI-compatible API base URL ending in `/v1` | OpenAI API |
| `AI_MODEL` | Vision-capable model name | empty |
| `AI_TIMEOUT_SECONDS` | Per-request timeout | `60` |
| `MAX_ANALYSIS_ATTEMPTS` | Maximum transient attempts | `3` |
| `FILE_STABLE_INTERVAL_SECONDS` | Delay between file-size checks | `0.5` |
| `FILE_STABLE_CHECKS` | Identical checks required | `3` |
| `HOST` / `PORT` | Local web bind address | `127.0.0.1:8765` |

## How to run

```powershell
screenshot-inbox
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Keep the PowerShell window open. New PNG, JPG, JPEG, and WEBP screenshots appear automatically. The console logs `WATCH`, `NEW`, `QUEUE`, `ANALYZING`, `DONE`, `RETRY`, and `FAILED` events without logging credentials.

The Inbox groups screenshots under `M.DD` headers using Asia/Seoul time and shows each event in 24-hour `HH:MM` format. Newer dates and screenshots appear first. Source filenames and filesystem paths remain hidden from the Inbox and detail UI. Individual trash buttons and the select-all bulk action remove only Inbox metadata, analysis, and local conversations; original screenshot files remain untouched. Dismissed content hashes are retained locally so startup recovery does not restore deleted Inbox entries.

While an Inbox page is open, analysis status is polled locally every 1.5 seconds. Status memory survives navigation and automatic detail refreshes within the tab. A newly completed analysis appears as a clickable notification in the lower-right corner for six seconds; existing completed records do not trigger notifications on the first visit. When the Inbox timeline is visible, new screenshots and status changes refresh the timeline in place without a full-page reload.

The in-page notification cannot be blocked by browser notification settings. Analysis completion also triggers a native Windows notification directly from the background app, even when no browser is open. Clicking it opens the matching screenshot detail page. Completion detection compares both status and `analyzed_at`, so fast reanalysis that finishes between polls is still detected.

Native notifications require the Windows master notification switch under **Settings > System > Notifications** to be enabled. The launcher installs a per-user Start Menu shortcut carrying the `ScreenshotInbox.Local` AppUserModelID, and the notifier uses the same identity so Windows attributes completion notifications to **Screenshot Inbox**, not PowerShell.

Each detail page includes a screenshot-aware chat. A question sends the screenshot and recent conversation to the configured AI provider, receives a Korean response, and stores the conversation in local SQLite. Deleting the Inbox record also removes that local conversation.

In the question box, press **Enter** to send immediately and **Shift+Enter** for a new line. AI Markdown responses are rendered locally with safe headings, lists, emphasis, inline code, and fenced code blocks; raw HTML is escaped.

You can also run:

```powershell
python -m screenshot_inbox.main
```

### Desktop shortcut

`launch_screenshot_inbox.ps1` checks the local health endpoint, starts Screenshot Inbox in the background when needed, waits until it is ready, and opens the Inbox in a standalone Edge or Chrome app window without browser tabs or an address bar. It falls back to the default browser only when neither app-capable browser is installed. A Windows shortcut can target PowerShell with this script so the app is available from a single desktop icon.

The launcher also runs `register_notification_app.ps1`, which installs the current-user Start Menu shortcut required for a dedicated Windows toast identity. No administrator access or remote runtime is required.

The same registration installs `Screenshot Inbox Background.lnk` in the current user's Startup folder. At Windows sign-in it launches `start_screenshot_inbox_background.ps1`, which starts only the hidden watcher and does not open a browser window. The normal Screenshot Inbox icon still opens the result window.

The app stores a local watcher checkpoint. After the first checkpoint has been created, later starts scan only files created or changed since the previous start, recovering screenshots captured while the watcher was stopped without analyzing the entire historical folder.

## Screenshot directory detection

At startup, the app uses the first existing folder in this order:

1. `%USERPROFILE%\Pictures\Screenshots`
2. `%USERPROFILE%\Pictures\스크린샷`
3. `%USERPROFILE%\OneDrive\Pictures\Screenshots`
4. `%USERPROFILE%\OneDrive\Pictures\스크린샷`
5. `%USERPROFILE%\OneDrive\사진\Screenshots`
6. `%USERPROFILE%\OneDrive\사진\스크린샷`

If none is found, set `SCREENSHOT_DIR` to an existing directory. The UI and database still run when the directory is unavailable.

## Provider configuration

### Mock mode

Mock mode requires no network or key and is useful for verifying the watcher, database, retry UI, and timeline:

```dotenv
AI_PROVIDER=mock
```

It reads image dimensions and derives a sample category only when the filename includes `error`, `problem`, `lecture`, `notice`, `code`, or `document`. It does not inspect screen content semantically.

### OpenAI-compatible provider

```dotenv
AI_PROVIDER=openai-compatible
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=your-vision-capable-model
```

For NVIDIA Build or another OpenAI-compatible service, use that service's documented `/v1` base URL and a model that accepts image input. No endpoint or model name is hard-coded. Credentials are sent in the `Authorization` header and are not written to SQLite or logs.

## Data and privacy

- SQLite is stored at `data/screenshot_inbox.db` unless `DATA_DIR` changes it.
- The database contains file paths, hashes, states, extracted text, structured analysis, timestamps, and provider/model metadata.
- Image bytes remain only in their original Windows files.
- Screenshots are not moved or deleted.
- API keys come from `.env` or the OS environment and are excluded by `.gitignore`.
- A configured remote AI provider receives the screenshot image. Mock mode makes no remote request.

## Verification commands

```powershell
python -m pytest
python -m ruff check .
python -m mypy
```

Tests use temporary folders, temporary SQLite databases, and fake providers. They never call an external AI API.

## Troubleshooting

### Wrong or missing screenshot directory

Set an existing absolute path in `.env`:

```dotenv
SCREENSHOT_DIR=C:\Users\YourName\Pictures\Screenshots
```

Restart the app and check the `[WATCH]` console line. Filesystem paths are intentionally hidden from the Inbox UI.

### HTTP 429

The provider rate-limited the request. The app retries with exponential backoff up to `MAX_ANALYSIS_ATTEMPTS`, then leaves the item as failed. Wait for the provider quota to recover and choose **Retry analysis** on the detail page.

### HTTP 503, 502, 500, or timeout

These are treated as transient errors and retried finitely. If failures continue, check provider status, `AI_BASE_URL`, network access, and model availability before retrying from the detail page.

### Model does not support images

Choose a vision-capable model and set its exact provider model name in `AI_MODEL`. A rejected image request becomes a failed item; the original screenshot remains untouched.

### Provider unavailable or missing settings

The watcher, database, and UI continue running. Fix `.env`, restart, then retry failed items. Use `AI_PROVIDER=mock` to verify the local pipeline without credentials.

### Database locked

Short-lived locks are retried automatically. Avoid opening the database with a tool that holds a write transaction. Restart Screenshot Inbox if a separate program abandoned a persistent lock.

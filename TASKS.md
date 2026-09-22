# Screenshot Inbox Tasks

Statuses: `TODO`, `READY`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

## Dependency graph and waves

```text
E0 audit
  -> E1 config -----> E2 watcher -----> E3 queue/status
       |                  |                   |
       +----> E3 DB ------+                   +----> E5 pipeline/reliability
       |                                      ^
       +----> E4 provider/schema --------------+
                                              |
E3 DB + E5 pipeline -----------------------> E6 web UI
E1..E6 ------------------------------------> E7/E8 verification and docs
```

## Wave 0 — Foundation

### T-001
- **Epic:** E0 — Repository Audit
- **Title:** Audit the repository and runtime
- **Goal:** Record structure, existing functionality, tools, configuration, secrets posture, and constraints before code changes.
- **Dependencies:** None
- **Files:** `AUDIT.md`
- **Acceptance Criteria:** Findings are evidence-based and identify the project as empty or existing.
- **Status:** DONE

### T-002
- **Epic:** E0 — Repository Audit
- **Title:** Define architecture and task graph
- **Goal:** Capture bounded decisions, dependencies, waves, and acceptance checks.
- **Dependencies:** T-001
- **Files:** `DECISIONS.md`, `TASKS.md`
- **Acceptance Criteria:** Every MVP epic has small tasks and explicit dependencies.
- **Status:** DONE

## Wave 1 — Configuration, storage, watcher

### T-101
- **Epic:** E1 — Configuration & Local Storage
- **Title:** Add environment-driven configuration
- **Goal:** Load safe defaults, `.env`, screenshot-directory override, provider settings, retry settings, and data paths.
- **Dependencies:** T-002
- **Files:** `config.py`, `.env.example`, `.gitignore`
- **Acceptance Criteria:** Keys are never persisted; Windows candidates are detected; an override is supported.
- **Status:** DONE

### T-102
- **Epic:** E3 — Database & Queue
- **Title:** Create SQLite schema and repository methods
- **Goal:** Persist screenshot metadata and the complete status lifecycle.
- **Dependencies:** T-002
- **Files:** `database.py`
- **Acceptance Criteria:** Schema is idempotent; hash is unique; records survive reconnection; locked writes are retried finitely.
- **Status:** DONE

### T-103
- **Epic:** E2 — Screenshot Watcher
- **Title:** Implement stable-file detection and observer events
- **Goal:** Accept supported create/move events only after writes settle.
- **Dependencies:** T-101
- **Files:** `watcher.py`
- **Acceptance Criteria:** PNG/JPG/JPEG/WEBP work; missing/deleted/unstable files are handled without crashing.
- **Status:** DONE

## Wave 2 — Deduplication and queue

### T-201
- **Epic:** E3 — Database & Queue
- **Title:** Add hashing, registration, and bounded worker queue
- **Goal:** Register each unique image once and process it asynchronously.
- **Dependencies:** T-102, T-103
- **Files:** `pipeline.py`, `database.py`
- **Acceptance Criteria:** Duplicate content makes no second analysis job; pending/analyzing/completed/failed transitions are durable.
- **Status:** DONE

## Wave 3 — Provider and schemas

### T-301
- **Epic:** E4 — AI Provider
- **Title:** Define structured analysis models
- **Goal:** Validate common and category-specific output with uncertainty-safe defaults.
- **Dependencies:** T-002
- **Files:** `schemas.py`
- **Acceptance Criteria:** Seven categories normalize; malformed output returns a controlled error.
- **Status:** DONE

### T-302
- **Epic:** E4 — AI Provider
- **Title:** Implement provider interface and providers
- **Goal:** Support OpenAI-compatible vision and an offline deterministic mock.
- **Dependencies:** T-101, T-301
- **Files:** `providers/base.py`, `providers/openai_compatible.py`, `providers/mock.py`, `analyzer.py`
- **Acceptance Criteria:** Endpoint/model are configurable; API errors are typed; secrets never enter logs.
- **Status:** DONE

## Wave 4 — Classification and reliability

### T-401
- **Epic:** E5 — Classification Pipeline
- **Title:** Complete analysis lifecycle and retry policy
- **Goal:** Analyze queued screenshots, retry transient failures with exponential backoff, and persist outcomes.
- **Dependencies:** T-201, T-302
- **Files:** `pipeline.py`
- **Acceptance Criteria:** 429/500/502/503/timeouts retry up to the configured limit; permanent failures remain retryable from UI.
- **Status:** DONE

## Wave 5 — Local web UI

### T-501
- **Epic:** E6 — Local Web UI
- **Title:** Build FastAPI routes and local image serving
- **Goal:** Provide inbox, detail, health, filtering, and retry endpoints without exposing arbitrary files.
- **Dependencies:** T-102, T-401
- **Files:** `web.py`, `main.py`
- **Acceptance Criteria:** Only registered image IDs are served; retry is POST; directory failures remain visible.
- **Status:** DONE

### T-502
- **Epic:** E6 — Local Web UI
- **Title:** Build inbox and detail templates
- **Goal:** Deliver the dense timeline and side-by-side analysis experience.
- **Dependencies:** T-501
- **Files:** `templates/`, `static/`
- **Acceptance Criteria:** Newest first; filters work; status/error/empty states are clear; mobile layout is usable.
- **Status:** DONE

## Wave 6 — Verification and handoff

### T-601
- **Epic:** E7 — Reliability
- **Title:** Add unit and integration tests
- **Goal:** Cover path detection, file stability, hashing, duplicates, DB updates, parsing, provider errors, retry limits, and web views.
- **Dependencies:** T-401, T-502
- **Files:** `tests/`
- **Acceptance Criteria:** No test calls an external AI API; temporary directories and databases are used.
- **Status:** DONE

### T-602
- **Epic:** E8 — Tests & Documentation
- **Title:** Add packaging, lint/type checks, and README
- **Goal:** Make installation, launch, configuration, privacy behavior, and troubleshooting reproducible.
- **Dependencies:** T-601
- **Files:** `pyproject.toml`, `README.md`, `AGENTS.md`
- **Acceptance Criteria:** Test, lint, type-check, and local run commands are documented and executed when available.
- **Status:** DONE

### T-603
- **Epic:** E8 — Tests & Documentation
- **Title:** Run acceptance verification
- **Goal:** Exercise watcher, dedupe, persistence, simulated transient failure, inbox, detail, and secret scan.
- **Dependencies:** T-601, T-602
- **Files:** `TASKS.md`
- **Acceptance Criteria:** Actual results are recorded; unverified items are labeled accurately.
- **Status:** DONE

## Verification record

- Unit/integration suite: 36 passed; two upstream TestClient deprecation warnings.
- Ruff lint: passed.
- Mypy strict type check: passed for 13 source files.
- Python bytecode compilation: passed.
- Live watcher check: a PNG written to a temporary watched directory emitted `NEW`, `QUEUE`, `ANALYZING`, and `DONE` and persisted as `problem`.
- Live web check: health, Inbox, and detail routes returned HTTP 200; the Inbox contained the new item and the detail referenced the registered image endpoint.
- Duplicate, persistence, malformed JSON, category normalization, and simulated 503 retry limit: covered by automated tests.
- Credential scan: no credential-like value found after replacing the README example with an empty key.
- Live Gemini vision calls were performed with the user's configured credential and screenshots after explicit approval; credentials were never printed or added to logs/tests.
- Korean/code-output contract, visible-error fallback, completed-item reanalysis, and Seoul `M.DD`/`HH:MM` conversion: covered by automated tests.
- Error recovery filtering, original-preserving record deletion, local chat persistence, provider chat payloads, and Python/Java/C++ tabs: covered by automated tests.
- Educational term expansion and normalized concept explanations: covered by automated tests.
- Safe chat Markdown rendering and removal of redundant chat helper text: covered by automated tests.
- Mapping-shaped explanation recovery, long-text wrapping, and completion-status notification API: covered by automated tests.
- Paired term-definition rendering, session-persistent completion tracking, and live timeline refresh triggers: covered by automated tests.

## Runtime follow-up

### T-701
- **Epic:** E7 — Reliability
- **Title:** Harden NVIDIA-compatible structured output
- **Goal:** Prevent the 11B vision model from returning truncated or non-JSON analysis output.
- **Dependencies:** T-302, T-401
- **Files:** `providers/openai_compatible.py`, `tests/test_provider.py`
- **Acceptance Criteria:** Provider requests compact JSON with a sufficient output budget and the behavior is covered without an external API call.
- **Status:** DONE

### T-702
- **Epic:** E4/E6 — Korean coding solutions
- **Title:** Generate Korean explanations and complete code solutions
- **Goal:** Answer in Korean, classify programming exercises as code, provide runnable solution code and complexity, and retain backend reanalysis for controlled refreshes.
- **Dependencies:** T-301, T-302, T-501, T-502
- **Files:** `providers/openai_compatible.py`, `schemas.py`, `database.py`, `templates/detail.html`, `static/app.css`, tests
- **Acceptance Criteria:** Provider requests Korean output and code solutions; error text is not left as `other`; code fields normalize and render as code; completed items can be queued internally without exposing the removed completed-item button.
- **Status:** DONE

### T-703
- **Epic:** E6 — Seoul timeline grouping
- **Title:** Group the timeline by Seoul calendar date
- **Goal:** Show newest local dates first with `M.DD` headers and 24-hour times, separated whenever the local day changes.
- **Dependencies:** T-501, T-502
- **Files:** `web.py`, `templates/index.html`, `static/app.css`, tests
- **Acceptance Criteria:** UTC database timestamps convert through `Asia/Seoul`; `9.21`/`9.22` boundaries render as distinct groups; times use `HH:MM`.
- **Status:** DONE

### T-704
- **Epic:** E4/E6 — Inbox actions and screenshot chat
- **Title:** Add safe deletion, recovery filtering, chat, and language-switched solutions
- **Goal:** Surface failed analyses under Error, remove Inbox records without touching originals, continue screenshot-grounded AI conversations, and show Python/Java/C++ solution tabs.
- **Dependencies:** T-302, T-401, T-501, T-502
- **Files:** `database.py`, providers, `web.py`, templates, static assets, tests, documentation
- **Acceptance Criteria:** Failed records appear in Error; trash cascades only SQLite metadata/chat; chat sends bounded history and the screenshot on explicit submit; code tabs switch locally; automated tests use fake providers only.
- **Status:** DONE

### T-705
- **Epic:** E4 — Educational depth
- **Title:** Expand acronyms and framework concepts
- **Goal:** Make lecture/article analysis define key terms, explain component relationships, and provide practical examples instead of only summarizing visible text.
- **Dependencies:** T-301, T-302
- **Files:** `providers/openai_compatible.py`, `schemas.py`, `templates/detail.html`, tests, documentation
- **Acceptance Criteria:** Lecture output contains normalized term explanations; 3V/5V explicitly covers all five V concepts and their relationship; tests remain external-API-free.
- **Status:** DONE

### T-706
- **Epic:** E6 — Chat ergonomics
- **Title:** Add Enter submission and safe Markdown rendering
- **Goal:** Remove redundant empty-state prompts, submit chat with Enter while preserving Shift+Enter and Korean IME behavior, and render common AI Markdown without allowing raw HTML.
- **Dependencies:** T-704
- **Files:** `web.py`, `templates/detail.html`, `static/app.js`, `static/app.css`, tests, documentation
- **Acceptance Criteria:** Empty helper and placeholder text are absent; Enter submits; Shift+Enter remains multiline; Markdown code/lists/emphasis render; HTML is escaped.
- **Status:** DONE

### T-707
- **Epic:** E8 — Windows launch experience
- **Title:** Add a one-click desktop launcher
- **Goal:** Open the Inbox from a desktop shortcut, starting the local server in the background only when it is not already healthy.
- **Dependencies:** T-602
- **Files:** `launch_screenshot_inbox.ps1`, `README.md`
- **Acceptance Criteria:** Existing healthy servers are reused; missing servers start hidden; the launcher waits for health before opening the default browser; runtime logs remain ignored under `work/`.
- **Status:** DONE

### T-708
- **Epic:** E4/E6 — Resilient detail rendering
- **Title:** Flatten mapping-shaped explanation entries
- **Goal:** Prevent AI-returned dictionaries or previously stringified dictionaries from rendering as raw Python mappings or overflowing the detail panel.
- **Dependencies:** T-301, T-502, T-705
- **Files:** `schemas.py`, `database.py`, `static/app.css`, tests
- **Acceptance Criteria:** Mapping entries become `term — explanation` list items; saved legacy strings are safely recovered without code execution; long content wraps; existing records improve without another AI request.
- **Status:** DONE

### T-709
- **Epic:** E6 — Completion feedback
- **Title:** Show lower-right analysis completion notifications
- **Goal:** Notify the user in an open Inbox browser page when a screenshot transitions to completed without replaying notifications for existing history.
- **Dependencies:** T-401, T-501, T-502
- **Files:** `web.py`, `templates/base.html`, `static/app.js`, `static/app.css`, tests, documentation
- **Acceptance Criteria:** A local status endpoint exposes recent IDs/statuses/titles; initial polling seeds state silently; new completions show a clickable six-second lower-right toast; polling recovers after server restarts.
- **Status:** DONE

### T-710
- **Epic:** E4/E6 — Live readable results
- **Title:** Combine term-definition objects and live-refresh the Inbox
- **Goal:** Render paired `term`/`explanation` objects as one readable line, preserve completion tracking across navigation, and show new screenshots without manual reloads.
- **Dependencies:** T-708, T-709
- **Files:** `schemas.py`, `static/app.js`, tests, documentation
- **Acceptance Criteria:** Paired objects render as `term: explanation`; status memory uses tab session storage; new IDs and status transitions refresh the visible timeline; completion toasts survive navigation and detail auto-refreshes.
- **Status:** DONE

### T-711
- **Epic:** E4/E6 — Definition formatting and system notifications
- **Title:** Combine term-definition pairs and add native Windows notifications
- **Goal:** Render `term`/`definition` output as one line and make completion detection robust enough for fast analyses while surfacing browser-independent Windows notifications.
- **Dependencies:** T-709, T-710
- **Files:** `schemas.py`, `web.py`, `templates/base.html`, `static/app.js`, `static/app.css`, tests, documentation
- **Acceptance Criteria:** `term` plus `definition` becomes `term: definition`; completion revision uses `analyzed_at`; in-page toast remains unconditional; the background process sends a clickable native Windows notification without browser permission.
- **Status:** DONE

### T-712
- **Epic:** E8 — Windows app experience
- **Title:** Open Screenshot Inbox as a standalone app window
- **Goal:** Make the desktop icon open the local Inbox without ordinary browser chrome while preserving the local-only server and one-click startup.
- **Dependencies:** T-707
- **Files:** `launch_screenshot_inbox.ps1`, tests, documentation
- **Acceptance Criteria:** The launcher prefers Edge or Chrome app mode, keeps the local URL and hidden background server, and falls back to the default browser when neither executable exists.
- **Status:** DONE

### T-713
- **Epic:** E3/E4 — Reliable programming solutions
- **Title:** Repair programming-problem misclassification and missing code
- **Goal:** Ensure recognizable competitive-programming screenshots return complete Python, Java, and C++ solutions without a redundant language metadata row.
- **Dependencies:** T-301, T-704
- **Files:** provider, schema, detail template, tests, documentation
- **Acceptance Criteria:** Contest markers trigger a code-only second pass after problem misclassification; all three solution strings are required; sample output hardcoding is explicitly prohibited; the standalone language field is not stored or rendered.
- **Status:** DONE

### T-714
- **Epic:** E4/E8 — Minimal local UI
- **Title:** Hide source names and paths from the interface
- **Goal:** Keep the Inbox focused on analysis results instead of implementation and filesystem metadata.
- **Dependencies:** T-401, T-712
- **Files:** base, Inbox and detail templates, styles, tests, documentation
- **Acceptance Criteria:** Timeline source filenames, watched-directory text, detail filesystem paths, provider label, and status dot are absent; the top-right area contains only Watching.
- **Status:** DONE

### T-715
- **Epic:** E6/E8 — Reliable Windows notifications
- **Title:** Register a dedicated native notification sender
- **Goal:** Make Windows attribute completion notifications to Screenshot Inbox instead of the PowerShell host process.
- **Dependencies:** T-711
- **Files:** notification module, tests, documentation
- **Acceptance Criteria:** The toast script registers the per-user ScreenshotInbox.Local identity and Screenshot Inbox display name, sends through that identity, and does not use the PowerShell sender ID; Windows master notification requirements are documented.
- **Status:** DONE

### T-716
- **Epic:** E6/E8 — Native app identity
- **Title:** Install the Screenshot Inbox notification shortcut
- **Goal:** Give Windows a complete local AppUserModelID registration so branded notifications are delivered instead of being dropped or attributed to PowerShell.
- **Dependencies:** T-707, T-715
- **Files:** Windows shortcut helper, registration and launcher scripts, notification module, tests, documentation
- **Acceptance Criteria:** A per-user Start Menu shortcut contains ScreenshotInbox.Local; launcher registration requires no administrator access; the notifier uses the same ID; GitHub remains source backup only and runtime stays local.
- **Status:** DONE

### T-717
- **Epic:** E2/E4/E8 — Background continuity and bulk Inbox management
- **Title:** Recover downtime screenshots and support bulk dismissal
- **Goal:** Keep screenshot monitoring active after Windows sign-in, recover screenshots captured during watcher downtime, and allow multiple Inbox records to be dismissed without touching source images.
- **Dependencies:** T-103, T-203, T-402, T-716
- **Files:** database, pipeline, application lifecycle, Windows launchers, Inbox template and script, tests, documentation
- **Acceptance Criteria:** A per-user Startup shortcut launches the watcher without a browser; a stored checkpoint bounds catch-up scanning; dismissed hashes prevent deleted Inbox entries from returning; select-all bulk deletion removes only local Inbox records and conversations; original screenshots remain unchanged.
- **Status:** DONE

### T-718
- **Epic:** E4/E8 — Contextual Inbox controls
- **Title:** Hide destructive controls behind Inbox selection mode
- **Goal:** Keep the normal timeline visually quiet while making bulk dismissal easy to discover from a top-right overflow menu.
- **Dependencies:** T-717
- **Files:** Inbox template, JavaScript, styles, tests, documentation
- **Acceptance Criteria:** The normal Inbox shows no checkboxes or trash controls; `⋮` → `항목 선택` reveals a contextual toolbar with selection count, select-all, and trash; clicking rows toggles selection; Cancel and Escape restore normal mode; deletion still preserves every source screenshot.
- **Status:** DONE

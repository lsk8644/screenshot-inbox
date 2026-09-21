# Architecture Decisions

## D-001 — Local Python application

Use Python 3.13 with FastAPI, Uvicorn, Jinja2, watchdog, Pillow, and the standard-library `sqlite3` module. This matches the requested local utility shape without introducing a frontend framework or ORM.

## D-002 — One process, bounded background worker

Run the web server, filesystem observer, and one in-process analysis queue together. A single worker makes SQLite writes predictable and keeps the MVP operationally simple. Durable screenshot state in SQLite lets startup recover interrupted `analyzing` records.

## D-003 — Content-addressed deduplication

Store a SHA-256 digest with a unique index. Paths are retained for display, but duplicate content does not trigger another AI request.

## D-004 — Provider boundary

Define an `AnalyzerProvider` protocol, an `OpenAICompatibleProvider`, and a deterministic `MockProvider`. Provider construction is configuration-driven. The external API is never called by tests.

## D-005 — Strict normalization with graceful fallback

Model responses are parsed and normalized into the seven supported categories. Invalid JSON or invalid field types become a controlled provider error instead of crashing the worker.

## D-006 — Server-rendered working surface

Use Jinja2 templates, CSS, and a small amount of vanilla JavaScript. The visual thesis is a dense, restrained Windows utility: a narrow filter rail, readable timeline rows, visible processing states, and the screenshot beside its analysis on detail pages.

## D-007 — Local-only delivery

Do not publish or deploy. The product explicitly operates on local Windows files and a local SQLite database, so hosting would conflict with its privacy and filesystem requirements.

## D-008 — Korean, task-complete analysis

Request Korean user-facing analysis regardless of the screenshot language while preserving source code and extracted text. Programming exercises must return runnable solution code, an approach, an explanation, and complexity. Strong visible error markers provide a deterministic fallback from `other` to `error` when the model under-classifies an error screen.

## D-009 — Seoul-local presentation over UTC storage

Keep SQLite timestamps in UTC for stable ordering and convert them at the web boundary to Korean Standard Time (`UTC+09:00`, named `Asia/Seoul`) without requiring an operating-system timezone database. Group the newest-first timeline by local calendar day, label groups as `M.DD`, and render screenshot times as 24-hour `HH:MM`.

## D-010 — Reversible Inbox deletion and screenshot-scoped chat

The trash action deletes only the SQLite Inbox record and its cascading local chat messages; it never removes or moves the original image. Screenshot chat reuses the configured provider, sends the image plus a bounded recent history on each explicit question, answers in Korean, and persists successful user/assistant pairs locally. Programming solutions are requested for Python, Java, and C++ together and switched client-side without another API call.

## D-011 — Concept-first educational analysis

Educational screenshots must explain rather than merely transcribe. The provider expands acronyms and frameworks, defines their components in plain Korean, relates them, and supplies concrete examples. Lecture details keep these explanations in a dedicated normalized list so the UI can present them separately from extracted keywords.

## D-012 — Safe local Markdown for chat

Render a deliberately small Markdown subset for AI chat responses after HTML escaping: headings, lists, emphasis, inline code, blockquotes, and fenced code blocks. This keeps technical answers readable without trusting provider-generated HTML or requiring a browser CDN. Enter submits a question, Shift+Enter inserts a line break, and IME composition is never intercepted.

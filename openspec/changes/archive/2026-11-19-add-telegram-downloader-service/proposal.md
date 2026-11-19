# Proposal

## Why

The backend only simulates downloads with a stub. `bot.py` downloads real Telegram chats, but it runs outside the stack and reports progress to nobody. It also takes the media chat from a fixed environment variable, `TELEGRAM_CHAT_NAME`. A `downloader` service brings the `bot.py` logic into the stack. It reports real progress to the backend, and the UI controls which chats get their media downloaded.

## What Changes

- A new `downloader` service (Python 3.15, Telethon) ports the download logic of `bot.py`:
  - It downloads every dialog in full: private chats, groups, and channels. Each chat starts with the oldest message, and the service downloads one chat at a time.
  - It continues each chat after its newest stored message, and stores new messages as they arrive.
  - It downloads media only for chats with `settings.media` on. This setting replaces `TELEGRAM_CHAT_NAME`.
- SQLAlchemy models and Alembic migrations manage `messages.db`. The first migration reproduces the `bot.py` schema, and the second renames `downloads_media` to `download_media`. A one-shot `migrate` service runs the migrations before the other services start. It adopts a database that `bot.py` created.
- The downloader serves a WebSocket API inside the Compose network. When the backend connects, the downloader sends the state of every chat, then each later change.
- The backend writes `settings.media` to the downloader's database, then sends `settings_changed`. After that notice, the downloader reads the settings again before its next media decision.
- The backend drops the stub:
  - `list_chats` reads chats and settings from the downloader's database, and states from the downloader.
  - `update_chat` stores the setting and notifies the downloader.
  - `/api/health` reports 503 while the backend has no link to the downloader.
- A fake downloader (`python -m dossier.downloader fake`) serves the same API with fake chats and the simulated downloads of the former stub.
- The e2e tests run in their own Compose project, `e2e/compose.yaml`, against the fake downloader. They need no Telegram account and no `.env`.
- `.env` holds `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`, `DATA_DIR`, and `DOWNLOADS_DIR`:
  - `DATA_DIR` is the host folder for `messages.db` and `dossier_bot.session`.
  - `DOWNLOADS_DIR` is the host folder for media.
  - A committed `.env.example` lists the keys, and git ignores `.env`.
- `docker compose run --rm downloader login` logs in to Telegram once and stores the session in `DATA_DIR`.
- **BREAKING**: the e2e command becomes `docker compose -f e2e/compose.yaml run --rm --build e2e`. `TELEGRAM_CHAT_NAME` is gone. The stack reports healthy only after the downloader runs with a logged-in session.

## Capabilities

### New Capabilities
- `downloader-api`: the WebSocket contract between the downloader and the backend. It covers the state snapshot, state updates, the settings notice, and the backend link.
- `fake-downloader`: the fake downloader that the e2e tests use in place of Telegram.

### Modified Capabilities
- `chat-download`: the stub requirements leave. New requirements describe how the downloader downloads and stores chats and media, reports states, and applies the media setting.
- `chat-download-api`: chats and settings come from the downloader's database, settings survive a restart, and a chat without a reported state has the zero state.
- `docker-stack`: the `migrate` and `downloader` services, `.env` configuration, the login command, downloader unit tests, readiness that needs the downloader, and the separate e2e project.

## Impact

- One Python project, `dossier`, at the repository root replaces `backend/`. It has one `pyproject.toml`, `uv.lock`, Dockerfile, `alembic.ini`, `migrations/`, and `tests/`. Its package `dossier/` holds the shared models, `backend/`, and `downloader/`. One image serves the `migrate`, `backend`, `downloader`, and `fake-downloader` services.
- The backend loses the stub. Its JSON-RPC methods live in `dossier/backend/api.py`. It uses the shared models, and it gets a WebSocket client for the downloader API.
- `compose.yaml`: new `migrate` and `downloader` services, and one `test` service in place of `backend-test`. The backend gets `/data` and `DOWNLOADER_URL`. The `e2e` service moves to `e2e/compose.yaml`.
- New Python dependencies: `telethon`, `sqlalchemy`, `alembic`, `websockets`, and `pytest-asyncio` for tests.
- The UI, the UI API wire format, and the e2e test code stay the same.
- `README.md`, `.env.example`, and `.gitignore` change.

## Out of Scope

- Media for messages that are already stored when a chat gets media on. The setting applies to the messages that the downloader stores after the change.
- Rewriting the `media_path` values that `bot.py` stored.
- Turning the download of a chat off.
- Serving media files to the UI.
- Authentication and more than one Telegram account.

## Assumptions

- `DATA_DIR` is on a local filesystem. The downloader and the backend share `messages.db`, and SQLite file locking across processes needs a local disk.
- The file names stay as in `bot.py`: `messages.db` and `dossier_bot.session`.
- The downloader API listens on port 8090. The host does not publish that port.
- When `DATA_DIR` or `DOWNLOADS_DIR` is unset, the stack uses `./data` and `./downloads`, which git ignores. This keeps test commands working without `.env`.

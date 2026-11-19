# Design

## Context

See `proposal.md` for the motivation. These facts shape the approach:

- `bot.py` is one `DossierBot` class on Telethon and `sqlite3`. It creates three tables with raw SQL: `messages`, `chats`, and `users`. It sets `journal_mode=WAL` and `synchronous=NORMAL`.
- `bot.py` resumes each chat after `MAX(message_id)`. It skips chats whose `dialog.top_message` is already stored. It commits every 100 messages and after each media file. It registers the new-message handler after the start-up download.
- `bot.py` stores message dates with `isoformat()`, which writes `+00:00`. It saves media to `<download_dir>/<chat id>/<aa>/<bb>/<cc>/<message id>/<file>` and stores that path in `media_path`.
- `bot.py` downloads private chats and groups, plus channels whose name equals `TELEGRAM_CHAT_NAME`. It writes `chats.downloads_media` from that variable on every start.
- The backend holds the UI API (`app/main.py`), a progress hub (`app/progress.py`), and the stub (`app/stub_downloader.py` and `fake_chats()` in `app/chats.py`). `create_app(step_seconds)` builds it.
- The UI and the e2e tests depend only on the UI API. The e2e tests need progress after a save, and the stub gives them that progress by restarting on each save.
- PyPI today has Telethon 1.46.0, SQLAlchemy 2.1.9, Alembic 1.20.1, and websockets 17.4. All of them install on Python 3.15 without a compiler. SQLAlchemy 2.1 no longer needs `greenlet`.
- `/root/work` is an NFS mount. New directories can list as empty to `ls` and to Docker.

## Goals / Non-Goals

**Goals:**
- Keep the download behavior of `bot.py`, except for the rules that the specs change: all dialogs, media from the database, and settings that the downloader never overwrites.
- Keep one source of truth for each fact: the database for chats and settings, and the downloader for progress.
- Keep the UI API and the e2e test code unchanged.
- Keep the real Telegram code out of all automated tests.

**Non-Goals:**
- Live sync of the dialog list to the UI. The UI sees a new chat at its next `list_chats`.
- Retries of a failed media download within one run. As in `bot.py`, the message stays without its file.

## Decisions

### 1. One Python project, `dossier`, for both services

The repository root holds one Python project: `pyproject.toml`, `uv.lock`, one Dockerfile with runtime and `test` stages, `alembic.ini`, `migrations/`, and `tests/`. The package `dossier/` holds:

- `dossier/models.py`: SQLAlchemy models `Chat`, `Message`, and `User` for the `bot.py` tables. Both services use them.
- `dossier/database.py`: the engine with the SQLite pragmas and the locking rules.
- `dossier/backend/`: the FastAPI app, the JSON-RPC methods in `api.py`, the progress hub, and the client of the downloader API.
- `dossier/downloader/config.py`: reads the Telegram keys from the environment. The container paths are fixed: `/data/messages.db`, `/data/dossier_bot.session`, and `/downloads`.
- `dossier/downloader/api.py`: the WebSocket server, the state of each chat, and the dispatch of `settings_changed`.
- `dossier/downloader/downloader.py`: the Telethon logic of `bot.py`, ported to the models.
- `dossier/downloader/fake.py`: the fake downloader.
- `dossier/downloader/__main__.py`: the commands `run` (default), `login`, and `fake`.

The Compose services `migrate`, `backend`, `downloader`, and `fake-downloader` run the same image with different commands.

Alternatives: a separate project for each service, or a separate `fake-downloader/` project. Rejected: both split or copy the models and the migrations, and the fake then tests less of the real code.

### 2. One SQLite file, migrated before every other service

The downloader and the backend share `/data/messages.db` and the models in `dossier/models.py`. The `migrate` service runs the migrations before either of them starts, so both can rely on the newest schema. Neither service runs migrations or handles a missing database.

- `list_chats` orders chats by name. A missing name becomes an empty string, which the UI shows as "Unnamed Chat".

In WAL mode, readers never wait, and one write lock covers the whole file. A transaction takes the lock at its first write and keeps it until it commits. A probe on Python 3.15.2 with SQLite 3.46.1 confirmed two failure modes:

- A writer that waits longer than the busy timeout fails with `database is locked`.
- A transaction that reads and then writes fails at once when the other process committed in between. A 5-second timeout does not help.

Both processes follow these rules:

- Every connection waits up to 5 seconds for a locked database.
- Every write transaction starts with `BEGIN IMMEDIATE`, so it waits at its start instead of failing at its first write. In the legacy transaction mode of `sqlite3`, which is still the default on Python 3.15, this is `isolation_level="IMMEDIATE"`. A test proves that SQLAlchemy keeps it.
- Every transaction is short, reads included. No transaction stays open across a network call.
- An idle connection holds no lock, because the SQLAlchemy pool rolls back each connection when it returns.

### 3. Migrations and adoption of `bot.py` databases

Alembic lives in `alembic.ini` and `migrations/` at the project root, with a standard `env.py` that builds its engine from `sqlalchemy.url`. The revisions use Alembic operations, not raw SQL:

- `0001` creates the `bot.py` tables, `UNIQUE(chat_id, message_id)`, `idx_chat_message`, and `idx_date`, with `if_not_exists`. On a `bot.py` database it creates nothing, so Alembic adopts that database without a stamp.
- `0002` renames `chats.downloads_media`, the name from `bot.py`, to `chats.download_media`. It uses batch mode, which SQLite needs for this change.

The `migrate` service runs `alembic upgrade head` with the URL from `alembic.ini`, and then exits. `prepend_sys_path = .` lets `env.py` import `dossier.models`, because the venv does not install the project. The tests run the same upgrade on temporary databases. A test runs Alembic's `compare_metadata` after the upgrade, which proves that the models and the migrations agree.

### 4. Downloader API: websockets with JSON-RPC notifications

`websockets.asyncio.server.serve` listens on `0.0.0.0:8090` in the same event loop as Telethon. `jsonrpcserver` dispatches incoming `settings_changed` notices. Malformed input gets no reply.

The API keeps the state of each chat and the set of open connections:

- A new connection first gets `chat_states`.
- `publish(chat_id, state)` stores the state and sends `chat_download_progress` to every connection.
- A failed send drops that connection.
- A new connection also clears the media cache of the downloader. A notice that a connection drop lost thus cannot leave a stale setting.

`DownloadStateJson` and `ChatStateJson` in `dossier/downloader/api.py` type the params of the notifications. The backend client uses the same types.

Alternative: HTTP polling by the backend. Rejected: you asked for a push API, and push needs no state comparison.

### 5. Downloader: `bot.py` with the new rules

- All dialogs download, channels included. The new-message handler takes every chat.
- `save_dialog` writes the name, type, username, and `tracked = true`. On conflict it keeps `download_media`. A new row gets `download_media = false`.
- The media decision reads a cache of `chat_id → download_media`. The cache loads from the database when it is empty. `settings_changed` and a new backend connection empty it.
- A state comes from the database: `COUNT(*)`, `MIN(date)`, and `MAX(date)` of the chat. At start, one `GROUP BY` query gives every state, with `complete = false`. `complete` becomes `true` when the start-up download of the chat ends, or at once when the chat is up to date.
- A chat that first appears through a new message reports `complete = true`.
- The downloader commits after each message. `bot.py` committed every 100 messages, but a flood wait inside such a batch would hold the write lock for up to an hour, and the backend could not save settings. WAL with `synchronous=NORMAL` keeps each commit cheap.
- The downloader fetches the sender and the media file of a message before it writes anything. Then it writes the rows of the message and commits, in one short transaction. `bot.py` wrote the sender row first and downloaded the media file with that transaction still open.
- The downloader uses one connection in its event loop, as `bot.py` did. It ends every unit of work with a commit or a rollback, including the state queries and the load of the media cache. Its waits for the lock last milliseconds, because each backend write is a single `UPDATE`.
- Reports go out after every 100 messages, at the end of each chat, and after each new message.
- `flood_sleep_threshold=3600` and the media layout stay as in `bot.py`. `media_path` stores the container path under `/downloads`.
- The new-message handler starts after the start-up download, as in `bot.py`. An earlier handler would raise `MAX(message_id)` before the history download of a chat, which would skip the gap.
- SQLAlchemy calls are synchronous, as the `sqlite3` calls in `bot.py` were. This needs no `greenlet`.

The downloader takes the Telethon client as a constructor argument. The tests pass a fake client and use real Telethon media types for the `isinstance` checks.

### 6. Commands and login

- `python -m dossier.downloader run` checks the keys. A missing or non-numeric `TELEGRAM_API_ID`, or a missing hash or phone, ends the downloader with code 1 and a message that names the key.
- `run` then loads the states, starts the API, and connects Telethon. If `is_user_authorized()` is false, `run` exits with code 1 and names `docker compose run --rm downloader login`.
- `python -m dossier.downloader login` calls `client.start(phone=...)`. Telethon asks for the code and the two-step password on the terminal. `docker compose run` attaches a terminal by default.
- `python -m dossier.downloader fake` needs no keys.

### 7. Backend: database, JSON-RPC methods, downloader client, and health

- `create_app(database_url, downloader_url)` replaces `create_app(step_seconds)`. The module-level app uses `sqlite:////data/messages.db` and `DOWNLOADER_URL`, which defaults to `ws://downloader:8090`.
- The backend reads and writes `chats` through the shared models and the engine of `dossier/database.py`.
- Each request uses a new session and runs its database calls in a worker thread with `run_in_threadpool`. A call that waits for the lock thus never freezes the event loop and its WebSockets. Worker threads take turns with the pooled connections, so the engine sets `check_same_thread=False`.
- `dossier/backend/api.py` holds `BackendApi` with every JSON-RPC method of the backend: `list_chats` and `update_chat` for the UI, and `chat_states` and `chat_download_progress` for the downloader. It keeps the state cache and publishes each state to the UI hub.
- `dossier/backend/downloader_api.py` holds the client, `DownloaderApiClient`. The lifespan starts it. It connects, dispatches the notifications of the downloader to `BackendApi` with `jsonrpcserver`, and reconnects one second after any failure. It also sends `settings_changed`.
- `update_chat` validates as today. It updates `download_media` with one `UPDATE` and commits, sends `settings_changed` when the link is up, and returns the chat with the cached state.
- `GET /api/health` returns 200 only while the link is up, and 503 otherwise. The stub files and `step_seconds` go away.

### 8. Fake downloader

`python -m dossier.downloader fake` uses the real API server and models:

- It inserts the four fake chats of the former stub when they are missing, and keeps the settings of the stored ones.
- It runs the former stub simulation in memory: 10 steps of 0.5 seconds, 100 messages a step, from the first-message date to the start time.
- At start, it simulates every chat.
- On `settings_changed` for a chat, it cancels that chat's simulation, publishes the zero state, and starts again.
- It stores no messages.

### 9. E2E in its own Compose project

`e2e/compose.yaml` has `name: dossier-e2e` and five services:

- `migrate`: built from `..`, command `alembic upgrade head`.
- `fake-downloader`: built from `..`, command `fake`, after `migrate` exits with code 0.
- `backend`: built from `..`, with `DOWNLOADER_URL=ws://fake-downloader:8090`, after `migrate` exits with code 0.
- `frontend`: built from `../frontend` with the same health check, and no host port.
- `e2e`: built from `.`, waiting for a healthy `frontend`, with `./test-results` bind-mounted.

`migrate`, `fake-downloader`, and `backend` share the named volume `e2e-data` at `/data`. The service names match the main stack, so `nginx.conf` and `baseURL` stay as they are. The main `compose.yaml` loses its `e2e` service. The health check makes the tests start only after the backend has a link to the fake downloader, so no `settings_changed` gets lost.

Alternative: profiles in the main `compose.yaml`. Rejected: the e2e backend needs another `DOWNLOADER_URL` and volume, and `nginx.conf` names the host `backend`.

### 10. Compose and configuration

The `migrate`, `backend`, and `downloader` services build the root project and set their own commands. The `migrate` service mounts `${DATA_DIR:-./data}:/data` and runs `alembic upgrade head`. The `downloader` service gets:

- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_PHONE` through `environment`, interpolated from `.env` with empty defaults.
- `${DATA_DIR:-./data}:/data` and `${DOWNLOADS_DIR:-./downloads}:/downloads`.
- `depends_on` with `migrate: service_completed_successfully`.

The `backend` service gets `${DATA_DIR:-./data}:/data`, `DOWNLOADER_URL`, and `depends_on` with `migrate: service_completed_successfully` and `downloader: service_started`. When `migrate` fails, Compose starts neither the downloader nor the backend. One `test` service in the `test` profile runs all Python tests, in place of `backend-test`. The defaults let Compose parse the file without `.env`, so the test commands work anywhere.

`.env.example` lists the five keys, and `.gitignore` adds `.env`, `data/`, `downloads/`, and `e2e/test-results/`.

### 11. Tests

- **Migrations:** `tests/migrate.py` runs the Alembic upgrade on a temporary database, as the `migrate` service does. Every test database starts this way. Tests cover a fresh database, the adoption of a database built from the `bot.py` DDL as literal SQL, and the agreement between the models and the migrations.
- **Downloader:** pytest with `pytest-asyncio`, a temporary data folder, and a fake Telethon client. Tests cover every scenario of `chat-download`, `downloader-api`, and `fake-downloader`, and the key and login error messages.
- **Two processes:** a downloader test starts a second process with the write pattern of the backend: the same engine options, and one `UPDATE` in `BEGIN IMMEDIATE` every 10 ms. Meanwhile, the downloader stores messages with its real code and a fake client. After several seconds, the test expects no `database is locked` error on either side.
- **Backend:** a temporary database that the real migrations create, and a fake downloader server in a background thread that records what it receives. The stub tests leave. New tests cover `list_chats`, `update_chat`, the relay, health, and reconnect. They also prove that `update_chat` starts with `BEGIN IMMEDIATE`.
- **E2E:** the test code stays. Only its Compose file moves.
- **Lint and format:** ruff checks and formats all Python code, with lines of up to 120 characters.
- **Types:** mypy in strict mode checks `dossier`, `migrations`, and `tests`. Telethon ships no `py.typed` marker, so mypy treats its imports as untyped.
- **Live check:** an automated test cannot log in to Telegram. The user runs the live check: login, `docker compose up`, and the UI.

## Risks / Trade-offs

- [SQLite on a network filesystem] → WAL needs local file locks and shared memory. `README.md` tells the user to put `DATA_DIR` on a local disk.
- [A bug holds the write lock for more than 5 seconds] → The other side gets `database is locked`. Then `update_chat` returns an error that the UI shows, or the downloader logs it and resumes the chat at its next start. The two-process test guards the normal write pattern.
- [Full download of large channels] → The first run can take hours and hit flood waits. The download is sequential, and `flood_sleep_threshold=3600` keeps waits inside the downloader. The UI shows the progress.
- [Messages during the start-up download] → As in `bot.py`, a chat that finished earlier in the run misses messages that arrive before the handler starts. The next start fetches them through the resume rule.
- [Old `media_path` values] → Rows from `bot.py` keep their old path form, and new rows use `/downloads/...`. No code reads `media_path` yet.
- [Turning media on] → The setting applies to the messages that the downloader stores later. Stored messages keep no media. A backfill is out of scope.
- [No real Telegram in tests] → A fake client covers the logic. The live check stays with the user.
- [New directories on the NFS mount] → After you create `dossier/`, its packages, `tests/`, `migrations/`, and `e2e/test-results/`, check them with `ls`. Rename an empty-looking leaf directory away and back.

## Open Questions

- Should the UI show channels with their own icon? Today it shows the group icon for every negative id.

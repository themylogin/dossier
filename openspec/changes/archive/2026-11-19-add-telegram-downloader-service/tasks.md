# Tasks

All paths are relative to `dossier/`. Run every build, install, lock, and test step in a container. Automated tests never call Telegram.

## 1. Bot project skeleton

- [x] 1.1 Create `bot/pyproject.toml` for Python 3.15 with `telethon`, `sqlalchemy`, `alembic`, `websockets`, and `jsonrpcserver`. Add a dev group with `pytest` and `pytest-asyncio`. Run `uv lock` in the uv image for Python 3.15. Verify that `ls bot` lists `uv.lock`.
- [x] 1.2 Write `bot/Dockerfile` with a runtime stage and a `test` stage, as in `backend/Dockerfile`, and add `bot/.dockerignore`. Create the `bot` and `tests` packages, and check them with `ls`. Add the `bot-test` service to `compose.yaml` in the `test` profile. Verify that `docker compose --profile test build bot-test` succeeds.
- [x] 1.3 Add `bot/config.py` with the key checks of design 6, and tests for "Missing key". Add the `bot-test` command to `README.md`. Verify that `docker compose --profile test run --rm --build bot-test` passes without `.env`.

## 2. Models and migrations

Each task adds its tests to `bot/tests/`. Each task is done when `bot-test` passes.

- [x] 2.1 Add `bot/models.py`, and `bot/database.py` with the engine, the pragmas, and the locking rules (design 2 and 3). Add `bot/alembic.ini`, `bot/migrations/`, and revision `0001` with the `bot.py` DDL. Check the new directories with `ls`. Verify with tests for "Empty data folder" and for the agreement of the models and the migrations. Also verify that a write transaction starts with `BEGIN IMMEDIATE`.
- [x] 2.2 Add the adoption of `bot.py` databases to `migrate()`. Verify with a test for "Database from bot.py" that builds the database from the `bot.py` DDL as literal SQL.

## 3. Bot API

- [x] 3.1 Add `bot/api.py` with the server, the chat states, `publish`, and the `settings_changed` dispatch (design 4). Verify with tests for "Backend connects", "First message after connect", and "Two connections". The task is done when `bot-test` passes.

## 4. Downloader

Each task adds its tests to `bot/tests/` with a fake Telethon client. Each task is done when `bot-test` passes.

- [x] 4.1 Port the dialog and history logic of `bot.py` to `bot/downloader.py` (design 5). Give each message one short write transaction, after all network calls for it. Verify with tests for "Three kinds of chats", "Interrupted download", "Chat up to date", and "250 messages to download". Verify that the two-process test of design 11 finds no `database is locked` error.
- [x] 4.2 Add the media download with the settings cache. Download the media before the write transaction of its message. Empty the cache on `settings_changed` and on each new connection. Verify with tests for "Media off", "Media on", "Media turned on during a download", "Dialog stored again", and "Photo of message 7890".
- [x] 4.3 Add the new-message handler after the start-up download. Verify with a test for "Message arrives".
- [x] 4.4 Add `bot/__main__.py` with the `run` and `login` commands (design 6). Verify with tests for "Not logged in", and for the start order: migrations, then the API, then Telethon.

## 5. Fake bot

- [x] 5.1 Add `bot/fake.py` and the `fake` command (design 8). Move the fake chats and the simulation of the stub from the backend. Verify with tests for "First start", "Later start", "All chats download at start", "Settings saved", "Settings saved again during a download", "Settings saved again after completion", and "Full simulated download". The task is done when `bot-test` passes.

## 6. Backend

Each task is done when `docker compose --profile test run --rm --build backend-test` passes.

- [x] 6.1 Add `sqlalchemy` and `websockets` to `backend/pyproject.toml`, and relock in the uv image. Add `app/database.py`, and change `create_app` to take `database_url` and `bot_url` (design 7). Read chats and settings from the database. Open it with `mode=rw`, use a new session per request, and run database calls in a worker thread. Start each write with `BEGIN IMMEDIATE` (design 2). Delete `app/stub_downloader.py`, `fake_chats()`, and the stub tests. Verify with tests for "Client lists chats", "Chat fields", "Chat without a reported state", "Turn media on", "Turn media off", "Unknown chat", "Media is not a boolean", and "Settings survive a restart". Also verify that `update_chat` starts with `BEGIN IMMEDIATE`, and that a missing database file stays missing while `list_chats` returns an empty list.
- [x] 6.2 Add `app/bot_link.py` (design 7), and a fake bot server fixture for the tests. Verify with tests for "Media turned on", "Bot restarts", "Two clients get the same progress", "A client disconnects", and the 503 and 200 health replies.

## 7. Stack configuration

- [x] 7.1 Add the `bot` service and the backend changes to `compose.yaml`, and remove the `e2e` service (design 10). Add `.env.example` and the `.gitignore` entries. Verify that `docker compose config` succeeds without `.env`. Verify that `git check-ignore` matches `.env`, `data/`, `downloads/`, and `e2e/test-results/`.
- [x] 7.2 Create a temporary `.env` that sets `DATA_DIR` and `DOWNLOADS_DIR`. Verify that `docker compose config` mounts these folders at `/data` and `/downloads`. Delete the temporary `.env`.
- [x] 7.3 Update `README.md`: setup from `.env.example`, the local disk for `DATA_DIR`, the login command, and the adoption of `bot.py` files. Run `docker compose up -d --build` without `.env`. Verify that the bot exits with a message that names `TELEGRAM_API_ID`. Verify that `/api/health` returns 503 with `{"status": "bot unavailable"}`, and that `frontend` turns unhealthy. Then run `docker compose down`.

## 8. E2E project

- [x] 8.1 Create `e2e/compose.yaml` (design 9), and check `e2e/test-results/` with `ls`. Replace the e2e command in `README.md`. Verify that `docker compose -f e2e/compose.yaml run --rm --build e2e` passes two times in a row. Verify that `GET http://backend:8080/api/health` in the e2e network returns 200.
- [x] 8.2 Verify that `docker compose -f e2e/compose.yaml config` mounts no host folder except `e2e/test-results`.
- [x] 8.3 Make one e2e assertion fail on purpose, and run the e2e command. Verify that the command exits with a non-zero code. Verify that `e2e/test-results/` holds a screenshot and a trace. Undo the change.

## 9. Integration check

- [x] 9.1 Replace the Purpose of `openspec/specs/chat-download/spec.md` with one that describes the bot download. Verify that `openspec validate --specs` passes.
- [x] 9.2 Run `docker compose down`, then run each test command from `README.md` in order, without `.env`. Verify that each command passes and that the host gets no new toolchain.
- [ ] 9.3 Ask the user for the live check. The user fills `.env`, runs `docker compose run --rm downloader login` or copies the `bot.py` files into `DATA_DIR`, runs `docker compose up --build`, and opens `http://localhost:8080`. Verify with the user that the UI lists the real chats with progress, and that media lands in `DOWNLOADS_DIR`. This covers "Stack starts", "First login", "Session from bot.py", and "Folders from .env".
- [x] 9.4 Run `openspec validate add-telegram-bot-service --strict`. Verify that it reports the change as valid.

## 10. One Python project

- [x] 10.1 Merge `backend/` and `bot/` into one Python project, `dossier`, at the repository root, with shared models in `dossier/models.py`. Replace `backend-test` and `bot-test` with one `test` service. Verify that `docker compose --profile test run --rm --build test` passes.
- [x] 10.2 Rename `chats.downloads_media` to `chats.download_media` with Alembic revision `0002`. Verify that a `bot.py` database ends at revision `0002` with its media settings kept.
- [x] 10.3 Point `compose.yaml`, `e2e/compose.yaml`, `README.md`, and the change artifacts at the new layout. Verify that the e2e command passes, and that the bot without `.env` exits with a message that names `TELEGRAM_API_ID`.
- [x] 10.4 Rewrite the migrations with Alembic operations and a standard `env.py`, and reduce `migrate()` to `command.upgrade`. Drop the stamp logic. Verify that a fresh database and a `bot.py` database both end at revision `0002`, that a downgrade to `base` works, and that the e2e command passes on a fresh e2e volume.

## 11. Downloader naming

- [x] 11.1 Rename `dossier/bot/` to `dossier/downloader/` and `tests/bot/` to `tests/downloader/`. Rename `BotApi` to `DownloaderApi` and `FakeBot` to `FakeDownloader`. Rename the Compose services to `downloader` and `fake-downloader`, and `BOT_URL` to `DOWNLOADER_URL`. Change the health body to `{"status": "downloader unavailable"}` and the login hint to `docker compose run --rm downloader login`. Verify that `docker compose --profile test run --rm --build test` passes.
- [x] 11.2 Rename `dossier/backend/bot_link.py` to `dossier/backend/downloader_api.py`, and `BotLink` to `DownloaderApiClient`. Verify that the e2e command passes.
- [x] 11.3 Point `README.md`, the change artifacts, and the Purpose of `openspec/specs/chat-download/spec.md` at the new names. Rename this change to `add-telegram-downloader-service`, and its capabilities to `downloader-api` and `fake-downloader`. Verify that `openspec validate add-telegram-downloader-service --strict` and `openspec validate --specs` pass.

## 12. Strict types

- [x] 12.1 Add `mypy` to the dev group in `pyproject.toml`, with `strict = true` for `dossier`, `migrations`, and `tests`. Configure Telethon as an untyped import, because it ships no `py.typed` marker. Annotate all code, and give every generic its type arguments. Verify that `docker compose --profile test run --rm --build test mypy` finds no issues. Verify that the Python tests and the e2e command pass.

## 13. Migrate service

- [x] 13.1 Add a `migrate` service to `compose.yaml` and `e2e/compose.yaml`. It runs `alembic upgrade head` and exits. Make `downloader`, `fake-downloader`, and `backend` depend on it with `condition: service_completed_successfully`. Add `prepend_sys_path` and `path_separator` to `alembic.ini`. Verify that the e2e command passes on a fresh e2e volume.
- [x] 13.2 Remove `migrate()` from `run`, `fake`, and `dossier/database.py`, and move it to `tests/migrate.py`. Move the migration tests to `tests/`. Remove the fallback for a missing database, the `mode=rw` URL, and the test for a missing database file. Verify that the Python tests pass.
- [x] 13.3 Move the JSON-RPC methods of the backend to `BackendApi` in `dossier/backend/api.py`. Verify that mypy, the Python tests, and the e2e command pass.
- [x] 13.4 Run `docker compose up -d --build` with an empty temporary `DATA_DIR` and no `.env`. Verify that `migrate` creates `messages.db` at revision `0002` and exits with code 0. Verify that the downloader then exits with the message that names `TELEGRAM_API_ID`. Repeat with a `messages.db` that is not a database. Verify that `migrate` fails and that the downloader and the backend do not start.

## 14. Ruff

- [x] 14.1 Add `ruff` to the dev group. Configure it in `pyproject.toml` with `line-length = 120` and the rules `E`, `F`, `ASYNC`, `TID`, and `I`, with `force-sort-within-sections`. Format all Python code, and fix all findings. Verify that `ruff check` and `ruff format --check` pass in the test image. Verify that mypy, the Python tests, and the e2e command pass.

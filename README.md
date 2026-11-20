# Dossier

Dossier downloads Telegram chats and shows the download progress of each chat.

- `dossier/`: the Python project. It holds the models in `dossier/models.py`, the Alembic migrations in `migrations/`, and two services:
  - `dossier/downloader/`: a Telethon service. It downloads every chat in full, and the media of the chats with media on. It also downloads each chat that the account joins while it runs. Every 15 minutes, it reads the dialog list again and completes each chat that is behind. It keeps each earlier version of an edited message in `message_versions`. It reports its progress over a WebSocket API.
  - `dossier/backend/`: a FastAPI app. It serves a JSON-RPC 2.0 API over a WebSocket to the UI. Its JSON-RPC methods are in `dossier/backend/api.py`. It reads chats and settings from the database, and it passes on the progress of the downloader.
- `frontend/`: the React UI, served by nginx.
- `e2e/`: Playwright tests in headless Chromium, against a fake downloader.

Everything runs in Docker. The host needs only Docker with Compose.

## Setup

Copy `.env.example` to `.env`, and fill in the keys:

- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`: the API keys of your app from https://my.telegram.org.
- `TELEGRAM_PHONE`: the phone number of the account, with the country code.
- `DATA_DIR`: the host folder for `messages.db` and `dossier_bot.session`. Use a local disk. Two processes cannot share an SQLite file safely over NFS or SMB.
- `DOWNLOADS_DIR`: the host folder for media files.

Log in to Telegram once. The command asks for the code that Telegram sends, and for the two-step password if the account has one:

```sh
docker compose run --rm downloader login
```

To keep the data of `bot.py`, copy its `messages.db` and `dossier_bot.session` into `DATA_DIR`, and its media into `DOWNLOADS_DIR`. The `migrate` service upgrades that database at the next start, and you need no new login.

## Run

Start the stack. The `migrate` service first upgrades `messages.db` and exits. Then the downloader, the API, and the UI start:

```sh
docker compose up --build
```

Then open http://localhost:8080. To download the media of a chat, right-click the chat, select `Download Settings`, and check `Download Media`. The downloader then saves the files of every stored message of the chat, newest first, and the UI shows the progress with `📎`. Uncheck `Download Media` to stop after the current file.

Stop them:

```sh
docker compose down
```

## Test

Run the Python tests of the downloader and the backend:

```sh
docker compose --profile test run --rm --build test
```

Check the types of the Python code with mypy in strict mode:

```sh
docker compose --profile test run --rm --build test mypy
```

Check the Python code with the ruff linter and formatter:

```sh
docker compose --profile test run --rm --build test ruff check
docker compose --profile test run --rm --build test ruff format --check
```

To fix the files in place, mount the project into the container:

```sh
docker compose --profile test run --rm --build -v "$PWD":/app test ruff check --fix
docker compose --profile test run --rm --build -v "$PWD":/app test ruff format
```

Run the UI unit tests:

```sh
docker compose --profile test run --rm --build frontend-test
```

Run the end-to-end tests in headless Chromium. They use their own stack with a fake downloader, so they need no `.env` and never touch your data. The command starts that stack when it is not running:

```sh
docker compose -f e2e/compose.yaml run --rm --build e2e
```

Stop the end-to-end stack:

```sh
docker compose -f e2e/compose.yaml down
```

When an end-to-end test fails, its screenshot and trace are in `e2e/test-results/`.

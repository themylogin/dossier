# Spec Delta

## MODIFIED Requirements

### Requirement: One command serves the app
`docker compose up --build` in `dossier/` SHALL build and start the downloader, the API, and the UI. The API and the UI SHALL share one origin, `http://localhost:8080`, with the UI at `/` and the API under `/api/`.

#### Scenario: Stack starts
- **GIVEN** `.env` holds the Telegram keys and the session is logged in
- **WHEN** a developer runs `docker compose up --build` in `dossier/`
- **THEN** `http://localhost:8080/` serves the UI
- **AND** the UI lists the chats of the Telegram account

### Requirement: Backend port
The backend SHALL listen on port 8080 inside its container. Other services SHALL reach it at `backend:8080`. The host SHALL NOT publish the backend port, because host port 8080 serves the UI.

#### Scenario: Backend inside the network
- **GIVEN** the backend has a link to the downloader
- **WHEN** a container in the Compose network sends `GET http://backend:8080/api/health`
- **THEN** the response has status 200 and the body `{"status": "ok"}`

### Requirement: Readiness check
`GET /api/health` SHALL return status 200 with the body `{"status": "ok"}` while the backend has a link to the downloader. Otherwise it SHALL return status 503 with the body `{"status": "downloader unavailable"}`. Docker SHALL mark the `frontend` service healthy only when this request returns 200 through the UI server.

#### Scenario: Health through the UI server
- **GIVEN** the downloader runs and the backend has a link to it
- **WHEN** a client sends `GET http://localhost:8080/api/health`
- **THEN** the response has status 200 and the body `{"status": "ok"}`

#### Scenario: API down
- **WHEN** the `backend` service is stopped
- **THEN** Docker reports the `frontend` service as unhealthy

#### Scenario: Downloader down
- **WHEN** the `downloader` service is stopped
- **THEN** `GET /api/health` returns status 503 with the body `{"status": "downloader unavailable"}`
- **AND** Docker reports the `frontend` service as unhealthy

### Requirement: Unit tests in containers
`docker compose --profile test run --rm --build test` SHALL run the Python tests of the backend and the downloader. `docker compose --profile test run --rm --build frontend-test` SHALL run the UI unit tests. Each command SHALL exit with a non-zero code when a test fails. The test commands SHALL need neither `.env` nor a Telegram account.

#### Scenario: A backend test fails
- **WHEN** a backend test fails during `docker compose --profile test run --rm --build test`
- **THEN** the command exits with a non-zero code

#### Scenario: All UI unit tests pass
- **WHEN** all UI unit tests pass during `docker compose --profile test run --rm --build frontend-test`
- **THEN** the command exits with code 0

#### Scenario: Python tests without .env
- **GIVEN** `dossier/` has no `.env` file
- **WHEN** a developer runs `docker compose --profile test run --rm --build test`
- **THEN** the backend and downloader tests run, and the command exits with code 0 when they pass

### Requirement: E2E tests in headless Chromium
`docker compose -f e2e/compose.yaml run --rm --build e2e` SHALL start its own stack with the fake downloader, the backend, and the UI when that stack is not running, and wait until it is ready. It SHALL then run the e2e tests in headless Chromium in a container. The e2e stack SHALL use its own containers, network, and database, and need neither `.env` nor a Telegram account. The command SHALL exit with a non-zero code when a test fails.

#### Scenario: E2E run on a stopped stack
- **GIVEN** the e2e stack is not running
- **WHEN** a developer runs `docker compose -f e2e/compose.yaml run --rm --build e2e`
- **THEN** the e2e stack starts, and the tests start after it is ready
- **AND** the tests drive the UI in headless Chromium

#### Scenario: Real data stays untouched
- **GIVEN** the main stack runs with real Telegram data
- **WHEN** a developer runs the e2e tests
- **THEN** the e2e tests neither read nor change the data in `DATA_DIR`

#### Scenario: Repeated E2E run
- **GIVEN** an earlier e2e run changed chat settings in the running e2e stack
- **WHEN** a developer runs the e2e tests again without a restart
- **THEN** the tests give the same result

#### Scenario: Failure evidence
- **WHEN** an e2e test fails
- **THEN** its screenshot and trace are in `e2e/test-results/` on the host

## ADDED Requirements

### Requirement: Configuration in .env
The stack SHALL read `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`, `DATA_DIR`, and `DOWNLOADS_DIR` from `.env` in `dossier/`. The downloader and the backend SHALL mount `DATA_DIR` at `/data`, and the downloader SHALL mount `DOWNLOADS_DIR` at `/downloads`. When `DATA_DIR` or `DOWNLOADS_DIR` is unset, the stack SHALL use `./data` or `./downloads`. A committed `.env.example` SHALL list the keys, and git SHALL ignore `.env`, `data/`, and `downloads/`.

#### Scenario: Folders from .env
- **GIVEN** `.env` sets `DATA_DIR=/srv/dossier/data` and `DOWNLOADS_DIR=/srv/dossier/downloads`
- **WHEN** the downloader downloads a chat with media on
- **THEN** `messages.db` and `dossier_bot.session` are in `/srv/dossier/data`
- **AND** the media files are in `/srv/dossier/downloads`

#### Scenario: Missing key
- **GIVEN** `.env` lacks `TELEGRAM_API_ID`
- **WHEN** the downloader starts
- **THEN** it exits with a non-zero code and a message that names `TELEGRAM_API_ID`

### Requirement: Telegram login
`docker compose run --rm downloader login` SHALL ask for the login code that Telegram sends, and for the two-step password when the account has one. It SHALL store the session in `DATA_DIR`. When the session is not logged in, the `downloader` service SHALL exit with a non-zero code and a message that names the login command.

#### Scenario: First login
- **GIVEN** `DATA_DIR` holds no session
- **WHEN** a developer runs `docker compose run --rm downloader login` and types the code
- **THEN** `DATA_DIR` holds `dossier_bot.session`
- **AND** a later `docker compose up` starts the downloader without questions

#### Scenario: Not logged in
- **GIVEN** `DATA_DIR` holds no logged-in session
- **WHEN** the `downloader` service starts
- **THEN** it exits with a non-zero code and a message that names `docker compose run --rm downloader login`

#### Scenario: Session from bot.py
- **GIVEN** `DATA_DIR` holds a logged-in `dossier_bot.session` from `bot.py`
- **WHEN** the `downloader` service starts
- **THEN** it starts without asking for a login

### Requirement: Migrations before start
A one-shot `migrate` service SHALL upgrade `messages.db` to the newest schema version, and then exit. The `downloader` and `backend` services SHALL start only after `migrate` exits with code 0. No other service SHALL run migrations. The e2e stack SHALL migrate its own database in the same way.

#### Scenario: Stack starts on an empty data folder
- **GIVEN** `DATA_DIR` holds no `messages.db`
- **WHEN** a developer runs `docker compose up --build`
- **THEN** `migrate` creates `messages.db` with the newest schema and exits with code 0
- **AND** then the downloader and the backend start

#### Scenario: Migration fails
- **GIVEN** `DATA_DIR` holds a `messages.db` that is not an SQLite database
- **WHEN** a developer runs `docker compose up --build`
- **THEN** `migrate` exits with a non-zero code
- **AND** the downloader and the backend do not start

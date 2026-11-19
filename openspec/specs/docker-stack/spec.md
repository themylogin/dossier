# docker-stack Specification

## Purpose

Defines how the project builds, runs, and tests in Docker, so that the host needs only Docker with Compose.

## Requirements

### Requirement: One command serves the app
`docker compose up --build` in `dossier/` SHALL build and start the UI and the API. Both SHALL share one origin, `http://localhost:8080`, with the UI at `/` and the API under `/api/`.

#### Scenario: Stack starts
- **WHEN** a developer runs `docker compose up --build` in `dossier/`
- **THEN** `http://localhost:8080/` serves the UI
- **AND** the UI lists the chats from the API

### Requirement: Backend port
The backend SHALL listen on port 8080 inside its container. Other services SHALL reach it at `backend:8080`. The host SHALL NOT publish the backend port, because host port 8080 serves the UI.

#### Scenario: Backend inside the network
- **WHEN** a container in the Compose network sends `GET http://backend:8080/api/health`
- **THEN** the response has status 200 and the body `{"status": "ok"}`

### Requirement: Readiness check
`GET /api/health` SHALL return status 200 with the body `{"status": "ok"}`. Docker SHALL mark the `frontend` service healthy only when this request succeeds through the UI server.

#### Scenario: Health through the UI server
- **WHEN** a client sends `GET http://localhost:8080/api/health` to a running stack
- **THEN** the response has status 200 and the body `{"status": "ok"}`

#### Scenario: API down
- **WHEN** the `backend` service is stopped
- **THEN** Docker reports the `frontend` service as unhealthy

### Requirement: Unit tests in containers
`docker compose --profile test run --rm --build backend-test` SHALL run the backend tests. `docker compose --profile test run --rm --build frontend-test` SHALL run the UI unit tests. Each command SHALL exit with a non-zero code when a test fails.

#### Scenario: A backend test fails
- **WHEN** a backend test fails during `docker compose --profile test run --rm --build backend-test`
- **THEN** the command exits with a non-zero code

#### Scenario: All UI unit tests pass
- **WHEN** all UI unit tests pass during `docker compose --profile test run --rm --build frontend-test`
- **THEN** the command exits with code 0

### Requirement: E2E tests in headless Chromium
`docker compose --profile e2e run --rm --build e2e` SHALL start the stack when it is not running, and wait until the stack is ready. It SHALL then run the e2e tests in headless Chromium in a container, against the UI that the stack serves. The command SHALL exit with a non-zero code when a test fails.

#### Scenario: E2E run on a stopped stack
- **GIVEN** the stack is not running
- **WHEN** a developer runs `docker compose --profile e2e run --rm --build e2e`
- **THEN** the stack starts, and the tests start after the stack is ready
- **AND** the tests drive the UI in headless Chromium

#### Scenario: Repeated E2E run
- **GIVEN** an earlier e2e run changed chat settings in the running backend
- **WHEN** a developer runs the e2e tests again without a backend restart
- **THEN** the tests give the same result

#### Scenario: Failure evidence
- **WHEN** an e2e test fails
- **THEN** its screenshot and trace are in `e2e/test-results/` on the host

### Requirement: No host installs
Builds, dependency installs, lock file updates, and test runs SHALL happen in containers. The host SHALL need only Docker with Compose.

#### Scenario: Host without toolchains
- **GIVEN** a host with Docker and Compose, and no Node, Python, uv, or browser
- **WHEN** a developer runs the commands from `README.md`
- **THEN** each command succeeds

# Dossier

Dossier shows Telegram chats and the download progress of each chat. The backend is a FastAPI app. It serves a JSON-RPC 2.0 API over a WebSocket. A stub simulates the chat downloads until the real downloader moves in.

Everything runs in Docker. The host needs only Docker with Compose.

## Run

Start the UI and the API:

```sh
docker compose up --build
```

Then open http://localhost:8080.

Stop them:

```sh
docker compose down
```

## Test

Run the backend tests:

```sh
docker compose --profile test run --rm --build backend-test
```

Run the UI unit tests:

```sh
docker compose --profile test run --rm --build frontend-test
```

Run the end-to-end tests in headless Chromium. The command starts the stack when it is not running:

```sh
docker compose --profile e2e run --rm --build e2e
```

When an end-to-end test fails, its screenshot and trace are in `e2e/test-results/`.

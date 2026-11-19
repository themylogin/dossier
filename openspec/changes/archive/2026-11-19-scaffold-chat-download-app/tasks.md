# Tasks

All paths are relative to `dossier/`. Run every build, install, lock, and test step in a container.

## 1. Backend skeleton

- [x] 1.1 Create `backend/pyproject.toml` for Python 3.12 with `fastapi`, `uvicorn[standard]`, and `jsonrpcserver`. Add a dev group with `pytest` and `httpx2`. Run `uv lock` in the uv image. Verify that `ls backend` lists `uv.lock`.
- [x] 1.2 Write `backend/Dockerfile` with a runtime stage and a `test` stage, and make uvicorn listen on port 8080 (design 3). Add `backend/.dockerignore`. Create `compose.yaml` with the `backend` service and the `backend-test` service in the `test` profile. Verify that `docker compose --profile test build backend backend-test` succeeds.
- [x] 1.3 Add `create_app(step_seconds)` and `GET /api/health` in `backend/app/main.py`. Add a test for the health reply in `backend/tests/`. Check both new directories with `ls`. Verify that `docker compose --profile test run --rm --build backend-test` passes.
- [x] 1.4 Create `README.md` with a short overview and the `backend-test` command. Verify that the command runs as written.

## 2. Chat download API and stub

Each task adds its tests to `backend/tests/`. Each task is done when `docker compose --profile test run --rm --build backend-test` passes.

- [x] 2.1 Add the models and the store with four fake chats in `backend/app/chats.py`. Add the `/api/ws_jsonrpc` endpoint with `async_dispatch`, a methods dict from `create_app`, and `list_chats` (design 4). Verify with tests for "Response carries the request id", "Unknown method", "Client lists chats", "Chat fields", and "Backend start".
- [x] 2.2 Add `update_chat`. It validates the params in strict mode, stores the settings, sets the zero state, and returns the chat. Verify with tests for "Turn media on", "Turn media off", "Unknown chat", "Media is not a boolean", "No messages yet", and "Settings saved".
- [x] 2.3 Add the hub in `backend/app/progress.py` and the stub in `backend/app/stub_downloader.py` (design 5 and 6). Connect them to the endpoint, to `update_chat`, and to the lifespan. Verify with tests for "Full simulated download", "Dates carry an offset", "All chats download at start", "Two clients get the same progress", and "A client disconnects".
- [x] 2.4 Make `start` cancel the running task of the chat before it resets the state. Verify with tests for "Settings saved again during a download" and "Settings saved again after completion". In the "during a download" test, use a step that is long enough for the save to arrive mid-run.

## 3. Frontend

- [x] 3.1 Copy the UI files from `../telegram_ai/` into `frontend/`, as design 1 lists them. Check each new directory with `ls`. Verify that `diff -r ../telegram_ai/src frontend/src` shows no difference.
- [x] 3.2 Remove the `playwright` dev dependency from `frontend/package.json`. Rebuild `package-lock.json` with `npm install --package-lock-only` in a `node:24-alpine` container. Verify that the lock file has no `node_modules/playwright` entry.
- [x] 3.3 Write `frontend/Dockerfile` with the `deps` and `build` stages, and add `frontend/.dockerignore`. Add the `frontend-test` service with `TZ=UTC` to `compose.yaml` (design 9). Add its command to `README.md`. Verify that `docker compose --profile test run --rm --build frontend-test` passes all 65 unchanged tests. If a test fails, stop and report it before you edit any test.
- [x] 3.4 Add `frontend/src/dates.js` (design 1 and 7). Use it in `ChatListItem` and `ChatDetails`, and delete their own date code. Add tests for "Offset is applied", "Z and +00:00 show the same time", and "Missing or invalid date". Verify that `frontend-test` passes.
- [x] 3.5 Move `useChats`, `ChatListItem`, and `ChatDetails` to `settings` and `state`. Remove the "Please download the chat" branch. Change the dialog in `App.jsx` to one `Download Media` checkbox that sends `{"id", "settings": {"media"}}`. Move the 52 test fixtures to the new shape, and remove the 3 tests of the old on/off switch. Verify that `frontend-test` passes.
- [x] 3.6 Change `frontend/src/main.jsx` to build the WebSocket URL from `window.location` (design 1). Add the nginx runtime stage and `frontend/nginx.conf`, which forwards `/api/` to `backend:8080` (design 2). Add the `frontend` service with port `8080:80` and the health check. Add `docker compose up --build` and `docker compose down` to `README.md`. Run `docker compose up -d --build`, then verify these five results:
  - `docker compose ps` shows `frontend` as healthy.
  - `GET http://localhost:8080/api/health` from the host returns `{"status": "ok"}`.
  - `GET http://backend:8080/api/health` from a `backend-test` container returns `{"status": "ok"}`.
  - A Python WebSocket client in a `backend-test` container calls `list_chats` through `ws://frontend/api/ws_jsonrpc`. It gets four chats, each with `settings` and `state`.
  - The JavaScript bundle in the `frontend` container contains `/api/ws_jsonrpc` and does not contain `192.168.0.3`.
- [x] 3.7 Stop the `backend` service. Verify that `docker compose ps` shows `frontend` as unhealthy after the next health check. Start `backend` again. Verify that `frontend` becomes healthy again.

## 4. E2E tests in Chromium

- [x] 4.1 Create `e2e/package.json` with `@playwright/test` pinned to the newest stable version. Rebuild the lock file in a `node:24-alpine` container. Verify that `ls e2e` lists `package-lock.json`.
- [x] 4.2 Write `e2e/Dockerfile` from the official Playwright image with the same version. Add `e2e/.dockerignore` and `e2e/playwright.config.js` (design 8). Add the `e2e` service to `compose.yaml` (design 9). Verify that `docker compose --profile e2e build e2e` succeeds.
- [x] 4.3 Write e2e case 1 in `e2e/tests/chat-download.spec.js` (design 8). It covers "Chats appear", "Turn media on", "Progress arrives", and "Download completes". Check `e2e/tests/` with `ls`. Verify that `docker compose --profile e2e run --rm --build e2e` passes.
- [x] 4.4 Write e2e case 2 for "Dialog shows the saved value" (design 8). Add the e2e command to `README.md`. Verify that the e2e command passes two times in a row without a backend restart.
- [x] 4.5 Make one e2e assertion fail on purpose and run the e2e command. Verify that the command exits with a non-zero code. Verify that `e2e/test-results/` on the host holds a screenshot and a trace. Undo the change.
- [x] 4.6 With the stack running, change the name of one fake chat and run the e2e command. Verify that `docker compose ps` shows a new start time for `backend`. Undo the change. If `backend` did not restart, add `docker compose up -d --build` before the e2e command in `README.md`.

## 5. Integration check

- [x] 5.1 Run `docker compose --profile test --profile e2e down`. Then run each command from `README.md` in order. Verify that each command succeeds and that the host gets no new toolchain.
- [x] 5.2 Run `openspec validate scaffold-chat-download-app --strict` in `dossier/`. Verify that it reports the change as valid.

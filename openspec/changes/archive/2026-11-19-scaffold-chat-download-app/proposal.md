# Proposal

## Why

The `telegram_ai` UI lists Telegram chats and shows their download progress. It connects to a fixed LAN address (`192.168.0.3:8081`), and that backend is not in this workspace. `bot.py` downloads chats, but it reports progress to nobody. The `dossier` project puts the UI and a FastAPI backend into one Docker Compose stack. The backend gives the UI its progress API now. A stub takes the place of the real download until the `bot.py` logic moves in.

## What Changes

- A new Docker Compose project in `dossier/` with two services, `frontend` and `backend`. `docker compose up` serves both on one origin, `http://localhost:8080`.
- `frontend` is a copy of the `telegram_ai` UI (React, Vite). nginx serves the production build and forwards `/api/` to the backend, WebSocket included.
- The copied UI changes in four places:
  - It connects to `/api/ws_jsonrpc` on its own origin, not to the fixed LAN address.
  - The settings dialog has one checkbox, `Download Media`. Every chat downloads in full, as in `bot.py`.
  - Each chat carries `settings` and `state` in place of `download`.
  - The UI reads the UTC offset of each date. It no longer adds `Z` to dates.
- `backend` is a FastAPI app that listens on port 8080. Its JSON-RPC 2.0 WebSocket endpoint is `/api/ws_jsonrpc`, and the `jsonrpcserver` library dispatches the requests.
- `list_chats` returns `{"chats": [{"id", "name", "settings": {"media"}, "state"}]}`. `update_chat` takes `{"id", "settings": {"media"}}` and returns the updated chat.
- The backend sends `chat_download_progress` notifications to every connected UI.
- A stub downloader in the backend simulates the complete download of a chat in a few seconds. It runs for every chat at startup, and again for a chat after each `update_chat`. It has no Telegram connection and no storage. A short list of fake chats replaces the Telegram dialogs.
- **BREAKING** for the `telegram_ai` protocol: chats carry `settings` and `state` in place of `download`, and `update_chat` takes `settings` in place of `download`. The original `telegram_ai` UI does not work with this backend.
- Tests run only in Docker:
  - The `test` profile runs backend API tests (pytest) and the UI unit tests copied from `telegram_ai` (Vitest).
  - The `e2e` profile runs Playwright tests in headless Chromium against the running stack.
- The host needs only Docker. Containers generate the lock files.

## Capabilities

### New Capabilities
- `chat-download-api`: the JSON-RPC 2.0 WebSocket contract between the UI and the backend. It covers methods, notifications, data shapes, and errors.
- `chat-download`: how the backend produces the download state of a chat. In this change, a stub simulates it.
- `chat-download-ui`: what the UI shows for chats, their settings, and their download progress, and how the UI reaches the API.
- `docker-stack`: how the project runs and runs its tests in Docker, with no installs on the host.

### Modified Capabilities

None.

## Impact

- All new code is in `dossier/`: `compose.yaml`, `backend/`, `frontend/`, `e2e/`, and a short `README.md` with the commands.
- `telegram_ai/`, `telegram_ai_frontend/`, and `bot.py` stay unchanged.
- New base images: Python with uv (backend), Node (UI build and unit tests), nginx (UI serving), and the official Playwright image (e2e).
- New Python dependencies: `fastapi`, `uvicorn`, and `jsonrpcserver`.
- Host port 8080 serves the UI and the API through nginx. The backend listens on port 8080 inside the Compose network, and the host does not publish it.
- `settings.media` maps to the `chats.downloads_media` column of `bot.py`.
- Dates are ISO 8601 strings with a UTC offset. `bot.py` stores message dates in the same form (`+00:00`).

## Out of Scope

- The real chat download: Telethon login, `bot.py` integration, SQLite storage, media files.
- Turning the download of a chat off.
- Authentication.
- A Vite dev server with hot reload.
- The analytics UI in `telegram_ai_frontend/`.

## Assumptions

- The change copies the UI source into `dossier/frontend/`. The build does not read from `telegram_ai/`.
- The stub runs in the backend process. A later change decides where the real downloader runs: in the backend process or as its own service.
- Chat settings and progress live in memory. A backend restart resets them.
- Each `update_chat` restarts the simulated download of the chat from zero. Thus each e2e run is independent of earlier runs.
- Port 8080 is free on the host. Today no process listens on it.

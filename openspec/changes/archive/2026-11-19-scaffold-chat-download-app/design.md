# Design

## Context

See `proposal.md` for the motivation. These facts shape the approach:

- The `telegram_ai` UI (React 19, Vite 7) talks JSON-RPC 2.0 over one WebSocket through the `json-rpc-2.0` library. The library handles both directions.
- `src/main.jsx` hard-codes `ws://192.168.0.3:8081/ws_jsonrpc`.
- `useChats` calls `list_chats` when it connects. It applies `chat_download_progress` params to the chat with the same `id`.
- `App.jsx` calls `update_chat`, then calls `list_chats` again, then closes the dialog.
- `ChatListItem` and `ChatDetails` each hold their own date code. Both add `Z` to a date string that does not end with `Z`, so `+00:00` becomes the invalid `+00:00Z`.
- The UI has 65 Vitest tests in 5 files, and 52 test fixtures use the old `download` shape. The `playwright` dev dependency serves only the git-ignored `tmp/` scripts.
- `bot.py` downloads every private chat and group, with the oldest message first. It commits and logs every 100 messages.
- The `chats` table of `bot.py` has a `downloads_media` flag per chat. `bot.py` stores message dates with `isoformat()`, which writes `+00:00`.
- `bot.py` runs on Python 3.12 with Telethon.
- `dossier/` holds only `openspec/` and is not a git repository.
- `/root/work` is an NFS mount. New directories can list as empty to `ls` and to Docker.

## Goals / Non-Goals

**Goals:**
- Follow the data model of `bot.py`: every chat downloads, and each chat has one setting, `media`.
- Keep the endpoint path, the method names, and the notification name of the UI protocol.
- Make one seam for progress: the downloader stores a state and publishes it. The real downloader later uses the same seam.
- Keep tests fast and repeatable. Backend tests run the stub with short steps. E2E tests do not depend on earlier runs.

**Non-Goals:**
- Server-to-client requests that wait for a reply.
- Live sync of settings between browser tabs. Other tabs see new settings after their next `list_chats`.

## Decisions

### 1. Copy the UI and change four parts

Copy `src/`, `public/`, `index.html`, `package.json`, `package-lock.json`, and the Vite, Vitest, and ESLint configs into `frontend/`. Skip `node_modules/`, `dist/`, `tmp/`, `.git/`, and the Markdown docs, because they describe host `npm` commands. Remove the `playwright` dev dependency. A Node container rebuilds `package-lock.json`.

Then change four parts:

- **URL:** `src/main.jsx` builds the URL from `window.location`: `wss:` or `ws:`, then the page host, then `/api/ws_jsonrpc`.
- **Dates:** a new `src/dates.js` exports `formatDate` and `formatDateTime`. Both parse with `new Date(value)`, which reads the offset. Both return `?` for `null` or an invalid date. `ChatListItem` and `ChatDetails` use them and lose their own date code.
- **Chat shape:** `useChats` writes `params.state` to the `state` of the matching chat. `ChatListItem` and `ChatDetails` read `chat.state`. `ChatDetails` loses the "Please download the chat" branch and its link, because every chat downloads.
- **Dialog:** `App.jsx` shows one checkbox, `Download Media`, bound to `settings.media`. `Save` sends `{"id": <chat id>, "settings": {"media": <value>}}`.

Alternative: use `../telegram_ai` as the build context. Rejected: it ties two repositories together, and the UI needs edits anyway.

### 2. nginx serves the bundle and proxies the API

The frontend Dockerfile has three stages: `deps` (`npm ci` on Node 24 Alpine), `build` (sources and `npm run build`), and an nginx Alpine runtime. nginx serves the bundle with a fallback to `index.html`. It forwards `/api/` to `backend:8080` with the WebSocket upgrade headers and keeps the `/api` prefix.

The upstream host is in an nginx variable, with Docker DNS (`127.0.0.11`) as the resolver. Thus nginx starts before the backend exists, and it finds a recreated backend.

The `frontend` health check runs `wget` against `http://127.0.0.1/api/health`. One check thus covers nginx, the proxy, and the backend. Uvicorn pings each WebSocket every 20 seconds, so the nginx 60-second read timeout does not close idle UI connections.

Alternatives: a Vite dev server with a proxy, or FastAPI serving the bundle. Rejected: e2e tests must run against the production bundle, and the request names two separate apps.

### 3. Backend layout

The backend is FastAPI on uvicorn with the `standard` extra for WebSocket support. Uvicorn listens on port 8080. The backend uses Python 3.12 to match `bot.py`, and `jsonrpcserver` 5.2 for the protocol. uv manages `pyproject.toml` and `uv.lock` in the image. The Dockerfile has a runtime stage (`uv sync --locked --no-dev`) and a `test` stage with the dev group (pytest, httpx2).

- `app/main.py`: the app factory, the lifespan, `GET /api/health`, and the `/api/ws_jsonrpc` endpoint.
- `app/chats.py`: pydantic models for settings, state, and chats, and the in-memory store with four fake chats (two private, two groups). Each fake chat has a fixed first-message date.
- `app/progress.py`: the hub that sends `chat_download_progress` to every open socket.
- `app/stub_downloader.py`: the stub with `start(chat_id)` and `close()`.

`create_app(step_seconds)` builds the app. The module-level app uses 0.5 seconds. Tests use 0.01 seconds.

### 4. JSON-RPC with jsonrpcserver

The endpoint passes each text message to `async_dispatch`. It sends the reply back when the reply is not empty. The library returns an empty reply for a notification from the UI.

- `create_app` builds a dict of methods as closures over its own store and stub, and passes it to `async_dispatch`. The global `@method` registry stays unused, so each test app has its own store.
- The library answers parse errors (`-32700`), invalid requests (`-32600`), unknown methods (`-32601`), and params that do not fit the signature (`-32602`). It also handles batches.
- `update_chat` validates its params with pydantic in strict mode, so `"yes"` or `1` is not a boolean. A validation error returns `InvalidParams`, which gives `-32602` and `Invalid params`.
- An unknown chat id returns `Error(-32602, "Chat <id> not found")`.
- `uv.lock` pins the library version. Versions from 5.0.10 keep exception messages out of replies.

Alternatives:
- Hand-written dispatch. Rejected: the library covers parse errors and batches, which hand-written code skips.
- `openrpc`. Rejected: its README requires Python 3.14+.
- `fastapi-jsonrpc`. Rejected: it serves HTTP only.
- `fastapi-websocket-rpc`. Rejected: it has its own message format, which the `json-rpc-2.0` client of the UI cannot read.

### 5. Progress fan-out through a hub

The endpoint adds its socket to the hub on accept and removes it on disconnect. `publish(chat_id, state)` sends a notification without `id` to each socket. A failed send removes that socket. Everything runs on one event loop, so the hub needs no lock.

Alternatives: per-chat subscriptions, or server-to-client requests with ids. Rejected: the UI has no subscribe call, and its `{success: true}` replies carry no data.

### 6. Stub downloader: one task per chat

At startup, the lifespan calls `start` for every chat. At shutdown, it calls `close`, which cancels all tasks.

`update_chat` validates the params, stores the settings, calls `start`, and returns the chat. `start` first cancels the running task of the chat, then sets the zero state, then creates a new task. The cancel comes first, so an old task cannot overwrite the new state.

Each fake chat has a fixed first-message date, `first`. The task takes the start time in UTC, cut to whole seconds. For each step k from 1 to 10, it sleeps `step_seconds` and sets `newest = first + (start - first) × k / 10`. Then it stores `(100 × k, first, newest, k == 10)` and publishes it. The stub ignores `settings.media`.

The steps copy `bot.py`: oldest messages first, one progress point per 100 messages, and a final point at the end. The real downloader keeps `start` and `publish`, and replaces only the task body.

### 7. Dates with a UTC offset

The backend models hold timezone-aware UTC `datetime` values. Pydantic JSON mode writes them with `Z`. Real data from `bot.py` later comes with `+00:00`. Both forms carry the offset, and the UI reads both.

`src/dates.js` is the only date code in the UI (decision 1). The `frontend-test` service sets `TZ=UTC`, so tests of times are stable. A backend test checks that `datetime.fromisoformat` gives each date a time zone.

### 8. Tests

- Backend: pytest with Starlette `TestClient` WebSocket sessions against `create_app(0.01)`. The startup run sends notifications too, so each test reads up to its own reply and filters notifications by chat id.
- Backend: a `receive_json` call has no timeout. To prove that no notification comes, a test waits, sends `list_chats`, and asserts that the next message is its reply. Tests assert literal texts, such as `Chat 999 not found`.
- UI unit tests: first, the copied suite runs unchanged with `npm run test:run` in the `build` stage. Then the fixtures move to `settings` and `state`, and the 3 tests of the old on/off switch go away. New tests cover `src/dates.js`.
- E2E: `@playwright/test` runs in the official Playwright image, with one version for both. The config has one `chromium` project, `baseURL` `http://frontend`, locale `en-US`, timezone `UTC`, and one worker.
- E2E keeps traces and screenshots of failed tests in `test-results/`, which is bind-mounted to `e2e/test-results/`. The service sets `init: true` and `ipc: host`, as the Playwright Docker docs advise.
- E2E case 1: check `Download Media` for the first chat and save. Expect `⏳` and the "being downloaded" text, then `✓`, `(1,000)`, and `The chat is downloaded`.
- E2E case 2: clear `Download Media` and save, then reopen the dialog and expect a clear box. Check it and save, then reopen and expect a checked box.
- Each e2e case saves first, and each save restarts the stub. Thus state from earlier runs does not change the result.

### 9. Compose services and commands

| Service | Profile | Build | Role |
|---|---|---|---|
| `backend` | default | `backend/`, runtime stage | API on port 8080, not published |
| `frontend` | default | `frontend/`, runtime stage | Port `8080:80`, health check |
| `backend-test` | `test` | `backend/`, `test` stage | Runs `pytest` |
| `frontend-test` | `test` | `frontend/`, `build` stage | Runs `npm run test:run` with `TZ=UTC` |
| `e2e` | `e2e` | `e2e/` | Runs `npx playwright test` after `frontend` is healthy |

Test commands use the form `docker compose --profile <profile> run --rm --build <service>`. The ai-assistant project uses the same form. Compose applies `--build` to the dependency images too, and it recreates `frontend` or `backend` when their image changes.

Alternative for e2e: `docker compose up --exit-code-from e2e`. Rejected: it stops the whole stack after the run and mixes the logs of all services.

### 10. Lock files from containers

`uv lock` runs in the uv image. `npm install --package-lock-only` runs in the Node image for `frontend/` and `e2e/`. The host runs only `docker`.

## Risks / Trade-offs

- [`dossier/frontend/` and `telegram_ai/` drift apart] → `dossier/frontend/` is the copy that changes from now on. `telegram_ai/` stays as it is.
- [New directories on the NFS mount list as empty to Docker] → After you create `backend/app/`, `backend/tests/`, `frontend/src/`, and `e2e/tests/`, check each one with `ls`. Rename an empty-looking leaf directory away and back.
- [The copied Vitest suite has not run in this setup] → Run it unchanged first. Report failures before you edit a test.
- [The startup run adds notifications to every backend test] → Tests match replies by request id and notifications by chat id.
- [The Playwright image is about 2 GB] → The request asks for Chromium tests in Docker. One pinned version makes the download happen once.
- [`run --build` does not rebuild a running dependency] → Check it once during apply with a backend code change. If the check fails, the README tells the developer to run `docker compose up -d --build` before e2e.
- [Each `update_chat` restarts the simulated download] → This is stub behavior only. The real downloader continues from the last stored message, as `bot.py` does.

## Open Questions

- Where does the real downloader run: in the backend process (Telethon is asyncio) or as its own service that reports to the backend? The `start`/`publish` seam fits both.
- Does turning `media` on make the real downloader fetch media for messages that it already stored? Today `bot.py` fetches media only while it reads new messages.
- Does `list_chats` list channels? `bot.py` does not download channels, except the one media chat. The stub has no channels.

# Design

## Context

See `proposal.md` for the motivation. These facts shape the approach:

- OpenClaw Gateway: `POST /hooks/agent` takes JSON with a required `message` and the optional `name`, `agentId`, `deliver`, `model`, and `waitForCompletion`. Auth is `Authorization: Bearer <hooks.token>`. An `Idempotency-Key` header makes a retry safe. The body limit is 1 MiB, and there is no field for files. The answer is `{"ok": true, "runId": ...}`, which can take up to 15 seconds, and it never holds the agent's reply. Errors include `400`, `401`, `404` (hooks off or wrong path), `413`, and `429`.
- OpenClaw runs on its own machine. You share the export folder between the two machines, and its path can differ on each side.
- Dossier backend: `BackendApi` in `dossier/backend/api.py` holds every JSON-RPC method, and `create_app` in `main.py` wires them. Database calls run in `run_in_threadpool`. The engine of `dossier/database.py` opens each write transaction with `BEGIN IMMEDIATE`, so a long write on it would hold the lock that the downloader needs.
- `messages.db` uses WAL. The backend mounts `/data` read-write, so the `-shm` file is there for read-only readers.
- UI: `ChatDetails.jsx` renders the stats in two branches, for a downloading chat and for the rest. `useRPC().call(method, params, {timeout})` passes a timeout to the client, whose default is 30 seconds.
- The largest real chat has 336,550 messages.

## Goals / Non-Goals

**Goals:**

- A request reaches the agent with the chat as a SQLite file that the agent can query.
- The export never blocks the downloader.
- One place reads the OpenClaw settings, and a missing key gives one clear error.

**Non-Goals:**

- No reply in Dossier, no history of requests, and no cleanup of exports.
- No sharing of the folder between the machines. You set it up.

## Decisions

### 1. A shared folder and a short hook message

The backend writes the export into `/exports`, which is `OPENCLAW_EXPORT_DIR` on this machine. It sends only the request text and the path of the file under `OPENCLAW_EXPORT_PATH`, the same folder on the OpenClaw machine, in `message`. The agent opens the file with its own tools.

Alternatives:

- The rows inside `message`. Rejected: the 1 MiB body limit.
- A download link from the backend. Rejected: the OpenClaw machine would need a network path into the machine with your conversations.
- The OpenAI-compatible endpoints of the Gateway. Rejected: they are off by default, answer in the request, and take no SQLite file either.

### 2. The export: a new file, and a read-only attach of the source

`export_chat(chat_id, exports_dir, now)` in `dossier/backend/openclaw.py`:

1. Create `<chat id>-<YYYY-MM-DD_HH-MM-SS>.sqlite` in `exports_dir` with `Base.metadata.create_all`. The models hold exactly the four tables, so the export has the schema of `messages.db`.
2. Open the export with `sqlite3`, and `ATTACH 'file:/data/messages.db?mode=ro' AS source` with URI file names on.
3. In one transaction, copy with `INSERT INTO main.<table> (<columns>) SELECT <columns> FROM source.<table> WHERE ...`. The column lists come from the models. `chats` and `messages` and `message_versions` match on `chat_id`. `users` matches `user_id IN (SELECT sender_id FROM main.messages) OR user_id = <chat id>`.
4. Commit and close.

The write lock is on the export file only. The source is read-only, so the downloader keeps writing. The one transaction gives all four copies the same snapshot of the source.

The function takes the path of `messages.db` from the engine URL, so the tests can use a temporary database.

Alternative: `ATTACH` the export to a connection of the shared engine. Rejected: its `BEGIN IMMEDIATE` takes the write lock of `messages.db` for the whole copy, and the downloader then waits or fails.

Alternative: `sqlite3 .dump` with filters. Rejected: the stdlib has no filtered dump, and an export must keep the schema.

### 3. The Gateway call with `urllib.request`

`submit(settings, text, chat_name, chat_id, file_path)` builds the message and posts it:

```
<text>

The Telegram chat "<name>" (id <chat id>) is in the SQLite database <host path>. Its tables are chats, messages, message_versions (earlier versions of edited messages), and users.
```

The body is `{"message": ..., "name": "Dossier", "sessionMode": "persistent", "sessionKey": "dossier:<chat id>:<time>", "deliver": false}`, plus `"agentId"` when it is set. A new key per request gives each request a fresh conversation. `deliver: false` stops OpenClaw from posting the result into the agent's main session as a system notice, where the main agent would then answer it.

`session_url(settings, session_key)` builds the link to the session in the OpenClaw web UI: `<OPENCLAW_URL>/chat/<agent>/` and the parts of the key, one URL-encoded path segment each. `<agent>` is `OPENCLAW_AGENT_ID` or `main`. This follows the literal-key form of the OpenClaw Control UI URLs. The docs do not say how a hook session key maps under the agent, so the first live request confirms the link. The headers are `Authorization`, `Content-Type: application/json`, and `Idempotency-Key: <uuid4>`. The timeout is 60 seconds, which covers the 15-second admission. `HTTPError` becomes `OpenClaw rejected the request: HTTP <code>`. Any other `OSError` becomes `OpenClaw is unreachable: <reason>`. Both raise `OpenClawError`.

The call runs in `run_in_threadpool`, like the export.

Alternative: `httpx`. Rejected: it is only a dev dependency, and one POST does not need a new runtime dependency.

### 4. Settings

`OpenClawSettings` is a frozen dataclass with `url`, `token`, `agent_id`, and `export_path`, the folder on the OpenClaw machine. `load_openclaw_settings(environ)` returns `None` when `OPENCLAW_URL`, `OPENCLAW_HOOK_TOKEN`, or `OPENCLAW_EXPORT_PATH` is empty. `main.py` reads it from `os.environ` and passes it to `create_app`, which passes it to `BackendApi`. The container path `/exports` is fixed, as `/data` is. `create_app` gets the exports folder as an argument, so the tests can use a temporary folder.

### 5. `submit_request`

In `BackendApi`:

1. Validate `{"id": StrictInt, "text": StrictStr}` with a pydantic model, and reject blank text. Both give `InvalidParams()`.
2. Read the chat. A missing chat gives `Error(-32602, "Chat <id> not found")`.
3. With no settings, return `Error(-32000, "OpenClaw is not configured")`.
4. Export, then submit, both in the thread pool. `OpenClawError` and `sqlite3.Error` give `Error(-32000, <message>)`.
5. Return `{"run_id": ..., "file": ..., "session_url": ...}`. One `now` gives the time of both the file name and the session key.

### 6. The form in the details panel

`RequestForm` in `ChatDetails.jsx` renders a `textarea` and a `Submit` button below the stats of both branches. It keeps the text, a sending flag, and a status line. `App.jsx` passes `onSubmitRequest(chatId, text)`, which calls `submit_request` with a timeout of 120 seconds. `ChatDetails` renders the form with `key={chat.id}`, so a new chat starts with an empty form.

### 7. Compose and `.env`

The backend gets `OPENCLAW_URL`, `OPENCLAW_HOOK_TOKEN`, `OPENCLAW_AGENT_ID`, and `OPENCLAW_EXPORT_PATH` with empty defaults, and the volume `${OPENCLAW_EXPORT_DIR:-./exports}:/exports`. It gets no host entry and no other network access. `.env.example` lists the five keys, and `.gitignore` adds `/exports/`.

### 8. Tests

- Backend: a fake Gateway, an `http.server` in a thread, records each request and answers with a set status. Tests cover each scenario of `openclaw-requests` and of `Submit a request`. They open the export with `sqlite3` and check its rows.
- UI: `ChatDetails.test.jsx` covers the three scenarios of `Request form` with a mocked `onSubmitRequest`.
- E2E: the e2e stack has no OpenClaw, so a test submits a request and expects `OpenClaw is not configured`. This proves the wiring from the form to the backend.

## Risks / Trade-offs

- [The Gateway call leaves this machine] → It carries only your text and the path. The chat itself goes only through the folder that you share.
- [The backend writes the export as root] → The agent can read it, with mode `0644`, but cannot delete it. Exports stay until you delete them.
- [A large chat takes seconds to export] → The copy runs in the thread pool. The UI waits up to 2 minutes.
- [The agent has no SQLite tool] → The message names the format, and the agent can use Python. This stays with your OpenClaw setup.

## Migration Plan

- Set the keys in `.env` as in `README.md`, then `docker compose up --build`. No schema change.
- Rollback: deploy the previous image. Exports stay in the folder.

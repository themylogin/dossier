# Proposal

## Why

You want to hand one downloaded chat to your OpenClaw agent with a request in plain text, such as "Summarize the decisions in this group", and let the agent do the work. Dossier holds the chat, and OpenClaw holds the agent, but nothing connects them.

OpenClaw accepts outside requests through `POST /hooks/agent` on its Gateway. The body is JSON with a text `message`, capped at 1 MiB, and with no file attachments. A large chat is far bigger than that. The real database holds a group with 336,550 messages. So the chat must reach OpenClaw as a file in a folder that both can read, and the request only names the file.

## What Changes

- The details panel of a selected chat gets a request form below its stats: a multiline text field and a `Submit` button.
- On `Submit`, the backend writes a new SQLite file with only that chat: its `chats` row, its messages, their earlier versions, and the users who sent them or who are the chat. The file goes into a folder that you share with the OpenClaw machine.
- The backend then calls `POST /hooks/agent` on the OpenClaw Gateway. The message holds your text and the path of the file.
- Each request runs in a new OpenClaw session named `dossier:<chat id>:<time>`, with no delivery to other sessions or channels. The UI shows that OpenClaw accepted the request and a link that opens the session in the OpenClaw web UI, where you read the answer and continue the conversation. On failure, it shows the error.
- New keys in `.env`: `OPENCLAW_URL`, `OPENCLAW_HOOK_TOKEN`, `OPENCLAW_AGENT_ID` (optional), `OPENCLAW_EXPORT_DIR` (the shared folder on this machine), and `OPENCLAW_EXPORT_PATH` (the same folder as the agent sees it). Without `OPENCLAW_URL`, `OPENCLAW_HOOK_TOKEN`, and `OPENCLAW_EXPORT_PATH`, `Submit` reports that OpenClaw is not configured.
- `README.md` lists the `.env` keys.

## Capabilities

### New Capabilities

- `openclaw-requests`: the chat export into the shared folder and the submission to the OpenClaw Gateway.

### Modified Capabilities

- `chat-download-api`: the new `submit_request` method.
- `chat-download-ui`: the request form in the details panel.
- `docker-stack`: the OpenClaw keys in `.env`, and the shared folder mounted into the backend.

## Impact

- `dossier/backend/openclaw.py` (new): the export and the Gateway call. `dossier/backend/api.py`: the `submit_request` method. `dossier/backend/main.py`: the method in the dispatch table.
- `frontend/src/components/ChatDetails.jsx` and `App.jsx`: the form and the call.
- `compose.yaml`, `.env.example`, and `README.md`.
- Tests in `tests/backend/`, `frontend/src/components/`, and `e2e/tests/`.
- No new Python dependency. The Gateway call uses `urllib.request`.
- No change to the downloader or the database schema.

## Out of Scope

- The agent's answer in Dossier. OpenClaw returns a run id, never the reply, so you read it in the OpenClaw web UI.
- Media files. The export holds the database rows only.
- Removal of old exports. Each submit writes a new file, and the folder keeps them.
- The sharing of the folder between the machines. You set it up, and Dossier only writes into its side.

## Assumptions

- OpenClaw runs on its own machine. You share the export folder between the two machines, and `OPENCLAW_EXPORT_PATH` is its path on the OpenClaw machine.
- The agent has a tool that reads a SQLite file, such as `sqlite3` or Python.
- The OpenClaw config allows request-chosen session keys with the prefix `dossier:` (`hooks.allowRequestSessionKey` and `hooks.allowedSessionKeyPrefixes`).
- The OpenClaw web UI is served at `OPENCLAW_URL`, and it shows a session `dossier:<chat id>:<time>` of agent `<agent>` at `/chat/<agent>/dossier/<chat id>/<time>`. The first live request confirms this.

# openclaw-requests Specification

## Purpose

Defines how Dossier hands one chat and a text request to an OpenClaw agent: the export of the chat into a shared folder, and the call to the OpenClaw Gateway.

## Requirements

### Requirement: Chat export
For each request, the backend SHALL write a new SQLite file named `<chat id>-<YYYY-MM-DD_HH-MM-SS>.sqlite`, in UTC, into the shared folder. The file SHALL have the tables `chats`, `messages`, `message_versions`, and `users`, with the columns of `messages.db`. It SHALL hold only the rows of the chat: its `chats` row, its messages and their earlier versions, and the users who sent them or whose id is the chat id.

#### Scenario: Group export
- **GIVEN** the database holds chats `-2001` and `-2002`, with 3 messages each, and the messages of `-2001` come from users 77 and 78
- **WHEN** a request for chat `-2001` arrives at `2026-05-22T10:30:00+00:00`
- **THEN** the shared folder holds `-2001-2026-05-22_10-30-00.sqlite`
- **AND** the file holds chat `-2001`, its 3 messages, and users 77 and 78, and no row of chat `-2002`

#### Scenario: Private chat export
- **GIVEN** chat `1001` is a private chat with user `1001`, and no message of the chat has a sender
- **WHEN** a request for chat `1001` arrives
- **THEN** the file holds user `1001`

#### Scenario: Edited message
- **GIVEN** message 5 of chat `-2001` has an earlier version in `message_versions`
- **WHEN** a request for chat `-2001` arrives
- **THEN** the file holds that earlier version

### Requirement: Submission to the OpenClaw Gateway
After the export, the backend SHALL send `POST <OPENCLAW_URL>/hooks/agent` with `Authorization: Bearer <OPENCLAW_HOOK_TOKEN>`, a new `Idempotency-Key`, and a JSON body: `name` `Dossier`, `agentId` when `OPENCLAW_AGENT_ID` is set, the fields of `Session per request`, and `message`. `message` SHALL be the request text, then a paragraph that names the chat, its id, and the file path under `OPENCLAW_EXPORT_PATH`. The backend SHALL return the `runId`, that path, and the session link.

#### Scenario: Request admitted
- **GIVEN** OpenClaw is configured with `OPENCLAW_EXPORT_PATH` `/home/me/.openclaw/workspace/dossier`
- **WHEN** a request with the text `Summarize the decisions` for chat `-2001` "Family" arrives at `2026-05-22T10:30:00+00:00`, and the Gateway answers `{"ok": true, "runId": "run-1"}`
- **THEN** the message starts with `Summarize the decisions`
- **AND** it names "Family", `-2001`, and `/home/me/.openclaw/workspace/dossier/-2001-2026-05-22_10-30-00.sqlite`
- **AND** the backend returns `run-1`, that path, and the session link

#### Scenario: Agent selected
- **GIVEN** `OPENCLAW_AGENT_ID` is `research`
- **WHEN** a request arrives
- **THEN** the body has `"agentId": "research"`

### Requirement: Session per request
Each request SHALL run in a new OpenClaw session. The body SHALL have `sessionMode` `persistent`, `sessionKey` `dossier:<chat id>:<YYYY-MM-DD_HH-MM-SS>` with the time of the export, and `deliver` `false`, so that OpenClaw posts nothing into other sessions or channels. The session link SHALL be `<OPENCLAW_URL>/chat/<agent>/dossier/<chat id>/<time>`, where `<agent>` is `OPENCLAW_AGENT_ID` or `main`.

#### Scenario: Session fields
- **GIVEN** `OPENCLAW_URL` is `https://openclaw.example.com` and `OPENCLAW_AGENT_ID` is empty
- **WHEN** a request for chat `-2001` arrives at `2026-05-22T10:30:00+00:00`
- **THEN** the body has `"sessionMode": "persistent"`, `"sessionKey": "dossier:-2001:2026-05-22_10-30-00"`, and `"deliver": false`
- **AND** the session link is `https://openclaw.example.com/chat/main/dossier/-2001/2026-05-22_10-30-00`

#### Scenario: Two requests
- **WHEN** two requests for chat `-2001` arrive one minute apart
- **THEN** they have two different session keys

### Requirement: Request errors
The backend SHALL refuse a request when `OPENCLAW_URL`, `OPENCLAW_HOOK_TOKEN`, or `OPENCLAW_EXPORT_PATH` is not set, and then write no file and call no Gateway. When the Gateway answers with an HTTP error, or cannot be reached, the backend SHALL return an error that names the cause. The file of such a request SHALL stay in the folder.

#### Scenario: Not configured
- **GIVEN** `.env` does not set `OPENCLAW_HOOK_TOKEN`
- **WHEN** a request arrives
- **THEN** the backend returns the error `OpenClaw is not configured`
- **AND** the shared folder gets no file

#### Scenario: Wrong token
- **WHEN** the Gateway answers `401`
- **THEN** the backend returns the error `OpenClaw rejected the request: HTTP 401`

#### Scenario: Gateway down
- **WHEN** the backend cannot connect to `OPENCLAW_URL`
- **THEN** the backend returns an error that starts with `OpenClaw is unreachable:`

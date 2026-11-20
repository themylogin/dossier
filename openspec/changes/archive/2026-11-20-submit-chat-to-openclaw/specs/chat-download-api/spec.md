# Spec Delta

## ADDED Requirements

### Requirement: Submit a request
The `submit_request` method SHALL take `{"id": <chat id>, "text": <request text>}`. It SHALL export the chat and send the request to OpenClaw, by the rules of `openclaw-requests`, and return `{"run_id", "file", "session_url"}`: the run id, the path of the export under `OPENCLAW_EXPORT_PATH`, and the link to the session. Blank or non-string text and an unknown chat SHALL get `-32602`. A failed export or submission SHALL get `-32000` with the message of the failure.

#### Scenario: Request submitted
- **WHEN** a client calls `submit_request` with a known chat id and `"text": "Summarize the decisions"`, and the Gateway admits the run `run-1`
- **THEN** the result is `{"run_id": "run-1", "file": <path>, "session_url": <link>}`

#### Scenario: Blank text
- **WHEN** a client calls `submit_request` with `"text": "  \n "`
- **THEN** the backend replies with `-32602` and `Invalid params`
- **AND** it writes no file

#### Scenario: Unknown chat
- **WHEN** a client calls `submit_request` with `"id": 999` and no chat has that id
- **THEN** the backend replies with `-32602` and `Chat 999 not found`

#### Scenario: OpenClaw not configured
- **GIVEN** `.env` sets no OpenClaw keys
- **WHEN** a client calls `submit_request` for a known chat
- **THEN** the backend replies with `-32000` and `OpenClaw is not configured`

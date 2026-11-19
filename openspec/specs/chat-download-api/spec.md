# chat-download-api Specification

## Purpose

Defines the JSON-RPC 2.0 WebSocket contract that the UI uses to list chats, change chat settings, and receive download progress.

## Requirements

### Requirement: JSON-RPC endpoint
The backend SHALL accept WebSocket connections at `/api/ws_jsonrpc`. Each text message SHALL carry one JSON-RPC 2.0 object. The backend SHALL answer each request that has an `id` with one response that carries the same `id`.

#### Scenario: Response carries the request id
- **WHEN** a client sends `{"jsonrpc": "2.0", "method": "list_chats", "id": 7}`
- **THEN** the backend replies with a JSON-RPC 2.0 response with `"id": 7`

#### Scenario: Unknown method
- **WHEN** a client sends a request with method `rename_chat` and `"id": 8`
- **THEN** the backend replies with `"id": 8` and an error with code `-32601` and message `Method not found`
- **AND** the connection stays open

### Requirement: Chat object
Each chat that the backend sends SHALL have `id` (the Telegram chat id, an integer), `name` (a string), `settings`, and `state`. `settings` SHALL be `{"media": <boolean>}`, where `media` tells whether the backend downloads the media of the chat. `state` SHALL be a download state.

#### Scenario: Chat fields
- **WHEN** the backend sends a chat
- **THEN** the chat object has the members `id`, `name`, `settings`, and `state`
- **AND** `settings` has one member, `media`, with a boolean value
- **AND** `state` has the members `messages_count`, `oldest_message_date`, `newest_message_date`, and `complete`

### Requirement: Download state format
A download state SHALL have `messages_count` (an integer), `oldest_message_date` and `newest_message_date` (a string or `null`), and `complete` (a boolean). Each date SHALL be an ISO 8601 date-time with a UTC offset, such as `2026-05-22T10:30:00+00:00` or `2026-05-22T10:30:00Z`.

#### Scenario: Dates carry an offset
- **WHEN** the backend sends a download state that has dates
- **THEN** each date parses as an ISO 8601 date-time with a UTC offset

#### Scenario: No messages yet
- **WHEN** the backend sends the state of a download that has no messages yet
- **THEN** `messages_count` is `0` and both dates are `null`

### Requirement: List chats
The `list_chats` method SHALL take no params. It SHALL return `{"chats": [...]}` with every known chat, its current settings, and its latest download state.

#### Scenario: Client lists chats
- **WHEN** a client calls `list_chats` without params
- **THEN** the result is an object with one member, `chats`
- **AND** `chats` holds every known chat with its current settings and latest state

### Requirement: Update chat settings
The `update_chat` method SHALL take `{"id": <chat id>, "settings": {"media": <boolean>}}`. It SHALL store the settings and return the updated chat object.

#### Scenario: Turn media on
- **WHEN** a client calls `update_chat` with a known chat id and `"settings": {"media": true}`
- **THEN** the result is the chat object with `"settings": {"media": true}`
- **AND** a later `list_chats` shows `"settings": {"media": true}` for the chat

#### Scenario: Turn media off
- **GIVEN** a chat has `"settings": {"media": true}`
- **WHEN** a client calls `update_chat` with the chat id and `"settings": {"media": false}`
- **THEN** the result is the chat object with `"settings": {"media": false}`

#### Scenario: Unknown chat
- **WHEN** a client calls `update_chat` with `"id": 999` and no chat has that id
- **THEN** the backend replies with an error with code `-32602` and message `Chat 999 not found`

#### Scenario: Media is not a boolean
- **WHEN** a client calls `update_chat` with `"settings": {"media": "yes"}`
- **THEN** the backend replies with an error with code `-32602` and message `Invalid params`
- **AND** the chat keeps its earlier settings

### Requirement: Progress notifications
When the download state of a chat changes, the backend SHALL send a `chat_download_progress` notification to every open connection. The notification SHALL have no `id`. Its params SHALL be `{"id": <chat id>, "state": <download state>}`.

#### Scenario: Two clients get the same progress
- **GIVEN** two clients have open connections
- **WHEN** the download state of a chat changes
- **THEN** each client receives `{"jsonrpc": "2.0", "method": "chat_download_progress", "params": {"id": <chat id>, "state": <new state>}}`

#### Scenario: A client disconnects
- **GIVEN** two clients have open connections
- **WHEN** one client closes its connection and then the download state of a chat changes
- **THEN** the other client still receives the notification

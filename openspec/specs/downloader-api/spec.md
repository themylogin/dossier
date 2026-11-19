# downloader-api Specification

## Purpose

Defines the WebSocket contract between the downloader and the backend: chat states from the downloader, and settings notices from the backend.

## Requirements

### Requirement: Downloader endpoint
The downloader SHALL accept WebSocket connections on port 8090 inside the Compose network, at `ws://downloader:8090/`. Each text message in either direction SHALL carry one JSON-RPC 2.0 notification, with no `id`. The host SHALL NOT publish the port.

#### Scenario: Backend connects
- **WHEN** the backend opens `ws://downloader:8090/`
- **THEN** the downloader accepts the connection

### Requirement: State snapshot on connect
On each new connection, the downloader SHALL first send `chat_states` with params `{"chats": [{"id": <chat id>, "state": <download state>}, ...]}` for every chat that it knows. A download state SHALL have the same format as in the UI API.

#### Scenario: First message after connect
- **GIVEN** the downloader knows 3 chats
- **WHEN** the backend connects
- **THEN** the first message is `chat_states` with 3 entries

### Requirement: State updates
After the snapshot, the downloader SHALL send `chat_download_progress` with params `{"id": <chat id>, "state": <download state>}` to every open connection when the state of a chat changes.

#### Scenario: Two connections
- **GIVEN** two connections are open
- **WHEN** the state of a chat changes
- **THEN** each connection receives `chat_download_progress` with the new state

### Requirement: Settings notice
After the backend stores new settings for a chat, it SHALL send `settings_changed` with params `{"id": <chat id>}` to the downloader.

#### Scenario: Media turned on
- **WHEN** a UI client calls `update_chat` with `"settings": {"media": true}` for a chat
- **THEN** the backend stores the setting in the database
- **AND** then it sends `settings_changed` with the chat id to the downloader

### Requirement: Backend link
The backend SHALL connect to the downloader when it starts, and connect again one second after it loses the connection. It SHALL keep the latest state of each chat from the snapshot and the updates. It SHALL send each state that it receives to the UI clients as `chat_download_progress`.

#### Scenario: Downloader restarts
- **GIVEN** the backend has a link to the downloader
- **WHEN** the downloader restarts
- **THEN** the backend connects again
- **AND** it sends the states from the new snapshot to the UI clients

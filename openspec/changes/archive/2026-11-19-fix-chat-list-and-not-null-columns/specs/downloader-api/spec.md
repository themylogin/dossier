# Spec Delta

## MODIFIED Requirements

### Requirement: Backend link
The backend SHALL connect to the downloader when it starts, and connect again one second after it loses the connection. While the connection lasts, it SHALL keep the latest state of each chat from the snapshot and the updates. It SHALL send each state that it receives to the UI clients as `chat_download_progress`. When it loses the connection, it SHALL drop the kept states, and send the stored state of each affected chat to the UI clients.

#### Scenario: Downloader restarts
- **GIVEN** the backend has a link to the downloader
- **WHEN** the downloader restarts
- **THEN** the backend connects again
- **AND** it sends the states from the new snapshot to the UI clients

#### Scenario: Downloader stops
- **GIVEN** the downloader reported a chat with `"complete": true`
- **WHEN** the backend loses the connection to the downloader
- **THEN** the UI clients receive `chat_download_progress` for the chat with `"complete": null`
- **AND** a later `list_chats` shows the chat with `"complete": null`

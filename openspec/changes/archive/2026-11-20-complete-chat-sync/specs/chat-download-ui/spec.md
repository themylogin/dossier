# Spec Delta

## ADDED Requirements

### Requirement: Media progress
When the chat has media on and `files_count` plus `files_pending` is above 0, the list item SHALL show `📎 <files_count>/<files_count + files_pending>` after the message count, and the details panel SHALL show a `Files:` row with the same two numbers. Both numbers SHALL use the number format of the browser locale. Otherwise, the UI SHALL show no media progress. Each `chat_download_progress` notification SHALL update it without a page reload.

#### Scenario: Files in progress
- **GIVEN** the browser locale is `en-US`
- **WHEN** the UI receives `chat_download_progress` for the selected chat with `"files_count": 1200` and `"files_pending": 300`
- **THEN** the list item shows `📎 1,200/1,500`
- **AND** the details panel shows `Files:` and `1,200/1,500`

#### Scenario: No media
- **WHEN** a chat has `"files_count": 0` and `"files_pending": 0`
- **THEN** neither the list item nor the details panel shows `📎` or `Files:`

#### Scenario: Media off
- **GIVEN** a chat has `"settings": {"media": false}`
- **WHEN** its state has `"files_count": 1200` and `"files_pending": 300`
- **THEN** neither the list item nor the details panel shows `📎` or `Files:`

### Requirement: Oldest date while downloading
While a state has `"downloaded": false`, the list item and the details panel SHALL show the date range from the oldest to the newest stored message. When a state has `"downloaded": true`, the list item SHALL show only the newest date and the message count, and the details panel SHALL show `Newest message:` with the newest date in place of `Date range:`.

#### Scenario: Chat downloading
- **GIVEN** the browser time zone is UTC
- **WHEN** a state has `"downloaded": false`, `oldest_message_date` `2024-01-01T00:00:00Z`, and `newest_message_date` `2024-01-24T00:00:00Z`
- **THEN** the list item shows `Jan 1, 2024 - Jan 24, 2024`
- **AND** the details panel shows `Date range:`

#### Scenario: Chat downloaded
- **GIVEN** the browser time zone is UTC
- **WHEN** a state has `"downloaded": true`, `oldest_message_date` `2024-01-01T00:00:00Z`, and `newest_message_date` `2024-01-24T00:00:00Z`
- **THEN** the list item shows `Jan 24, 2024` and not `Jan 1, 2024`
- **AND** the details panel shows `Newest message:` and `Jan 24, 2024`, and no `Date range:`

## MODIFIED Requirements

### Requirement: Chat list
After it connects, the UI SHALL load the chats with `list_chats` and show one list item per chat. Each list item SHALL show the download line of its chat: the download status, the date range or, for a downloaded chat, the newest date, and the message count. The status SHALL be `⏳` for `"complete": false` and `✓` for `"complete": true`. A state with `"complete": null` SHALL show no status.

#### Scenario: Chats appear
- **WHEN** the UI connects to the backend
- **THEN** the list shows one item for each chat from `list_chats`
- **AND** each item shows the dates and the message count under the chat name


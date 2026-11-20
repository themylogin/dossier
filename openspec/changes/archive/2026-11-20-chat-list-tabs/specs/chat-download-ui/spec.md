# Spec Delta

## ADDED Requirements

### Requirement: Chat tabs
The UI SHALL show tabs over the chat list, in this order: `All` with every chat, `Downloaded` with the chats whose state has `"downloaded": true`, and `Downloading` with the other chats. `Downloading` SHALL show only while it holds at least one chat. Each tab SHALL show its number of chats. `All` SHALL be active on load. When the active tab disappears, `All` SHALL become active.

#### Scenario: Tabs while a chat downloads
- **GIVEN** `list_chats` returns 3 chats, and 1 of them has `"downloaded": true`
- **WHEN** the UI shows the list
- **THEN** the tabs are `All` with 3, `Downloaded` with 1, and `Downloading` with 2
- **AND** `All` is active, and the list shows the 3 chats

#### Scenario: Tab selected
- **GIVEN** the tabs show `Downloaded` with 1 chat
- **WHEN** the user clicks `Downloaded`
- **THEN** the list shows only that chat

#### Scenario: Last chat downloaded
- **GIVEN** `Downloading` is active and holds 1 chat
- **WHEN** a notification gives that chat `"downloaded": true`
- **THEN** the `Downloading` tab disappears
- **AND** `All` becomes active

#### Scenario: New message
- **GIVEN** a chat with `"downloaded": true` is in `Downloaded`
- **WHEN** a notification gives the chat `"complete": false` for a new message
- **THEN** the chat stays in `Downloaded`

## MODIFIED Requirements

### Requirement: Chat list
After it connects, the UI SHALL load the chats with `list_chats` and show one list item per chat. Each list item SHALL show the download line of its chat: the download status, and the date range or, for a downloaded chat, the newest date. The list item SHALL NOT show the message count or the file count. The status SHALL be `⏳` for `"complete": false` and `✓` for `"complete": true`. A state with `"complete": null` SHALL show no status.

#### Scenario: Chats appear
- **WHEN** the UI connects to the backend
- **THEN** the list shows one item for each chat from `list_chats`
- **AND** each item shows the dates under the chat name, and no message count

### Requirement: Live download progress
The UI SHALL apply each `chat_download_progress` notification to the matching chat without a page reload. While the download runs, the list item SHALL show `⏳` and the date range. The details panel SHALL show `The chat is being downloaded, please wait...` and the message count.

#### Scenario: Progress arrives
- **WHEN** the UI receives `chat_download_progress` for the selected chat with `"complete": false`
- **THEN** the list item shows `⏳` and the date range
- **AND** the details panel shows `The chat is being downloaded, please wait...` and the message count

### Requirement: Download completion
When a notification has `"complete": true`, the list item SHALL show `✓` in place of `⏳`. The details panel SHALL show `The chat is downloaded` and the message count.

#### Scenario: Download completes
- **GIVEN** the browser locale is `en-US`
- **WHEN** the UI receives `chat_download_progress` for the selected chat with `"complete": true` and `"messages_count": 1000`
- **THEN** the list item shows `✓` and not `1,000`
- **AND** the details panel shows `The chat is downloaded` and `1,000`

### Requirement: Media progress
When the chat has media on and `files_count` plus `files_pending` is above 0, the details panel SHALL show a `Files:` row with `<files_count>/<files_count + files_pending>`. Both numbers SHALL use the number format of the browser locale. Otherwise, the details panel SHALL show no `Files:` row. The list item SHALL NOT show the media progress. Each `chat_download_progress` notification SHALL update it without a page reload.

#### Scenario: Files in progress
- **GIVEN** the browser locale is `en-US`, and the chat has media on
- **WHEN** the UI receives `chat_download_progress` for the selected chat with `"files_count": 1200` and `"files_pending": 300`
- **THEN** the details panel shows `Files:` and `1,200/1,500`
- **AND** the list item shows no `📎`

#### Scenario: No media
- **WHEN** a chat has `"files_count": 0` and `"files_pending": 0`
- **THEN** the details panel shows no `Files:`

#### Scenario: Media off
- **GIVEN** a chat has `"settings": {"media": false}`
- **WHEN** its state has `"files_count": 1200` and `"files_pending": 300`
- **THEN** the details panel shows no `Files:`

### Requirement: Oldest date while downloading
While a state has `"downloaded": false`, the list item and the details panel SHALL show the date range from the oldest to the newest stored message. When a state has `"downloaded": true`, the list item SHALL show only the newest date, and the details panel SHALL show `Newest message:` with the newest date in place of `Date range:`.

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

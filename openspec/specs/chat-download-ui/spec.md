# chat-download-ui Specification

## Purpose

Defines what the browser UI shows for chats, their settings, and their download progress, and how the UI reaches the API.

## Requirements

### Requirement: Same-origin API connection
The UI SHALL open its WebSocket to `/api/ws_jsonrpc` on the host that served the page. It SHALL use `wss:` for pages served over `https:`, and `ws:` for all other pages.

#### Scenario: Page from localhost:8080
- **WHEN** the browser loads `http://localhost:8080/`
- **THEN** the UI connects to `ws://localhost:8080/api/ws_jsonrpc`

### Requirement: Chat list
After it connects, the UI SHALL load the chats with `list_chats` and show one list item per chat. Each list item SHALL show the download line of its chat: the download status, and the date range or, for a downloaded chat, the newest date. The list item SHALL NOT show the message count or the file count. The status SHALL be `⏳` for `"complete": false` and `✓` for `"complete": true`. A state with `"complete": null` SHALL show no status.

#### Scenario: Chats appear
- **WHEN** the UI connects to the backend
- **THEN** the list shows one item for each chat from `list_chats`
- **AND** each item shows the dates under the chat name, and no message count

### Requirement: Download settings dialog
The `Download Settings` item of the chat context menu SHALL open a dialog with one checkbox, `Download Media`. The checkbox SHALL show the `settings.media` value of the chat. `Save` SHALL call `update_chat` with the chat id and `{"media": <checkbox value>}` as `settings`. On success, the UI SHALL close the dialog and reload the chat list.

#### Scenario: Turn media on
- **GIVEN** a chat has `"settings": {"media": false}`
- **WHEN** the user right-clicks the chat, selects `Download Settings`, checks `Download Media`, and clicks `Save`
- **THEN** the UI calls `update_chat` with `{"id": <chat id>, "settings": {"media": true}}`
- **AND** the dialog closes

#### Scenario: Dialog shows the saved value
- **GIVEN** the user saved `Download Media` as checked for a chat
- **WHEN** the user opens `Download Settings` for the chat again
- **THEN** `Download Media` is checked

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

### Requirement: Date display
The UI SHALL read the UTC offset of each date and show the date in the time zone of the browser. A missing or invalid date SHALL show as `?`.

#### Scenario: Offset is applied
- **GIVEN** the browser time zone is UTC
- **WHEN** a state has `newest_message_date` `2026-05-22T10:30:00+02:00`
- **THEN** the list item shows `May 22, 2026, 08:30` as the newest date

#### Scenario: Z and +00:00 show the same time
- **GIVEN** the browser time zone is UTC
- **WHEN** one state has `newest_message_date` `2026-05-22T10:30:00Z` and another has `2026-05-22T10:30:00+00:00`
- **THEN** both list items show `May 22, 2026, 10:30` as the newest date

#### Scenario: Missing or invalid date
- **WHEN** a state has `oldest_message_date` `null` or `not-a-date`
- **THEN** the list item shows `?` in place of that date

### Requirement: No download status
When a state has `"complete": null`, the list item SHALL show neither `⏳` nor `✓`. The details panel SHALL show the message count and the date range without a download message.

#### Scenario: Downloader down
- **GIVEN** the browser locale is `en-US`
- **AND** `list_chats` returns a chat with `"complete": null` and `"messages_count": 1500`
- **WHEN** the user selects the chat
- **THEN** its list item shows neither `⏳` nor `✓`
- **AND** the details panel shows `1,500`, and neither `The chat is being downloaded, please wait...` nor `The chat is downloaded`

### Requirement: Chat order
The chat list SHALL order the chats by `newest_message_date`, newest first. Chats without a `newest_message_date` SHALL come last. Chats with the same date SHALL follow in name order. The download status SHALL NOT change the order. When a progress notification changes the `newest_message_date` of a chat, the UI SHALL move the chat to its new place.

#### Scenario: Newest chat first
- **GIVEN** `list_chats` returns chat A with `newest_message_date` `2026-05-20T10:00:00Z`, chat B with `2026-05-22T10:00:00Z`, and chat C without messages
- **WHEN** the UI shows the list
- **THEN** the list shows B, then A, then C

#### Scenario: Download status does not change the order
- **GIVEN** chat A has `"complete": false` and `newest_message_date` `2026-05-20T10:00:00Z`
- **AND** chat B has `"complete": true` and `newest_message_date` `2026-05-22T10:00:00Z`
- **WHEN** the UI shows the list
- **THEN** chat B comes before chat A

#### Scenario: Dates with different offsets
- **GIVEN** chat A has `newest_message_date` `2026-05-22T12:00:00+02:00`
- **AND** chat B has `newest_message_date` `2026-05-22T11:00:00Z`
- **WHEN** the UI shows the list
- **THEN** chat B comes before chat A

#### Scenario: Same date
- **GIVEN** the chats "Bob" and "Alice" have the same `newest_message_date`
- **WHEN** the UI shows the list
- **THEN** "Alice" comes before "Bob"

#### Scenario: Progress moves a chat
- **GIVEN** the list shows chat B before chat A
- **WHEN** the UI receives `chat_download_progress` for chat A with a `newest_message_date` later than the one of chat B
- **THEN** the list shows chat A before chat B

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

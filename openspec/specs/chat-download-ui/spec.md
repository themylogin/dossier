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
After it connects, the UI SHALL load the chats with `list_chats` and show one list item per chat. Each list item SHALL show the download line of its chat: `⏳` or `✓`, the date range, and the message count.

#### Scenario: Chats appear
- **WHEN** the UI connects to the backend
- **THEN** the list shows one item for each chat from `list_chats`
- **AND** each item shows `⏳` or `✓` under the chat name

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
The UI SHALL apply each `chat_download_progress` notification to the matching chat without a page reload. While the download runs, the list item SHALL show `⏳`, the date range, and the message count. The details panel SHALL show `The chat is being downloaded, please wait...`.

#### Scenario: Progress arrives
- **WHEN** the UI receives `chat_download_progress` for the selected chat with `"complete": false`
- **THEN** the list item shows `⏳`, the date range, and the message count in parentheses
- **AND** the details panel shows `The chat is being downloaded, please wait...` and the message count

### Requirement: Download completion
When a notification has `"complete": true`, the list item SHALL show `✓` in place of `⏳`. The details panel SHALL show `The chat is downloaded`.

#### Scenario: Download completes
- **GIVEN** the browser locale is `en-US`
- **WHEN** the UI receives `chat_download_progress` for the selected chat with `"complete": true` and `"messages_count": 1000`
- **THEN** the list item shows `✓` and `(1,000)`
- **AND** the details panel shows `The chat is downloaded`

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

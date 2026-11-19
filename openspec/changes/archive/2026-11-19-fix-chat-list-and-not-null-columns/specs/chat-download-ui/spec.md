# Spec Delta

## MODIFIED Requirements

### Requirement: Chat list
After it connects, the UI SHALL load the chats with `list_chats` and show one list item per chat. Each list item SHALL show the download line of its chat: the download status, the date range, and the message count. The status SHALL be `⏳` for `"complete": false` and `✓` for `"complete": true`. A state with `"complete": null` SHALL show no status.

#### Scenario: Chats appear
- **WHEN** the UI connects to the backend
- **THEN** the list shows one item for each chat from `list_chats`
- **AND** each item shows the date range and the message count under the chat name

## ADDED Requirements

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

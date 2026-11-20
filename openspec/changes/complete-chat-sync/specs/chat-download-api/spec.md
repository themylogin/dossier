# Spec Delta

## MODIFIED Requirements

### Requirement: Download state format
A download state SHALL have `messages_count` (an integer), `oldest_message_date` and `newest_message_date` (a string or `null`), `files_count` and `files_pending` (integers), `downloaded` (a boolean), and `complete`. `downloaded` SHALL be `true` when the stored history of the chat reaches its first message. `complete` SHALL be `false` while the downloader downloads the chat, `true` when the download is complete, and `null` when no connected downloader reports the chat. Each date SHALL be an ISO 8601 date-time with a UTC offset, such as `2026-05-22T10:30:00+00:00` or `2026-05-22T10:30:00Z`.

#### Scenario: Dates carry an offset
- **WHEN** the backend sends a download state that has dates
- **THEN** each date parses as an ISO 8601 date-time with a UTC offset

#### Scenario: No messages yet
- **WHEN** the backend sends the state of a download that has no messages yet
- **THEN** `messages_count` is `0` and both dates are `null`
- **AND** `files_count` and `files_pending` are `0`

#### Scenario: No downloader
- **GIVEN** no downloader is connected to the backend
- **WHEN** the backend sends the state of a chat
- **THEN** `complete` is `null`

### Requirement: List chats
The `list_chats` method SHALL take no params. It SHALL return `{"chats": [...]}` with every chat in the downloader's database, its stored settings, and the latest state from the connected downloader. A chat without such a state SHALL have the state of its stored messages: their count, the dates of the oldest and the newest of them, `files_count` and `files_pending` by the rules of the downloader, its stored `downloaded` mark, and `complete` `null`.

#### Scenario: Client lists chats
- **WHEN** a client calls `list_chats` without params
- **THEN** the result is an object with one member, `chats`
- **AND** `chats` holds every known chat with its current settings and latest state

#### Scenario: Chat without a reported state
- **GIVEN** the database holds 3 messages of a chat, sent on 2024-01-01, 2024-01-02, and 2024-01-03 at 10:00 UTC
- **AND** the downloader has not reported the chat
- **WHEN** a client calls `list_chats`
- **THEN** the chat has `messages_count` `3` and `complete` `null`
- **AND** `oldest_message_date` is 2024-01-01 10:00 UTC, and `newest_message_date` is 2024-01-03 10:00 UTC

#### Scenario: Chat without messages
- **GIVEN** the database holds a chat without messages, and the downloader has not reported the chat
- **WHEN** a client calls `list_chats`
- **THEN** the chat has `messages_count` `0`, both dates `null`, and `complete` `null`

#### Scenario: Reported state wins
- **GIVEN** the database holds 3 messages of a chat
- **AND** the downloader reported the chat with `messages_count` `7` and `"complete": true`
- **WHEN** a client calls `list_chats`
- **THEN** the chat has `messages_count` `7` and `"complete": true`

#### Scenario: Stored file counts
- **GIVEN** the database holds 4 messages of a chat with media: 1 with a saved file, 1 with `media_type` `other`, and 2 without a file
- **AND** the downloader has not reported the chat
- **WHEN** a client calls `list_chats`
- **THEN** the chat has `files_count` `1` and `files_pending` `2`

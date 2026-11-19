# Spec Delta

## MODIFIED Requirements

### Requirement: Chat object
Each chat that the backend sends SHALL have `id` (the Telegram chat id, an integer), `name` (a string), `settings`, and `state`. `settings` SHALL be `{"media": <boolean>}`, where `media` tells whether the downloader downloads the media of the chat. `state` SHALL be a download state.

#### Scenario: Chat fields
- **WHEN** the backend sends a chat
- **THEN** the chat object has the members `id`, `name`, `settings`, and `state`
- **AND** `settings` has one member, `media`, with a boolean value
- **AND** `state` has the members `messages_count`, `oldest_message_date`, `newest_message_date`, and `complete`

### Requirement: List chats
The `list_chats` method SHALL take no params. It SHALL return `{"chats": [...]}` with every chat in the downloader's database, its stored settings, and the latest state from the downloader. A chat that the downloader has not reported yet SHALL have the zero state.

#### Scenario: Client lists chats
- **WHEN** a client calls `list_chats` without params
- **THEN** the result is an object with one member, `chats`
- **AND** `chats` holds every known chat with its current settings and latest state

#### Scenario: Chat without a reported state
- **GIVEN** the database holds a chat that the downloader has not reported
- **WHEN** a client calls `list_chats`
- **THEN** the chat has `messages_count` `0`, both dates `null`, and `complete` `false`

### Requirement: Update chat settings
The `update_chat` method SHALL take `{"id": <chat id>, "settings": {"media": <boolean>}}`. It SHALL store the settings in the downloader's database and return the updated chat object.

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

#### Scenario: Settings survive a restart
- **GIVEN** a client turned media on for a chat
- **WHEN** the backend restarts
- **THEN** `list_chats` shows `"settings": {"media": true}` for the chat

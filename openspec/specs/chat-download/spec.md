# chat-download Specification

## Purpose

Defines how the backend produces the download state of each chat. In this change, a stub simulates downloads without a Telegram connection.

## Requirements

### Requirement: Fake chats
The backend SHALL offer a fixed list of fake chats in place of Telegram dialogs. The list SHALL hold at least one private chat (positive id) and one group (negative id). Each fake chat SHALL have a fixed date for its first message, in the past. Each chat SHALL start with `"settings": {"media": false}`. Settings and state SHALL live in memory only.

#### Scenario: Backend start
- **WHEN** the backend starts
- **THEN** `list_chats` returns the fake chats
- **AND** at least one chat has a positive id and at least one chat has a negative id
- **AND** every chat has `"settings": {"media": false}`

### Requirement: Simulated download at start
When the backend starts, the stub SHALL start a simulated download of every chat.

#### Scenario: All chats download at start
- **GIVEN** the backend started and no client called `update_chat`
- **WHEN** the simulated downloads that began at start finish
- **THEN** `list_chats` shows `complete` `true` and `messages_count` `1000` for every chat

### Requirement: Simulated download on save
Each `update_chat` call SHALL restart the simulated download of its chat from zero. The new simulation SHALL replace a running simulation of the same chat. The `media` setting SHALL NOT change the simulation.

#### Scenario: Settings saved
- **WHEN** a client calls `update_chat` for a chat
- **THEN** the returned state has `messages_count` `0`, both dates `null`, and `complete` `false`

#### Scenario: Settings saved again during a download
- **GIVEN** a simulated download of a chat runs and has reported `messages_count` `300`
- **WHEN** a client calls `update_chat` for the chat
- **THEN** the returned state has `messages_count` `0`
- **AND** the next notification for the chat has `messages_count` `100`

#### Scenario: Settings saved again after completion
- **GIVEN** the simulated download of a chat is complete
- **WHEN** a client calls `update_chat` for the chat with the same settings
- **THEN** a new simulated download of the chat starts from zero

### Requirement: Simulated progress steps
A simulated download SHALL cover the whole history of its chat in 10 steps, one step every 0.5 seconds. Step k SHALL have `messages_count` 100 × k. `oldest_message_date` SHALL be the date of the first message of the chat. `newest_message_date` SHALL grow at each step and reach the start time of the simulation at step 10. Only step 10 SHALL have `complete` `true`.

#### Scenario: Full simulated download
- **GIVEN** a client called `update_chat` for a chat
- **WHEN** the simulation runs to the end
- **THEN** the backend sends exactly 10 `chat_download_progress` notifications for the chat
- **AND** their `messages_count` values are 100, 200, and so on up to 1000
- **AND** all 10 notifications have the same `oldest_message_date`, which is earlier than every `newest_message_date`
- **AND** each `newest_message_date` is later than the one before
- **AND** in the last notification, `newest_message_date` is the start time of the simulation and `complete` is `true`

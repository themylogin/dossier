# Spec Delta

## Purpose

Defines the fake downloader that the e2e tests use in place of Telegram. It serves the downloader API with fake chats and simulated downloads.

## ADDED Requirements

### Requirement: Fake chats
The fake downloader SHALL store a fixed list of fake chats in its database, so that the backend lists them. The list SHALL hold at least one private chat (positive id) and one group (negative id). Each fake chat SHALL have a fixed date for its first message, in the past. A fake chat SHALL start with media off, and a later start SHALL keep its stored setting.

#### Scenario: First start
- **GIVEN** the database holds no chats
- **WHEN** the fake downloader starts
- **THEN** `list_chats` on the backend returns the fake chats
- **AND** at least one chat has a positive id and at least one chat has a negative id
- **AND** every chat has `"settings": {"media": false}`

#### Scenario: Later start
- **GIVEN** a fake chat has media on in the database
- **WHEN** the fake downloader starts again
- **THEN** the chat still has media on

### Requirement: Simulated download at start
When the fake downloader starts, it SHALL start a simulated download of every fake chat.

#### Scenario: All chats download at start
- **GIVEN** the fake downloader started and no settings changed
- **WHEN** the simulated downloads that began at start finish
- **THEN** `list_chats` shows `complete` `true` and `messages_count` `1000` for every chat

### Requirement: Simulated download on a settings notice
Each `settings_changed` notice SHALL restart the simulated download of its chat from zero, and the fake downloader SHALL report the zero state at once. The new simulation SHALL replace a running simulation of the same chat. The media setting SHALL NOT change the simulation.

#### Scenario: Settings saved
- **WHEN** the fake downloader gets `settings_changed` for a chat
- **THEN** it reports the chat with `messages_count` `0`, both dates `null`, and `complete` `false`

#### Scenario: Settings saved again during a download
- **GIVEN** a simulated download of a chat runs and has reported `messages_count` `300`
- **WHEN** the fake downloader gets `settings_changed` for the chat
- **THEN** it reports the zero state
- **AND** its next report for the chat has `messages_count` `100`

#### Scenario: Settings saved again after completion
- **GIVEN** the simulated download of a chat is complete
- **WHEN** the fake downloader gets `settings_changed` for the chat
- **THEN** a new simulated download of the chat starts from zero

### Requirement: Simulated progress steps
A simulated download SHALL cover the whole history of its chat in 10 steps, one step every 0.5 seconds. Step k SHALL have `messages_count` 100 × k. `oldest_message_date` SHALL be the date of the first message of the chat. `newest_message_date` SHALL grow at each step and reach the start time of the simulation at step 10. Only step 10 SHALL have `complete` `true`.

#### Scenario: Full simulated download
- **GIVEN** the fake downloader got `settings_changed` for a chat
- **WHEN** the simulation runs to the end
- **THEN** after the zero state, the fake downloader sends exactly 10 `chat_download_progress` notices for the chat
- **AND** their `messages_count` values are 100, 200, and so on up to 1000
- **AND** all 10 notices have the same `oldest_message_date`, which is earlier than every `newest_message_date`
- **AND** each `newest_message_date` is later than the one before
- **AND** in the last notice, `newest_message_date` is the start time of the simulation and `complete` is `true`

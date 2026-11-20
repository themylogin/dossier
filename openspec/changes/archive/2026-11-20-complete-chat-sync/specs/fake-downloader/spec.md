# Spec Delta

## MODIFIED Requirements

### Requirement: Simulated progress steps
A simulated download SHALL cover the whole history of its chat in 10 steps, one step every 0.5 seconds. Step k SHALL have `messages_count` 100 × k. `oldest_message_date` SHALL be the date of the first message of the chat. `newest_message_date` SHALL grow at each step and reach the start time of the simulation at step 10. Only step 10 SHALL have `complete` `true` and `downloaded` `true`. When the chat has media on in the database, step k SHALL have `files_count` 10 × k and `files_pending` 100 − 10 × k. When the chat has media off, both SHALL be 0. The zero state SHALL have both at 0.

#### Scenario: Full simulated download
- **GIVEN** the fake downloader got `settings_changed` for a chat
- **WHEN** the simulation runs to the end
- **THEN** after the zero state, the fake downloader sends exactly 10 `chat_download_progress` notices for the chat
- **AND** their `messages_count` values are 100, 200, and so on up to 1000
- **AND** all 10 notices have the same `oldest_message_date`, which is earlier than every `newest_message_date`
- **AND** each `newest_message_date` is later than the one before
- **AND** in the last notice, `newest_message_date` is the start time of the simulation and `complete` is `true`

#### Scenario: Simulated files with media on
- **GIVEN** a chat has media on in the database
- **WHEN** the fake downloader gets `settings_changed` for the chat and the simulation runs to the end
- **THEN** the last notice has `files_count` 100 and `files_pending` 0

#### Scenario: No files with media off
- **GIVEN** a chat has media off in the database
- **WHEN** the simulation of the chat runs to the end
- **THEN** every notice has `files_count` 0 and `files_pending` 0

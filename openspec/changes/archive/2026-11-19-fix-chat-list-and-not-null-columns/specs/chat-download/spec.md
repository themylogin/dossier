# Spec Delta

## ADDED Requirements

### Requirement: Required columns
The schema of `messages.db` SHALL declare these columns NOT NULL: `messages.date`, `messages.text`, `messages.has_media`, `messages.created_at`, `chats.name`, `chats.type`, `chats.tracked`, `chats.download_media`, `chats.first_seen_at`, `chats.updated_at`, `users.is_bot`, `users.first_seen_at`, and `users.updated_at`. The migrations SHALL apply this to a database that `bot.py` created, with no data loss.

#### Scenario: Database from bot.py gets the constraints
- **GIVEN** the data folder holds a `messages.db` that `bot.py` created, with no NULL in the required columns
- **WHEN** the `migrate` service runs
- **THEN** each required column is NOT NULL
- **AND** all messages, chats, and users are still there

#### Scenario: Message without a date
- **GIVEN** the database is at the newest schema version
- **WHEN** a write stores a message without a date
- **THEN** the database rejects the write

#### Scenario: Message from the downloader
- **WHEN** the downloader stores a message
- **THEN** the stored row has a date, a text, and a `has_media` value

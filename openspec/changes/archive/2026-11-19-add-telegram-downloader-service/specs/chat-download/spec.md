# Spec Delta

## REMOVED Requirements

### Requirement: Fake chats
**Reason**: The backend no longer simulates downloads. The downloader downloads real Telegram chats.
**Migration**: The fake downloader offers fake chats to the e2e tests. See `fake-downloader`.

### Requirement: Simulated download at start
**Reason**: The backend no longer simulates downloads. The downloader downloads real Telegram chats.
**Migration**: The fake downloader simulates a download of every fake chat at start. See `fake-downloader`.

### Requirement: Simulated download on save
**Reason**: The backend no longer simulates downloads. A saved setting now reaches the downloader as a `settings_changed` notice.
**Migration**: The fake downloader restarts a simulation when it gets `settings_changed`. See `fake-downloader`.

### Requirement: Simulated progress steps
**Reason**: The backend no longer simulates downloads. The downloader reports the progress of real downloads.
**Migration**: The fake downloader keeps the same steps. See `fake-downloader`.

## ADDED Requirements

### Requirement: Every chat downloads in full
The downloader SHALL download the whole history of every dialog of the account: private chats, groups, and channels. It SHALL download one chat at a time, with the oldest message first.

#### Scenario: Three kinds of chats
- **GIVEN** the account has a private chat, a group, and a channel, and the database holds no messages
- **WHEN** the downloader starts
- **THEN** it stores every message of the three chats
- **AND** each of the three chats reports `complete` `true` at the end

### Requirement: Resume after the newest stored message
On start, the downloader SHALL continue each chat after its newest stored message. A chat whose newest Telegram message is already stored SHALL report `complete` `true` without a history download.

#### Scenario: Interrupted download
- **GIVEN** the database holds messages 1 to 500 of a chat that has 800 messages
- **WHEN** the downloader starts
- **THEN** it downloads messages 501 to 800 and no other messages of the chat

#### Scenario: Chat up to date
- **GIVEN** the database holds the newest message of a chat
- **WHEN** the downloader starts
- **THEN** the chat reports `complete` `true`
- **AND** the downloader requests no history of the chat

### Requirement: Media follows the chat setting
The downloader SHALL store the text and data of every message. It SHALL download the media of a message only when the media setting of the chat is on. After a `settings_changed` notice, the downloader SHALL read the media settings from the database again before its next media decision. Storing a dialog SHALL NOT change its media setting, and a new chat SHALL start with media off.

#### Scenario: Media off
- **GIVEN** a chat has media off
- **WHEN** the downloader downloads a message with a photo from the chat
- **THEN** it stores the message with `has_media` true and with no media file

#### Scenario: Media on
- **GIVEN** a chat has media on
- **WHEN** the downloader downloads a message with a photo from the chat
- **THEN** it saves the photo in the downloads folder and stores the path with the message

#### Scenario: Media turned on during a download
- **GIVEN** the downloader downloads a chat with media off
- **WHEN** the backend stores media on for the chat and sends `settings_changed`
- **THEN** the downloader downloads the media of the next messages of the chat

#### Scenario: Dialog stored again
- **GIVEN** a stored chat has media on
- **WHEN** the downloader stores the dialog list on start
- **THEN** the chat keeps media on

### Requirement: Progress reports
The downloader SHALL report the state of a chat after every 100 downloaded messages and when the chat completes. A state SHALL count the stored messages of the chat and give the dates of its oldest and newest stored messages. `complete` SHALL be `true` only when the stored history of the chat reaches its newest message.

#### Scenario: 250 messages to download
- **GIVEN** a chat has 250 messages that the downloader has not stored
- **WHEN** the downloader downloads the chat
- **THEN** it reports states with `messages_count` 100, 200, and 250
- **AND** only the last of these states has `complete` `true`

### Requirement: New messages
After its start-up download, the downloader SHALL store each new message of any chat when it arrives, and report the new state of the chat.

#### Scenario: Message arrives
- **GIVEN** the start-up download is over and a chat reports `messages_count` 40
- **WHEN** a new message arrives in the chat
- **THEN** the downloader stores the message
- **AND** it reports the chat with `messages_count` 41 and the date of the new message as `newest_message_date`

### Requirement: Storage locations
The downloader SHALL keep `messages.db` and `dossier_bot.session` in the data folder. It SHALL save each media file in the downloads folder at `<chat id>/<aa>/<bb>/<cc>/<message id>/<file name>`. `aa`, `bb`, and `cc` SHALL be the first six digits of the message id, padded with zeros to six digits, in pairs. The file SHALL get the message date as its modification time.

#### Scenario: Photo of message 7890
- **GIVEN** chat `-2001` has media on
- **WHEN** the downloader saves the photo of message 7890, sent at `2026-05-22T10:30:00+00:00`
- **THEN** the file is `-2001/00/78/90/7890/photo_7890.jpg` in the downloads folder
- **AND** its modification time is `2026-05-22T10:30:00+00:00`

### Requirement: Database schema
Versioned migrations SHALL define the schema of `messages.db`. The `migrate` service SHALL upgrade the database to the newest version. It SHALL adopt a database that `bot.py` created, with no data loss.

#### Scenario: Empty data folder
- **GIVEN** the data folder holds no `messages.db`
- **WHEN** the `migrate` service runs
- **THEN** it creates `messages.db` with the newest schema

#### Scenario: Database from bot.py
- **GIVEN** the data folder holds a `messages.db` that `bot.py` created, with messages and a chat with media on
- **WHEN** the `migrate` service runs
- **THEN** the database is at the newest schema version
- **AND** all messages are still there, and the chat still has media on

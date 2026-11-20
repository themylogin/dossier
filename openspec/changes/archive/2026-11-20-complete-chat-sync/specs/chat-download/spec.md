# Spec Delta

## ADDED Requirements

### Requirement: Incomplete chats complete at the next check
Every 15 minutes, the downloader SHALL read the dialog list again. It SHALL start a history download for each dialog that it does not track, a catch-up download for each complete chat whose top message is newer than its newest stored message, and a history download again for each chat whose download failed. It SHALL also start the media downloads of each chat with media on.

#### Scenario: Service message at the top
- **GIVEN** a chat reports `complete` `true` with messages 1 to 40
- **WHEN** message 41 is a service message, which arrives as no new-message event, and nothing else arrives
- **THEN** the next check starts a catch-up download that stores message 41
- **AND** the chat reports `complete` `true` with `messages_count` 41

#### Scenario: Missed join
- **GIVEN** a chat with 50 messages appears in the dialog list, and the downloader got no sign of it
- **WHEN** the next check runs
- **THEN** the downloader stores the chat and its 50 messages
- **AND** the chat reports `complete` `true` at the end

#### Scenario: Failed download retries
- **GIVEN** the history download of chat `-2001`, which has 5 messages, failed at message 3
- **WHEN** the next check runs and Telegram serves the chat
- **THEN** the downloader downloads messages 3 down to 1
- **AND** the chat reports `complete` `true`

#### Scenario: Lost settings notice
- **GIVEN** the backend stored media on for a chat while it had no link to the downloader
- **WHEN** the next check runs
- **THEN** the downloader saves the files of the chat

#### Scenario: Nothing to do
- **GIVEN** every chat is complete, and no chat has media on
- **WHEN** the next check runs
- **THEN** the downloader reads the dialog list once
- **AND** it requests no history and no file

### Requirement: Message versions
The `messages` row of a message SHALL hold its newest known version, with its edit date. When the downloader gets a version of a stored message with a later edit date, it SHALL first copy the stored version into `message_versions`, and then store the new version in `messages`. It SHALL get versions from edit events, from the updates that Telegram replays at connect, and from each stored message that it fetches again.

#### Scenario: Text edited
- **GIVEN** message 5 of a chat is stored with the text `A` and no edit date
- **WHEN** an edit event gives message 5 with the text `B` and the edit date `2026-05-22T10:30:00+00:00`
- **THEN** `messages` holds message 5 with the text `B` and that edit date
- **AND** `message_versions` holds one row for message 5, with the text `A` and the message date as its version date

#### Scenario: Two edits
- **GIVEN** message 5 has the versions `A`, then `B` at 10:30, and the downloader stored both
- **WHEN** an edit event gives the text `C` at 11:00
- **THEN** `messages` holds `C`
- **AND** `message_versions` holds `A` and `B`

#### Scenario: Same version again
- **GIVEN** message 5 is stored with the edit date `2026-05-22T10:30:00+00:00`
- **WHEN** the downloader gets message 5 again with the same edit date
- **THEN** it changes no row

#### Scenario: Edit of a message that is not stored
- **GIVEN** the database lacks message 150 of a chat
- **WHEN** an edit event gives message 150
- **THEN** the downloader stores no version of message 150

#### Scenario: Edit while the downloader was stopped
- **GIVEN** message 5 is stored with the text `A`, and the downloader is stopped
- **WHEN** message 5 is edited to `B`, and the downloader starts again
- **THEN** `messages` holds `B` and `message_versions` holds `A`

### Requirement: Media of edited messages
When a new version keeps the media of the stored version, the downloader SHALL keep the file of the message. When the new version has other media, the earlier version SHALL keep its file in `message_versions`, and the downloader SHALL save the new file when the chat has media on. It SHALL NOT download a file for a version in `message_versions`.

#### Scenario: Caption edited
- **GIVEN** message 5 has a photo, its file is saved, and the chat has media on
- **WHEN** an edit changes the caption of message 5 and keeps the photo
- **THEN** `messages` holds the new caption with the same `media_path`
- **AND** the downloader downloads no file

#### Scenario: Photo replaced
- **GIVEN** message 5 has a photo, its file `-2001/00/00/05/5/photo_5.jpg` is saved, and the chat has media on
- **WHEN** an edit at `2026-05-22T10:30:00+00:00` replaces the photo
- **THEN** `message_versions` holds the earlier version with the path of `photo_5.jpg`
- **AND** the downloader saves the new photo as `-2001/00/00/05/5/2026-05-22_10-30-00/photo_5.jpg` and stores that path in `messages`

#### Scenario: Photo replaced while media is off
- **GIVEN** message 5 has a photo, no file, and the chat has media off
- **WHEN** an edit replaces the photo, and later the chat gets media on
- **THEN** the downloader saves the new photo only

### Requirement: Media stops and resumes
When the media setting of a chat goes off, the downloader SHALL download no further file of the chat. The file in progress SHALL complete and be stored. When the setting goes on again, the downloader SHALL continue with the files that are still missing, and SHALL NOT download a file twice.

#### Scenario: Media turned off during the downloads
- **GIVEN** a chat has media on and 300 stored photo messages without files, and the downloader saved the photos of messages 300 to 201
- **WHEN** the backend stores media off for the chat and sends `settings_changed`
- **THEN** the downloader saves no further photo of the chat

#### Scenario: Media turned on again
- **GIVEN** the downloader saved the photos of messages 300 to 201 of a chat, and then media went off
- **WHEN** the backend stores media on for the chat and sends `settings_changed`
- **THEN** the downloader saves the photos of messages 200 down to 1
- **AND** it requests no photo of messages 300 to 201 again

### Requirement: Media without a file
When a chat has media on and Telegram returns no file for a message, the downloader SHALL store `media_type` `other` and no `media_path` for the message. This covers media that is not a file, such as a web page preview, a poll, or a location, an empty photo, and a message that no longer exists. The downloader SHALL NOT request such a message again in a later media run.

#### Scenario: Web page preview
- **GIVEN** a chat has media on, and its stored message 9 has a web page preview
- **WHEN** the downloader downloads the files of the chat
- **THEN** message 9 gets `media_type` `other` and no `media_path`
- **AND** the next media run of the chat does not request message 9

#### Scenario: Deleted message
- **GIVEN** a chat has media on, and its stored message 6 no longer exists in Telegram
- **WHEN** the downloader downloads the files of the chat
- **THEN** message 6 gets `media_type` `other` and no `media_path`

### Requirement: Failed file downloads
When a file download fails, the downloader SHALL log the error, leave the message without `media_type` and `media_path`, and continue with the next file of the chat. A later media run of the chat SHALL retry the file.

#### Scenario: File download fails
- **GIVEN** a chat has media on and stored photo messages 1 to 3 without files, and the download of the photo of message 2 fails
- **WHEN** the downloader downloads the files of the chat
- **THEN** messages 3 and 1 get their photos
- **AND** message 2 keeps no `media_type` and no `media_path`
- **AND** the next media run of the chat saves the photo of message 2

### Requirement: Media progress reports
A state SHALL give `files_count`, the stored messages of the chat with a saved file, and `files_pending`, the stored messages with media, no file, and no `media_type` `other`. During a media run, the downloader SHALL report the state of the chat after every 10 saved files and at the end of the run. Versions in `message_versions` SHALL NOT count.

#### Scenario: 25 files to save
- **GIVEN** a chat has 25 stored photo messages without files
- **WHEN** the backend stores media on for the chat and sends `settings_changed`
- **THEN** the downloader reports states with `files_count` 10, 20, and 25
- **AND** with `files_pending` 15, 5, and 0

#### Scenario: Media off
- **GIVEN** a chat has media off and 25 stored photo messages
- **WHEN** the downloader reports the chat
- **THEN** the state has `files_count` 0 and `files_pending` 25

### Requirement: Clean stop
The downloader SHALL handle SIGTERM as Ctrl+C. It SHALL then disconnect from Telegram, so that Telethon saves its update state, and stop within the grace period of Docker.

#### Scenario: Stack stopped
- **GIVEN** the downloader runs
- **WHEN** `docker compose stop` or Ctrl+C on `docker compose up` sends SIGTERM
- **THEN** it disconnects from Telegram and stops without a forced kill

## MODIFIED Requirements

### Requirement: Every chat downloads in full
The downloader SHALL download the whole history of every dialog of the account: private chats, groups, and channels. It SHALL run at most one history download and one catch-up download at a time. A chat without stored messages SHALL download newest first. The stored messages of a chat SHALL always cover every message between its oldest and its newest stored message.

#### Scenario: Three kinds of chats
- **GIVEN** the account has a private chat, a group, and a channel, and the database holds no messages
- **WHEN** the downloader starts
- **THEN** it stores every message of the three chats
- **AND** each of the three chats reports `complete` `true` at the end

#### Scenario: New chat
- **GIVEN** the database holds no message of a chat with 5 messages
- **WHEN** the downloader downloads the chat
- **THEN** it stores messages 5, 4, 3, 2, and 1, in that order
- **AND** it sets `downloaded` for the chat

#### Scenario: Newer messages before older messages
- **GIVEN** the database holds messages 200 to 300 of a chat that has 400 messages, and `downloaded` is not set for the chat
- **WHEN** the downloader starts
- **THEN** it stores messages 301 to 400, oldest first
- **AND** then it stores messages 199 down to 1, newest first
- **AND** the chat reports `complete` `true` at the end

### Requirement: Resume after the newest stored message
On start, the downloader SHALL continue each chat after its newest stored message, oldest first. When `chats.downloaded` is not set, it SHALL then continue before the oldest stored message, newest first, until Telegram returns no older message, and set `downloaded`. It SHALL NOT request messages before the oldest stored message of a chat with `downloaded` set. A chat whose newest Telegram message is stored, and whose `downloaded` is set, SHALL report `complete` `true` without a history request.

#### Scenario: Interrupted download
- **GIVEN** the database holds messages 1 to 500 of a chat that has 800 messages, and `downloaded` is set for the chat
- **WHEN** the downloader starts
- **THEN** it downloads messages 501 to 800 and no other messages of the chat

#### Scenario: Chat up to date
- **GIVEN** the database holds the newest message of a chat, and `downloaded` is set for the chat
- **WHEN** the downloader starts
- **THEN** the chat reports `complete` `true`
- **AND** the downloader requests no history of the chat

#### Scenario: Chat stored from its first live message
- **GIVEN** the database holds messages 3328 to 3400 of a supergroup that has 3400 messages, and `downloaded` is not set
- **WHEN** the downloader starts
- **THEN** it downloads messages 3327 down to 1
- **AND** it sets `downloaded` for the chat
- **AND** the chat reports `complete` `true`

#### Scenario: Database from the previous version
- **GIVEN** an upgraded database holds messages 1 to 500 of a small group that has 500 messages, and `downloaded` is not set
- **WHEN** the downloader starts
- **THEN** it requests the messages before message 1 once, and Telegram returns none
- **AND** it sets `downloaded` for the chat
- **AND** the chat reports `complete` `true`

#### Scenario: Stop during the older download
- **GIVEN** the database holds messages 2000 to 3400 of a chat, because the downloader stopped during the older download, and `downloaded` is not set
- **WHEN** the downloader starts
- **THEN** it downloads messages 1999 down to 1
- **AND** the database holds messages 1 to 3400 with no gap

### Requirement: Media follows the chat setting
The downloader SHALL store the text and data of every message without its media file. While the media setting of a chat is on, it SHALL download the files of the chat: the stored messages without a file, newest first, and then each message that it stores later. After a `settings_changed` notice, it SHALL read the media settings from the database again before its next file. Storing a dialog SHALL NOT change its media setting, and a new chat SHALL start with media off.

#### Scenario: Media off
- **GIVEN** a chat has media off
- **WHEN** the downloader downloads a message with a photo from the chat
- **THEN** it stores the message with `has_media` true and with no media file

#### Scenario: Media on
- **GIVEN** a chat has media on
- **WHEN** the downloader downloads a message with a photo from the chat
- **THEN** it stores the message
- **AND** then it saves the photo in the downloads folder and stores the path with the message

#### Scenario: Media turned on for a stored chat
- **GIVEN** the database holds messages 1 to 3 of a chat, each with a photo and no file, and the chat has media off
- **WHEN** the backend stores media on for the chat and sends `settings_changed`
- **THEN** the downloader saves the photos of messages 3, 2, and 1, in that order
- **AND** it stores each path with its message

#### Scenario: Media turned on during a download
- **GIVEN** the downloader downloads a chat with media off
- **WHEN** the backend stores media on for the chat and sends `settings_changed`
- **THEN** the downloader downloads the media of the messages that it stored, and of the next messages of the chat

#### Scenario: Dialog stored again
- **GIVEN** a stored chat has media on
- **WHEN** the downloader stores the dialog list on start
- **THEN** the chat keeps media on

#### Scenario: Message stored again keeps its file
- **GIVEN** message 5 of a chat has a `media_type` and a `media_path`
- **WHEN** the downloader stores message 5 again with the same edit date
- **THEN** the message keeps its `media_type` and `media_path`

### Requirement: Progress reports
The downloader SHALL report the state of a chat after every 100 downloaded messages and when the chat completes. A state SHALL count the stored messages of the chat, give the dates of its oldest and newest stored messages, and give `downloaded`, the mark of the chat. `complete` SHALL be `true` only when the stored history of the chat reaches both its first message and its newest message, and no download of the chat is queued or runs.

#### Scenario: 250 messages to download
- **GIVEN** a chat has 250 messages that the downloader has not stored
- **WHEN** the downloader downloads the chat
- **THEN** it reports states with `messages_count` 100, 200, and 250
- **AND** only the last of these states has `complete` `true`

#### Scenario: Chat without its older history
- **GIVEN** the database holds messages 3328 to 3400 of a chat, and `downloaded` is not set
- **WHEN** the downloader starts
- **THEN** the first state of the chat has `complete` `false`

### Requirement: New messages
The downloader SHALL listen for new messages from its start. It SHALL store no message from the event itself. For a complete chat, a new message SHALL start a catch-up download after the newest stored message, which SHALL NOT wait for the history download of another chat. While a download of the chat is queued or runs, that download SHALL fetch the message with one more request after its current one. After a failed download, the downloader SHALL drop the new messages of the chat until the next check.

#### Scenario: Message arrives
- **GIVEN** a chat reports `complete` `true` and `messages_count` 40
- **WHEN** a new message arrives in the chat
- **THEN** the downloader fetches the message with a history request after message 40, and stores it
- **AND** it reports the chat with `messages_count` 41 and the date of the new message as `newest_message_date`

#### Scenario: Service message before a new message
- **GIVEN** a chat reports `complete` `true` with messages 1 to 40
- **WHEN** message 41 is a service message, which arrives as no new-message event, and message 42 arrives
- **THEN** the catch-up download stores messages 41 and 42
- **AND** the chat reports `complete` `true` with `messages_count` 42

#### Scenario: Message during the start-up download
- **GIVEN** the downloader downloads chat `-2001` on start, and chat `-2002` is complete with 40 messages
- **WHEN** a new message arrives in chat `-2002`
- **THEN** the downloader stores the message before the download of chat `-2001` ends
- **AND** it reports chat `-2002` with `messages_count` 41

#### Scenario: Message during the last history request
- **GIVEN** the downloader downloads chat `-2001`, which has 300 messages
- **WHEN** message 301 arrives in the chat during the last history request
- **THEN** the history download stores message 301
- **AND** the chat reports `complete` `true` with `messages_count` 301

#### Scenario: Restart during a download
- **GIVEN** the downloader stored messages 300 down to 201 of chat `-2001`, which has 300 messages
- **AND** messages 301 and 302 arrived in the chat during the download
- **WHEN** the downloader stops and starts again
- **THEN** it downloads messages 301 and 302, and then messages 200 down to 1

#### Scenario: Message after a failed download
- **GIVEN** the history download of chat `-2001` failed
- **WHEN** a new message arrives in the chat
- **THEN** the downloader does not store the message
- **AND** at the next check, it downloads the message with the rest of the history

### Requirement: Storage locations
The downloader SHALL keep `messages.db` and `dossier_bot.session` in the data folder. It SHALL save each media file in the downloads folder at `<chat id>/<aa>/<bb>/<cc>/<message id>/<file name>`. `aa`, `bb`, and `cc` SHALL be the first six digits of the message id, padded with zeros to six digits, in pairs. `<file name>` SHALL be the name of the document without any folder part. The file of an edited version with new media SHALL go into the subfolder `<edit date>` of that folder, in the form `YYYY-MM-DD_HH-MM-SS` in UTC. The file SHALL get the message date as its modification time.

#### Scenario: Photo of message 7890
- **GIVEN** chat `-2001` has media on
- **WHEN** the downloader saves the photo of message 7890, sent at `2026-05-22T10:30:00+00:00`
- **THEN** the file is `-2001/00/78/90/7890/photo_7890.jpg` in the downloads folder
- **AND** its modification time is `2026-05-22T10:30:00+00:00`

#### Scenario: Document named with a folder
- **GIVEN** chat `-2001` has media on
- **WHEN** the downloader saves the document of message 12, whose name is `photos/trip.jpg`
- **THEN** the file is `-2001/00/00/12/12/trip.jpg` in the downloads folder

### Requirement: Required columns
The schema of `messages.db` SHALL declare these columns NOT NULL: `messages.date`, `messages.text`, `messages.has_media`, `messages.created_at`, `message_versions.chat_id`, `message_versions.message_id`, `message_versions.version_date`, `message_versions.text`, `message_versions.has_media`, `message_versions.created_at`, `chats.name`, `chats.type`, `chats.download_media`, `chats.downloaded`, and `users.is_bot`. The migrations SHALL apply this to a database that `bot.py` created, with no data loss.

#### Scenario: Database from bot.py gets the constraints
- **GIVEN** the data folder holds a `messages.db` that `bot.py` created, with no NULL in the required columns
- **WHEN** the `migrate` service runs
- **THEN** each required column is NOT NULL
- **AND** all messages, chats, and users are still there

#### Scenario: No timestamp columns
- **GIVEN** the database is at the newest schema version
- **WHEN** a reader lists the columns of `chats` and `users`
- **THEN** neither table has `first_seen_at` or `updated_at`
- **AND** `chats` has no `tracked`

#### Scenario: Message without a date
- **GIVEN** the database is at the newest schema version
- **WHEN** a write stores a message without a date
- **THEN** the database rejects the write

#### Scenario: Message from the downloader
- **WHEN** the downloader stores a message
- **THEN** the stored row has a date, a text, and a `has_media` value

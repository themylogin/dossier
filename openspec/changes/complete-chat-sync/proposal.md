# Proposal

## Why

The downloader must keep a full copy of every chat of the account: every message, every version of an edited message, and the media files of the chats with media on. A review of `dossier/downloader/downloader.py`, on the working tree of `download-joined-chats`, found these defects:

1. Older history never downloads. The resume rule only continues after `MAX(message_id)`. A chat that was first stored from a live message keeps only the messages from that point. The real `messages.db` has two such supergroups, stored from messages 3328 and 1879.
2. Media on applies only to the messages that the downloader stores after the change. Stored messages never get their files. Media off and on again does not continue with the missing files.
3. A stored live message hides older messages. Telethon's `events.NewMessage` drops service messages, and Telegram can skip updates. The next live store raises `MAX(message_id)` past them, and no later download fetches them.
4. Edits are lost. The downloader stores the first version of a message and ignores every edit.
5. A failed history download waits for the next start. Nothing retries it while the downloader runs.
6. A missed sign waits for the next start: a chat that moves in the dialog list during a read, or a `settings_changed` notice while the backend has no link. Nothing checks again.
7. One media object without a file stops a chat. `download_media` reads `document.mime_type` outside its `try`. A `MessageMediaDocument` without a `Document` raises out of `store_message`. The history download of the chat then fails at that message at every start.
8. A document name with a folder part, such as `photos/trip.jpg`, makes the download fail or puts the file in another folder.
9. `save_message` replaces `media_type` and `media_path` on conflict. A message that the downloader stores again loses its file path.
10. `download_media` gets `message.media`. Telethon can refetch an expired file reference only when it gets the message.
11. The UI shows no media progress. You cannot see how many files of a chat are saved.

## What Changes

- **Both directions, newest first.** A chat without stored messages downloads newest first. A chat with stored messages first fetches the messages after its newest stored message, oldest first. Then, until the chat is marked `downloaded`, it fetches the messages before its oldest stored message, newest first, until Telegram returns none. A new column `chats.downloaded` records that mark, and the downloader never requests older messages of a marked chat again. Everything between the oldest and the newest stored message counts as downloaded.
- **Live messages through history requests.** The new-message handler stores nothing. It queues a catch-up download after the newest stored message. The catch-up fetches the message and every message before it that the event stream did not deliver, service messages included. A second worker runs catch-ups, so a long history download of another chat does not delay them. No new gap can appear.
- **Message versions.** `messages` always holds the newest known version of a message. A new table `message_versions` holds each earlier version, with its text and its media columns. The downloader records a version from `events.MessageEdited`, and from each stored message that it fetches again. `catch_up` replays the edits that arrive while the downloader is stopped. A caption edit keeps the file. Replaced media gets a new file in a folder named by the edit date. Earlier versions never get a file download.
- **Media backfill, stop, and resume.** Storing a message no longer downloads its media. A media worker downloads the files of a chat with media on: the stored messages without a file, newest first, and then each message that the downloader stores later. Media off stops the worker after the file in progress. Media on again continues with the missing files. A message whose media is not a file gets `media_type` `other`, so no run fetches it again. A failed file keeps no `media_type`, and a later run retries it.
- **Media progress.** A download state gets `files_count` and `files_pending`. The downloader reports them during media runs. The UI shows them in the chat list and in the details panel. The fake downloader simulates them.
- **A check every 15 minutes.** The downloader reads the dialog list again. It queues each dialog that it does not track, a catch-up for each complete chat with a newer top message, and a new history download for each failed chat. It also starts the media worker for each chat with media on.
- **Small fixes.** A file name keeps only its last path segment. `download_media` gets the message. `save_message` never overwrites a stored row. A media object without a file never stops a chat.
- **Migration file names.** All Alembic revision files take the form `%Y-%m-%d_%H-%M-<slug>.py`, through `file_template` in `alembic.ini`. The three existing files get new names. The revision ids stay.
- `complete` keeps its meaning. A chat reports `complete` `true` when its stored history reaches its first and its newest message, and no download of it is queued or runs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `chat-download`: newest-first download with a `downloaded` mark; message versions; media backfill, stop, and resume; media progress; new messages through history requests; a check every 15 minutes; a folder per replaced file; file names without a folder part; one history download and one catch-up at a time; a clean stop on SIGTERM; required columns of the new table. The `New messages` delta modifies the version of `download-joined-chats`.
- `chat-download-api`: the download state gets `files_count` and `files_pending`.
- `chat-download-ui`: the chat list and the details panel show the media progress.
- `fake-downloader`: the simulation reports file counts when media is on.

## Impact

- `dossier/models.py`, `alembic.ini`, and `migrations/versions/`: the new columns, the new table, revisions `0004` and `0005`, the file template, and the renamed files.
- `dossier/downloader/downloader.py`: the chat states, the two message workers, the versions, the media worker, the 15-minute check, the new handlers, and the fixes.
- `dossier/downloader/__main__.py`: `run` starts the four tasks and passes `settings_changed` to the downloader. The client gets `catch_up=True`.
- `dossier/downloader/api.py`, `dossier/downloader/fake.py`, `dossier/backend/api.py`, and `dossier/backend/chats.py`: the two new state fields.
- `frontend/src/components/`: the media progress in `ChatListItem` and `ChatDetails`.
- `tests/`, `frontend/src/**/*.test.*`, and `e2e/tests/`: tests for each new scenario. Existing assertions on `history_requests` change, because each chat gets one older-history request at its first start.
- `README.md`: one sentence each on the 15-minute check, media backfill, and versions.
- Telegram requests: one older-history request per chat without the mark at the first start after the upgrade (416 for the real account); one or two history requests per live message, merged while a chat waits in a queue; five dialog requests every 15 minutes; one request per 100 messages with media in a media run.
- This change builds on the working tree of `download-joined-chats`. Sync or archive that change first, so that its spec delta reaches `openspec/specs/chat-download/spec.md`.
- No change to the WebSocket contract except the two state fields, and no change to the Compose stack.

## Out of Scope

- Deletions. The downloader never removes a row or a file.
- Files of earlier versions that the downloader did not save before the edit.
- Old gaps. A message that `bot.py` skipped in the middle of a chat stays missing.
- Edits that Telegram does not replay after a long stop of the downloader.
- Chats in the database that are not in the dialog list, such as left chats. They keep their rows and get no download.
- A stop of the file download in progress. The file completes and is stored, and then the worker stops.

## Assumptions

- The main Telegram app and the downloader use the same account.
- Telegram accepts one or two history requests per live message. Telethon sleeps through flood waits of up to one hour.
- 15 minutes is a good period for the check. Telethon uses the same period for channels without updates.
- An edit always sets a later `edit_date`. Updates without a new `edit_date`, such as a changed keyboard, are not versions.

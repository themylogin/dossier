# Design

## Context

See `proposal.md` for the motivation. These facts come from the working tree of `download-joined-chats`, from Telethon 1.46.0 in the test image, and from the Telegram API.

The downloader today:

- `downloading: dict[int, bool]` holds the chats with a queued or running history download. The value marks that a message arrived during the current pass. `complete` and `outside` are sets. One queue feeds one worker.
- `read_dialogs()` runs under `sync_lock`, at start and on each sign from an untracked chat. It handles untracked dialogs only.
- `on_new_message` stores the message of a complete chat at once. `store_message` downloads the media inline when `media_enabled()` says so. `save_message` upserts every column, the media columns included.
- A history download resumes after `MAX(message_id)` and never looks before `MIN(message_id)`.

Telethon 1.46.0:

- `iter_messages(chat, min_id=n, reverse=True)` yields the messages with id above `n`, oldest first. It ends only after an empty response. A pass that finds `k` messages costs `k // 100 + 1` requests, or `k // 100 + 2` when `k` is not a multiple of 100.
- `iter_messages(chat, offset_id=n)` yields the messages with id below `n`, newest first. With `offset_id=0` it starts at the newest message. It ends after an empty response, or when the highest id of a response is at most 100.
- With no limit, Telethon waits one second between the chunks of one iteration.
- `get_messages(chat, ids=[...])` sends 100 ids per request. It returns `None` for a message that Telegram does not return, and for a message of another chat.
- `events.NewMessage` drops `MessageService`. A history request returns service messages.
- `download_media(message, file=...)` returns `None` when the message has no file. Given the message, it refetches an expired file reference of a document. Given `message.media`, it cannot.
- Telethon fetches the difference of a channel after 15 minutes without updates.
- `events.MessageEdited` builds an event from `UpdateEditMessage` and `UpdateEditChannelMessage`. The event carries the whole new message, with `edit_date`.
- `catch_up=False` is the default. With `catch_up=True`, Telethon loads the update state from the session file at connect and fetches the difference. Telegram then replays the new messages and the edits since the last run. On `DifferenceTooLong`, Telethon moves to the newest state and replays nothing.

Telegram message ids are sequential in each channel and supergroup. Private chats and small groups share the global sequence of the account.

The database rules of the first downloader change hold: short transactions with `BEGIN IMMEDIATE`, and every downloader write in the event loop thread. `tests/test_database.py` and `tests/test_bot_py_adoption.py` pin the newest revision as the literal `"0003"`. `tests/test_database.py` also compares the models with the migrations.

The three revision files are `0001_bot_py_schema.py`, `0002_rename_download_media.py`, and `0003_not_null_columns.py`. Their headers have no `Create Date`. Git added the first two at `2026-11-19 11:54` UTC and the third at `13:30` UTC. `alembic.ini` has no `file_template`.

The UI shows a state in `ChatListItem.jsx` (the list item line) and `ChatDetails.jsx` (the `download-stats` rows). The backend builds a state in `BackendApi.to_chat` from one `GROUP BY` query.

The real `messages.db` has 416 chats, so one dialog read costs 5 requests.

## Goals / Non-Goals

**Goals:**

- One code path stores messages: a history pass. The stored messages of a chat always cover everything between its oldest and its newest stored message.
- Every download and every media run resumes from the database alone. A stop at any point leaves no gap and no lost file.
- A failure costs at most one new attempt every 15 minutes.
- A live message of a complete chat never waits for a long history download.

**Non-Goals:**

- No stored queue. The dialog read at the next start builds the queues again.
- No change to the update handling of Telethon, such as `catch_up` or `sequential_updates`.
- No new message in the downloader API. The UI learns nothing new.
- No stop of a file download in progress.
- No file download for a version in `message_versions`.
- No full scan for edits. Only edit events, the replay at connect, and messages that the downloader fetches again give versions.

## Decisions

### 1. Chat states

Per run, in memory:

- `downloading: dict[int, bool]`: the chat has a queued or running download. The value is the mark: run a newer pass.
- `complete: set[int]`: the last download of the chat ended without an error.
- `failed: set[int]`: the last download of the chat raised.
- `outside: set[int]`: a dialog read did not find the chat, as in `download-joined-chats`.
- `names: dict[int, str]`: the dialog names, for the log.

`tracks(chat_id)` is true for a chat in `downloading`, `complete`, or `failed`. The transitions:

- A dialog read, under `sync_lock`, handles every dialog. An untracked dialog gets its row, as today. Then, when `top_message` is above `MAX(message_id)` or `downloaded` is unset, the read puts the chat into `downloading` with the mark `top_message > MAX(message_id)`, and into the history queue. Otherwise, the chat goes into `complete` with a report. A complete chat whose `top_message` is above `MAX(message_id)` leaves `complete` and goes into `downloading` with the mark set, and into the live queue. A failed chat leaves `failed` and goes into `downloading` and the history queue, with the same mark rule as an untracked one.
- A new message: an untracked chat first gets `find_chat()`, as today, and then the same rule. A chat in `downloading` gets the mark. A complete chat leaves `complete` and goes into `downloading` with the mark set, and into the live queue. A chat in `failed` or `outside` gets nothing.
- The end of a download: on success, the chat goes into `complete`. On an exception, it goes into `failed`. Both report the chat.

All transitions run between awaits, so no lock protects them.

### 2. A download: newer passes, the older pass, and a last check

`download_history(chat_id)`:

```
while True:
    while self.downloading[chat_id]:
        self.downloading[chat_id] = False
        if downloaded is set or the chat has stored messages:
            newer pass: iter_messages(chat_id, min_id=MAX(message_id), reverse=True)
    if downloaded is unset:
        older pass: iter_messages(chat_id, offset_id=MIN(message_id) or 0)
        set downloaded
    if not self.downloading[chat_id]:
        break
leave downloading, enter complete        # no await between the check and this line
report; queue_media(chat_id)
```

Both passes share one store loop, with the count and the report after every 100 messages. The passes only extend the stored range of a chat at its two ends, so everything between the oldest and the newest stored message counts as downloaded.

A chat without stored messages skips the newer pass. The older pass then starts at the newest message, so a new chat downloads newest first, and its recent messages reach the UI first. A stop in the middle leaves a range from the newest message down to some message. The next start runs the newer pass for the messages that arrived since, and the older pass from the oldest stored message.

`chats.downloaded` records that the older pass reached the first message. The downloader never requests older messages of such a chat again. The last check catches a message that arrives during the older pass.

Alternative: no column, and one older request per chat in each run. Rejected: 416 requests at every start, for no new message.

Alternative: request every missing id between the oldest and the newest stored message, to fill old gaps of `bot.py`. Rejected: the real database misses 350,224 ids in 33 channels and supergroups. Almost all are deleted messages, and Telegram throttles the requests to about one per 30 seconds, so the pass would take days.

### 3. Live messages are triggers, not data

`on_new_message` stores nothing. For a complete chat, it queues a catch-up download, which is `download_history` with the mark set. The newer pass then fetches the message, and every message that `events.NewMessage` did not deliver: service messages, and updates that Telegram skipped.

Costs: a catch-up costs two requests, one with the message and one empty. Every message that arrives while the chat is queued or running shares one extra pass with the others. The report at the end of the pass gives the `messages_count` of the `Message arrives` scenario.

Alternative: store the message at once, and fetch the hole when the id is not `MAX(message_id) + 1`. Rejected: private chats and small groups share the global sequence, so a hole is not visible there, and their service messages would be lost.

Alternative: store the message at once and queue a catch-up too. Rejected: the direct store moves `MAX(message_id)`, so the catch-up would need a second watermark.

### 4. Two message workers

Two `asyncio.Queue[int]`: `history_queue` for untracked and failed chats, and `live_queue` for the catch-ups of complete chats. One worker coroutine serves a queue, and both run `download_history`. The transitions of decision 1 put a chat into at most one queue, so the two workers never download the same chat.

Two passes at a time are fine for Telethon, which serializes the requests on its connection, and for SQLite, because every write is a short transaction in one thread. The spec relaxes "one chat at a time" to one history download and one catch-up.

Alternative: one worker with bounded passes and a priority queue. Rejected: `download_history` would need to resume per chunk and move a chat to `complete` only at exhaustion. More state for the same effect.

Alternative: a catch-up inside the handler. Rejected, as in `download-joined-chats`: Telethon runs each handler in its own task, so two messages would start two passes on one chat.

### 5. The media worker

State: `media_queue: asyncio.Queue[int]` and `media_pending: set[int]`, the chats in the queue. `queue_media(chat_id)` puts a chat into the queue when `media_enabled(chat_id)` is true and the chat is not pending. The triggers are `start_up()` and the check, for every chat with media on; `settings_changed(chat_id)`, after it clears the cache; and the end of each `download_history`.

A run, `download_chat_media(chat_id)`, walks the stored messages of the chat newest first, with a keyset cursor and 100 ids per step:

```
SELECT message_id FROM messages
WHERE chat_id = ? AND has_media AND media_path IS NULL AND media_type IS NOT 'other'
  AND message_id < cursor
ORDER BY message_id DESC LIMIT 100
```

Each step calls `get_messages(chat_id, ids=ids)`. Each returned message first goes through `store_version` of decision 11, because it can be newer than the stored row. For each message, the run then checks `media_enabled(chat_id)` and returns when the setting is off. A `None` message, or a `None` from `download_media`, writes `media_type` `other`. A file writes `media_type` and `media_path`. When `store_version` replaced the media of the row, the run takes the new media in the same step. An exception from `download_media` goes to the log, and the run continues. Each write is one `UPDATE` of the two columns in a short transaction. The cursor, not the `NULL` filter, moves the loop, so a failing file cannot loop within one run.

`save_message` becomes an insert that ignores a stored `(chat_id, message_id)`. It writes `media_id` and `edit_date`, but never `media_type` and `media_path`. Only the media worker writes those two.

The run reports the state of the chat after every 10 saved files and at its end, as in decision 12.

Why newest first: recent media matters more, and a stopped run continues with the older files. Why `other` only for a definite "no file": a `NULL` pair means "try again later", so a transient error retries at the next run. Why fetch the messages again: the database holds no media object, `get_messages` costs one request per 100 messages, and a fresh message carries a valid file reference.

Alternative: keep the inline download in `store_message`. Rejected: two writers of the same columns, a slower history download, and the stop rule needs the worker anyway.

Alternative: a `media_state` column. Rejected: `media_type` and `media_path` already encode the three states: `NULL` and `NULL` for missing, a type and a path for done, `other` and `NULL` for no file.

Stop rule: the check of `media_enabled` comes before each file, never during one. A file in progress when media goes off completes, its row gets its path, and the run then returns.

### 6. The check every 15 minutes

`check()` takes `sync_lock`, calls `read_dialogs()`, and then calls `queue_media` for every chat with media on. `start_up()` calls `check()` after it loads the seen senders. `check_forever()` sleeps 900 seconds and calls `check()`, without end. The dialog read of decision 1 handles untracked, complete, and failed chats, so the check needs no other logic. Cost: 5 requests every 15 minutes.

Alternative: signs and restarts only, as today. Rejected: items 3 to 5 of the proposal.

Alternative: every minute. Rejected: 15 times the requests for a delay that nobody waits on. Telethon uses the same 15 minutes for a channel without updates.

### 7. Failed downloads

On an exception in `download_history`, the worker logs the traceback, moves the chat from `downloading` to `failed`, and reports it with `complete` `false`. The chat ignores new messages until the next check puts it into the history queue again. A lasting error thus costs one attempt and one log entry every 15 minutes.

Alternative: queue the chat again at its next new message. Rejected: a lasting error, such as `ChannelPrivateError`, then retries at the message rate of the chat and fills the log.

### 8. `download_media`

`download_media(message, folder)` returns `tuple[str, str] | None`, the type and the path, and raises on a download error. `folder` is the message folder of the spec, plus the subfolder `<edit date>` when the row has `media_replaced_at`, as in decision 11. The caller catches. The type comes from the media: `MessageMediaPhoto` gives `photo`; `MessageMediaDocument` with a `Document` gives `video`, `image`, or `document` by mime type; anything else gives `None`. The file name is `Path(attribute.file_name).name`, or the default of the type when the attribute is missing or empty. The call passes the message to `client.download_media`, so Telethon can refetch an expired file reference. A `None` from the client means no file, and the function returns `None` without `utime`.

### 9. Schema and revision files

`alembic.ini` gets `file_template = %%(year)d-%%(month).2d-%%(day).2d_%%(hour).2d-%%(minute).2d-%%(slug)s`. The three existing files get new names from their Git dates:

- `0001_bot_py_schema.py` → `2026-11-19_11-54-bot_py_schema.py`
- `0002_rename_download_media.py` → `2026-11-19_11-55-rename_download_media.py`
- `0003_not_null_columns.py` → `2026-11-19_13-30-not_null_columns.py`

Alembic reads the revision ids from the files, so `0001` to `0003` stay valid, and a stored `alembic_version` needs no change. The new revision gets the id `0004` with `alembic revision --rev-id 0004 -m history_checked_and_versions`, which also names the file.

Revision `0004`:

- `chats.history_checked BOOLEAN NOT NULL DEFAULT 0`, which revision `0005` renames.
- `messages.edit_date TEXT`, the edit date of the stored version, `NULL` for an original.
- `messages.media_id INTEGER`, the Telegram id of the photo or the document.
- `messages.media_replaced_at TEXT`, the edit date of the version that brought the current media, `NULL` for the original media. Decision 12 explains it.
- Table `message_versions`: `id` primary key, `chat_id`, `message_id`, `version_date`, `text`, `has_media`, `media_type`, `media_path`, `media_id`, `created_at`. `UNIQUE(chat_id, message_id, version_date)`, which also serves the lookup of a message.

`op.add_column` adds the columns without batch mode. The downgrade drops them in batch mode, and drops the table. The models follow. `save_chat` inserts `downloaded` `False` and keeps it on conflict. Both pinned revisions in the tests become `"0004"`.

Revision `0005` renames `chats.history_checked`, the first name of the column, to `chats.downloaded` in batch mode. The rename keeps the marks that a run of `0004` already set.

Why `version_date` for the original is the message date: an edit date is always later, so the unique constraint holds with no `NULL`.

### 10. `run` and `settings_changed`

`main` builds the client with `catch_up=True`. `listen()` also registers `events.MessageEdited` with `on_message_edited`. `run` calls `listen()`, connects, checks the login, and then opens a `TaskGroup` with four tasks: the history worker, the live worker, the media worker, and `check_forever()`. It calls `start_up()`, waits for `run_until_disconnected()`, and cancels the four tasks. `api.serve` gets `downloader.clear_media_cache` for a new connection, as today, and `downloader.settings_changed` for a notice. `settings_changed(chat_id)` clears the cache and calls `queue_media(chat_id)`.

### 11. Message versions

`store_version(message)` runs in one short transaction:

1. Read the row of `(chat_id, message_id)`. With no row, return: the history pass stores the message later, already edited.
2. Compare `message.edit_date` with the stored `edit_date`. Return unless the new one is set and later. `NULL` is earliest. Both are ISO strings in UTC with `+00:00`, so string order is time order.
3. Insert the stored version into `message_versions`: `version_date` is the stored `edit_date`, or the message `date` for an original. Ignore a duplicate.
4. Update the row: `text`, `edit_date`, `has_media`, and `media_id`. When the new `media_id` differs from the stored one, also set `media_type` and `media_path` to `NULL` and `media_replaced_at` to the new edit date. Then call `queue_media(chat_id)`.

Callers: `on_message_edited`, and the media run of decision 5. The replay of `catch_up` arrives as normal edit events. `on_message_edited` ignores a chat that the downloader does not track.

The media folder of a replaced file adds the subfolder `media_replaced_at` in the form `%Y-%m-%d_%H-%M-%S`. The earlier version keeps its path in `message_versions`, so no file moves and no file gets overwritten. The photo name `photo_<id>.jpg` would collide without the subfolder.

Why `media_id`: a caption edit is the most common edit of a media message. Without the id, each caption edit would download the same file again.

Why `media_replaced_at` and not `edit_date` for the folder: a later caption edit changes `edit_date` but not the file. The media worker needs the date of the version that brought the file.

Alternative: store every version, the current one included, in `message_versions`. Rejected: you asked for the newest version in `messages`, and all readers of `messages` then stay as they are.

Alternative: a periodic fetch of all stored messages to find edits. Rejected: one request per 100 messages for each check, for the whole database.

### 12. Media progress

`DownloadStateJson` gets `files_count` and `files_pending`. `state()` and `initial_states()` compute them from `messages` with `count(media_path)` and `sum(has_media AND media_path IS NULL AND media_type IS NOT 'other')`. `download_state()` takes the two numbers. The backend `DownloadState` gets both fields with the default 0, and `read_chats` computes them with the same expressions. The fake downloader reads the media setting of the chat at the start of each simulation. `ChatListItem` appends ` 📎 <files>/<total>` to the download line, and `ChatDetails` adds a `Files:` row to both of its `download-stats` blocks, when the total is above 0.

Why after every 10 files: a file takes seconds, not milliseconds, so 100 would leave the UI still for minutes.

### 13. Tests

- `FakeClient.iter_messages(chat_id, min_id=0, offset_id=0, reverse=False)`: with `reverse`, the ids above `min_id`, ascending; otherwise the ids below `offset_id`, or all ids when it is 0, descending. `history_requests` records `(chat_id, "after", min_id)` or `(chat_id, "before", offset_id)`.
- `FakeClient.get_messages(chat_id, ids)` returns the messages of `histories` with these ids, in order, and `None` for a missing id. `message_requests` records each list of ids.
- `FakeClient.download_media(message, file)` writes `b"media"`. A `before_download` hook gets the message and can raise, for the failure scenarios.
- `download_queued()` runs the three workers and joins `history_queue`, `live_queue`, and `media_queue`, in that order. The workers queue media before they mark a task done, so the order holds. `start()` calls `listen()`, `start_up()`, and `download_queued()`, as today.
- The check scenarios call `downloader.check()` and then `download_queued()`. `check_forever()` is three lines around `check()` and has no test.
- A test sets `downloaded` through the model where a scenario names it. New chats start unset, as in production.
- The fake messages get `edit_date` and a `media` object with an id. `make_photo(media_id)` builds a `MessageMediaPhoto` with a `Photo` of that id. The version tests call the `MessageEdited` handler with an edited message.
- The UI tests in `ChatListItem.test.jsx` and `ChatDetails.test.jsx` cover the two `Media progress` scenarios. The e2e test turns media on and waits for `📎 100/100`.
- `tests/backend/` covers the `Stored file counts` scenario. `tests/downloader/test_fake.py` covers the fake file counts.

## Risks / Trade-offs

- [Two requests per live message in a busy chat] → Messages that arrive while the chat waits share one pass. Telethon sleeps through flood waits of up to one hour. The live check watches the log.
- [The first start after the upgrade queues every chat for the older check] → About 416 requests, a few minutes. The UI shows every chat as downloading during that time, once.
- [The older pass of a big supergroup takes long] → Telethon waits one second between chunks, as in a first download today. The newer pass ran first, so the live messages of the chat are stored.
- [A `top_message` that no history request returns] → The check queues the chat every 15 minutes, two requests each time. The chat shows `complete` `false`.
- [A big file in progress when media goes off] → The file completes. The worker stops before the next one.
- [A media run and a history download on the same chat at the same time] → They write different columns. The run sees only stored rows, and the end of the download queues one more run.
- [A deleted message marked `other` by mistake] → `MessageEmpty` is the definite answer of Telegram for a deleted message.
- [Telegram does not deliver `MessageService` for the chats that matter] → Not needed: the catch-up fetches them with a history request.
- [`DifferenceTooLong` after a long stop] → The edits of the stop are lost. The messages are not, because the dialog read finds them. The proposal puts this out of scope.
- [A message stored before the upgrade has no `media_id`] → Its first edit counts as new media, so the downloader saves a second copy of the same file. One file per such edit.
- [Old gaps from `bot.py`] → A message that `bot.py` skipped in the middle of a chat stays missing. The proposal puts this out of scope.
- [No automated test talks to Telegram] → The fake client covers the logic. The live check stays with you.

## Migration Plan

- `docker compose up --build`. The `migrate` service runs `0004` and `0005`. The renamed files keep their ids, so the stored version `0003` resolves. The downloader then checks the older history and the gaps of each chat once, and downloads the files of the chats with media on.
- Rollback: deploy the previous image. It finds the revision `0005` in `alembic_version` but no file for it, so its `migrate` service fails. First run `alembic downgrade 0003` with the new image, then deploy the old one. The downgrade drops `message_versions` and its rows.

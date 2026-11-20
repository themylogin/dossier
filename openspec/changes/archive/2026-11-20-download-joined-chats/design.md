# Design

## Context

See `proposal.md` for the motivation. These facts come from the code of this project, from Telethon 1.46.0 (the version in `uv.lock`), and from the Telegram API docs.

The downloader today:

- `start_up()` reads the dialog list, stores every dialog, and downloads the chats with unstored messages, one by one. `run` registers the new-message handler only after that.
- The handler stores the message of an unknown chat through `store_event_chat`, and marks the chat complete. No history download follows.
- A history download resumes after `MAX(message_id)` of the chat. A stored live message thus hides all older messages that the chat does not hold yet.

Telethon 1.46.0:

- `events.NewMessage` drops service messages, such as "X added you". `events.ChatAction` builds events from them, and from `UpdateChatParticipantAdd`.
- Telethon builds no event from `updateChannel`. Only `events.Raw(types.UpdateChannel)` receives it.
- Telethon dispatches each update in its own task, because `sequential_updates` is off by default. A handler that waits does not block other updates.
- Telethon follows the update sequence of a channel only when it knows the `pts` of the channel. At connect, it loads the `pts` values from the session file. Of the public calls, only `get_dialogs()` and `iter_dialogs()` set the `pts` of a channel that the session file does not hold.
- For a channel that it does not follow, Telethon drops `updateChannelTooLong`. It starts to follow the channel at the first message update that the server pushes for it.
- When a followed channel sends no update for 15 minutes, Telethon fetches its difference.
- Telethon saves the `pts` of each followed channel in the session file. It stops to follow a channel only when Telegram answers that the channel is private or invalid.

Telegram:

- The API docs say that `updateChannel` always comes with the channel object. They do not say when the server sends it.
- The API docs say that the server can stop or reduce passive updates for some channels and supergroups.
- The API docs say that a client can poll the difference of a public channel that the account did not join. So Telethon keeps on getting the posts of a public channel that the account left.
- A broadcast channel posts no service message when a member joins.

The real `messages.db` holds 416 chats: 322 private chats, 70 groups, and 24 channels. `get_dialogs()` reads 100 dialogs per request, so one read of this account takes 5 requests.

## Goals / Non-Goals

**Goals:**

- A joined chat follows the same rules as a chat at start: the same row, the same resume rule, and the same reports.
- A stop during any history download leaves no gap that the next start cannot fill.
- One history download at a time, for start-up chats and joined chats alike.

**Non-Goals:**

- No periodic read of the dialog list. Only a sign starts a read.
- No stored queue. The queue lives in memory, and the dialog read at the next start builds it again.
- No change to the update handling of Telethon, such as `catch_up` or `sequential_updates`.

## Decisions

### 1. Three signs, from untracked chats only

`listen()` registers three handlers:

- `events.Raw(types.UpdateChannel)`. The chat id is `utils.get_peer_id(types.PeerChannel(update.channel_id))`, the id with the channel mark.
- `events.ChatAction`, with `event.chat_id`.
- `events.NewMessage`, with `event.chat_id`.

The downloader tracks a chat when the chat is complete, or when its history download is queued, running, or failed. A sign counts only for a chat that the downloader does not track. A sign from a tracked chat costs no request and takes no lock. A message or a chat action also does not count when an earlier read did not find its chat, as in decision 5.

Alternatives:

- A read of the dialog list every minute. Rejected: it adds up to one minute of delay. It also costs 5 requests every minute for the real account, also when nothing changes.
- `events.ChatAction` alone. Rejected: a broadcast channel posts no service message for a join, and Telethon builds no chat action from `updateChannel`.
- `updateChannel` alone. Rejected: a small group and a new private chat send no `updateChannel`.

### 2. A dialog read on each sign

On a sign, the handler takes the sync lock. It checks again that it does not track the chat, and then reads the dialog list with `get_dialogs()`. The read handles each dialog that the downloader does not track, as on start:

- It stores the dialog with `save_dialog`. A new chat thus starts with media off, and a stored chat keeps its setting.
- When `dialog.dialog.top_message` is greater than the newest stored message id, it queues the chat.
- Otherwise, it marks the chat complete and reports it.

`start_up()` is the same read under the same lock, when the downloader tracks no chat yet. The check after the lock merges the signs of one join: the first read tracks the chat, so the other signs return at once.

Why the dialog list:

- `get_dialogs()` sets the `pts` of a new channel in Telethon. Telethon then follows the channel like a channel from the start, with gap checks and the difference after 15 minutes.
- The dialog list holds only the chats of the account. A channel that the account left, or never joined, is not in it. No separate membership check is necessary.
- Each dialog gives the name, the type, and the username in the form that `save_dialog` stores today.

Alternative: get the chat of the sign with `get_entity()` or `event.get_chat()`, check `Channel.left`, and queue the chat. This costs one request instead of 5. Rejected: Telethon then does not know the `pts` of the channel. It drops `updateChannelTooLong` for the channel and never fetches its difference on its own. The code would also need a second type mapping and a membership check.

### 3. One queue and one worker

An `asyncio.Queue` holds the dialogs to download. One worker task takes them in order, and downloads one chat at a time. `start_up()` and the later reads use the same queue. A chat that the account joins during a long start-up download thus waits for the chats before it.

The worker downloads a chat in passes. A pass is `iter_messages(chat_id, min_id=<newest stored id>, reverse=True)`, as in `download_history` today. Reports go out after every 100 messages of a pass, and once with `complete` `true` at the end.

Alternative: download the chat inside the handler. Rejected: Telethon runs each handler in its own task, so two joins would download two chats at the same time. A sign during the start-up download would also start a second download.

### 4. New messages: one rule per chat

`run` calls `listen()` before `client.connect()`, so no update arrives before the handlers. The new-message handler decides per chat:

- Untracked chat: it waits for a dialog read, as in decision 2, and then decides again.
- Chat with a queued, running, or failed history download: it does not store the message. It marks the chat, so that the worker runs one more pass after the current pass.
- Complete chat: it stores the message and reports the chat, as today.
- Chat outside the dialog list, which the dialog read did not track: it drops the message, as in decision 5.

The worker ends a download only after a pass during which no message arrived. It checks the mark and moves the chat to complete with no `await` between the two steps. Thus no message falls between the last pass and the complete state.

Why: the resume rule uses `MAX(message_id)`. A live message that the downloader stores during a history download raises it above the unstored history. If the downloader then stops, the next start skips that history for good. The current code prevents this for the start-up download with one global rule: the handler starts after the start-up download. The per-chat rule keeps this guarantee for each chat. It also lets the handler store the messages of complete chats during the start-up download.

A message can reach the handler while the worker waits for the answer to its last history request. That answer does not always hold the message. The mark catches this case. Without the mark, a busy chat loses such a message for good, at its next stored live message.

At start, signs can arrive before `start_up()` takes the lock, for example messages from the time when the downloader was stopped. The first such sign then makes the full read, and `start_up()` finds no untracked dialog. This costs one more read.

Alternatives:

- Store each live message at once, as today. Rejected: a stop during the download of a joined chat leaves a gap that no start fills.
- Keep the global rule, and start the handlers after the start-up download. Rejected: the downloader then misses the joins during the start-up download, which can take hours on a first run.
- Keep the skipped messages in memory and store them after the download. Rejected: the mark and one more pass give the same result with less state.

### 5. Chats outside the dialog list

When a dialog read does not find the chat of a sign, the downloader puts the chat into `outside`, a set for the current run. It logs the chat id and drops the message of the sign. A later message or chat action from a chat in `outside` causes no read, and the downloader drops it. Only `updateChannel` from such a chat starts a read, because it can mark a join. When a later read finds the chat, the chat becomes tracked as in decision 2.

Why: the posts of a public channel that the account left still arrive, as the context explains. This also applies to a channel that the account left before the start, because the session file keeps its `pts`. Without `outside`, each post costs a read of 5 requests, and a busy channel can cause flood waits. With `outside`, such a channel costs one read in each run.

The current code stores these posts, because `store_event_chat` creates a row for any unknown chat. The downloader downloads the dialogs of the account, so it now drops them.

Alternatives:

- Store the posts as today. Rejected: the chat then holds live posts with no history, which is the gap that this change removes.
- Let only `updateChannel` start a read for a channel, and drop all posts of untracked channels. Rejected: if Telegram does not send `updateChannel` for a join, the first post is the only sign of the channel.

### 6. A failed history download

When a pass raises an exception, the worker logs it and takes the next chat, as `start_up()` does today. The chat keeps its failed state until the next start. The handler stores none of its messages, and a sign does not queue it again. The next start resumes the chat after its newest stored message, with no gap.

Alternative: forget the chat, so that its next message queues it again. Rejected: a lasting error then retries at every new message of the chat and fills the log.

### 7. Code shape

- `Downloader` keeps `downloading: dict[int, bool]`, `complete: set[int]`, `outside: set[int]`, `queue: asyncio.Queue[Dialog]`, and `sync_lock: asyncio.Lock`. The value in `downloading` tells that a message arrived during the current pass. `known_chat_ids` and `store_event_chat` go away.
- `listen()` registers the three handlers.
- `start_up()` reads the dialog list under the lock. It no longer downloads.
- `download_queued_chats()` is the worker. It runs until `run` cancels it.
- `run` in `__main__.py` calls `listen()`, `connect()`, the login check, starts the worker task, and then calls `start_up()` and `run_until_disconnected()`. At the end, it cancels the worker.

### 8. Tests

- `FakeClient.add_event_handler` keeps each callback with its event builder. A helper finds a handler by its event type.
- `FakeClient.get_dialogs` returns the current list, so a test joins a chat when it adds a dialog. The fake counts the dialog reads.
- A hook at the end of a fake history lets a test send a message during the last history request.
- A test helper runs a downloader: `listen()`, the worker task, `start_up()`, and `queue.join()`.
- Each scenario of `specs/chat-download/spec.md` gets a test. The existing tests that call `start_up()` or `handlers[0]` move to the helpers.

## Risks / Trade-offs

- [Telegram does not send `updateChannel` to the session of the downloader for a join] → The live check in the tasks verifies it. Without it, a broadcast channel appears at its first post, through the new-message sign. Its history still downloads in full.
- [`updateChannel` arrives often for a channel outside the dialog list] → Each such sign costs a read of 5 requests. The log shows each read, so the live check can spot this.
- [A read misses a new chat, because the chat moves in the dialog list during the read] → The chat goes into `outside`. A channel then waits for its next `updateChannel`, and other chats wait for the next start. The next start downloads the chat in full.
- [The account leaves a public channel during a run] → The downloader still tracks the channel, so it stores its posts until the next start. The proposal puts leaves out of scope.
- [A flood wait during a dialog read] → Telethon sleeps through waits of up to one hour inside the read. The read keeps the lock during the wait. Signs of untracked chats wait. The worker and the messages of tracked chats go on.
- [Telegram stops the passive updates of a large joined channel] → Telethon follows the channel after the read. It fetches the difference after 15 minutes without updates. The next start fetches the rest.
- [A joined chat shows no download status at first] → The UI shows the chat after a page reload. `list_chats` gives it `complete` `null` until the first report, after 100 messages or at the end.
- [No automated test talks to Telegram] → The fake client covers the logic. The live check stays with you, as in the first downloader change.

## Migration Plan

- No schema change and no data migration. Rebuild and restart the stack with `docker compose up --build`.
- Rollback: deploy the previous image. The database needs no change.

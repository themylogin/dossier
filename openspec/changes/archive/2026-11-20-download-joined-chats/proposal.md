# Proposal

## Why

When you join a chat in your main Telegram app, the downloader does not download the chat. It notices the chat only at its first new message. It then stores that one message and marks the chat `complete`. The resume rule only fetches messages after the newest stored message, so the older history never downloads, not even after a restart.

The real `messages.db` shows the result. `bot.py` had the same rule. It stored two supergroups at their first new messages, 3328 and 1879, and it stored no older message of either.

## What Changes

- The downloader notices a chat that the account joins while the downloader runs. Any of these signs from a chat that it does not track starts this:
  - `updateChannel` from Telegram, for channels and supergroups. A broadcast channel sends no other sign of a join.
  - A new message, for example the first message of a new private chat.
  - A chat action, for example "added you" in a small group.
- On a sign, the downloader reads the dialog list again. It handles each dialog that it does not track as on start:
  - It stores the chat. A new chat starts with media off.
  - It queues the history download of the chat when Telegram has messages after the newest stored message.
  - Otherwise, the chat is complete.
- The downloader drops the messages of a chat that the dialog read does not find. An example is a public channel that you left: Telethon still gets its posts. Later messages of such a chat cause no new read in the same run. Before this change, the downloader stored them.
- One queue holds all history downloads, at start and later. One worker downloads one chat at a time.
- The downloader listens for new messages from its start, not after the start-up download. It stores a new message at once only when the chat has no queued or running history download. Otherwise, the history download fetches the message.
- A chat that first appears through a new message reports `complete` `false` until its history download ends. Before this change, it reported `complete` `true` at once.
- The downloader now stores the new messages that arrive during the start-up download in chats that are up to date or done. Before this change, it missed them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `chat-download`: new requirements for joined chats and for chats outside the dialog list. The `New messages` requirement now applies from the start of the downloader. It leaves the messages of a downloading chat to the history download.

## Impact

- `dossier/downloader/downloader.py`: the dialog read on a sign, and the download queue with its worker. It also gets the handlers for `updateChannel` and chat actions, and the new rule for new messages. `store_event_chat` and `known_chat_ids` go away.
- `dossier/downloader/__main__.py`: `run` registers the handlers before the start-up download. It runs the worker until Telegram disconnects.
- `tests/downloader/`: the fake client keeps each handler with its event type and counts the dialog reads. Tests that call `start_up()` also wait until the queue is empty. New tests cover the new scenarios.
- `README.md`: one sentence about joined chats.
- Telegram requests: one dialog read for each sign. The real account has 416 dialogs, so one read takes 5 requests.
- No change to the database schema, the downloader API, the backend, the UI, or the fake downloader.

## Out of Scope

- The older history of chats that are already stored without it, such as the two supergroups above. Such a chat needs a download of the messages before its oldest stored message.
- A chat that the account leaves and joins again while the downloader runs. The downloader still tracks the chat, so it does not fetch the messages from the time between.
- A live update of the UI chat list. The UI shows a new chat at its next `list_chats`, for example after a page reload.

## Assumptions

- The main Telegram app and the downloader use the same account.
- Telegram sends `updateChannel` to all sessions of the account when the account joins a channel or a supergroup. No automated test can check this. The live check in the tasks confirms it.
- A chat that the account joins while the downloader is stopped downloads at the next start, as before.

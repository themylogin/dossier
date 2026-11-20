# Tasks

## 1. One download queue and the per-chat message rule

- [x] 1.1 In `tests/downloader/fakes.py`, make `FakeClient.add_event_handler` keep each callback with its event builder. Add a lookup of a handler by its event type. Count the calls of `get_dialogs`. Add a hook that runs after the last message of a fake history. Verify that `docker compose --profile test run --rm --build test mypy` passes.
- [x] 1.2 In `dossier/downloader/downloader.py`, replace `known_chat_ids` with `downloading`, and add `outside`, `queue`, and `sync_lock`, as in design decision 7. Make `start_up()` read the dialog list under the lock, as in decision 2. It queues or completes each untracked dialog, and downloads nothing. Verify that mypy passes.
- [x] 1.3 Add the worker `download_queued_chats()`, as in decisions 3, 4, and 6. It downloads one chat at a time, in passes after the newest stored message. It runs one more pass while the chat has the mark. Between the last check and the complete state, it has no `await`. On an exception, it logs the error and keeps the chat in `downloading`. Verify that mypy passes.
- [x] 1.4 Change `on_new_message` to the per-chat rule of decision 4. For an untracked chat, it takes the lock, checks the chat again, and reads the dialog list. It skips the read for a chat in `outside`. A chat that the read does not find goes into `outside`, as in decision 5. Remove `store_event_chat`. Verify that mypy passes.
- [x] 1.5 In `dossier/downloader/__main__.py`, make `run` call `listen()` before `client.connect()`. After the login check, `run` starts the worker task and calls `start_up()`. After `run_until_disconnected()`, it cancels the worker. Verify that mypy passes.
- [x] 1.6 Add a test helper that calls `listen()`, starts the worker, calls `start_up()`, and waits for `queue.join()`. Move the tests in `test_downloader.py`, `test_media.py`, `test_concurrency.py`, and `test_new_messages.py` to the helper. Replace each use of `handlers[0]` with the lookup by event type. In `test_main.py`, wait for the `complete` report of chat `-2001` before the photo events. Remove `test_message_from_a_new_chat_stores_the_chat_with_media_off`, because task 2.2 covers that case with the new rule. Verify that `docker compose --profile test run --rm --build test pytest tests/downloader` passes.
- [x] 1.7 Add a test for each scenario of the modified `New messages` requirement in `specs/chat-download/spec.md`. For "Message during the last history request", use the hook of task 1.1 to send message 301. For the scenarios with a restart or a failed download, let the fake history raise an error. Then start a second downloader on the same database. Verify that the downloader tests pass, and that the restart test finds messages 1 to 302 with no gap.

## 2. Joined chats

- [x] 2.1 In `listen()`, register `events.Raw(types.UpdateChannel)` and `events.ChatAction`, as in decision 1. For `updateChannel`, the chat id is `utils.get_peer_id(types.PeerChannel(update.channel_id))`. For an untracked chat, each handler starts the dialog read of task 1.4. The `updateChannel` handler reads also for a chat in `outside`. Log each dialog read, each queued chat, and each chat that goes into `outside`. Verify that mypy passes.
- [x] 2.2 Add a test for each scenario of the `Joined chats` and `Chats outside the dialog list` requirements in `specs/chat-download/spec.md`. A test joins a chat when it adds a dialog and a history to the fake client. Check the count of dialog reads where a scenario names a read. Verify that the downloader tests pass.
- [x] 2.3 In `README.md`, add to the downloader item that it also downloads each chat that the account joins while it runs. Verify that the sentence is in `README.md`.

## 3. Integration checks

- [x] 3.1 Run the Python tests, mypy, `ruff check`, and `ruff format --check` with the commands in `README.md`. Verify that each command passes.
- [x] 3.2 Run the end-to-end tests with `docker compose -f e2e/compose.yaml run --rm --build e2e`. Verify that they pass. They use the fake downloader, so they show that the UI and the backend still work.
- [ ] 3.3 Ask the user to run the live check with their account. If `DATA_DIR` holds no `dossier_bot.session`, they first run `docker compose run --rm downloader login`. They start the stack with `docker compose up --build` and wait for the start-up download to end. Then they join a broadcast channel in the main Telegram app. Verify that the downloader log shows a dialog read and the download of the channel. Verify that, after a page reload, the UI shows the channel with `✓`. Repeat with a small group or a new private chat. Verify that each chat that the log puts into `outside` is a chat that the user left.

## Workflow follow-up

- Archive the change after the user confirms the live check of task 3.3.

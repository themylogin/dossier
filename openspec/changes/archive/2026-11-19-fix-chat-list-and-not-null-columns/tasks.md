# Tasks

Run every command in `dossier/`, and run every build, check, and test in a container.

## 1. Chat order in the UI

- [x] 1.1 Sort the chats in `frontend/src/components/ChatList.jsx` as in design 1. Add tests to `ChatList.test.jsx` for "Newest chat first", "Download status does not change the order", "Dates with different offsets", "Same date", and "Progress moves a chat". Verify that `docker compose --profile test run --rm --build frontend-test` passes. Verify that `npm run lint` in the same service reports no errors.

## 2. Stored-message states

- [x] 2.1 Change `BackendApi` in `dossier/backend/api.py` as in design 2. Unreported chats get stored-message states in `list_chats` and `update_chat`. Remove the order by name. Add backend tests for "Chat without a reported state", "Chat without messages", "Reported state wins", and "Result with stored messages". Make the test that expected the name order compare the chats without order. Verify that mypy and the Python tests pass.

## 3. Required columns

- [x] 3.1 Change the annotations of the 13 columns of design 3 in `dossier/models.py`. Change the code and the test fixtures as in design 5. Verify that mypy passes.
- [x] 3.2 Generate revision `0003` with the command of design 4, and check the new file with `ls`. Run `ruff check --fix` and `ruff format` on the file, and remove the marker comments of autogenerate. Verify that the file holds 13 `alter_column` calls in three `batch_alter_table` blocks, and the reverse calls in `downgrade`.
- [x] 3.3 Change the expected revision in the migration tests to `0003`. In the `bot.py` adoption test, check that each required column is NOT NULL and that all rows stay. Add a test for "Message without a date". The downloader tests cover "Message from the downloader". Verify that the Python tests pass, including the test that the models match the migrations.
- [x] 3.4 In a container, upgrade a fresh database to `head`, downgrade it to `base`, and upgrade it to `head` again. Verify that each step exits with code 0.

## 4. Real database

- [x] 4.1 Copy `data/messages.db` to the local disk with the SQLite backup API. Run `alembic upgrade head` on the copy in a container, and record the time. Verify that the counts of messages, chats, and users stay the same, and that the 13 columns are NOT NULL.
- [x] 4.2 Run `docker compose down`, and back up `data/messages.db`. Run `docker compose up -d --build`. Verify that `migrate` exits with code 0, and that the database is at revision `0003`.
- [x] 4.3 Call `list_chats` through the backend. Verify that it returns 416 chats with their stored counts and dates. Ask the user to check the order and the counts in the UI.

## 5. Integration checks

- [x] 5.1 Run `ruff check`, `ruff format --check`, mypy, the Python tests, the UI unit tests, and ESLint. Run the e2e command on a fresh e2e volume. Verify that each command passes.

## 6. No download status without the downloader

- [x] 6.1 Make `complete` `null` for chats without a state from the connected downloader. Drop the reported states when the backend loses the downloader, and send the stored states to the UI, as in design 6. Add a backend test for "Downloader stops", and update the tests that expected `false`. Verify that mypy and the Python tests pass.
- [x] 6.2 Show `⏳` only for `false` and `✓` only for `true` in `ChatListItem.jsx` and `ChatDetails.jsx`. Add UI tests for "Downloader down". Verify that the UI unit tests and ESLint pass.
- [x] 6.3 Rebuild and restart the stack. Verify that `list_chats` returns `"complete": null` for every chat. Run the checks of task 5.1 again, and ask the user to check the UI.

## Workflow follow-up

- Archive the change after the user confirms the UI check of task 4.3.

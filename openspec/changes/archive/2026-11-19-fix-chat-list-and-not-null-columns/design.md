# Design

## Context

See `proposal.md` for the motivation. These facts shape the approach:

- `ChatList.jsx` renders the chats in the order of `list_chats`. `useChats` replaces the state of a chat in place on each notification. Nothing in the UI sorts.
- `BackendApi.read_chats` orders by `chats.name`. The real database has 46 chats with an empty name, so "Unnamed Chat" fills the top of the list.
- `BackendApi` knows only the states that the downloader reports. Without a downloader, as now without `.env`, every chat has the zero state.
- `ChatListItem` shows `⏳` for every state whose `complete` is not `true`. `ChatDetails` shows "The chat is being downloaded" for the same states. A state that says nothing about a download thus reads as a running download.
- The fake downloader reports 1,000 simulated messages per chat, but it stores no messages. The e2e tests and the `fake-downloader` spec rely on these reported states.
- The real database holds 1,676,499 messages, 416 chats, and 35,810 users.
- The state query `SELECT chat_id, COUNT(*), MIN(date), MAX(date) FROM messages GROUP BY chat_id` scans `idx_chat_message` and reads each row. It takes 0.41 s on the local disk. On the NFS data folder, it takes 2.0 s cold and 0.34 s warm.
- `migrations/env.py` sets `render_as_batch=True`. Autogenerate thus emits `batch_alter_table` blocks, which SQLite needs for a NOT NULL change. In batch mode, Alembic copies each table into a new one.
- The models derive nullability from their `Mapped` annotations. `Mapped[str]` is NOT NULL, and `Mapped[str | None]` allows NULL.

## Goals / Non-Goals

**Goals:**
- The UI shows the stored counts and dates when no downloader runs.
- Revision `0003` comes from autogenerate, not from hand-written operations.

**Non-Goals:**
- An index for the state query.
- Server defaults for the new NOT NULL columns.
- A `complete` value without the downloader.

## Decisions

### 1. The UI sorts the list

`ChatList` sorts the filtered chats at render time:

- by the instant of `newest_message_date`, newest first, so the UTC offset of the text does not matter;
- chats without a `newest_message_date` last;
- ties by name, with `localeCompare`.

`useChats` already replaces the state of a chat on each notification. A sort at render time thus covers the loaded list and every progress update.

The backend drops its `ORDER BY name`, because the UI order replaces it.

Alternative: order the chats in the SQL of `list_chats`. Rejected: progress changes the dates after the load, so the UI must sort anyway.

### 2. Stored-message states for unreported chats

`BackendApi.read_chats` runs one query in the worker thread. It joins each chat to its messages with a LEFT JOIN, and reads `COUNT`, `MIN(date)`, and `MAX(date)` per chat. One statement reads one snapshot of the database. On the local copy, the query takes 0.38 s, as long as the plain `GROUP BY`.

For each chat, the state is the reported state when the downloader has reported the chat. Otherwise, it is the stored-message state with `complete = null`. `update_chat` stores the setting with `session.get` and an attribute change. Then it runs the same query for its one chat.

A reported state wins, because the fake downloader reports simulated counts without stored messages. The `fake-downloader` spec requires `list_chats` to show them. The real downloader computes its states from the same tables, so the precedence changes nothing for real chats.

Alternatives:
- Stored counts for every chat. Rejected: this breaks the fake downloader and its spec.
- The fake stores its messages. Rejected: a restarted simulation would then have to delete messages, which changes the `fake-downloader` capability for no user gain.
- An aggregate only for the unreported chats. Rejected: one aggregate for all chats is simpler. It costs 0.34 s to 2 s for each list load.

### 3. Required columns from the data

A column becomes NOT NULL when the real database holds no NULL in it, and no code path writes NULL to it:

| Table | NOT NULL | Stays nullable, with NULLs in the data |
|---|---|---|
| `messages` | `date`, `text`, `has_media`, `created_at` | `sender_id` (3,073), `grouped_id`, `media_type`, `media_path` |
| `chats` | `name`, `type`, `tracked`, `download_media`, `first_seen_at`, `updated_at` | `username` (130) |
| `users` | `is_bot`, `first_seen_at`, `updated_at` | `username`, `first_name`, `last_name`, `phone` |

`chats.name` holds 46 empty strings and no NULL. The empty strings stay. The primary keys, `messages.chat_id`, and `messages.message_id` are NOT NULL already.

### 4. The models first, then autogenerate

The models change their annotations, such as `Mapped[str | None]` to `Mapped[str]`. Then a one-off container generates the revision against a fresh database at revision `0002`:

```sh
docker compose --profile test run --rm --build -v "$PWD":/app test \
  sh -c "mkdir -p /data && alembic upgrade head && alembic revision --autogenerate --rev-id 0003 -m 'Not null columns'"
```

The fresh database lives in the container and goes away with it. `--rev-id 0003` keeps the numbering of the revisions.

After generation, ruff fixes and formats the file. The marker comments of autogenerate go, because of the comment rules. Nothing else in the file changes by hand.

The expected content is 13 `alter_column(..., nullable=False)` calls in three `batch_alter_table` blocks. `downgrade` holds the reverse calls.

### 5. Code that writes the columns

- `Downloader.save_message` stores `message.date.isoformat()`, without the branch for a missing date.
- `BackendApi.to_chat` uses `row.name` and `row.download_media` directly, without the fallbacks for NULL.
- The tests that insert `Chat` rows set `type` and `tracked`.

The NOT NULL constraints reject any other path at write time. The downloader tests cover the real write paths.

### 6. No download status without the downloader

`complete` has three values: `false` while the downloader downloads the chat, `true` when the download is complete, and `null` when no connected downloader reports the chat.

- `BackendApi` keeps the reported states only while the link lasts. When the link drops, `DownloaderApiClient.run` calls its `on_disconnect` callback, `BackendApi.downloader_disconnected`. This callback clears the states and sends the stored state of each chat that had one to the UI.
- The UI shows `⏳` only for `false`, and `✓` only for `true`. The details panel shows its download message only for these two values.

Alternatives:
- A separate notification for the status of the downloader, plus a flag in `list_chats`. Rejected: this adds API, and the UI would have to combine two sources, while `complete` already carries the status of each chat.
- Keep the reported states after a lost link. Rejected: the chats would then stay on `⏳` while nothing downloads.

## Migration Plan

In batch mode, revision `0003` copies the 1,676,499 messages into a new table. The copy needs time and free space for a second copy of the table. The rollout thus has four steps:

1. Run `alembic upgrade head` on a copy of the real database on the local disk. Record the time, and compare the row counts.
2. Stop the stack with `docker compose down`, so that no service holds the file during the copy.
3. Back up `data/messages.db`.
4. Run `docker compose up -d --build`. The `migrate` service applies `0003`, and then the services start.

Rollback: `alembic downgrade 0002` makes the columns nullable again. The backup restores the file.

## Risks / Trade-offs

- [A NULL in a required column before the migration] → The batch copy fails, `migrate` exits with a non-zero code, and no service starts. The real data holds no such NULL today, and the backup keeps the file safe.
- [The copy of 1.68M rows on NFS is slow] → Step 1 measures it on a local copy first. The stack stays down during the copy.
- [The file grows by the size of the rebuilt tables] → On the local copy, the upgrade took 13.5 s, and the file grew from 475 MB to 852 MB. SQLite reuses the free pages for new rows. A `VACUUM` can shrink the file later.
- [Chats move while the user reads the list] → A history download raises `newest_message_date` with each report, so its chat moves up. This is the requested order.
- [A short restart of the downloader drops all states] → For about one second, the UI shows no status, until the new snapshot arrives.
- [`list_chats` reads all messages on each call] → 0.34 s to 2 s is acceptable for a list load. An index stays out of scope.
- [The e2e tests pick the first list item] → They read its test id once, so a later move of the item does not break them.

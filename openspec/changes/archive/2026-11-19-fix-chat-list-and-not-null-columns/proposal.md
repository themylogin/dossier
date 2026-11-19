# Proposal

## Why

The chat list is hard to use with the real database. It orders chats by name, so 46 unnamed chats come first. Every chat shows 0 messages, although `messages.db` holds 1,676,499 messages. The schema also allows NULL in 13 columns that hold no NULL in the real data.

## What Changes

- The UI orders the chat list by the date of the newest stored message, newest first. Chats without messages come last. The download status does not change the order. A progress notification moves its chat to its new place.
- `list_chats` and `update_chat` give a chat that the downloader has not reported the state of its stored messages. This state has the message count, the oldest and newest dates, and `complete` `null`: no downloader reports the chat. A reported state still wins. Before this change, such a chat had the zero state.
- The UI shows no download status for `"complete": null`: no `⏳`, no `✓`, and no download message. When the backend loses the downloader, it drops the reported states. No chat thus shows `⏳` while the downloader is down.
- The backend no longer orders the chats by name.
- 13 columns become NOT NULL: `messages.date`, `messages.text`, `messages.has_media`, `messages.created_at`, `chats.name`, `chats.type`, `chats.tracked`, `chats.download_media`, `chats.first_seen_at`, `chats.updated_at`, `users.is_bot`, `users.first_seen_at`, and `users.updated_at`. The models change first. Then `alembic revision --autogenerate` generates revision `0003` from them.
- The downloader always stores the date of a message.

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `chat-download-ui`: the order of the chat list, and no download status without a downloader.
- `chat-download-api`: the state of a chat that the downloader has not reported, and `complete` `null`.
- `downloader-api`: the backend drops the reported states when it loses the downloader.
- `chat-download`: the required columns of `messages.db`.

## Impact

- `frontend/src/components/ChatList.jsx` and its tests: the order of the list.
- `frontend/src/components/ChatListItem.jsx`, `ChatDetails.jsx`, and their tests: no download status for `"complete": null`.
- `dossier/backend/api.py`, `downloader_api.py`, `chats.py`, and the backend tests: stored-message states, `complete` `null`, the dropped states on a lost link, and no order by name.
- `dossier/models.py`, `dossier/downloader/downloader.py`, and the test fixtures that insert rows: the required columns.
- `migrations/versions/0003_not_null_columns.py`: a new, generated revision.
- The real `messages.db`: revision `0003` rebuilds the `messages`, `chats`, and `users` tables. The stack must stop before the `migrate` service applies the revision.

## Assumptions

- Chats with the same newest date, and chats without messages, follow in name order.
- The stored-message state query reads all 1,676,499 messages. It takes 0.41 s on the local disk, and 0.34 s to 2.0 s on NFS. The change adds no index.
- The 46 chats with an empty name keep the empty string. NOT NULL accepts it, and the UI shows "Unnamed Chat".

# Proposal

## Why

The chat list mixed dates, message counts, and file counts in one line, so the dates were hard to read. The list also gave no quick way to see which chats are still downloading.

## What Changes

- Each list item shows only the download status and the dates. The message count and the file count stay in the details panel.
- Tabs over the list, as the folder tabs of Telegram: `All`, `Downloaded`, and `Downloading`, each with its number of chats. `All` is the first tab and is active on load. `Downloading` shows only while at least one chat is not downloaded.
- A chat belongs to `Downloaded` when its state has `"downloaded": true`. The `downloaded` field changes once per chat, so a new message does not move a chat between tabs.
- The active tab has a translucent blue indicator with round top corners over the bottom line of the tab bar.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `chat-download-ui`: list items without counts, the media progress in the details panel only, and the new chat tabs.

## Impact

- `frontend/src/components/ChatTabs.jsx` (new), `ChatListItem.jsx`, `App.jsx`, and `App.css`.
- `frontend/src/components/*.test.jsx` and `e2e/tests/chat-download.spec.js`.
- No change to the backend, the downloader, or the API.

# Tasks

## 1. Chat list and tabs

- [x] 1.1 In `ChatListItem.jsx`, show only the status and the dates, as in the `Chat list` requirement of `specs/chat-download-ui/spec.md`. Update the tests in `ChatListItem.test.jsx` and `ChatList.test.jsx`. Verify that `docker compose --profile test run --rm --build frontend-test` passes.
- [x] 1.2 Add `ChatTabs.jsx` with `visibleTabs` and `chatsOfTab`, and use it in `App.jsx`, as in the `Chat tabs` requirement. Style the active tab in `App.css` with a translucent indicator with round top corners over the bottom line of the bar. Add `ChatTabs.test.jsx`. Verify that the UI tests pass.
- [x] 1.3 In `e2e/tests/chat-download.spec.js`, check the message count and the files in the details panel, and the chat in `Downloaded` after it completes. Verify that `docker compose -f e2e/compose.yaml run --rm --build e2e` passes.

# Tasks

## 1. Export and Gateway call

- [x] 1.1 Add `dossier/backend/openclaw.py` with `OpenClawSettings`, `load_openclaw_settings`, `OpenClawError`, `export_chat`, and `submit`, as in design decisions 2, 3, and 4. Verify that `docker compose --profile test run --rm --build test mypy` passes.
- [x] 1.2 Add `tests/backend/test_openclaw.py` with a fake Gateway in a thread. Cover each scenario of `specs/openclaw-requests/spec.md`, calling `export_chat` and `submit` directly. Open each export with `sqlite3` and assert its rows. Verify that `docker compose --profile test run --rm --build test pytest tests/backend/test_openclaw.py` passes.

## 2. JSON-RPC method

- [x] 2.1 Add `submit_request` to `BackendApi` as in design decision 5. Give `create_app` the settings and the exports folder, and dispatch `submit_request` in `ws_jsonrpc`. Make `main.py` read the settings from `os.environ`. Verify that mypy passes.
- [x] 2.2 Add a test for each scenario of `Submit a request` in `specs/chat-download-api/spec.md` to `tests/backend/`, over the WebSocket, with the fake Gateway of task 1.2. Verify that `docker compose --profile test run --rm --build test pytest tests/backend` passes.

## 3. Request form

- [x] 3.1 Add `RequestForm` to `ChatDetails.jsx` below the stats of both branches, and pass `onSubmitRequest` from `App.jsx` with a timeout of 120 seconds, as in design decision 6. Add a CSS rule for the form in `App.css`. Verify that the UI builds with `docker compose --profile test run --rm --build frontend-test`.
- [x] 3.2 Add a test for each scenario of `Request form` in `specs/chat-download-ui/spec.md` to `ChatDetails.test.jsx`. Verify that `docker compose --profile test run --rm --build frontend-test` passes.
- [x] 3.3 Add an e2e test that selects a chat, submits a request, and expects `OpenClaw is not configured`. Verify that `docker compose -f e2e/compose.yaml run --rm --build e2e` passes.

## 4. Configuration and documentation

- [x] 4.1 In `compose.yaml`, give the backend `OPENCLAW_URL`, `OPENCLAW_HOOK_TOKEN`, `OPENCLAW_AGENT_ID`, and `OPENCLAW_EXPORT_PATH` with empty defaults, and the volume `${OPENCLAW_EXPORT_DIR:-./exports}:/exports`, with no host entry. Add the five keys to `.env.example`, and `/exports/` to `.gitignore`. Verify that `docker compose config` shows the volume and no `extra_hosts`.
- [x] 4.2 In `README.md`, add an `OpenClaw` section that lists the five `.env` keys. Verify that each key of `.env.example` appears in the section.

## 5. Session link

- [x] 5.1 In `submit`, send `sessionMode` `persistent`, the session key `dossier:<chat id>:<time>`, and `deliver` `false`. Add `session_url`, and return the link from `submit_request`. In `RequestForm`, show `Open in OpenClaw` with the link. Extend the tests of `Submission to the OpenClaw Gateway`, `Submit a request`, and `Request form`. Add the two OpenClaw `hooks` settings to the `OpenClaw` section of `README.md`. Verify that the Python tests, mypy, ruff, and the UI tests pass.

## 6. Integration checks

- [x] 6.1 Run the Python tests, mypy, `ruff check`, `ruff format --check`, the UI unit tests, and the e2e tests with the commands in `README.md`. Verify that each passes.
- [x] 6.2 Ask the user to set the `.env` keys, run `docker compose up --build`, and submit a request for a small chat. Verify that the UI shows `Submitted to OpenClaw` and `Open in OpenClaw`, that the file is in the shared folder, and that the link opens the session with the agent's answer about the chat.

## Workflow follow-up

- Archive the change after the user confirms the live check of task 6.2.

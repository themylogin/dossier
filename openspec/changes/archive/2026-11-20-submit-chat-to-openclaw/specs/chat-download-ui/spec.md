# Spec Delta

## ADDED Requirements

### Requirement: Request form
The details panel of the selected chat SHALL show, below its stats, a multiline text field and a `Submit` button. Enter SHALL add a line break. `Submit` SHALL be disabled while the text holds only whitespace or a request is in progress. `Submit` SHALL call `submit_request` with the chat id and the text, and wait up to 2 minutes. On success, the UI SHALL clear the text and show `Submitted to OpenClaw`. On error, it SHALL keep the text and show the error message.

#### Scenario: Request sent
- **GIVEN** the user selected chat `-2001` and typed two lines into the request field
- **WHEN** the user clicks `Submit` and the backend returns a result
- **THEN** the UI called `submit_request` with `"id": -2001` and the two lines
- **AND** the field is empty, and the panel shows `Submitted to OpenClaw`

#### Scenario: Request failed
- **WHEN** `submit_request` returns the error `OpenClaw is not configured`
- **THEN** the panel shows `OpenClaw is not configured`
- **AND** the field keeps its text

#### Scenario: Empty field
- **WHEN** the request field holds only spaces
- **THEN** `Submit` is disabled

### Requirement: Link to the session
After a successful request, the request form SHALL show the link `Open in OpenClaw` to the `session_url` of the result. The link SHALL open in a new tab.

#### Scenario: Link after a request
- **WHEN** `submit_request` returns `"session_url": "https://openclaw.example.com/chat/main/dossier/-2001/2026-05-22_10-30-00"`
- **THEN** the panel shows `Open in OpenClaw`, which links to that URL in a new tab

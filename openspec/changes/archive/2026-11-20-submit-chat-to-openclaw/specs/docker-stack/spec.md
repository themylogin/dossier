# Spec Delta

## MODIFIED Requirements

### Requirement: Configuration in .env
The stack SHALL read `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`, `DATA_DIR`, `DOWNLOADS_DIR`, `OPENCLAW_URL`, `OPENCLAW_HOOK_TOKEN`, `OPENCLAW_AGENT_ID`, `OPENCLAW_EXPORT_DIR`, and `OPENCLAW_EXPORT_PATH` from `.env` in `dossier/`. The downloader and the backend SHALL mount `DATA_DIR` at `/data`, the downloader SHALL mount `DOWNLOADS_DIR` at `/downloads`, and the backend SHALL mount `OPENCLAW_EXPORT_DIR` at `/exports`. When `DATA_DIR`, `DOWNLOADS_DIR`, or `OPENCLAW_EXPORT_DIR` is unset, the stack SHALL use `./data`, `./downloads`, or `./exports`. A committed `.env.example` SHALL list the keys, and git SHALL ignore `.env`, `data/`, `downloads/`, and `exports/`.

#### Scenario: Folders from .env
- **GIVEN** `.env` sets `DATA_DIR=/srv/dossier/data` and `DOWNLOADS_DIR=/srv/dossier/downloads`
- **WHEN** the downloader downloads a chat with media on
- **THEN** `messages.db` and `dossier_bot.session` are in `/srv/dossier/data`
- **AND** the media files are in `/srv/dossier/downloads`

#### Scenario: Missing key
- **GIVEN** `.env` lacks `TELEGRAM_API_ID`
- **WHEN** the downloader starts
- **THEN** it exits with a non-zero code and a message that names `TELEGRAM_API_ID`

#### Scenario: Shared folder from .env
- **GIVEN** `.env` sets `OPENCLAW_EXPORT_DIR=/mnt/openclaw-share`
- **WHEN** a request for a chat is submitted
- **THEN** the export file is in `/mnt/openclaw-share` on this machine

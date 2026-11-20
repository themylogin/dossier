# Spec Delta

## ADDED Requirements

### Requirement: Joined chats
While it runs, the downloader SHALL download each chat that the account joins. A sign from a chat that it does not track SHALL make it read the dialog list again: `updateChannel` from Telegram, a new message, or a chat action. It SHALL then handle each dialog that it does not track as on start. It tracks a chat from the time that it reads the chat from the dialog list. A sign from a tracked chat SHALL NOT make it read the dialog list.

#### Scenario: Channel joined in the main app
- **GIVEN** the downloader runs, and the database holds no message of channel `-1000000005001`
- **WHEN** the account joins the channel, which has 300 messages, in the main Telegram app
- **THEN** the downloader stores the channel with media off
- **AND** it downloads the 300 messages, oldest first
- **AND** the channel reports `complete` `true` at the end

#### Scenario: Added to a group
- **GIVEN** the downloader runs
- **WHEN** a member adds the account to a small group with 50 messages
- **THEN** the downloader stores the 50 messages of the group
- **AND** the group reports `complete` `true` at the end

#### Scenario: First message of a new private chat
- **GIVEN** the downloader runs, and the account has no chat with a person
- **WHEN** the person sends the first message to the account
- **THEN** the downloader stores the chat and the message
- **AND** the chat reports `complete` `true` with `messages_count` 1

#### Scenario: Join during the start-up download
- **GIVEN** the downloader downloads chat `-2001` on start
- **WHEN** the account joins channel `-1000000005001`
- **THEN** the downloader downloads the channel after chat `-2001`

#### Scenario: Change of a tracked channel
- **GIVEN** the downloader tracks channel `-1000000005001`
- **WHEN** Telegram sends `updateChannel` for the channel
- **THEN** the downloader does not read the dialog list

### Requirement: Chats outside the dialog list
The downloader SHALL store no message from a chat that its dialog read did not find. For the rest of the run, a new message or a chat action from that chat SHALL NOT cause a new dialog read. Only `updateChannel` from the chat SHALL do so.

#### Scenario: Channel outside the dialog list
- **GIVEN** the dialog list of the account does not hold channel `-1000000005002`
- **WHEN** Telegram sends `updateChannel` for the channel
- **THEN** the downloader stores no chat and downloads no history

#### Scenario: Posts of a public channel that the account left
- **GIVEN** the account left public channel `-1000000005003`, and Telegram still sends its posts
- **WHEN** two posts of the channel arrive
- **THEN** the downloader reads the dialog list once
- **AND** it stores neither post

#### Scenario: Left channel joined again
- **GIVEN** a dialog read did not find channel `-1000000005003`
- **WHEN** the account joins the channel again
- **THEN** the downloader reads the dialog list
- **AND** it downloads the channel after its newest stored message

## MODIFIED Requirements

### Requirement: New messages
The downloader SHALL listen for new messages from its start, before the start-up download. It SHALL store each new message of a chat when it arrives, and report the new state of the chat. While a history download of the chat is queued or runs, the history download SHALL store the message instead. This SHALL hold also for a message that arrives during the last history request. After a failed history download, the downloader SHALL store no new message of the chat until the next start.

#### Scenario: Message arrives
- **GIVEN** a chat reports `complete` `true` and `messages_count` 40
- **WHEN** a new message arrives in the chat
- **THEN** the downloader stores the message
- **AND** it reports the chat with `messages_count` 41 and the date of the new message as `newest_message_date`

#### Scenario: Message during the start-up download
- **GIVEN** the downloader downloads chat `-2001` on start, and chat `-2002` is up to date with 40 messages
- **WHEN** a new message arrives in chat `-2002`
- **THEN** the downloader stores the message at once
- **AND** it reports chat `-2002` with `messages_count` 41

#### Scenario: Message during the last history request
- **GIVEN** the downloader downloads chat `-2001`, which has 300 messages
- **WHEN** message 301 arrives in the chat during the last history request
- **THEN** the history download stores message 301
- **AND** the chat reports `complete` `true` with `messages_count` 301

#### Scenario: Restart during a download
- **GIVEN** the downloader stored messages 1 to 100 of chat `-2001`, which has 300 messages
- **AND** messages 301 and 302 arrived in the chat during the download
- **WHEN** the downloader stops and starts again
- **THEN** it downloads messages 101 to 302 of the chat

#### Scenario: Message after a failed download
- **GIVEN** the history download of chat `-2001` failed
- **WHEN** a new message arrives in the chat
- **THEN** the downloader does not store the message
- **AND** at the next start, it downloads the message with the rest of the history

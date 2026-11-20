import React, { useState } from 'react';
import { formatDate } from '../dates';

function DateStat({ state }) {
  const newestDate = formatDate(state?.newest_message_date);
  if (state?.downloaded) {
    return (
      <div className="stat-item">
        <span className="stat-label">Newest message:</span>
        <span className="stat-value">{newestDate}</span>
      </div>
    );
  }
  return (
    <div className="stat-item">
      <span className="stat-label">Date range:</span>
      <span className="stat-value">{formatDate(state?.oldest_message_date)} - {newestDate}</span>
    </div>
  );
}

function FilesStat({ state, media }) {
  const files = state?.files_count ?? 0;
  const total = files + (state?.files_pending ?? 0);
  if (!media || total === 0) {
    return null;
  }
  return (
    <div className="stat-item">
      <span className="stat-label">Files:</span>
      <span className="stat-value">{`${files.toLocaleString()}/${total.toLocaleString()}`}</span>
    </div>
  );
}

function RequestForm({ chatId, onSubmitRequest }) {
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSending(true);
    setStatus(null);
    try {
      await onSubmitRequest(chatId, text);
      setText('');
      setStatus('Submitted to OpenClaw');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <form className="request-form" onSubmit={handleSubmit}>
      <textarea
        className="request-text"
        aria-label="Request"
        placeholder="Ask OpenClaw about this chat"
        rows={4}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
      <div className="request-footer">
        <button type="submit" className="dialog-button dialog-button-primary" disabled={sending || !text.trim()}>
          Submit
        </button>
        {status && <span className="request-status">{status}</span>}
      </div>
    </form>
  );
}

/**
 * Chat details panel component
 *
 * Displays information about the selected chat and its download status
 *
 * @param {Object} props
 * @param {Object|null} props.selectedChat - The currently selected chat
 */
export function ChatDetails({ selectedChat, onSubmitRequest }) {
  // No chat selected
  if (!selectedChat) {
    return (
      <div className="chat-details">
        <div className="chat-details-empty">
          <div className="empty-icon">💬</div>
          <h2>Select a chat</h2>
          <p>Please select a chat you want to analyze</p>
        </div>
      </div>
    );
  }

  if (selectedChat.state?.complete === false) {
    const state = selectedChat.state;

    const messageCount = state?.messages_count?.toLocaleString() || '0';

    return (
      <div className="chat-details">
        <div className="chat-details-content">
          <div className="chat-details-header">
            <h2>{selectedChat.name || 'Unnamed Chat'}</h2>
          </div>
          <div className="chat-details-body">
            <div className="info-message">
              <div className="downloading-spinner">⏳</div>
              <p>The chat is being downloaded, please wait...</p>
              <div className="download-stats">
                <div className="stat-item">
                  <span className="stat-label">Messages:</span>
                  <span className="stat-value">{messageCount}</span>
                </div>
                <DateStat state={state} />
                <FilesStat state={state} media={selectedChat.settings?.media} />
              </div>
            </div>
            <RequestForm key={selectedChat.id} chatId={selectedChat.id} onSubmitRequest={onSubmitRequest} />
          </div>
        </div>
      </div>
    );
  }

  const state = selectedChat.state;
  const complete = state?.complete === true;
  const messageCount = state?.messages_count?.toLocaleString() || '0';

  return (
    <div className="chat-details">
      <div className="chat-details-content">
        <div className="chat-details-header">
          <h2>{selectedChat.name || 'Unnamed Chat'}</h2>
        </div>
        <div className="chat-details-body">
          <div className={complete ? 'info-message success' : 'info-message'}>
            {complete && <div className="download-complete-icon">✓</div>}
            {complete && <p>The chat is downloaded</p>}
            <div className="download-stats">
              <div className="stat-item">
                <span className="stat-label">Messages:</span>
                <span className="stat-value">{messageCount}</span>
              </div>
              <DateStat state={state} />
              <FilesStat state={state} media={selectedChat.settings?.media} />
            </div>
          </div>
          <RequestForm key={selectedChat.id} chatId={selectedChat.id} onSubmitRequest={onSubmitRequest} />
        </div>
      </div>
    </div>
  );
}

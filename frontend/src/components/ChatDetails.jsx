import React from 'react';
import { formatDate } from '../dates';

function FilesStat({ state }) {
  const files = state?.files_count ?? 0;
  const total = files + (state?.files_pending ?? 0);
  if (total === 0) {
    return null;
  }
  return (
    <div className="stat-item">
      <span className="stat-label">Files:</span>
      <span className="stat-value">{`${files.toLocaleString()}/${total.toLocaleString()}`}</span>
    </div>
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
export function ChatDetails({ selectedChat }) {
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
    const oldestDate = formatDate(state?.oldest_message_date);
    const newestDate = formatDate(state?.newest_message_date);

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
                <div className="stat-item">
                  <span className="stat-label">Date range:</span>
                  <span className="stat-value">{oldestDate} - {newestDate}</span>
                </div>
                <FilesStat state={state} />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const state = selectedChat.state;
  const complete = state?.complete === true;
  const messageCount = state?.messages_count?.toLocaleString() || '0';

  const oldestDate = formatDate(state?.oldest_message_date);
  const newestDate = formatDate(state?.newest_message_date);

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
              <div className="stat-item">
                <span className="stat-label">Date range:</span>
                <span className="stat-value">{oldestDate} - {newestDate}</span>
              </div>
              <FilesStat state={state} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

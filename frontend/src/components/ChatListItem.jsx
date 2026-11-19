import React from 'react';
import { formatDate, formatDateTime } from '../dates';

function DownloadStatus({ complete }) {
  if (complete === true) {
    return <><span className="download-complete">✓</span>{' '}</>;
  }
  if (complete === false) {
    return <><span className="download-spinner">⏳</span>{' '}</>;
  }
  return null;
}

/**
 * Individual chat item component
 *
 * @param {Object} props
 * @param {Object} props.chat - Chat data
 * @param {number} props.chat.id - Chat ID
 * @param {string} props.chat.name - Chat name
 * @param {Object|null} props.chat.state - Download state
 * @param {boolean} props.isSelected - Whether this chat is selected
 * @param {Function} props.onClick - Click handler
 * @param {Function} props.onContextMenu - Context menu handler
 * @param {Function} props.getAvatarColor - Get avatar color for chat
 * @param {Function} props.getInitials - Get initials for chat name
 */
export function ChatListItem({ chat, isSelected, onClick, onContextMenu, getAvatarColor, getInitials }) {
  const isGroup = chat.id < 0;

  const formatDownloadInfo = (state) => {
    if (!state) return null;

    const { oldest_message_date, newest_message_date, messages_count, complete } = state;

    const oldestDate = formatDate(oldest_message_date);
    const newestDateTime = formatDateTime(newest_message_date);
    const count = messages_count.toLocaleString();

    return {
      text: `${oldestDate} - ${newestDateTime} (${count})`,
      complete
    };
  };

  const downloadInfo = formatDownloadInfo(chat.state);

  return (
    <div
      className={`chat-item${isSelected ? ' selected' : ''}`}
      onClick={() => onClick(chat)}
      onContextMenu={(e) => onContextMenu(e, chat)}
      data-testid={`chat-item-${chat.id}`}
    >
      <div
        className="chat-avatar"
        style={{ backgroundColor: getAvatarColor(chat.id) }}
      >
        {getInitials(chat.name)}
      </div>
      <div className="chat-info">
        <div className="chat-title-row">
          <div className="chat-name">
            {isGroup && (
              <span className="chat-type-icon">👥</span>
            )}
            <span className="chat-name-text">{chat.name || 'Unnamed Chat'}</span>
          </div>
        </div>
        <div className="chat-subtitle">
          {downloadInfo ? (
            <span className="download-info">
              <DownloadStatus complete={downloadInfo.complete} />
              {downloadInfo.text}
            </span>
          ) : (
            <span className="chat-preview">
              {isGroup ? 'Group chat' : 'Private chat'}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

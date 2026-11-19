import React from 'react';
import { ChatListItem } from './ChatListItem';
import { parseDate } from '../dates';

function newestTime(chat) {
  return parseDate(chat.state?.newest_message_date)?.getTime() ?? -Infinity;
}

function compareChats(first, second) {
  return newestTime(second) - newestTime(first) || first.name.localeCompare(second.name);
}

/**
 * Chat list component
 *
 * @param {Object} props
 * @param {Array} props.chats - Array of chat objects
 * @param {boolean} props.loading - Loading state
 * @param {boolean} props.isConnected - WebSocket connection state
 * @param {string} props.connectionState - Connection state string
 * @param {string} props.searchQuery - Search query
 * @param {Function} props.onContextMenu - Context menu handler
 * @param {Function} props.getAvatarColor - Get avatar color
 * @param {Function} props.getInitials - Get initials
 */
export function ChatList({
  chats,
  loading,
  isConnected,
  connectionState,
  searchQuery,
  selectedChatId,
  onChatClick,
  onContextMenu,
  getAvatarColor,
  getInitials
}) {
  const filteredChats = chats
    .filter(chat => chat.name.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort(compareChats);

  if (loading) {
    return (
      <div className="chat-list">
        <div className="loading-state">Loading chats...</div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="chat-list">
        <div className="empty-state">
          <div
            className="connection-status-badge"
            style={{
              backgroundColor: connectionState === 'CONNECTING' ? '#fbbf24' : '#f87171'
            }}
          >
            {connectionState}
          </div>
          <p>Connecting to server...</p>
        </div>
      </div>
    );
  }

  if (filteredChats.length === 0) {
    return (
      <div className="chat-list">
        <div className="empty-state">
          {searchQuery ? 'No chats found' : 'No chats available'}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-list" data-testid="chat-list">
      {filteredChats.map((chat) => (
        <ChatListItem
          key={chat.id}
          chat={chat}
          isSelected={chat.id === selectedChatId}
          onClick={onChatClick}
          onContextMenu={onContextMenu}
          getAvatarColor={getAvatarColor}
          getInitials={getInitials}
        />
      ))}
    </div>
  );
}

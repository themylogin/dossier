import React from 'react';

function isDownloaded(chat) {
  return chat.state?.downloaded === true;
}

export function visibleTabs(chats) {
  const tabs = [
    { id: 'all', label: 'All' },
    { id: 'downloaded', label: 'Downloaded' }
  ];
  if (chats.some(chat => !isDownloaded(chat))) {
    tabs.push({ id: 'downloading', label: 'Downloading' });
  }
  return tabs;
}

export function chatsOfTab(chats, tab) {
  if (tab === 'downloaded') {
    return chats.filter(isDownloaded);
  }
  if (tab === 'downloading') {
    return chats.filter(chat => !isDownloaded(chat));
  }
  return chats;
}

export function ChatTabs({ chats, activeTab, onSelect }) {
  return (
    <div className="tabs">
      {visibleTabs(chats).map(tab => (
        <button
          key={tab.id}
          className={`tab${tab.id === activeTab ? ' tab-active' : ''}`}
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
          <span className="tab-badge">{chatsOfTab(chats, tab.id).length}</span>
        </button>
      ))}
    </div>
  );
}

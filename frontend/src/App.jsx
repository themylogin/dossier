import { useState, useEffect } from 'react';
import './App.css';
import { useRPC } from './hooks/useRPC';
import { useAsyncDialogAction } from './hooks/useAsyncDialogAction';
import { ErrorDialog } from './components/ErrorDialog';
import { ChatList } from './components/ChatList';
import { ChatDetails } from './components/ChatDetails';
import { ChatTabs, chatsOfTab, visibleTabs } from './components/ChatTabs';
import { useChats } from './hooks/useChats';

function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTab, setSelectedTab] = useState('all');
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [downloadDialog, setDownloadDialog] = useState(null);
  const { call, isConnected, connectionState } = useRPC();
  const { executeAction, loading: saveLoading, error: saveError, clearError } = useAsyncDialogAction();
  const { chats, loading, loadChats } = useChats();

  let activeTab = selectedTab;
  if (!visibleTabs(chats).some(tab => tab.id === activeTab)) {
    activeTab = 'all';
  }

  // Get selected chat object from chats array
  const selectedChat = selectedChatId
    ? chats.find(chat => chat.id === selectedChatId) || null
    : null;

  // Close context menu on click outside
  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    if (contextMenu) {
      document.addEventListener('click', handleClick);
      return () => document.removeEventListener('click', handleClick);
    }
  }, [contextMenu]);

  const getAvatarColor = (id) => {
    const colors = [
      '#e17076', '#7bc862', '#65aadd', '#a695e7',
      '#ee7aae', '#6ec9cb', '#faa774', '#f48fb1'
    ];
    const index = Math.abs(id) % colors.length;
    return colors[index];
  };

  const getInitials = (name) => {
    if (!name || name.trim() === '') return '?';
    const words = name.trim().split(' ');
    if (words.length === 1) {
      return words[0].substring(0, 2).toUpperCase();
    }
    return (words[0][0] + words[1][0]).toUpperCase();
  };

  const handleChatClick = (chat) => {
    setSelectedChatId(chat.id);
  };

  const handleContextMenu = (e, chat) => {
    e.preventDefault();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      chat: chat
    });
  };

  const handleDownloadSettings = () => {
    if (contextMenu) {
      setDownloadDialog({
        chat: contextMenu.chat,
        media: contextMenu.chat.settings.media
      });
      setContextMenu(null);
    }
  };

  const handleSubmitRequest = (chatId, text) =>
    call('submit_request', { id: chatId, text }, { timeout: 120000 });

  const handleDialogCancel = () => {
    setDownloadDialog(null);
  };

  const handleDialogSave = async () => {
    if (!downloadDialog) return;

    const success = await executeAction(async () => {
      await call('update_chat', {
        id: downloadDialog.chat.id,
        settings: { media: downloadDialog.media }
      });

      // Reload chats to get updated state
      await loadChats();
    });

    // Close dialog only if successful
    if (success) {
      setDownloadDialog(null);
    }
  };

  return (
    <div className="telegram-container">
      <div className="sidebar">
        <div className="sidebar-header">
          <button className="menu-button">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M4 18h16c.55 0 1-.45 1-1s-.45-1-1-1H4c-.55 0-1 .45-1 1s.45 1 1 1zm0-5h16c.55 0 1-.45 1-1s-.45-1-1-1H4c-.55 0-1 .45-1 1s.45 1 1 1zM3 7c0 .55.45 1 1 1h16c.55 0 1-.45 1-1s-.45-1-1-1H4c-.55 0-1 .45-1 1z"/>
            </svg>
          </button>
          <div className="search-container">
            <input
              type="text"
              className="search-input"
              placeholder="Search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <ChatTabs chats={chats} activeTab={activeTab} onSelect={setSelectedTab} />

        <ChatList
          chats={chatsOfTab(chats, activeTab)}
          loading={loading}
          isConnected={isConnected}
          connectionState={connectionState}
          searchQuery={searchQuery}
          selectedChatId={selectedChatId}
          onChatClick={handleChatClick}
          onContextMenu={handleContextMenu}
          getAvatarColor={getAvatarColor}
          getInitials={getInitials}
        />
      </div>

      <div className="main-content">
        <ChatDetails
          selectedChat={selectedChat}
          onSubmitRequest={handleSubmitRequest}
        />
      </div>

      {contextMenu && (
        <div
          className="context-menu"
          style={{
            position: 'fixed',
            left: `${contextMenu.x}px`,
            top: `${contextMenu.y}px`
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button className="context-menu-item" onClick={handleDownloadSettings}>
            <span className="context-menu-icon">⚙️</span>
            Download Settings
          </button>
        </div>
      )}

      {downloadDialog && (
        <div className="dialog-overlay" onClick={handleDialogCancel}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-header">
              <h2>Download Settings</h2>
              <button className="dialog-close" onClick={handleDialogCancel}>×</button>
            </div>

            <div className="dialog-content">
              <div className="dialog-chat-info">
                <div
                  className="dialog-chat-avatar"
                  style={{ backgroundColor: getAvatarColor(downloadDialog.chat.id) }}
                >
                  {getInitials(downloadDialog.chat.name)}
                </div>
                <div className="dialog-chat-name">{downloadDialog.chat.name}</div>
              </div>

              <div className="dialog-form">
                <label className="dialog-checkbox-label">
                  <input
                    type="checkbox"
                    checked={downloadDialog.media}
                    onChange={(e) =>
                      setDownloadDialog({
                        ...downloadDialog,
                        media: e.target.checked
                      })
                    }
                  />
                  <span>Download Media</span>
                </label>
              </div>
            </div>

            <div className="dialog-footer">
              <button
                className="dialog-button dialog-button-secondary"
                onClick={handleDialogCancel}
                disabled={saveLoading}
              >
                Cancel
              </button>
              <button
                className="dialog-button dialog-button-primary"
                onClick={handleDialogSave}
                disabled={saveLoading}
              >
                {saveLoading && <span className="button-spinner"></span>}
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      <ErrorDialog error={saveError} onClose={clearError} />
    </div>
  );
}

export default App;

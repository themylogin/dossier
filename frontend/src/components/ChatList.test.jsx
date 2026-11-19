import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatList } from './ChatList';

describe('ChatList', () => {
  const mockOnContextMenu = vi.fn();
  const mockGetAvatarColor = vi.fn(() => '#e17076');
  const mockGetInitials = vi.fn(() => 'TC');

  const defaultProps = {
    chats: [],
    loading: false,
    isConnected: true,
    connectionState: 'CONNECTED',
    searchQuery: '',
    onContextMenu: mockOnContextMenu,
    getAvatarColor: mockGetAvatarColor,
    getInitials: mockGetInitials
  };

  it('shows loading state', () => {
    render(<ChatList {...defaultProps} loading={true} />);

    expect(screen.getByText('Loading chats...')).toBeInTheDocument();
    expect(screen.queryByTestId('chat-list')).not.toBeInTheDocument();
  });

  it('shows connecting state when not connected', () => {
    render(
      <ChatList
        {...defaultProps}
        isConnected={false}
        connectionState="CONNECTING"
      />
    );

    expect(screen.getByText('CONNECTING')).toBeInTheDocument();
    expect(screen.getByText('Connecting to server...')).toBeInTheDocument();
  });

  it('shows disconnected state with red badge', () => {
    const { container } = render(
      <ChatList
        {...defaultProps}
        isConnected={false}
        connectionState="DISCONNECTED"
      />
    );

    expect(screen.getByText('DISCONNECTED')).toBeInTheDocument();

    const badge = container.querySelector('.connection-status-badge');
    expect(badge).toHaveStyle({ backgroundColor: '#f87171' });
  });

  it('shows yellow badge for connecting state', () => {
    const { container } = render(
      <ChatList
        {...defaultProps}
        isConnected={false}
        connectionState="CONNECTING"
      />
    );

    const badge = container.querySelector('.connection-status-badge');
    expect(badge).toHaveStyle({ backgroundColor: '#fbbf24' });
  });

  it('shows empty state when no chats', () => {
    render(<ChatList {...defaultProps} chats={[]} />);

    expect(screen.getByText('No chats available')).toBeInTheDocument();
  });

  it('shows "no chats found" when search has no results', () => {
    render(<ChatList {...defaultProps} chats={[]} searchQuery="test" />);

    expect(screen.getByText('No chats found')).toBeInTheDocument();
  });

  it('renders list of chats', () => {
    const chats = [
      { id: 1, name: 'Chat 1', settings: { media: false } },
      { id: 2, name: 'Chat 2', settings: { media: false } },
      { id: 3, name: 'Chat 3', settings: { media: false } }
    ];

    render(<ChatList {...defaultProps} chats={chats} />);

    expect(screen.getByTestId('chat-list')).toBeInTheDocument();
    expect(screen.getByText('Chat 1')).toBeInTheDocument();
    expect(screen.getByText('Chat 2')).toBeInTheDocument();
    expect(screen.getByText('Chat 3')).toBeInTheDocument();
  });

  it('filters chats by search query', () => {
    const chats = [
      { id: 1, name: 'Alpha Chat', settings: { media: false } },
      { id: 2, name: 'Beta Chat', settings: { media: false } },
      { id: 3, name: 'Gamma Chat', settings: { media: false } }
    ];

    render(<ChatList {...defaultProps} chats={chats} searchQuery="beta" />);

    expect(screen.getByText('Beta Chat')).toBeInTheDocument();
    expect(screen.queryByText('Alpha Chat')).not.toBeInTheDocument();
    expect(screen.queryByText('Gamma Chat')).not.toBeInTheDocument();
  });

  it('filters chats case-insensitively', () => {
    const chats = [
      { id: 1, name: 'Important Chat', settings: { media: false } },
      { id: 2, name: 'Other Chat', settings: { media: false } }
    ];

    render(<ChatList {...defaultProps} chats={chats} searchQuery="IMPORTANT" />);

    expect(screen.getByText('Important Chat')).toBeInTheDocument();
    expect(screen.queryByText('Other Chat')).not.toBeInTheDocument();
  });

  it('passes correct props to ChatListItem', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false }
    };

    render(<ChatList {...defaultProps} chats={[chat]} />);

    // Verify ChatListItem rendered with correct data
    expect(screen.getByTestId('chat-item-123')).toBeInTheDocument();
    expect(screen.getByText('Test Chat')).toBeInTheDocument();
  });

  it('renders chats with download progress including time', () => {
    const chats = [
      {
        id: 1,
        name: 'Chat with download',
        settings: { media: false },
        state: {
          messages_count: 100,
          oldest_message_date: '2024-01-01T00:00:00Z',
          newest_message_date: '2024-01-24T00:00:00Z',
          complete: false
        }
      }
    ];

    render(<ChatList {...defaultProps} chats={chats} />);

    expect(screen.getByText('Chat with download')).toBeInTheDocument();
    expect(screen.getByText('⏳')).toBeInTheDocument();
    // Should include time in format
    expect(screen.getByText(/Jan 1, 2024 - Jan 24, 2024, \d{2}:\d{2} \(100\)/)).toBeInTheDocument();
  });

  it('handles empty search query showing all chats', () => {
    const chats = [
      { id: 1, name: 'Chat 1', settings: { media: false } },
      { id: 2, name: 'Chat 2', settings: { media: false } }
    ];

    render(<ChatList {...defaultProps} chats={chats} searchQuery="" />);

    expect(screen.getByText('Chat 1')).toBeInTheDocument();
    expect(screen.getByText('Chat 2')).toBeInTheDocument();
  });

  it('filters partial matches in chat names', () => {
    const chats = [
      { id: 1, name: 'Project Alpha', settings: { media: false } },
      { id: 2, name: 'Project Beta', settings: { media: false } },
      { id: 3, name: 'Work Chat', settings: { media: false } }
    ];

    render(<ChatList {...defaultProps} chats={chats} searchQuery="project" />);

    expect(screen.getByText('Project Alpha')).toBeInTheDocument();
    expect(screen.getByText('Project Beta')).toBeInTheDocument();
    expect(screen.queryByText('Work Chat')).not.toBeInTheDocument();
  });

  it('renders unique key for each chat item', () => {
    const chats = [
      { id: 100, name: 'Chat A', settings: { media: false } },
      { id: 200, name: 'Chat B', settings: { media: false } },
      { id: 300, name: 'Chat C', settings: { media: false } }
    ];

    render(<ChatList {...defaultProps} chats={chats} />);

    expect(screen.getByTestId('chat-item-100')).toBeInTheDocument();
    expect(screen.getByTestId('chat-item-200')).toBeInTheDocument();
    expect(screen.getByTestId('chat-item-300')).toBeInTheDocument();
  });
});

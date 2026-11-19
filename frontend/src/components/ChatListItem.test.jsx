import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatListItem } from './ChatListItem';

describe('ChatListItem', () => {
  const mockGetAvatarColor = vi.fn(() => '#e17076');
  const mockGetInitials = vi.fn(() => 'TC');
  const mockOnContextMenu = vi.fn();

  const defaultProps = {
    onContextMenu: mockOnContextMenu,
    getAvatarColor: mockGetAvatarColor,
    getInitials: mockGetInitials
  };

  it('renders private chat without download', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    expect(screen.getByText('Test Chat')).toBeInTheDocument();
    expect(screen.getByText('Private chat')).toBeInTheDocument();
    expect(screen.queryByText('👥')).not.toBeInTheDocument();
  });

  it('renders group chat indicator for negative ID', () => {
    const chat = {
      id: -100,
      name: 'Test Group',
      settings: { media: false }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    expect(screen.getByText('Test Group')).toBeInTheDocument();
    expect(screen.getByText('👥')).toBeInTheDocument();
    expect(screen.getByText('Group chat')).toBeInTheDocument();
  });

  it('shows no download status when no downloader reports the chat', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 100,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        complete: null
      }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    expect(screen.queryByText('⏳')).not.toBeInTheDocument();
    expect(screen.queryByText('✓')).not.toBeInTheDocument();
    expect(screen.getByText(/Jan 1, 2024 - Jan 24, 2024, \d{2}:\d{2} \(100\)/)).toBeInTheDocument();
  });

  it('renders download info when download is active', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 100,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        complete: false
      }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    // Should show download info instead of chat type
    expect(screen.queryByText('Private chat')).not.toBeInTheDocument();
    expect(screen.getByText('⏳')).toBeInTheDocument();
  });

  it('displays spinner and date range with time for incomplete download', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 1500,
        oldest_message_date: '2023-06-01T10:30:00Z',
        newest_message_date: '2024-01-24T15:45:00Z',
        complete: false
      }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    // Should show spinner
    expect(screen.getByText('⏳')).toBeInTheDocument();

    // Should show formatted date range with time and count
    // Format: "Jun 1, 2023 - Jan 24, 2024, HH:MM (1,500)"
    const downloadInfo = screen.getByText(/Jun 1, 2023 - Jan 24, 2024, \d{2}:\d{2} \(1,500\)/);
    expect(downloadInfo).toBeInTheDocument();
  });

  it('displays green checkmark for complete download with end time', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: true },
      state: {
        messages_count: 2500,
        oldest_message_date: '2023-06-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        complete: true
      }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    // Should show checkmark
    expect(screen.getByText('✓')).toBeInTheDocument();

    // Should show formatted date range with time and count
    const downloadInfo = screen.getByText(/Jun 1, 2023 - Jan 24, 2024, \d{2}:\d{2} \(2,500\)/);
    expect(downloadInfo).toBeInTheDocument();
  });

  it('handles null dates in download state', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 10,
        oldest_message_date: null,
        newest_message_date: null,
        complete: false
      }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    // Should show ? for missing dates
    expect(screen.getByText(/\? - \? \(10\)/)).toBeInTheDocument();
  });

  it('calls onContextMenu when right-clicked', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    const chatItem = screen.getByTestId('chat-item-123');
    chatItem.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true }));

    expect(mockOnContextMenu).toHaveBeenCalledWith(
      expect.any(Object),
      chat
    );
  });

  it('calls getAvatarColor and getInitials with correct params', () => {
    const chat = {
      id: 456,
      name: 'Another Chat',
      settings: { media: false }
    };

    mockGetAvatarColor.mockClear();
    mockGetInitials.mockClear();

    render(<ChatListItem chat={chat} {...defaultProps} />);

    expect(mockGetAvatarColor).toHaveBeenCalledWith(456);
    expect(mockGetInitials).toHaveBeenCalledWith('Another Chat');
  });

  it('displays "Unnamed Chat" for empty name', () => {
    const chat = {
      id: 123,
      name: '',
      settings: { media: false }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    expect(screen.getByText('Unnamed Chat')).toBeInTheDocument();
  });

  it('formats large message counts with commas and shows time', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 123456,
        oldest_message_date: '2023-01-01T00:00:00Z',
        newest_message_date: '2024-01-01T00:00:00Z',
        complete: true
      }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    // Should have comma-separated count and time format
    expect(screen.getByText(/Jan 1, 2023 - Jan 1, 2024, \d{2}:\d{2} \(123,456\)/)).toBeInTheDocument();
  });

  it('handles download with missing state gracefully', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: null
    };

    // Should not crash
    render(<ChatListItem chat={chat} {...defaultProps} />);

    // Should fall back to showing chat type
    expect(screen.getByText('Private chat')).toBeInTheDocument();
  });

  it('applies the UTC offset of a date', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 100,
        oldest_message_date: '2026-05-01T00:00:00+00:00',
        newest_message_date: '2026-05-22T10:30:00+02:00',
        complete: false
      }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    expect(screen.getByText(/May 1, 2026 - May 22, 2026, 08:30 \(100\)/)).toBeInTheDocument();
  });

  it('shows Z and +00:00 dates as the same time', () => {
    const chatWithZ = {
      id: 123,
      name: 'Chat With Z',
      settings: { media: false },
      state: {
        messages_count: 100,
        oldest_message_date: '2026-05-01T00:00:00Z',
        newest_message_date: '2026-05-22T10:30:00Z',
        complete: false
      }
    };
    const chatWithOffset = {
      id: 124,
      name: 'Chat With Offset',
      settings: { media: false },
      state: {
        messages_count: 100,
        oldest_message_date: '2026-05-01T00:00:00+00:00',
        newest_message_date: '2026-05-22T10:30:00+00:00',
        complete: false
      }
    };

    render(
      <>
        <ChatListItem chat={chatWithZ} {...defaultProps} />
        <ChatListItem chat={chatWithOffset} {...defaultProps} />
      </>
    );

    expect(screen.getAllByText(/May 22, 2026, 10:30 \(100\)/)).toHaveLength(2);
  });

  it('shows ? for a missing or invalid date', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 10,
        oldest_message_date: null,
        newest_message_date: 'not-a-date',
        complete: false
      }
    };

    render(<ChatListItem chat={chat} {...defaultProps} />);

    expect(screen.getByText(/\? - \? \(10\)/)).toBeInTheDocument();
  });
});

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatDetails } from './ChatDetails';

describe('ChatDetails', () => {
  const defaultProps = {
    selectedChat: null
  };

  it('shows empty state when no chat is selected', () => {
    render(<ChatDetails {...defaultProps} selectedChat={null} />);

    expect(screen.getByText('Select a chat')).toBeInTheDocument();
    expect(screen.getByText('Please select a chat you want to analyze')).toBeInTheDocument();
    expect(screen.getByText('💬')).toBeInTheDocument();
  });

  it('shows the stats without a download status when no downloader reports the chat', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 1500,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        complete: null
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('Test Chat')).toBeInTheDocument();
    expect(screen.queryByText('The chat is being downloaded, please wait...')).not.toBeInTheDocument();
    expect(screen.queryByText('The chat is downloaded')).not.toBeInTheDocument();
    expect(screen.queryByText('⏳')).not.toBeInTheDocument();
    expect(screen.queryByText('✓')).not.toBeInTheDocument();
    expect(screen.getByText('1,500')).toBeInTheDocument();
    expect(screen.getByText(/Jan 1, 2024 - Jan 24, 2024/)).toBeInTheDocument();
  });

  it('shows downloading state with progress stats', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 1500,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        complete: false
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('Test Chat')).toBeInTheDocument();
    expect(screen.getByText('The chat is being downloaded, please wait...')).toBeInTheDocument();
    expect(screen.getByText('⏳')).toBeInTheDocument();
    expect(screen.getByText('Messages:')).toBeInTheDocument();
    expect(screen.getByText('1,500')).toBeInTheDocument();
    expect(screen.getByText('Date range:')).toBeInTheDocument();
    expect(screen.getByText(/Jan 1, 2024 - Jan 24, 2024/)).toBeInTheDocument();
  });

  it('shows completed state with stats', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 2500,
        oldest_message_date: '2023-06-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        complete: true
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('Test Chat')).toBeInTheDocument();
    expect(screen.getByText('The chat is downloaded')).toBeInTheDocument();
    expect(screen.getByText('✓')).toBeInTheDocument();
    expect(screen.getByText('Messages:')).toBeInTheDocument();
    expect(screen.getByText('2,500')).toBeInTheDocument();
    expect(screen.getByText('Date range:')).toBeInTheDocument();
    expect(screen.getByText(/Jun 1, 2023 - Jan 24, 2024/)).toBeInTheDocument();
  });

  it('handles chat with undefined name', () => {
    const chat = {
      id: 123,
      name: undefined,
      settings: { media: false }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('Unnamed Chat')).toBeInTheDocument();
  });

  it('handles chat with empty name', () => {
    const chat = {
      id: 123,
      name: '',
      settings: { media: false }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('Unnamed Chat')).toBeInTheDocument();
  });

  it('handles download state without messages_count', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: null,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        complete: false
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('handles download state with null dates', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 100,
        oldest_message_date: null,
        newest_message_date: null,
        complete: false
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('? - ?')).toBeInTheDocument();
  });

  it('shows no download status for a chat without a state', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: null
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.queryByText('The chat is being downloaded, please wait...')).not.toBeInTheDocument();
    expect(screen.queryByText('The chat is downloaded')).not.toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
    expect(screen.getByText('? - ?')).toBeInTheDocument();
  });

  it('formats large message counts with commas', () => {
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

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('123,456')).toBeInTheDocument();
  });

  it('displays chat name in header for all states', () => {
    const chatName = 'Important Project Chat';

    // Test without state
    const { rerender } = render(
      <ChatDetails
        {...defaultProps}
        selectedChat={{ id: 1, name: chatName, settings: { media: false } }}
      />
    );
    expect(screen.getByText(chatName)).toBeInTheDocument();

    // Test with downloading
    rerender(
      <ChatDetails
        {...defaultProps}
        selectedChat={{
          id: 1,
          name: chatName,
          settings: { media: false },
          state: { messages_count: 100, complete: false }
        }}
      />
    );
    expect(screen.getByText(chatName)).toBeInTheDocument();

    // Test with complete
    rerender(
      <ChatDetails
        {...defaultProps}
        selectedChat={{
          id: 1,
          name: chatName,
          settings: { media: false },
          state: { messages_count: 100, complete: true }
        }}
      />
    );
    expect(screen.getByText(chatName)).toBeInTheDocument();
  });
});

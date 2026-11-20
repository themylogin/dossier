import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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

  it('shows the media progress when the chat has files', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: true },
      state: {
        messages_count: 2000,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        files_count: 1200,
        files_pending: 300,
        complete: false
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('Files:')).toBeInTheDocument();
    expect(screen.getByText('1,200/1,500')).toBeInTheDocument();
  });

  it('shows no media progress when the chat has no files', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 2000,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        files_count: 0,
        files_pending: 0,
        complete: true
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.queryByText('Files:')).not.toBeInTheDocument();
  });

  it('shows only the newest date when the chat is downloaded', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 2000,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        files_count: 1200,
        files_pending: 300,
        downloaded: true,
        complete: true
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.getByText('Newest message:')).toBeInTheDocument();
    expect(screen.getByText('Jan 24, 2024')).toBeInTheDocument();
    expect(screen.queryByText('Date range:')).not.toBeInTheDocument();
  });

  it('shows no media progress when media is off', () => {
    const chat = {
      id: 123,
      name: 'Test Chat',
      settings: { media: false },
      state: {
        messages_count: 2000,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-24T00:00:00Z',
        files_count: 1200,
        files_pending: 300,
        downloaded: true,
        complete: true
      }
    };

    render(<ChatDetails {...defaultProps} selectedChat={chat} />);

    expect(screen.queryByText('Files:')).not.toBeInTheDocument();
  });

  describe('request form', () => {
    const chat = {
      id: -2001,
      name: 'Family',
      settings: { media: false },
      state: {
        messages_count: 3,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-03T00:00:00Z',
        downloaded: true,
        complete: true
      }
    };

    it('submits the text and clears the field', async () => {
      const sessionUrl = 'https://openclaw.example.com/chat/main/dossier/-2001/2026-05-22_10-30-00';
      const onSubmitRequest = vi.fn().mockResolvedValue({ run_id: 'run-1', file: '/x.sqlite', session_url: sessionUrl });
      render(<ChatDetails selectedChat={chat} onSubmitRequest={onSubmitRequest} />);
      const field = screen.getByLabelText('Request');

      fireEvent.change(field, { target: { value: 'Summarize\nthe decisions' } });
      fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

      expect(await screen.findByText('Submitted to OpenClaw')).toBeInTheDocument();
      expect(onSubmitRequest).toHaveBeenCalledWith(-2001, 'Summarize\nthe decisions');
      expect(field).toHaveValue('');
      const link = screen.getByRole('link', { name: 'Open in OpenClaw' });
      expect(link).toHaveAttribute('href', sessionUrl);
      expect(link).toHaveAttribute('target', '_blank');
    });

    it('shows the error and keeps the text', async () => {
      const onSubmitRequest = vi.fn().mockRejectedValue(new Error('OpenClaw is not configured'));
      render(<ChatDetails selectedChat={chat} onSubmitRequest={onSubmitRequest} />);
      const field = screen.getByLabelText('Request');

      fireEvent.change(field, { target: { value: 'Summarize' } });
      fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

      expect(await screen.findByText('OpenClaw is not configured')).toBeInTheDocument();
      expect(field).toHaveValue('Summarize');
    });

    it('disables Submit while the field holds only spaces', () => {
      render(<ChatDetails selectedChat={chat} onSubmitRequest={vi.fn()} />);

      fireEvent.change(screen.getByLabelText('Request'), { target: { value: '   ' } });

      expect(screen.getByRole('button', { name: 'Submit' })).toBeDisabled();
    });
  });
});

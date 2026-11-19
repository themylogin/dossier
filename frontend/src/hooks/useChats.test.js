import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useChats } from './useChats';
import * as useRPCModule from './useRPC';

// Mock the useRPC module
vi.mock('./useRPC', () => ({
  useRPC: vi.fn(),
  useRPCMethod: vi.fn()
}));

describe('useChats', () => {
  let mockCall;
  let mockUseRPCMethod;

  beforeEach(() => {
    mockCall = vi.fn();
    mockUseRPCMethod = vi.fn();

    // Setup default mock implementation
    useRPCModule.useRPC.mockReturnValue({
      call: mockCall,
      isConnected: false
    });
    useRPCModule.useRPCMethod.mockImplementation(mockUseRPCMethod);
  });

  it('initializes with empty chats and not loading', () => {
    const { result } = renderHook(() => useChats());

    expect(result.current.chats).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(typeof result.current.loadChats).toBe('function');
  });

  it('registers chat_download_progress RPC method handler', () => {
    renderHook(() => useChats());

    expect(mockUseRPCMethod).toHaveBeenCalledWith(
      'chat_download_progress',
      expect.any(Function)
    );
  });

  it('loads chats successfully', async () => {
    const mockChats = [
      { id: 1, name: 'Chat 1', settings: { media: false } },
      { id: 2, name: 'Chat 2', settings: { media: false } }
    ];

    mockCall.mockResolvedValue({ chats: mockChats });

    const { result } = renderHook(() => useChats());

    expect(result.current.loading).toBe(false);

    await act(async () => {
      await result.current.loadChats();
    });

    expect(mockCall).toHaveBeenCalledWith('list_chats');
    expect(result.current.chats).toEqual(mockChats);
    expect(result.current.loading).toBe(false);
  });

  it('sets loading state during loadChats', async () => {
    let resolvePromise;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    mockCall.mockReturnValue(promise);

    const { result } = renderHook(() => useChats());

    act(() => {
      result.current.loadChats();
    });

    // Should be loading immediately
    expect(result.current.loading).toBe(true);

    // Resolve the promise
    await act(async () => {
      resolvePromise({ chats: [] });
      await promise;
    });

    // Should not be loading after completion
    expect(result.current.loading).toBe(false);
  });

  it('handles loadChats error gracefully', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockCall.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useChats());

    await act(async () => {
      await result.current.loadChats();
    });

    expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to load chats:', expect.any(Error));
    expect(result.current.loading).toBe(false);
    expect(result.current.chats).toEqual([]);

    consoleErrorSpy.mockRestore();
  });

  it('handles loadChats with null result', async () => {
    mockCall.mockResolvedValue(null);

    const { result } = renderHook(() => useChats());

    await act(async () => {
      await result.current.loadChats();
    });

    expect(result.current.chats).toEqual([]);
  });

  it('handles loadChats with result missing chats property', async () => {
    mockCall.mockResolvedValue({ success: true });

    const { result } = renderHook(() => useChats());

    await act(async () => {
      await result.current.loadChats();
    });

    expect(result.current.chats).toEqual([]);
  });

  it('auto-loads chats when connected', async () => {
    mockCall.mockResolvedValue({ chats: [{ id: 1, name: 'Chat 1' }] });

    // Start with connected
    useRPCModule.useRPC.mockReturnValue({
      call: mockCall,
      isConnected: true
    });

    const { result } = renderHook(() => useChats());

    await waitFor(() => {
      expect(mockCall).toHaveBeenCalledWith('list_chats');
    });

    await waitFor(() => {
      expect(result.current.chats).toEqual([{ id: 1, name: 'Chat 1' }]);
    });
  });

  it('reports loading until the first auto-load finishes', async () => {
    let resolvePromise;
    mockCall.mockReturnValue(new Promise((resolve) => {
      resolvePromise = resolve;
    }));
    useRPCModule.useRPC.mockReturnValue({
      call: mockCall,
      isConnected: true
    });

    const { result } = renderHook(() => useChats());

    expect(result.current.loading).toBe(true);

    await act(async () => {
      resolvePromise({ chats: [] });
    });

    expect(result.current.loading).toBe(false);
  });

  it('does not auto-load chats when disconnected', () => {
    useRPCModule.useRPC.mockReturnValue({
      call: mockCall,
      isConnected: false
    });

    renderHook(() => useChats());

    expect(mockCall).not.toHaveBeenCalled();
  });

  it('does not auto-load chats if chats already exist', async () => {
    mockCall.mockResolvedValue({ chats: [{ id: 1, name: 'Chat 1' }] });

    useRPCModule.useRPC.mockReturnValue({
      call: mockCall,
      isConnected: true
    });

    const { result, rerender } = renderHook(() => useChats());

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.chats.length).toBe(1);
    });

    const firstCallCount = mockCall.mock.calls.length;

    // Rerender should not trigger another load
    rerender();

    expect(mockCall.mock.calls.length).toBe(firstCallCount);
  });

  it('updates chat download state on chat_download_progress notification', async () => {
    const { result } = renderHook(() => useChats());

    // Load initial chats
    const initialChats = [
      {
        id: 1,
        name: 'Chat 1',
        settings: { media: false },
        state: {
          messages_count: 100,
          oldest_message_date: '2024-01-01T00:00:00Z',
          newest_message_date: '2024-01-10T00:00:00Z',
          complete: false
        }
      },
      { id: 2, name: 'Chat 2', settings: { media: false } }
    ];

    mockCall.mockResolvedValue({ chats: initialChats });

    await act(async () => {
      await result.current.loadChats();
    });

    // Get the registered handler
    const handlerCall = mockUseRPCMethod.mock.calls.find(
      call => call[0] === 'chat_download_progress'
    );
    expect(handlerCall).toBeDefined();
    const handler = handlerCall[1];

    // Simulate download progress notification
    const progressParams = {
      id: 1,
      state: {
        messages_count: 150,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-15T00:00:00Z',
        complete: false
      }
    };

    act(() => {
      const handlerResult = handler(progressParams);
      expect(handlerResult).toEqual({ success: true });
    });

    // Verify chat state was updated
    const updatedChat = result.current.chats.find(c => c.id === 1);
    expect(updatedChat.state).toEqual(progressParams.state);
    expect(updatedChat.state.messages_count).toBe(150);
    expect(updatedChat.state.complete).toBe(false);

    // Verify other chat was not affected
    const otherChat = result.current.chats.find(c => c.id === 2);
    expect(otherChat).toEqual({ id: 2, name: 'Chat 2', settings: { media: false } });
  });

  it('marks download as complete on chat_download_progress notification', async () => {
    const { result } = renderHook(() => useChats());

    const initialChats = [
      {
        id: 1,
        name: 'Chat 1',
        settings: { media: false },
        state: {
          messages_count: 100,
          oldest_message_date: '2024-01-01T00:00:00Z',
          newest_message_date: '2024-01-10T00:00:00Z',
          complete: false
        }
      }
    ];

    mockCall.mockResolvedValue({ chats: initialChats });

    await act(async () => {
      await result.current.loadChats();
    });

    const handlerCall = mockUseRPCMethod.mock.calls.find(
      call => call[0] === 'chat_download_progress'
    );
    const handler = handlerCall[1];

    // Simulate completion notification
    const completionParams = {
      id: 1,
      state: {
        messages_count: 200,
        oldest_message_date: '2024-01-01T00:00:00Z',
        newest_message_date: '2024-01-20T00:00:00Z',
        complete: true
      }
    };

    act(() => {
      handler(completionParams);
    });

    const updatedChat = result.current.chats.find(c => c.id === 1);
    expect(updatedChat.state.complete).toBe(true);
    expect(updatedChat.state.messages_count).toBe(200);
  });

  it('does not update state for non-existent chat ID', async () => {
    const { result } = renderHook(() => useChats());

    const initialChats = [
      { id: 1, name: 'Chat 1', settings: { media: false } },
      { id: 2, name: 'Chat 2', settings: { media: false } }
    ];

    mockCall.mockResolvedValue({ chats: initialChats });

    await act(async () => {
      await result.current.loadChats();
    });

    const handlerCall = mockUseRPCMethod.mock.calls.find(
      call => call[0] === 'chat_download_progress'
    );
    const handler = handlerCall[1];

    // Simulate notification for non-existent chat
    act(() => {
      handler({
        id: 999,
        state: {
          messages_count: 100,
          oldest_message_date: '2024-01-01T00:00:00Z',
          newest_message_date: '2024-01-10T00:00:00Z',
          complete: false
        }
      });
    });

    // Chats should remain unchanged
    expect(result.current.chats).toEqual(initialChats);
  });

  it('logs received download progress', async () => {
    const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

    const { result } = renderHook(() => useChats());

    const initialChats = [
      {
        id: 1,
        name: 'Chat 1',
        settings: { media: false },
        state: { messages_count: 0, complete: false }
      }
    ];

    mockCall.mockResolvedValue({ chats: initialChats });

    await act(async () => {
      await result.current.loadChats();
    });

    const handlerCall = mockUseRPCMethod.mock.calls.find(
      call => call[0] === 'chat_download_progress'
    );
    const handler = handlerCall[1];

    const progressParams = {
      id: 1,
      state: { messages_count: 50, complete: false }
    };

    act(() => {
      handler(progressParams);
    });

    expect(consoleLogSpy).toHaveBeenCalledWith(
      '[useChats] Received chat_download_progress:',
      progressParams
    );

    consoleLogSpy.mockRestore();
  });
});

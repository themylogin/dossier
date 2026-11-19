import { useState, useCallback, useEffect } from 'react';
import { useRPC, useRPCMethod } from './useRPC';

/**
 * Custom hook for managing chat list state and download progress updates
 *
 * Features:
 * - Loads chats from server
 * - Automatically registers handler for download progress updates
 * - Updates chat state when server sends notifications
 * - Auto-loads chats when connected
 *
 * @returns {Object} { chats, loading, loadChats }
 */
export function useChats() {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadedOnce, setLoadedOnce] = useState(false);
  const { call, isConnected } = useRPC();

  const fetchChats = useCallback(
    () => call('list_chats')
      .then((result) => {
        if (result && result.chats) {
          setChats(result.chats);
        }
      })
      .catch((error) => {
        console.error('Failed to load chats:', error);
      })
      .finally(() => {
        setLoadedOnce(true);
      }),
    [call]
  );

  /**
   * Load chats from server
   */
  const loadChats = useCallback(async () => {
    setLoading(true);
    try {
      await fetchChats();
    } finally {
      setLoading(false);
    }
  }, [fetchChats]);

  /**
   * Handle download progress notifications from server
   *
   * Server calls this with:
   * {
   *   id: number,
   *   state: {
   *     messages_count: number,
   *     oldest_message_date: string,
   *     newest_message_date: string,
   *     complete: boolean
   *   }
   * }
   */
  const handleDownloadProgress = useCallback((params) => {
    console.log('[useChats] Received chat_download_progress:', params);

    setChats(prevChats => {
      return prevChats.map(chat => {
        if (chat.id === params.id) {
          return { ...chat, state: params.state };
        }
        return chat;
      });
    });

    return { success: true };
  }, []);

  // Register RPC handler for download progress updates
  useRPCMethod('chat_download_progress', handleDownloadProgress);

  // Auto-load chats when connected
  useEffect(() => {
    if (isConnected && chats.length === 0) {
      fetchChats();
    }
  }, [isConnected, chats.length, fetchChats]);

  return {
    chats,
    loading: loading || (isConnected && !loadedOnce),
    loadChats
  };
}

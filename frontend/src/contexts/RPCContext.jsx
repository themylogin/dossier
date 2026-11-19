import { useEffect, useState } from 'react';
import { RPCClient } from '../services/rpc-client';
import { RPCContext } from './useRPCContext';

/**
 * RPC Provider Component
 * Manages the WebSocket connection and provides RPC functionality to child components
 */
export function RPCProvider({ url, children, autoConnect = true }) {
  const [client, setClient] = useState(null);
  const [connectionState, setConnectionState] = useState('CLOSED');
  const [error, setError] = useState(null);
  const [reconnectInfo, setReconnectInfo] = useState(null);

  // Initialize RPC client
  useEffect(() => {
    if (!url) {
      console.warn('[RPCProvider] No URL provided, skipping connection');
      return;
    }

    const rpcClient = new RPCClient(url);

    // Set up event listeners
    const handleConnected = () => {
      setClient(rpcClient);
      setConnectionState('OPEN');
      setError(null);
      setReconnectInfo(null);
    };

    const handleDisconnected = (info) => {
      setConnectionState('CLOSED');
      if (info?.reason) {
        setError(`Disconnected: ${info.reason}`);
      }
    };

    const handleError = (err) => {
      setError(err?.message || 'Connection error');
    };

    const handleReconnecting = (info) => {
      setConnectionState('CONNECTING');
      setReconnectInfo(info);
    };

    rpcClient.on('connected', handleConnected);
    rpcClient.on('disconnected', handleDisconnected);
    rpcClient.on('error', handleError);
    rpcClient.on('reconnecting', handleReconnecting);

    // Auto-connect if enabled
    if (autoConnect) {
      rpcClient.connect();
    }

    // Cleanup on unmount
    return () => {
      rpcClient.off('connected', handleConnected);
      rpcClient.off('disconnected', handleDisconnected);
      rpcClient.off('error', handleError);
      rpcClient.off('reconnecting', handleReconnecting);
      rpcClient.disconnect();
    };
  }, [url, autoConnect]);

  const contextValue = {
    client,
    connectionState,
    isConnected: connectionState === 'OPEN',
    error,
    reconnectInfo,
    connect: () => client?.connect(),
    disconnect: () => client?.disconnect(),
  };

  return (
    <RPCContext.Provider value={contextValue}>
      {children}
    </RPCContext.Provider>
  );
}

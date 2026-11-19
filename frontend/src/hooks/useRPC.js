import { useCallback, useEffect, useRef } from 'react';
import { useRPCContext } from '../contexts/useRPCContext';

/**
 * Hook for calling RPC methods and registering method handlers
 *
 * @example
 * // Call a method on the server
 * const { call, notify, isConnected } = useRPC();
 * const result = await call('getUserData', { userId: 123 });
 *
 * @example
 * // Register a method handler for server->client calls
 * const { registerMethod } = useRPC();
 * useEffect(() => {
 *   return registerMethod('updateNotification', (params) => {
 *     console.log('Received notification:', params);
 *     return { success: true };
 *   });
 * }, []);
 */
export function useRPC() {
  const { client, isConnected, connectionState, error, reconnectInfo } = useRPCContext();
  const registeredMethodsRef = useRef(new Set());

  /**
   * Call a method on the server
   */
  const call = useCallback(
    async (methodName, params, options = {}) => {
      if (!client) {
        throw new Error('RPC client not initialized');
      }

      try {
        const result = await client.call(methodName, params, options.timeout);
        return result;
      } catch (error) {
        console.error(`[RPC] Error calling ${methodName}:`, error);
        throw error;
      }
    },
    [client]
  );

  /**
   * Send a notification to the server (no response expected)
   */
  const notify = useCallback(
    (methodName, params) => {
      if (!client) {
        throw new Error('RPC client not initialized');
      }

      try {
        client.notify(methodName, params);
      } catch (error) {
        console.error(`[RPC] Error sending notification ${methodName}:`, error);
        throw error;
      }
    },
    [client]
  );

  /**
   * Register a method handler for server->client calls
   * Returns an unregister function
   */
  const registerMethod = useCallback(
    (methodName, handler) => {
      if (!client) {
        console.warn('RPC client not initialized, cannot register method');
        return () => {};
      }

      client.registerMethod(methodName, handler);
      registeredMethodsRef.current.add(methodName);

      // Return cleanup function
      return () => {
        if (client && registeredMethodsRef.current.has(methodName)) {
          client.unregisterMethod(methodName);
          registeredMethodsRef.current.delete(methodName);
        }
      };
    },
    [client]
  );

  // Cleanup all registered methods on unmount
  useEffect(() => {
    const registeredMethods = registeredMethodsRef.current;
    return () => {
      if (client) {
        registeredMethods.forEach((methodName) => {
          client.unregisterMethod(methodName);
        });
        registeredMethods.clear();
      }
    };
  }, [client]);

  return {
    call,
    notify,
    registerMethod,
    isConnected,
    connectionState,
    error,
    reconnectInfo,
  };
}

/**
 * Hook to register a method handler that persists for the component lifecycle
 * Automatically handles cleanup
 *
 * @example
 * useRPCMethod('updateStatus', (params) => {
 *   setStatus(params.status);
 *   return { success: true };
 * });
 */
export function useRPCMethod(methodName, handler) {
  const { registerMethod } = useRPC();

  useEffect(() => {
    if (!methodName || !handler) return;

    const unregister = registerMethod(methodName, handler);
    return unregister;
  }, [methodName, handler, registerMethod]);
}

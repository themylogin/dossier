import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * Hook for handling async actions in dialogs with loading state and error handling
 *
 * Features:
 * - Tracks loading state
 * - Shows error dialog on failure
 * - Prevents error dialog if dialog is closed during action
 * - Reusable across multiple dialogs
 *
 * @example
 * const { executeAction, loading, error, clearError } = useAsyncDialogAction();
 *
 * const handleSave = async () => {
 *   await executeAction(async () => {
 *     await call('save_data', { data });
 *     onSuccess();
 *   });
 * };
 */
export function useAsyncDialogAction() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const isMountedRef = useRef(true);

  // Track if component is mounted
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  /**
   * Execute an async action with loading state and error handling
   * @param {Function} action - Async function to execute
   * @returns {Promise<boolean>} - Returns true if successful, false if error occurred
   */
  const executeAction = useCallback(async (action) => {
    setLoading(true);
    setError(null);

    try {
      await action();
      setLoading(false);
      return true;
    } catch (err) {
      setLoading(false);

      // Only show error if dialog is still mounted
      if (isMountedRef.current) {
        setError(err.message || 'An error occurred');
      }

      return false;
    }
  }, []);

  /**
   * Clear the current error
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    executeAction,
    loading,
    error,
    clearError,
  };
}

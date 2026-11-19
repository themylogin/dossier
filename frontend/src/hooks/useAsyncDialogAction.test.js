import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAsyncDialogAction } from './useAsyncDialogAction';

describe('useAsyncDialogAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with default state', () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(typeof result.current.executeAction).toBe('function');
    expect(typeof result.current.clearError).toBe('function');
  });

  it('manages loading state during action execution', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    // Initially loading should be false
    expect(result.current.loading).toBe(false);

    await act(async () => {
      await result.current.executeAction(async () => {
        await new Promise(resolve => setTimeout(resolve, 10));
      });
    });

    // Loading should be false after completion
    expect(result.current.loading).toBe(false);
  });

  it('returns true on successful action execution', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    let returnValue;
    await act(async () => {
      returnValue = await result.current.executeAction(async () => {
        return 'success';
      });
    });

    expect(returnValue).toBe(true);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('sets error message when action fails', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    await act(async () => {
      await result.current.executeAction(async () => {
        throw new Error('Test error message');
      });
    });

    expect(result.current.error).toBe('Test error message');
    expect(result.current.loading).toBe(false);
  });

  it('returns false when action fails', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    let returnValue;
    await act(async () => {
      returnValue = await result.current.executeAction(async () => {
        throw new Error('Test error');
      });
    });

    expect(returnValue).toBe(false);
  });

  it('handles error without message property', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    await act(async () => {
      await result.current.executeAction(async () => {
        throw 'String error';
      });
    });

    expect(result.current.error).toBe('An error occurred');
  });

  it('clears error when clearError is called', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    // First, create an error
    await act(async () => {
      await result.current.executeAction(async () => {
        throw new Error('Test error');
      });
    });

    expect(result.current.error).toBe('Test error');

    // Clear the error
    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  it('does not set error if component unmounts during action', async () => {
    const { result, unmount } = renderHook(() => useAsyncDialogAction());

    const actionPromise = act(async () => {
      return result.current.executeAction(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
        throw new Error('Should not appear');
      });
    });

    // Unmount before action completes
    await new Promise(resolve => setTimeout(resolve, 10));
    unmount();

    // Wait for action to complete
    const returnValue = await actionPromise;

    // Error should not be set because component unmounted
    expect(returnValue).toBe(false);
  });

  it('handles multiple sequential actions', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    // First action - success
    await act(async () => {
      await result.current.executeAction(async () => {
        await new Promise(resolve => setTimeout(resolve, 10));
      });
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();

    // Second action - error
    await act(async () => {
      await result.current.executeAction(async () => {
        throw new Error('Second error');
      });
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Second error');

    // Third action - success (should clear previous error)
    act(() => {
      result.current.clearError();
    });

    await act(async () => {
      await result.current.executeAction(async () => {
        await new Promise(resolve => setTimeout(resolve, 10));
      });
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('clears previous error when starting new action', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    // First action - error
    await act(async () => {
      await result.current.executeAction(async () => {
        throw new Error('First error');
      });
    });

    expect(result.current.error).toBe('First error');

    // Second action - should clear previous error
    await act(async () => {
      await result.current.executeAction(async () => {
        await new Promise(resolve => setTimeout(resolve, 10));
      });
    });

    // Error should be cleared after successful execution
    expect(result.current.error).toBeNull();
  });

  it('can execute action that calls other async functions', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    const mockApiCall = vi.fn(async () => {
      await new Promise(resolve => setTimeout(resolve, 10));
      return { success: true };
    });

    const mockDataRefresh = vi.fn(async () => {
      await new Promise(resolve => setTimeout(resolve, 10));
    });

    let returnValue;
    await act(async () => {
      returnValue = await result.current.executeAction(async () => {
        await mockApiCall();
        await mockDataRefresh();
      });
    });

    expect(returnValue).toBe(true);
    expect(mockApiCall).toHaveBeenCalledTimes(1);
    expect(mockDataRefresh).toHaveBeenCalledTimes(1);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('preserves error details from thrown Error objects', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    const errorMessage = 'Network request failed: 404 Not Found';

    await act(async () => {
      await result.current.executeAction(async () => {
        throw new Error(errorMessage);
      });
    });

    expect(result.current.error).toBe(errorMessage);
  });

  it('handles synchronous errors', async () => {
    const { result } = renderHook(() => useAsyncDialogAction());

    await act(async () => {
      await result.current.executeAction(async () => {
        // Synchronous throw inside async function
        throw new Error('Sync error');
      });
    });

    expect(result.current.error).toBe('Sync error');
    expect(result.current.loading).toBe(false);
  });
});

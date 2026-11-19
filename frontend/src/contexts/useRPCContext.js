import { createContext, useContext } from 'react';

export const RPCContext = createContext(null);

export function useRPCContext() {
  const context = useContext(RPCContext);
  if (!context) {
    throw new Error('useRPCContext must be used within RPCProvider');
  }
  return context;
}

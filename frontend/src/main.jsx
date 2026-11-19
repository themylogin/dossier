import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { RPCProvider } from './contexts/RPCContext.jsx'

const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${wsProtocol}//${window.location.host}/api/ws_jsonrpc`;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <RPCProvider url={WS_URL} autoConnect={true}>
      <App />
    </RPCProvider>
  </StrictMode>,
)

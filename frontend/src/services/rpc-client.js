import { JSONRPCClient, JSONRPCServer, JSONRPCServerAndClient } from 'json-rpc-2.0';

/**
 * Bidirectional JSON-RPC 2.0 WebSocket Client
 * Supports both client->server and server->client method calls
 */
export class RPCClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = Infinity;
    this.reconnectDelay = 1000; // Start with 1 second
    this.maxReconnectDelay = 30000; // Max 30 seconds
    this.reconnectTimer = null;
    this.isIntentionallyClosed = false;
    this.requestQueue = [];

    // Event listeners
    this.listeners = {
      connected: [],
      disconnected: [],
      error: [],
      reconnecting: [],
    };

    // Create bidirectional JSON-RPC handler
    this.serverAndClient = new JSONRPCServerAndClient(
      new JSONRPCServer(),
      new JSONRPCClient((jsonRPCRequest) => {
        return this.sendRequest(jsonRPCRequest);
      })
    );

    // Method handlers registered by the application
    this.methodHandlers = new Map();
  }

  /**
   * Register a method handler for server->client calls
   */
  registerMethod(methodName, handler) {
    this.methodHandlers.set(methodName, handler);
    this.serverAndClient.addMethod(methodName, handler);
  }

  /**
   * Unregister a method handler
   */
  unregisterMethod(methodName) {
    this.methodHandlers.delete(methodName);
    this.serverAndClient.removeMethod(methodName);
  }

  /**
   * Call a method on the server (client->server)
   */
  async call(methodName, params, timeout = 30000) {
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error(`RPC call timeout: ${methodName}`)), timeout);
    });

    const callPromise = this.serverAndClient.request(methodName, params);

    return Promise.race([callPromise, timeoutPromise]);
  }

  /**
   * Send a notification to the server (no response expected)
   */
  notify(methodName, params) {
    this.serverAndClient.notify(methodName, params);
  }

  /**
   * Connect to the WebSocket server
   */
  connect() {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.isIntentionallyClosed = false;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[RPC] Connected to server');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.emit('connected');
        this.flushRequestQueue();
      };

      this.ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          // Handle incoming JSON-RPC messages (both responses and requests)
          await this.serverAndClient.receiveAndSend(message, (response) => {
            if (response) {
              this.sendRaw(response);
            }
          });
        } catch (error) {
          console.error('[RPC] Error processing message:', error);
          this.emit('error', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[RPC] WebSocket error:', error);
        this.emit('error', error);
      };

      this.ws.onclose = (event) => {
        console.log('[RPC] Disconnected from server', event.code, event.reason);
        this.emit('disconnected', { code: event.code, reason: event.reason });

        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('[RPC] Connection error:', error);
      this.emit('error', error);
      if (!this.isIntentionallyClosed) {
        this.scheduleReconnect();
      }
    }
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect() {
    this.isIntentionallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send a JSON-RPC request through the WebSocket
   */
  sendRequest(jsonRPCRequest) {
    return new Promise((resolve, reject) => {
      if (!this.isConnected()) {
        // Queue the request if not connected
        this.requestQueue.push({ jsonRPCRequest, resolve, reject });
        return;
      }

      try {
        this.sendRaw(jsonRPCRequest);
        resolve();
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Send raw data through the WebSocket
   */
  sendRaw(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      throw new Error('WebSocket is not connected');
    }
  }

  /**
   * Flush queued requests after reconnection
   */
  flushRequestQueue() {
    while (this.requestQueue.length > 0) {
      const { jsonRPCRequest, resolve, reject } = this.requestQueue.shift();
      try {
        this.sendRaw(jsonRPCRequest);
        resolve();
      } catch (error) {
        reject(error);
      }
    }
  }

  /**
   * Schedule a reconnection attempt with exponential backoff
   */
  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[RPC] Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );

    console.log(`[RPC] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.emit('reconnecting', { attempt: this.reconnectAttempts, delay });

    this.reconnectTimer = setTimeout(() => {
      console.log('[RPC] Attempting to reconnect...');
      this.connect();
    }, delay);
  }

  /**
   * Check if the WebSocket is connected
   */
  isConnected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get current connection state
   */
  getState() {
    if (!this.ws) return 'CLOSED';

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'CONNECTING';
      case WebSocket.OPEN:
        return 'OPEN';
      case WebSocket.CLOSING:
        return 'CLOSING';
      case WebSocket.CLOSED:
        return 'CLOSED';
      default:
        return 'UNKNOWN';
    }
  }

  /**
   * Add an event listener
   */
  on(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event].push(callback);
    }
  }

  /**
   * Remove an event listener
   */
  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  }

  /**
   * Emit an event
   */
  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => callback(data));
    }
  }
}

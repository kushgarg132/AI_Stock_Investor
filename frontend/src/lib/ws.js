import { AUTH_TOKEN_STORAGE_KEY, refreshAccessToken } from '../utils/api';

/**
 * Cheap client-side peek at a JWT's own `exp` claim -- no signature check,
 * just enough to avoid opening a socket with a token that's already dead
 * and immediately getting closed for it. A 30s buffer covers the time the
 * handshake itself takes.
 */
const isExpired = (token) => {
  try {
    const { exp } = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return !exp || exp * 1000 < Date.now() + 30000;
  } catch {
    return true;
  }
};

/**
 * One socket for the whole app.
 *
 * Every page subscribes to topics on this single connection rather than
 * opening its own. Subscriptions are held here, not on the socket, so a
 * reconnect can restore them without any page knowing the socket dropped.
 */

const SOCKET_URL = (() => {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
  const normalised = base.replace(/\/$/, '');
  const withPrefix = normalised.endsWith('/api/v1') ? normalised : `${normalised}/api/v1`;
  return `${withPrefix.replace(/^http/, 'ws')}/ws`;
})();

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

class Stream {
  constructor() {
    this.socket = null;
    this.handlers = new Map(); // topic -> Set<fn>
    this.statusHandlers = new Set();
    this.status = 'idle';
    this.attempt = 0;
    this.retryTimer = null;
    this.intentionallyClosed = false;
    this.connecting = false;
  }

  connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }
    if (this.connecting) return;
    this.connecting = true;

    (async () => {
      let token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
      if (!token || isExpired(token)) {
        try {
          token = await refreshAccessToken();
        } catch {
          // No live session (never logged in, or the refresh cookie is
          // gone too) -- nothing to connect with. A later subscribe() call
          // or login will call connect() again.
          this.connecting = false;
          return;
        }
      }
      this._open(token);
      this.connecting = false;
    })();
  }

  _open(token) {
    this.intentionallyClosed = false;
    this.setStatus(this.attempt === 0 ? 'connecting' : 'reconnecting');

    // The token rides in the query string because a browser cannot set an
    // Authorization header on a WebSocket handshake, and this app holds its
    // access token in localStorage rather than a cookie (the refresh token
    // is the one that lives in a cookie -- see utils/api.js).
    const socket = new WebSocket(`${SOCKET_URL}?token=${encodeURIComponent(token)}`);
    this.socket = socket;

    socket.onopen = () => {
      this.attempt = 0;
      this.setStatus('live');
      this.flushSubscriptions();
    };

    socket.onmessage = (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.event === 'ping') return;
      const listeners = this.handlers.get(message.topic);
      if (listeners) listeners.forEach((fn) => fn(message));
    };

    socket.onclose = () => {
      this.socket = null;
      if (this.intentionallyClosed) {
        this.setStatus('idle');
        return;
      }
      this.setStatus('offline');
      this.scheduleReconnect();
    };

    socket.onerror = () => socket.close();
  }

  scheduleReconnect() {
    if (this.retryTimer) return;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** this.attempt, RECONNECT_MAX_MS);
    this.attempt += 1;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.connect();
    }, delay);
  }

  disconnect() {
    this.intentionallyClosed = true;
    clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.attempt = 0;
    this.handlers.clear();
    if (this.socket) this.socket.close();
  }

  send(payload) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  flushSubscriptions() {
    const topics = [...this.handlers.keys()].filter((t) => !t.startsWith('__'));
    if (topics.length) this.send({ action: 'subscribe', topics });
  }

  subscribe(topic, handler) {
    let listeners = this.handlers.get(topic);
    if (!listeners) {
      listeners = new Set();
      this.handlers.set(topic, listeners);
      this.send({ action: 'subscribe', topics: [topic] });
    }
    listeners.add(handler);
    this.connect();

    return () => {
      const current = this.handlers.get(topic);
      if (!current) return;
      current.delete(handler);
      if (current.size === 0) {
        this.handlers.delete(topic);
        this.send({ action: 'unsubscribe', topics: [topic] });
      }
    };
  }

  onStatus(handler) {
    this.statusHandlers.add(handler);
    handler(this.status);
    return () => this.statusHandlers.delete(handler);
  }

  setStatus(status) {
    this.status = status;
    this.statusHandlers.forEach((fn) => fn(status));
  }

  /**
   * A one-shot request that streams its reply on a topic of its own, so two
   * analyses running at once cannot interleave.
   */
  request(action, payload, onEvent) {
    const reqId = Math.random().toString(36).slice(2, 10);
    const topicPrefix = { chat: 'chat', quick_analyze: 'quick_analysis' }[action] || 'analysis';
    const topic = `${topicPrefix}:${reqId}`;
    const unsubscribe = this.subscribe(topic, (message) => {
      onEvent(message);
      if (message.event === 'done' || message.event === 'error' || message.event === 'report') {
        unsubscribe();
      }
    });
    const sent = this.send({ action, req_id: reqId, ...payload });
    if (!sent) {
      unsubscribe();
      return { ok: false, cancel: () => {} };
    }
    return { ok: true, cancel: unsubscribe };
  }
}

export const stream = new Stream();

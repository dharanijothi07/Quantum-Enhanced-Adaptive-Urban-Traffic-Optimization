import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for resilient, auto-reconnecting WebSocket streaming.
 */
export function useSocket(url = 'ws://localhost:8000/ws') {
  const [latestState, setLatestState] = useState(null);
  const [connected, setConnected] = useState(false);
  const [isReplaying, setIsReplaying] = useState(false);
  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectDelayRef = useRef(1000);

  const connect = useCallback(() => {
    if (isReplaying) return;
    try {
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectDelayRef.current = 1000;
        console.log('[WebSocket] Connected to QuantumFlow engine');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.type === 'state') {
            setLatestState(data);
          }
        } catch (e) {
          console.error('[WebSocket] Malformed state frame:', e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!isReplaying) {
          // Exponential backoff capped at 5s
          const delay = Math.min(reconnectDelayRef.current * 1.5, 5000);
          reconnectDelayRef.current = delay;
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = (err) => {
        setConnected(false);
        ws.close();
      };
    } catch (err) {
      console.error('[WebSocket] Setup exception:', err);
      reconnectTimeoutRef.current = setTimeout(connect, 2000);
    }
  }, [url, isReplaying]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, [connect]);

  const sendPing = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ action: 'ping' }));
    }
  }, []);

  return {
    latestState,
    setLatestState,
    connected,
    isReplaying,
    setIsReplaying,
    sendPing
  };
}

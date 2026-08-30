import { useEffect, useRef } from 'react';
import { getToken } from '../api/client';

/**
 * Listen for safe academic-structure events and let a State view reload itself.
 * The event contains only school metadata; financial data is never carried on
 * the socket. Cookie-only mobile sessions are supported too: same-origin
 * WebSockets carry the HttpOnly login cookie when no bearer token is stored.
 */
export function useAcademicStructureUpdates(onUpdate) {
  const callback = useRef(onUpdate);
  callback.current = onUpdate;

  useEffect(() => {
    const token = getToken();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Same-origin WebSockets include the HttpOnly login cookie, so a browser
    // that blocks localStorage still receives live authorized updates.
    const query = token ? `?token=${encodeURIComponent(token)}` : '';
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws${query}`);
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'academic_structure_changed') callback.current?.(message.payload);
      } catch {
        // Ignore malformed live events; API data remains the source of truth.
      }
    };
    return () => socket.close();
  }, []);
}

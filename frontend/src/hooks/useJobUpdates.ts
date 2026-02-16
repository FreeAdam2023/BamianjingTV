"use client";

import { useEffect, useRef, useCallback } from "react";

interface JobUpdateData {
  status: string;
  progress: number;
  error: string | null;
  title?: string;
  item_id?: string;
  source_id?: string;
  pipeline_id?: string;
  timeline_id?: string;
}

interface JobUpdateMessage {
  type: "job_update";
  job_id: string;
  timestamp: string;
  data: JobUpdateData;
}

/**
 * Hook that subscribes to real-time job updates via WebSocket.
 * Calls `onUpdate` whenever a job status change is received.
 * Falls back to periodic polling if WebSocket disconnects.
 */
export function useJobUpdates(onUpdate: () => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const pollTimer = useRef<ReturnType<typeof setInterval>>();
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const connect = useCallback(() => {
    // Build WebSocket URL from current host
    const { hostname } = window.location;
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${hostname}:8001/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Subscribe to jobs topic
        ws.send(JSON.stringify({ action: "subscribe", topic: "jobs" }));
        // Stop polling fallback while WS is alive
        if (pollTimer.current) {
          clearInterval(pollTimer.current);
          pollTimer.current = undefined;
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as { type: string };
          if (msg.type === "job_update") {
            onUpdateRef.current();
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        // Start polling fallback
        if (!pollTimer.current) {
          pollTimer.current = setInterval(() => onUpdateRef.current(), 5000);
        }
        // Attempt reconnect after 3s
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // WebSocket creation failed — use polling
      if (!pollTimer.current) {
        pollTimer.current = setInterval(() => onUpdateRef.current(), 5000);
      }
      reconnectTimer.current = setTimeout(connect, 5000);
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (pollTimer.current) clearInterval(pollTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on unmount
        wsRef.current.close();
      }
    };
  }, [connect]);
}

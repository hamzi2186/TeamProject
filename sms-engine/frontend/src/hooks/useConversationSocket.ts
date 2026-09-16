import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { conversationSocketUrl } from "../api/sms";

export function useConversationSocket(conversationId: string | undefined) {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!conversationId) return;
    let retry: number | undefined;
    let socket: WebSocket | undefined;
    let closed = false;

    const connect = () => {
      socket = new WebSocket(conversationSocketUrl(conversationId));
      socket.onopen = () => setConnected(true);
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as { type: string };
        if (message.type !== "heartbeat" && message.type !== "connected") {
          void queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
          void queryClient.invalidateQueries({ queryKey: ["conversations"] });
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (!closed) retry = window.setTimeout(connect, 1500);
      };
    };
    connect();
    return () => {
      closed = true;
      if (retry) window.clearTimeout(retry);
      socket?.close();
    };
  }, [conversationId, queryClient]);

  return connected;
}

import { useState } from "react";
import type { Message } from "@/api/types";

export interface OptimisticMessageState {
  optimisticMessage: Message | null;
  optimisticUserMessage: Message | null;
  setOptimisticMessage: (msg: Message | null) => void;
  setOptimisticUserMessage: (msg: Message | null) => void;
}

export function useOptimisticMessages(): OptimisticMessageState {
  const [optimisticMessage, setOptimisticMessage] = useState<Message | null>(null);
  const [optimisticUserMessage, setOptimisticUserMessage] = useState<Message | null>(null);

  return {
    optimisticMessage,
    optimisticUserMessage,
    setOptimisticMessage,
    setOptimisticUserMessage,
  };
}

/**
 * Merges raw server messages with optimistic state.
 * - optimisticUserMessage: shown immediately on send, removed once real message arrives
 * - optimisticMessage: assistant message from streaming result_ready, removed on refetch
 */
export function mergeOptimisticMessages(
  rawMessages: Message[],
  optimisticUserMessage: Message | null,
  optimisticMessage: Message | null,
  clearOptimisticUserMessage: () => void,
  clearOptimisticMessage: () => void,
): Message[] {
  let base = rawMessages;

  // UX-H9: Remove optimistic user message once the real one arrives
  if (optimisticUserMessage) {
    const hasRealUser = rawMessages.some(
      (m) => m.role === "user" && m.content === optimisticUserMessage.content
    );
    if (hasRealUser) {
      queueMicrotask(clearOptimisticUserMessage);
    } else {
      base = [...rawMessages, optimisticUserMessage];
    }
  }

  // Optimistic assistant message (from streaming result_ready)
  if (optimisticMessage) {
    const hasReal = base.some(
      (m) => m.role === "assistant" && m.content === optimisticMessage.content
    );
    if (hasReal) {
      queueMicrotask(clearOptimisticMessage);
      return base;
    }
    return [...base, optimisticMessage];
  }

  return base;
}

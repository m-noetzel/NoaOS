/**
 * Chat state management — Zustand store.
 * Manages conversation threads, messages, and streaming state.
 */

import { create } from "zustand";

export interface MessageMeta {
  model?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  cost_usd?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  meta?: MessageMeta;
}

export interface Thread {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
}

interface ChatState {
  threads: Thread[];
  activeThreadId: string | null;

  createThread: (title: string) => string;
  deleteThread: (threadId: string) => void;
  setActiveThread: (threadId: string) => void;
  addMessage: (
    threadId: string,
    msg: Omit<Message, "id" | "timestamp">,
  ) => string;
  appendStreamingToken: (threadId: string, token: string) => void;
  getThreads: () => Thread[];
}

let nextId = 1;
function genId(): string {
  return `thread-${nextId++}`;
}

let nextMsgId = 1;
function genMsgId(): string {
  return `msg-${nextMsgId++}`;
}

export const useChatStore = create<ChatState>((set, get) => ({
  threads: [],
  activeThreadId: null,

  createThread(title: string): string {
    const id = genId();
    set((state) => ({
      threads: [
        ...state.threads,
        { id, title, messages: [], createdAt: new Date().toISOString() },
      ],
    }));
    return id;
  },

  deleteThread(threadId: string) {
    set((state) => ({
      threads: state.threads.filter((t) => t.id !== threadId),
      activeThreadId:
        state.activeThreadId === threadId ? null : state.activeThreadId,
    }));
  },

  setActiveThread(threadId: string) {
    set({ activeThreadId: threadId });
  },

  addMessage(threadId, msg) {
    const msgId = genMsgId();
    set((state) => ({
      threads: state.threads.map((t) =>
        t.id === threadId
          ? {
              ...t,
              messages: [
                ...t.messages,
                {
                  ...msg,
                  id: msgId,
                  timestamp: new Date().toISOString(),
                },
              ],
            }
          : t,
      ),
    }));
    return msgId;
  },

  appendStreamingToken(threadId: string, token: string) {
    set((state) => ({
      threads: state.threads.map((t) => {
        if (t.id !== threadId) return t;
        const messages = [...t.messages];
        const last = messages[messages.length - 1];
        if (last && last.isStreaming) {
          messages[messages.length - 1] = {
            ...last,
            content: last.content + token,
          };
        }
        return { ...t, messages };
      }),
    }));
  },

  getThreads() {
    return get().threads;
  },
}));

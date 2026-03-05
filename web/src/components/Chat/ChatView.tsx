/**
 * ChatView — main chat interface with message list, input, and model selector.
 */

import { useState } from "react";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";
import type { Message } from "../../store/chat";

export function ChatView() {
  const [messages, setMessages] = useState<Message[]>([]);

  const handleSend = (content: string, model: string) => {
    const msg: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, msg]);
  };

  return (
    <div>
      <div role="list" aria-label="messages">
        <MessageList messages={messages} />
      </div>
      <MessageInput onSend={handleSend} />
    </div>
  );
}

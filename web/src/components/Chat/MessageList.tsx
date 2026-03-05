/**
 * MessageList — displays chat messages with role styling and cost info.
 */

import type { Message } from "../../store/chat";

interface MessageListProps {
  messages: Message[];
  isStreaming?: boolean;
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div>
      {messages.map((msg) => (
        <div key={msg.id} data-role={msg.role}>
          <div>{msg.content}</div>

          {msg.isStreaming && (
            <span role="status" aria-label="streaming">
              ...
            </span>
          )}

          {msg.meta && (
            <div data-testid="message-meta">
              <span>{msg.meta.model}</span>
              <span>{msg.meta.prompt_tokens}</span>
              <span>{msg.meta.completion_tokens}</span>
              <span>${msg.meta.cost_usd}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

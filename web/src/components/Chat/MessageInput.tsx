/**
 * MessageInput — text input with send button and model selector.
 */

import { useState } from "react";

interface MessageInputProps {
  onSend: (content: string, model: string) => void;
}

export function MessageInput({ onSend }: MessageInputProps) {
  const [content, setContent] = useState("");
  const [model, setModel] = useState("ollama");

  const canSend = content.trim().length > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    onSend(content, model);
    setContent("");
  };

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="message-input" className="sr-only">
        Message input
      </label>
      <input
        id="message-input"
        role="textbox"
        aria-label="message input"
        type="text"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Type a message..."
      />

      <label htmlFor="model-selector" className="sr-only">
        Model
      </label>
      <select
        id="model-selector"
        aria-label="model"
        value={model}
        onChange={(e) => setModel(e.target.value)}
      >
        <option value="ollama">Ollama (Private)</option>
        <option value="anthropic">Anthropic (Claude)</option>
        <option value="openai">OpenAI (GPT-4o)</option>
      </select>

      <button type="submit" disabled={!canSend} aria-label="send">
        Send
      </button>
    </form>
  );
}

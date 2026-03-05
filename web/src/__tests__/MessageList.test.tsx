import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageList } from "../components/Chat/MessageList";
import type { Message } from "../store/chat";

const makeMessage = (overrides: Partial<Message> = {}): Message => ({
  id: "msg-1",
  role: "user",
  content: "Hello",
  timestamp: new Date().toISOString(),
  ...overrides,
});

describe("MessageList", () => {
  it("renders user messages with correct styling", () => {
    const messages: Message[] = [
      makeMessage({
        id: "msg-1",
        role: "user",
        content: "What is the weather?",
      }),
    ];

    render(<MessageList messages={messages} />);

    const messageEl = screen.getByText("What is the weather?");
    expect(messageEl).toBeInTheDocument();

    // User messages should have a distinct container class/attribute
    const container = messageEl.closest("[data-role='user']");
    expect(container).toBeInTheDocument();
  });

  it("renders assistant messages with correct styling", () => {
    const messages: Message[] = [
      makeMessage({
        id: "msg-2",
        role: "assistant",
        content: "It is sunny today.",
      }),
    ];

    render(<MessageList messages={messages} />);

    const messageEl = screen.getByText("It is sunny today.");
    expect(messageEl).toBeInTheDocument();

    // Assistant messages should have a distinct container class/attribute
    const container = messageEl.closest("[data-role='assistant']");
    expect(container).toBeInTheDocument();
  });

  it("shows streaming indicator when response is in progress", () => {
    const messages: Message[] = [
      makeMessage({
        id: "msg-1",
        role: "user",
        content: "Tell me a story",
      }),
      makeMessage({
        id: "msg-2",
        role: "assistant",
        content: "Once upon a time",
        isStreaming: true,
      }),
    ];

    render(<MessageList messages={messages} />);

    // Should show some kind of streaming/typing indicator
    expect(screen.getByRole("status", { name: /streaming/i })).toBeInTheDocument();
  });

  it("displays per-message cost info (model, tokens, cost)", () => {
    const messages: Message[] = [
      makeMessage({
        id: "msg-2",
        role: "assistant",
        content: "The answer is 42.",
        meta: {
          model: "anthropic/claude-3-haiku",
          prompt_tokens: 150,
          completion_tokens: 25,
          cost_usd: 0.0003,
        },
      }),
    ];

    render(<MessageList messages={messages} />);

    // Should display model name
    expect(screen.getByText(/claude-3-haiku/i)).toBeInTheDocument();

    // Should display token counts
    expect(screen.getByText(/150/)).toBeInTheDocument();
    expect(screen.getByText(/25/)).toBeInTheDocument();

    // Should display cost
    expect(screen.getByText(/\$0\.0003/)).toBeInTheDocument();
  });
});

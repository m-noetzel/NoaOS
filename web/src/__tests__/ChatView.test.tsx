import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatView } from "../components/Chat/ChatView";

describe("ChatView", () => {
  it("renders message list and input area", () => {
    render(<ChatView />);

    expect(screen.getByRole("list", { name: /messages/i })).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: /message input/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /send/i }),
    ).toBeInTheDocument();
  });

  it("allows user to type a message and submit", async () => {
    const user = userEvent.setup();
    render(<ChatView />);

    const input = screen.getByRole("textbox", { name: /message input/i });
    await user.type(input, "Hello, Noa!");
    expect(input).toHaveValue("Hello, Noa!");

    const sendButton = screen.getByRole("button", { name: /send/i });
    await user.click(sendButton);

    // Input should be cleared after sending
    expect(input).toHaveValue("");
  });

  it("displays submitted message in the message list", async () => {
    const user = userEvent.setup();
    render(<ChatView />);

    const input = screen.getByRole("textbox", { name: /message input/i });
    await user.type(input, "Hello, Noa!");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText("Hello, Noa!")).toBeInTheDocument();
    });
  });

  it("renders model selector dropdown with provider options", () => {
    render(<ChatView />);

    const selector = screen.getByRole("combobox", { name: /model/i });
    expect(selector).toBeInTheDocument();

    // Check that expected model provider options are present
    const options = screen.getAllByRole("option");
    const optionValues = options.map((opt) => opt.textContent?.toLowerCase());
    expect(optionValues).toContain(expect.stringContaining("ollama"));
    expect(optionValues).toContain(expect.stringContaining("anthropic"));
    expect(optionValues).toContain(expect.stringContaining("openai"));
  });

  it("prevents submitting an empty message", async () => {
    const user = userEvent.setup();
    render(<ChatView />);

    const sendButton = screen.getByRole("button", { name: /send/i });

    // Send button should be disabled when input is empty
    expect(sendButton).toBeDisabled();

    // Type something then clear it
    const input = screen.getByRole("textbox", { name: /message input/i });
    await user.type(input, "   ");

    // Whitespace-only should also keep send disabled
    expect(sendButton).toBeDisabled();
  });
});

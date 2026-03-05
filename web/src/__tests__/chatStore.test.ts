import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "../store/chat";

describe("chatStore", () => {
  beforeEach(() => {
    // Reset store state before each test
    const store = useChatStore.getState();
    // Clear all threads by resetting store
    useChatStore.setState({
      threads: [],
      activeThreadId: null,
    });
  });

  it("can create a new conversation thread", () => {
    const { createThread } = useChatStore.getState();

    const threadId = createThread("New conversation");

    const { threads } = useChatStore.getState();
    expect(threads).toHaveLength(1);
    expect(threads[0].id).toBe(threadId);
    expect(threads[0].title).toBe("New conversation");
    expect(threads[0].messages).toEqual([]);
  });

  it("can add a message to a thread", () => {
    const { createThread, addMessage } = useChatStore.getState();

    const threadId = createThread("Test thread");

    addMessage(threadId, {
      role: "user",
      content: "Hello, Noa!",
    });

    const { threads } = useChatStore.getState();
    const thread = threads.find((t) => t.id === threadId);
    expect(thread).toBeDefined();
    expect(thread!.messages).toHaveLength(1);
    expect(thread!.messages[0].role).toBe("user");
    expect(thread!.messages[0].content).toBe("Hello, Noa!");
  });

  it("can switch between threads", () => {
    const { createThread, setActiveThread } = useChatStore.getState();

    const thread1 = createThread("Thread 1");
    const thread2 = createThread("Thread 2");

    setActiveThread(thread1);
    expect(useChatStore.getState().activeThreadId).toBe(thread1);

    setActiveThread(thread2);
    expect(useChatStore.getState().activeThreadId).toBe(thread2);
  });

  it("can delete a thread", () => {
    const { createThread, deleteThread } = useChatStore.getState();

    const thread1 = createThread("Thread 1");
    const thread2 = createThread("Thread 2");

    expect(useChatStore.getState().threads).toHaveLength(2);

    deleteThread(thread1);

    const { threads } = useChatStore.getState();
    expect(threads).toHaveLength(1);
    expect(threads[0].id).toBe(thread2);
  });

  it("streaming tokens append to current assistant message", () => {
    const { createThread, addMessage, appendStreamingToken } =
      useChatStore.getState();

    const threadId = createThread("Test thread");

    // Add an assistant message that will receive streaming tokens
    addMessage(threadId, {
      role: "assistant",
      content: "",
      isStreaming: true,
    });

    appendStreamingToken(threadId, "Hello");
    appendStreamingToken(threadId, " world");

    const { threads } = useChatStore.getState();
    const thread = threads.find((t) => t.id === threadId);
    const lastMessage = thread!.messages[thread!.messages.length - 1];

    expect(lastMessage.content).toBe("Hello world");
    expect(lastMessage.isStreaming).toBe(true);
  });

  it("can list all threads", () => {
    const { createThread, getThreads } = useChatStore.getState();

    createThread("Thread A");
    createThread("Thread B");
    createThread("Thread C");

    const threads = useChatStore.getState().threads;
    expect(threads).toHaveLength(3);
    expect(threads.map((t) => t.title)).toEqual([
      "Thread A",
      "Thread B",
      "Thread C",
    ]);
  });
});

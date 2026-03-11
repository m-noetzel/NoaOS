import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import { SSEClient } from "@/api/sse";
import type { Thread, Message, SSEEvent, ChatRequest, Run, PrivacyMode, Provider, UserSettings } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ActivityStream } from "@/components/chat/ActivityStream";
import { ExecutionDetails } from "@/components/chat/ExecutionDetails";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { Send, Plus, Settings2, Sparkles, User, Trash2 } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";

/** Group messages by their run_id so we can show activity streams between exchanges */
interface MessageGroup {
  runId?: string;
  userMessage?: Message;
  assistantMessage?: Message;
  run?: Run;
}

function groupMessagesByRun(messages: Message[], runs: Run[]): MessageGroup[] {
  const groups: MessageGroup[] = [];
  const runMap = new Map(runs.map((r) => [r.id, r]));

  let currentGroup: MessageGroup | null = null;

  for (const msg of messages) {
    if (msg.role === "user") {
      currentGroup = {
        runId: msg.run_id,
        userMessage: msg,
        run: msg.run_id ? runMap.get(msg.run_id) : undefined,
      };
      groups.push(currentGroup);
    } else if (msg.role === "assistant" && currentGroup) {
      currentGroup.assistantMessage = msg;
      currentGroup = null;
    } else {
      groups.push({ assistantMessage: msg });
    }
  }

  return groups;
}

/** Derive a thread title from the first message content */
function deriveThreadTitle(message: string): string {
  const trimmed = message.trim();
  if (!trimmed) return "New Thread";
  if (trimmed.length <= 50) return trimmed;
  return trimmed.slice(0, 50) + "...";
}

export default function Chat() {
  const { toast } = useToast();
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [optimisticMessage, setOptimisticMessage] = useState<Message | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamEvents, setStreamEvents] = useState<SSEEvent[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [systemPrompt, setSystemPrompt] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  // Load saved settings — use query data directly (UI-M8: no local state copy)
  const { data: settingsRes } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<UserSettings>("/api/v1/settings"),
  });

  // Derive model/provider/privacyMode directly from settings query data
  const settings = settingsRes?.data;
  const model = settings?.default_model || "claude-sonnet-4-20250514";
  const provider = (settings?.default_provider || "anthropic") as Provider;
  const privacyMode = (settings?.default_privacy_mode || "external") as PrivacyMode;

  const createThreadMutation = useMutation({
    mutationFn: (title: string) =>
      apiRequest<Thread>("/api/v1/threads", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      if (res.data) {
        setActiveThread(res.data.id);
      }
    },
  });

  const deleteThreadMutation = useMutation({
    mutationFn: (threadId: string) =>
      apiRequest(`/api/v1/threads/${threadId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      setActiveThread(null);
    },
  });

  const { data: threadsRes } = useQuery({
    queryKey: ["threads"],
    queryFn: () => apiRequest<Thread[]>("/api/v1/threads"),
  });

  const { data: messagesRes } = useQuery({
    queryKey: ["messages", activeThread],
    queryFn: () => apiRequest<Message[]>(`/api/v1/threads/${activeThread}/messages`),
    enabled: !!activeThread,
  });

  const { data: runsRes } = useQuery({
    queryKey: ["runs"],
    queryFn: () => apiRequest<Run[]>("/api/v1/runs"),
  });

  const threads = threadsRes?.data || [];
  const rawMessages = messagesRes?.data || [];
  const runs = runsRes?.data || [];
  const threadRuns = runs.filter((r) => r.thread_id === activeThread);

  // UI-M4: Include optimistic message, clear it when refetch brings real data
  const messages = (() => {
    if (optimisticMessage && rawMessages.length > 0) {
      // If the refetched messages already contain assistant content matching the optimistic one, drop it
      const hasReal = rawMessages.some(
        (m) => m.role === "assistant" && m.content === optimisticMessage.content
      );
      if (hasReal) {
        // Clear optimistic on next tick to avoid state update during render
        queueMicrotask(() => setOptimisticMessage(null));
        return rawMessages;
      }
    }
    if (optimisticMessage) {
      return [...rawMessages, optimisticMessage];
    }
    return rawMessages;
  })();

  const messageGroups = groupMessagesByRun(messages, threadRuns);

  useEffect(() => {
    if (threads.length && !activeThread) {
      setActiveThread(threads[0].id);
    }
  }, [threads, activeThread]);

  useEffect(() => {
    if (messagesEndRef.current?.scrollIntoView) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingContent, streamEvents]);

  // Ref to hold the latest activeThread for SSE event handler
  const activeThreadRef = useRef(activeThread);
  activeThreadRef.current = activeThread;

  const handleSSEEvent = useCallback((event: SSEEvent) => {
    setStreamEvents((prev) => [...prev, event]);

    switch (event.event) {
      case "meta":
        if (event.data.run_id) {
          setCurrentRunId(event.data.run_id as string);
        }
        break;
      case "token_stream":
        setStreamingContent((prev) => prev + (event.data.token as string));
        break;
      case "result_ready":
        // UI-M4: Optimistically append assistant message before clearing streaming
        setStreamingContent((prev) => {
          if (prev) {
            setOptimisticMessage({
              id: `optimistic-${Date.now()}`,
              thread_id: activeThreadRef.current || "",
              role: "assistant",
              content: prev,
              created_at: new Date().toISOString(),
            });
          }
          return "";
        });
        setIsStreaming(false);
        queryClient.invalidateQueries({ queryKey: ["messages", activeThreadRef.current] });
        break;
      case "error":
        setIsStreaming(false);
        toast({
          title: "Chat error",
          description: (event.data.error as string) || "An unexpected error occurred",
          variant: "destructive",
        });
        break;
    }
  }, [queryClient]);

  // Create SSEClient eagerly so event handler is wired at mount time
  const sseClientRef = useRef<SSEClient | null>(null);
  if (!sseClientRef.current) {
    sseClientRef.current = new SSEClient({
      onEvent: (event) => handleSSEEvent(event),
      onError: (err) => {
        setIsStreaming(false);
        toast({
          title: "Connection failed",
          description: err?.message || "Could not reach the backend. Is Noa running?",
          variant: "destructive",
        });
      },
      onClose: () => setIsStreaming(false),
    });
  }

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const message = input.trim();
    setInput("");
    setStreamingContent("");
    setOptimisticMessage(null);
    setStreamEvents([]);
    setIsStreaming(true);

    // UI-M5: Create a new thread and await its ID before connecting SSE
    let threadId = activeThread;
    if (!threadId) {
      try {
        const title = deriveThreadTitle(message);
        const res = await createThreadMutation.mutateAsync(title);
        threadId = res.data?.id ?? null;
        if (!threadId) {
          setIsStreaming(false);
          toast({ title: "Failed to create thread", description: "Server returned no thread ID", variant: "destructive" });
          return;
        }
      } catch (err) {
        setIsStreaming(false);
        toast({
          title: "Failed to create thread",
          description: err instanceof Error ? err.message : "Unknown error",
          variant: "destructive",
        });
        return;
      }
    }

    const body: ChatRequest = {
      message,
      thread_id: threadId || undefined,
      privacy_mode: privacyMode,
      model,
      provider,
      temperature,
      max_tokens: maxTokens,
      ...(systemPrompt.trim() ? { system_prompt: systemPrompt.trim() } : {}),
    };

    await sseClientRef.current!.connect("/api/v1/chat", body);
  };

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      {/* Thread sidebar */}
      <div className="w-60 border-r border-border/50 flex flex-col shrink-0 bg-muted/20">
        <div className="p-3 flex items-center justify-between border-b border-border/30">
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">Threads</span>
          <Button variant="ghost" size="icon" aria-label="New thread" className="h-7 w-7 rounded-lg hover:bg-accent/60 hover:text-primary transition-all" onClick={() => createThreadMutation.mutate("New Thread")}>
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-1.5 space-y-0.5">
            {threads.map((thread, i) => (
              <div
                key={thread.id}
                className={cn(
                  "group relative w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all duration-200 animate-fade-in cursor-pointer",
                  activeThread === thread.id
                    ? "bg-accent text-accent-foreground font-medium glow-sm border border-border/50"
                    : "hover:bg-accent/40 text-muted-foreground hover:text-foreground"
                )}
                style={{ animationDelay: `${i * 50}ms` }}
                onClick={() => setActiveThread(thread.id)}
              >
                <p className="truncate text-[13px] pr-6">{thread.title}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{thread.message_count} messages</p>
                <button
                  className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/20 hover:text-destructive transition-all"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm("Delete this thread?")) {
                      deleteThreadMutation.mutate(thread.id);
                    }
                  }}
                  aria-label="Delete thread"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Message area */}
      <div className="flex-1 flex flex-col min-w-0">
        <ScrollArea className="flex-1 p-4">
          <div className="max-w-2xl mx-auto space-y-3 py-4" data-testid="message-list">
            {/* Render message groups with run context */}
            {messageGroups.map((group, gi) => (
              <div key={gi} className="space-y-2">
                {/* User message */}
                {group.userMessage && (
                  <div className="flex gap-3 flex-row-reverse animate-fade-in">
                    <div className="flex-shrink-0 h-7 w-7 rounded-lg bg-primary/10 text-primary flex items-center justify-center mt-0.5">
                      <User className="h-3.5 w-3.5" />
                    </div>
                    <div className="rounded-2xl px-4 py-3 max-w-[80%] bg-primary text-primary-foreground rounded-tr-md shadow-md">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{group.userMessage.content}</p>
                      <p className="text-[10px] mt-1.5 text-primary-foreground/60">
                        {new Date(group.userMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                )}

                {/* Completed run activity summary */}
                {group.run && (
                  <ActivityStream
                    events={[]}
                    isStreaming={false}
                    runId={group.run.id}
                    runStatus={group.run.status}
                    runSummary={group.run.summary}
                  />
                )}

                {/* Assistant message */}
                {group.assistantMessage && (
                  <div className="flex gap-3 flex-row animate-fade-in">
                    <div className="flex-shrink-0 h-7 w-7 rounded-lg gradient-primary text-primary-foreground flex items-center justify-center mt-0.5 shadow-sm">
                      <Sparkles className="h-3.5 w-3.5" />
                    </div>
                    <div className="rounded-2xl rounded-tl-md px-4 py-3 glass-strong max-w-[80%]">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{group.assistantMessage.content}</p>
                      <p className="text-[10px] mt-1.5 text-muted-foreground">
                        {new Date(group.assistantMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Live activity stream during execution */}
            {(isStreaming || streamEvents.length > 0) && (
              <div className="ml-10">
                <ActivityStream
                  events={streamEvents}
                  isStreaming={isStreaming}
                  runId={currentRunId || undefined}
                  runStatus={isStreaming ? "running" : "completed"}
                  runSummary="Task completed"
                />
                <ExecutionDetails events={streamEvents} />
              </div>
            )}

            {/* Streaming content */}
            {streamingContent && (
              <div className="flex gap-3 animate-fade-in" data-testid="streaming-content">
                <div className="flex-shrink-0 h-7 w-7 rounded-lg gradient-primary text-primary-foreground flex items-center justify-center mt-0.5 shadow-sm animate-glow-pulse">
                  <Sparkles className="h-3.5 w-3.5" />
                </div>
                <div className="rounded-2xl rounded-tl-md px-4 py-3 glass-strong max-w-[80%]">
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{streamingContent}</p>
                  <span className="inline-block w-0.5 h-4 bg-primary animate-pulse-subtle rounded-full ml-0.5" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Composer */}
        <div className="border-t border-border/30 bg-background/50 backdrop-blur-sm">
          <div className="p-4 max-w-2xl mx-auto w-full">
            <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
              <CollapsibleContent className="mb-3 space-y-3 animate-fade-in">
                <div className="space-y-3 p-3 rounded-xl bg-muted/40 border border-border/30">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                        Temperature: {temperature}
                      </Label>
                      <Slider value={[temperature]} onValueChange={([v]) => setTemperature(v)} min={0} max={2} step={0.1} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                        Max tokens: {maxTokens}
                      </Label>
                      <Slider value={[maxTokens]} onValueChange={([v]) => setMaxTokens(v)} min={256} max={16384} step={256} />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                      System prompt
                    </Label>
                    <Textarea
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      placeholder="Optional system prompt (e.g. 'Antworte immer auf Deutsch')"
                      className="min-h-[60px] text-sm bg-background/50 border-border/40 resize-y"
                      rows={2}
                    />
                  </div>
                </div>
              </CollapsibleContent>

              <div className="flex gap-2 items-end">
                <CollapsibleTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Advanced settings"
                    className={cn(
                      "h-10 w-10 shrink-0 rounded-xl transition-all duration-200",
                      advancedOpen ? "bg-accent text-primary" : "hover:bg-accent/60"
                    )}
                  >
                    <Settings2 className="h-4 w-4" />
                  </Button>
                </CollapsibleTrigger>
                <div className="flex-1 relative">
                  <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                    placeholder="Message Noa…"
                    className="h-10 pr-12 rounded-xl bg-muted/40 border-border/40 focus:border-primary/40 focus:glow-sm transition-all placeholder:text-muted-foreground/50"
                    disabled={isStreaming}
                    data-testid="chat-input"
                  />
                </div>
                <Button
                  onClick={handleSend}
                  disabled={!input.trim() || isStreaming}
                  size="icon"
                  className="h-10 w-10 shrink-0 rounded-xl gradient-primary shadow-md hover:shadow-lg hover:brightness-110 transition-all duration-200 disabled:opacity-30"
                  data-testid="chat-send"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </Collapsible>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import { SSEClient } from "@/api/sse";
import type { Thread, Message, SSEEvent, SSEEventType, ChatRequest, Run, PrivacyMode, Provider, UserSettings } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ActivityStream } from "@/components/chat/ActivityStream";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { Send, Plus, Settings2, Sparkles, User, Trash2, Pencil, Check, X } from "lucide-react";
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
  // UX-H9: Optimistic user message shown immediately on send
  const [optimisticUserMessage, setOptimisticUserMessage] = useState<Message | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamEvents, setStreamEvents] = useState<SSEEvent[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [pendingApproval, setPendingApproval] = useState<{
    tool: string; function: string; args: Record<string, unknown>; risk_tier: string;
    approval_id?: string;
  } | null>(null);
  const [temperature, setTemperature] = useState<number | null>(null);
  const [maxTokens, setMaxTokens] = useState<number | null>(null);
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  // Load saved settings — use query data directly (UI-M8: no local state copy)
  const { data: settingsRes } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<UserSettings>("/api/v1/settings"),
  });

  // Derive model/provider/privacyMode directly from settings query data
  const settings = settingsRes?.data;
  const model = settings?.default_model || "gpt-4.1";
  const provider = (settings?.default_provider || "openai") as Provider;
  const privacyMode = (settings?.default_privacy_mode || "external") as PrivacyMode;

  // Initialize chat defaults from saved settings (once loaded)
  const effectiveTemperature = temperature ?? settings?.temperature ?? 0.7;
  const effectiveMaxTokens = maxTokens ?? settings?.max_tokens ?? 4096;
  const effectiveSystemPrompt = systemPrompt ?? settings?.system_prompt ?? "";

  // Save chat defaults to settings on change
  const saveChatDefaultsMutation = useMutation({
    mutationFn: (updates: Record<string, unknown>) =>
      apiRequest("/api/v1/settings", {
        method: "PATCH",
        body: JSON.stringify(updates),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

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

  // UX-M3: Inline thread rename
  const [renamingThread, setRenamingThread] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const renameThreadMutation = useMutation({
    mutationFn: ({ threadId, title }: { threadId: string; title: string }) =>
      apiRequest(`/api/v1/threads/${threadId}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      setRenamingThread(null);
      setRenameValue("");
    },
    onError: (err: Error) => {
      toast({ title: "Failed to rename thread", description: err.message, variant: "destructive" });
    },
  });

  const startRename = (threadId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingThread(threadId);
    setRenameValue(currentTitle);
  };

  const commitRename = (threadId: string) => {
    const title = renameValue.trim();
    if (!title) return;
    renameThreadMutation.mutate({ threadId, title });
  };

  const cancelRename = () => {
    setRenamingThread(null);
    setRenameValue("");
  };

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

  // UI-M4: Include optimistic messages, clear them when refetch brings real data
  const messages = (() => {
    let base = rawMessages;

    // UX-H9: Remove optimistic user message once the real one arrives
    if (optimisticUserMessage) {
      const hasRealUser = rawMessages.some(
        (m) => m.role === "user" && m.content === optimisticUserMessage.content
      );
      if (hasRealUser) {
        queueMicrotask(() => setOptimisticUserMessage(null));
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
        queueMicrotask(() => setOptimisticMessage(null));
        return base;
      }
      return [...base, optimisticMessage];
    }

    return base;
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
        // UI-M4: Optimistically append assistant message before clearing streaming.
        // Use accumulated streaming content if available, otherwise fall back to
        // the response payload (runner may not emit token_stream events).
        setStreamingContent((prev) => {
          const content = prev || (event.data.response as string) || "";
          if (content) {
            setOptimisticMessage({
              id: `optimistic-${Date.now()}`,
              thread_id: activeThreadRef.current || "",
              role: "assistant",
              content,
              created_at: new Date().toISOString(),
            });
          }
          return "";
        });
        setIsStreaming(false);
        // UX-H9: Do NOT clear optimisticUserMessage here — the deduplication logic
        // in the messages memo removes it when the real message arrives from the
        // refetch. Clearing early causes a flash where the message disappears
        // momentarily before the refetch completes.
        queryClient.invalidateQueries({ queryKey: ["messages", activeThreadRef.current] });
        queryClient.invalidateQueries({ queryKey: ["threads"] });
        break;
      case "approval_requested":
        setPendingApproval({
          tool: event.data.tool as string,
          function: event.data.function as string,
          args: (event.data.args as Record<string, unknown>) || {},
          risk_tier: event.data.risk_tier as string,
          approval_id: event.data.approval_id as string | undefined,
        });
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

  // CRITICAL 1: Disconnect SSE client when component unmounts to prevent
  // event callbacks firing on an unmounted component and memory leaks.
  useEffect(() => {
    return () => { sseClientRef.current?.disconnect(); };
  }, []);

  const handleSend = async () => {
    // UX-H2: Allow clicking send even when input is empty (show toast), never
    // disable the button outright — only block during active streaming.
    if (isStreaming) return;
    if (!input.trim()) {
      toast({ title: "Type a message", description: "Enter a message before sending.", variant: "destructive" });
      return;
    }

    const message = input.trim();
    setInput("");
    setStreamingContent("");
    setStreamEvents([]);
    setIsStreaming(true);

    // UX-H9: Optimistically add the user message immediately so it appears in
    // the chat before the SSE stream returns — creates a snappier feel.
    const optimisticUserMessage: Message = {
      id: `optimistic-user-${Date.now()}`,
      thread_id: activeThread || "",
      role: "user",
      content: message,
      created_at: new Date().toISOString(),
    };
    setOptimisticMessage(null);  // clear any previous assistant optimistic
    // We add the user message via a separate state so it renders instantly
    setOptimisticUserMessage(optimisticUserMessage);

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
      temperature: effectiveTemperature,
      max_tokens: effectiveMaxTokens,
      ...(effectiveSystemPrompt.trim() ? { system_prompt: effectiveSystemPrompt.trim() } : {}),
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
                onClick={() => renamingThread !== thread.id && setActiveThread(thread.id)}
              >
                {/* UX-M3: Inline rename mode */}
                {renamingThread === thread.id ? (
                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    <input
                      autoFocus
                      className="flex-1 text-[13px] bg-transparent border-b border-primary outline-none min-w-0"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename(thread.id);
                        if (e.key === "Escape") cancelRename();
                      }}
                      aria-label="Thread title"
                    />
                    <button
                      className="p-1 rounded hover:bg-green-500/20 hover:text-green-600 text-muted-foreground transition-all"
                      onClick={() => commitRename(thread.id)}
                      aria-label="Confirm rename"
                    >
                      <Check className="h-3 w-3" />
                    </button>
                    <button
                      className="p-1 rounded hover:bg-muted hover:text-foreground text-muted-foreground transition-all"
                      onClick={cancelRename}
                      aria-label="Cancel rename"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ) : (
                  <>
                    <p className="truncate text-[13px] pr-12">{thread.title}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">{thread.message_count} messages</p>
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-all">
                      <button
                        className="p-1 rounded hover:bg-accent/60 hover:text-primary transition-all"
                        onClick={(e) => startRename(thread.id, thread.title, e)}
                        aria-label="Rename thread"
                      >
                        <Pencil className="h-3 w-3" />
                      </button>
                      <button
                        className="p-1 rounded hover:bg-destructive/20 hover:text-destructive transition-all"
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
                  </>
                )}
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
              </div>
            )}

            {/* Approval request card */}
            {pendingApproval && (
              <div className="animate-fade-in mx-auto max-w-md">
                <div className="rounded-xl border-2 border-amber-500/50 bg-amber-500/10 p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-amber-500 text-lg">⚠</span>
                    <span className="font-semibold text-sm">Approval Required</span>
                    <span className="ml-auto text-[10px] uppercase tracking-wider font-medium text-amber-600 bg-amber-500/20 px-2 py-0.5 rounded-full">
                      {pendingApproval.risk_tier} risk
                    </span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Noa wants to execute <span className="font-mono font-medium text-foreground">{pendingApproval.tool}.{pendingApproval.function}</span>
                  </div>
                  {Object.keys(pendingApproval.args).length > 0 && (
                    <div className="text-xs bg-background/50 rounded-lg p-2 space-y-0.5 font-mono max-h-32 overflow-y-auto">
                      {Object.entries(pendingApproval.args).map(([k, v]) => (
                        <div key={k}>
                          <span className="text-muted-foreground">{k}:</span>{" "}
                          <span className="text-foreground">{typeof v === "string" ? v : JSON.stringify(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex gap-2 pt-1">
                    <Button
                      size="sm"
                      className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                      onClick={async () => {
                        const aid = pendingApproval.approval_id;
                        const toolLabel = `${pendingApproval.tool}.${pendingApproval.function}`;
                        setPendingApproval(null);
                        setIsStreaming(true);  // Show "executing" state while tool runs
                        // Add a visual event so user sees what's happening
                        setStreamEvents((prev) => [...prev, {
                          event: "step_started" as SSEEventType,
                          data: { step: `Executing ${toolLabel} (approved)` },
                        }]);
                        if (aid) {
                          try {
                            const res = await apiRequest<{
                              approval_id: string;
                              decision: string;
                              tool_result?: Record<string, unknown>;
                            }>(`/api/v1/approvals/${aid}/decide`, {
                              method: "POST",
                              body: JSON.stringify({ decision: "approved" }),
                            });
                            // Show tool result in activity stream
                            const toolResult = res.data?.tool_result;
                            setStreamEvents((prev) => [...prev, {
                              event: "tool_end" as SSEEventType,
                              data: {
                                tool_name: toolLabel,
                                result: toolResult ?? { status: "executed" },
                              },
                            }]);
                            // Build a completion message from the result
                            const resultSummary = toolResult?.error
                              ? `Tool execution failed: ${toolResult.error}`
                              : `${toolLabel} executed successfully.`;
                            setOptimisticMessage({
                              id: `optimistic-approval-${Date.now()}`,
                              thread_id: activeThreadRef.current || "",
                              role: "assistant",
                              content: resultSummary,
                              created_at: new Date().toISOString(),
                            });
                            queryClient.invalidateQueries({ queryKey: ["approvals"] });
                            queryClient.invalidateQueries({ queryKey: ["messages", activeThreadRef.current] });
                            queryClient.invalidateQueries({ queryKey: ["runs"] });
                            toast({ title: "Approved & Executed", description: resultSummary });
                          } catch (err) {
                            toast({
                              title: "Execution failed",
                              description: err instanceof Error ? err.message : "Unknown error",
                              variant: "destructive",
                            });
                          }
                        }
                        setIsStreaming(false);
                      }}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1 border-destructive/50 text-destructive hover:bg-destructive/10"
                      onClick={async () => {
                        const aid = pendingApproval.approval_id;
                        setPendingApproval(null);
                        setIsStreaming(false);
                        if (aid) {
                          try {
                            await apiRequest(`/api/v1/approvals/${aid}/decide`, {
                              method: "POST",
                              body: JSON.stringify({ decision: "denied" }),
                            });
                            queryClient.invalidateQueries({ queryKey: ["approvals"] });
                            queryClient.invalidateQueries({ queryKey: ["runs"] });
                          } catch { /* ignore */ }
                        }
                        toast({ title: "Denied", description: "Action was denied" });
                      }}
                    >
                      Deny
                    </Button>
                  </div>
                </div>
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
                        Temperature: {effectiveTemperature}
                      </Label>
                      <Slider
                        value={[effectiveTemperature]}
                        onValueChange={([v]) => setTemperature(v)}
                        onValueCommit={([v]) => saveChatDefaultsMutation.mutate({ temperature: v })}
                        min={0} max={2} step={0.1}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                        Max tokens: {effectiveMaxTokens}
                      </Label>
                      <Slider
                        value={[effectiveMaxTokens]}
                        onValueChange={([v]) => setMaxTokens(v)}
                        onValueCommit={([v]) => saveChatDefaultsMutation.mutate({ max_tokens: v })}
                        min={256} max={16384} step={256}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                      System prompt
                    </Label>
                    <Textarea
                      value={effectiveSystemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      onBlur={() => {
                        const val = (systemPrompt ?? "").trim();
                        const saved = (settings?.system_prompt ?? "").trim();
                        if (val !== saved) {
                          saveChatDefaultsMutation.mutate({ system_prompt: val || null });
                        }
                      }}
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
                {/* UX-H2: Send is enabled at all times (only disabled during streaming) */}
                <Button
                  onClick={handleSend}
                  disabled={isStreaming}
                  size="icon"
                  aria-label="Send message"
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

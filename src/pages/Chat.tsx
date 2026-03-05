import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import { SSEClient } from "@/api/sse";
import type { Thread, Message, SSEEvent, ChatRequest, Run } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ActivityStream } from "@/components/chat/ActivityStream";
import { ExecutionDetails } from "@/components/chat/ExecutionDetails";
import { cn } from "@/lib/utils";
import { Send, Plus, Settings2, Sparkles, User } from "lucide-react";
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

export default function Chat() {
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamEvents, setStreamEvents] = useState<SSEEvent[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(4096);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sseRef = useRef<SSEClient | null>(null);

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
  const messages = messagesRes?.data || [];
  const runs = runsRes?.data || [];
  const threadRuns = runs.filter((r) => r.thread_id === activeThread);

  const messageGroups = groupMessagesByRun(messages, threadRuns);

  useEffect(() => {
    if (threads.length && !activeThread) {
      setActiveThread(threads[0].id);
    }
  }, [threads, activeThread]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, streamEvents]);

  const handleSSEEvent = useCallback((event: SSEEvent) => {
    setStreamEvents((prev) => [...prev, event]);

    switch (event.event) {
      case "token_stream":
        setStreamingContent((prev) => prev + (event.data.token as string));
        break;
      case "result_ready":
        setStreamingContent("");
        setIsStreaming(false);
        break;
      case "error":
        setIsStreaming(false);
        break;
    }
  }, []);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const message = input.trim();
    setInput("");
    setStreamingContent("");
    setStreamEvents([]);
    setIsStreaming(true);

    const isMock = !import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_USE_MOCKS === "true";
    if (isMock) {
      // Simulate activity stream
      const mockRunId = "r_" + Date.now();
      setCurrentRunId(mockRunId);

      const mockActivities: SSEEvent[] = [
        { event: "planner_step", data: { step: "Planning request" } },
        { event: "planner_step", data: { step: "Searching the web" } },
        { event: "tool_called", data: { tool_name: "web_search", args: { query: message } } },
        { event: "tool_result", data: { tool_name: "web_search", result: "Found 8 results", duration_ms: 3200 } },
        { event: "planner_step", data: { step: "Parsing results" } },
        { event: "planner_step", data: { step: "Writing response" } },
      ];

      for (const activity of mockActivities) {
        await new Promise((r) => setTimeout(r, 600));
        setStreamEvents((prev) => [...prev, activity]);
      }

      const mockResponse = "This is a simulated response from the Noa agent. In production, this would stream tokens from the backend via SSE.";
      for (let i = 0; i < mockResponse.length; i++) {
        await new Promise((r) => setTimeout(r, 15));
        setStreamingContent((prev) => prev + mockResponse[i]);
      }

      setStreamEvents((prev) => [...prev, { event: "result_ready", data: { response_text: mockResponse } }]);
      setIsStreaming(false);
      setStreamingContent("");
      return;
    }

    const client = new SSEClient({
      onEvent: handleSSEEvent,
      onError: () => setIsStreaming(false),
      onClose: () => setIsStreaming(false),
    });
    sseRef.current = client;

    const body: ChatRequest = {
      message,
      thread_id: activeThread || undefined,
      privacy_mode: "private",
      model: "claude-3.5-sonnet",
      provider: "anthropic",
      temperature,
      max_tokens: maxTokens,
    };

    await client.connect("/api/v1/chat", body);
  };

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      {/* Thread sidebar */}
      <div className="w-60 border-r border-border/50 flex flex-col shrink-0 bg-muted/20">
        <div className="p-3 flex items-center justify-between border-b border-border/30">
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">Threads</span>
          <Button variant="ghost" size="icon" className="h-7 w-7 rounded-lg hover:bg-accent/60 hover:text-primary transition-all">
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-1.5 space-y-0.5">
            {threads.map((thread, i) => (
              <button
                key={thread.id}
                onClick={() => setActiveThread(thread.id)}
                className={cn(
                  "w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all duration-200 animate-fade-in",
                  activeThread === thread.id
                    ? "bg-accent text-accent-foreground font-medium glow-sm border border-border/50"
                    : "hover:bg-accent/40 text-muted-foreground hover:text-foreground"
                )}
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <p className="truncate text-[13px]">{thread.title}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{thread.message_count} messages</p>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Message area */}
      <div className="flex-1 flex flex-col min-w-0">
        <ScrollArea className="flex-1 p-4">
          <div className="max-w-2xl mx-auto space-y-3 py-4">
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
              <div className="flex gap-3 animate-fade-in">
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
                <div className="grid grid-cols-2 gap-4 p-3 rounded-xl bg-muted/40 border border-border/30">
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
              </CollapsibleContent>

              <div className="flex gap-2 items-end">
                <CollapsibleTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
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
                  />
                </div>
                <Button
                  onClick={handleSend}
                  disabled={!input.trim() || isStreaming}
                  size="icon"
                  className="h-10 w-10 shrink-0 rounded-xl gradient-primary shadow-md hover:shadow-lg hover:brightness-110 transition-all duration-200 disabled:opacity-30"
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

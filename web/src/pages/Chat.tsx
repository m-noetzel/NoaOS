import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { Thread, Message, Run, UserSettings, SSEEvent } from "@/api/types";
import { ThreadSidebar } from "@/components/chat/ThreadSidebar";
import { ChatMessages, groupMessagesByRun } from "@/components/chat/ChatMessages";
import { ApprovalCard } from "@/components/chat/ApprovalCard";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { useChatSSE, type PendingApproval } from "@/hooks/useChatSSE";
import {
  useOptimisticMessages,
  mergeOptimisticMessages,
} from "@/hooks/useOptimisticMessages";
import { Button } from "@/components/ui/button";
import { CheckCircle2 } from "lucide-react";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";

export default function Chat() {
  const queryClient = useQueryClient();

  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamEvents, setStreamEvents] = useState<SSEEvent[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] =
    useState<PendingApproval | null>(null);

  const {
    optimisticMessage,
    optimisticUserMessage,
    setOptimisticMessage,
    setOptimisticUserMessage,
  } = useOptimisticMessages();

  // Load saved settings
  const { data: settingsRes } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<UserSettings>("/api/v1/settings"),
  });
  const settings = settingsRes?.data;

  const { data: messagesRes } = useQuery({
    queryKey: ["messages", activeThread],
    queryFn: () =>
      apiRequest<Message[]>(`/api/v1/threads/${activeThread}/messages`),
    enabled: !!activeThread,
  });

  const { data: runsRes } = useQuery({
    queryKey: ["runs"],
    queryFn: () => apiRequest<Run[]>("/api/v1/runs"),
  });

  const rawMessages = messagesRes?.data || [];
  const runs = runsRes?.data || [];
  const threadRuns = runs.filter((r) => r.thread_id === activeThread);

  // Ref to hold the latest activeThread for SSE event handler
  const activeThreadRef = useRef(activeThread);
  activeThreadRef.current = activeThread;

  // Merge optimistic messages for display
  const messages = mergeOptimisticMessages(
    rawMessages,
    optimisticUserMessage,
    optimisticMessage,
    () => setOptimisticUserMessage(null),
    () => setOptimisticMessage(null)
  );

  const messageGroups = groupMessagesByRun(messages, threadRuns);

  const { sseClientRef } = useChatSSE({
    activeThreadRef,
    setStreamingContent,
    setIsStreaming,
    setStreamEvents,
    setCurrentRunId,
    setPendingApproval,
    setOptimisticMessage,
  });

  // Auto-select first thread on load
  const { data: threadsRes } = useQuery({
    queryKey: ["threads"],
    queryFn: () => apiRequest<Thread[]>("/api/v1/threads"),
  });
  const threads = threadsRes?.data || [];

  useEffect(() => {
    if (threads.length && !activeThread) {
      setActiveThread(threads[0].id);
    }
  }, [threads, activeThread]);

  // Detect active (non-terminal) run on the current thread
  const activeRun = threadRuns.find(
    (r) => r.status === "running" || r.status === "awaiting_approval"
  );

  // Mutation to manually complete a run
  const completeRunMutation = useMutation({
    mutationFn: (runId: string) =>
      apiRequest(`/api/v1/runs/${runId}/complete`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  // Approval invalidation helper
  const handleApprovalInvalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["approvals"] });
    queryClient.invalidateQueries({
      queryKey: ["messages", activeThreadRef.current],
    });
    queryClient.invalidateQueries({ queryKey: ["runs"] });
  };

  return (
    <ResizablePanelGroup direction="horizontal" className="h-[calc(100vh-3rem)]">
      <ResizablePanel defaultSize={22} minSize={12} maxSize={40}>
        <ThreadSidebar
          activeThread={activeThread}
          onSelectThread={setActiveThread}
          onThreadDeleted={() => setActiveThread(null)}
        />
      </ResizablePanel>

      <ResizableHandle withHandle />

      <ResizablePanel defaultSize={78} minSize={40}>
      <div className="flex-1 flex flex-col min-w-0 h-full">
        <ChatMessages
          messageGroups={messageGroups}
          isStreaming={isStreaming}
          streamEvents={streamEvents}
          streamingContent={streamingContent}
          currentRunId={currentRunId}
          pendingApprovalSlot={
            pendingApproval ? (
              <ApprovalCard
                pendingApproval={pendingApproval}
                activeThreadRef={activeThreadRef}
                onApproved={(msg) => {
                  setPendingApproval(null);
                  setOptimisticMessage(msg);
                }}
                onDenied={() => {
                  setPendingApproval(null);
                  setIsStreaming(false);
                }}
                onSetStreaming={setIsStreaming}
                onAddStreamEvent={(event) =>
                  setStreamEvents((prev) => [...prev, event as SSEEvent])
                }
                onInvalidateQueries={handleApprovalInvalidate}
              />
            ) : null
          }
        />

        {/* Complete Task button — shown when there's an active run and not streaming */}
        {activeRun && !isStreaming && (
          <div className="flex justify-center px-4 py-1.5">
            <Button
              variant="outline"
              size="sm"
              className="text-xs gap-1.5 text-muted-foreground hover:text-foreground"
              disabled={completeRunMutation.isPending}
              onClick={() => completeRunMutation.mutate(activeRun.id)}
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              {completeRunMutation.isPending ? "Completing…" : "Complete Task"}
            </Button>
          </div>
        )}

        <ChatComposer
          activeThread={activeThread}
          isStreaming={isStreaming}
          settings={settings}
          sseClientRef={sseClientRef}
          onThreadCreated={(id) => {
            setActiveThread(id);
          }}
          onSendStart={() => {
            setStreamingContent("");
            setStreamEvents([]);
            setIsStreaming(true);
            setOptimisticMessage(null);
          }}
          onSendError={() => setIsStreaming(false)}
          onOptimisticUserMessage={(content) => {
            setOptimisticUserMessage({
              id: `optimistic-user-${Date.now()}`,
              thread_id: activeThread || "",
              role: "user",
              content,
              created_at: new Date().toISOString(),
            });
          }}
        />
      </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}

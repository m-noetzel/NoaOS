import { useRef, useCallback, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { SSEClient } from "@/api/sse";
import { useToast } from "@/hooks/use-toast";
import type { SSEEvent, SSEEventType } from "@/api/types";
import type { Message } from "@/api/types";

export interface PendingApproval {
  tool: string;
  function: string;
  args: Record<string, unknown>;
  risk_tier: string;
  approval_id?: string;
}

export interface UseChatSSEOptions {
  activeThreadRef: React.MutableRefObject<string | null>;
  setStreamingContent: React.Dispatch<React.SetStateAction<string>>;
  setIsStreaming: React.Dispatch<React.SetStateAction<boolean>>;
  setStreamEvents: React.Dispatch<React.SetStateAction<SSEEvent[]>>;
  setCurrentRunId: React.Dispatch<React.SetStateAction<string | null>>;
  setPendingApproval: React.Dispatch<React.SetStateAction<PendingApproval | null>>;
  setOptimisticMessage: (msg: Message | null) => void;
}

export function useChatSSE({
  activeThreadRef,
  setStreamingContent,
  setIsStreaming,
  setStreamEvents,
  setCurrentRunId,
  setPendingApproval,
  setOptimisticMessage,
}: UseChatSSEOptions) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const handleSSEEvent = useCallback(
    (event: SSEEvent) => {
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
          queryClient.invalidateQueries({
            queryKey: ["messages", activeThreadRef.current],
          });
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
            description:
              (event.data.error as string) || "An unexpected error occurred",
            variant: "destructive",
          });
          break;
      }
    },
    [
      queryClient,
      activeThreadRef,
      setStreamingContent,
      setIsStreaming,
      setStreamEvents,
      setCurrentRunId,
      setPendingApproval,
      setOptimisticMessage,
      toast,
    ]
  );

  // Create SSEClient eagerly so event handler is wired at mount time
  const sseClientRef = useRef<SSEClient | null>(null);
  if (!sseClientRef.current) {
    sseClientRef.current = new SSEClient({
      onEvent: (event) => handleSSEEvent(event),
      onError: (err) => {
        setIsStreaming(false);
        toast({
          title: "Connection failed",
          description:
            err?.message || "Could not reach the backend. Is Noa running?",
          variant: "destructive",
        });
      },
      onClose: () => setIsStreaming(false),
    });
  }

  // CRITICAL: Disconnect SSE client when component unmounts
  useEffect(() => {
    return () => {
      sseClientRef.current?.disconnect();
    };
  }, []);

  return { sseClientRef, handleSSEEvent };
}

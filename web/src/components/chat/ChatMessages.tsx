import { useRef, useEffect, useState } from "react";
import type { Message, Run, SSEEvent } from "@/api/types";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ActivityStream } from "@/components/chat/ActivityStream";
import { Sparkles, User, ThumbsUp, ThumbsDown } from "lucide-react";
import { apiRequest } from "@/api/client";

/** Thumbs up/down rating buttons for an assistant message. */
function RatingButtons({ runId }: { runId: string | undefined }) {
  const [selected, setSelected] = useState<1 | -1 | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!runId) return null;

  const handleRate = async (rating: 1 | -1) => {
    if (submitting || selected === rating) return;
    setSubmitting(true);
    try {
      await apiRequest("/api/v1/ratings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: runId, rating }),
      });
      setSelected(rating);
    } catch {
      // Silently ignore rating failures — non-critical
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex gap-1 mt-1.5" data-testid={`rating-buttons-${runId}`}>
      <button
        type="button"
        aria-label="Thumbs up"
        disabled={submitting}
        onClick={() => void handleRate(1)}
        className={`p-1 rounded transition-colors ${
          selected === 1
            ? "text-green-500"
            : "text-muted-foreground/40 hover:text-muted-foreground"
        }`}
        data-testid={`rating-up-${runId}`}
      >
        <ThumbsUp className={`h-3 w-3 ${selected === 1 ? "fill-green-500" : ""}`} />
      </button>
      <button
        type="button"
        aria-label="Thumbs down"
        disabled={submitting}
        onClick={() => void handleRate(-1)}
        className={`p-1 rounded transition-colors ${
          selected === -1
            ? "text-red-500"
            : "text-muted-foreground/40 hover:text-muted-foreground"
        }`}
        data-testid={`rating-down-${runId}`}
      >
        <ThumbsDown className={`h-3 w-3 ${selected === -1 ? "fill-red-500" : ""}`} />
      </button>
    </div>
  );
}

/** Group messages by their run_id so we can show activity streams between exchanges */
export interface MessageGroup {
  runId?: string;
  userMessage?: Message;
  assistantMessage?: Message;
  run?: Run;
}

export function groupMessagesByRun(
  messages: Message[],
  runs: Run[]
): MessageGroup[] {
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

interface ChatMessagesProps {
  messageGroups: MessageGroup[];
  isStreaming: boolean;
  streamEvents: SSEEvent[];
  streamingContent: string;
  currentRunId: string | null;
  pendingApprovalSlot?: React.ReactNode;
  askUserSlot?: React.ReactNode;
}

export function ChatMessages({
  messageGroups,
  isStreaming,
  streamEvents,
  streamingContent,
  currentRunId,
  pendingApprovalSlot,
  askUserSlot,
}: ChatMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messagesEndRef.current?.scrollIntoView) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messageGroups, streamingContent, streamEvents]);

  return (
    <ScrollArea className="flex-1 p-4">
      <div
        className="max-w-2xl mx-auto space-y-3 py-4"
        data-testid="message-list"
      >
        {messageGroups.map((group, gi) => (
          <div key={gi} className="space-y-2">
            {/* User message */}
            {group.userMessage && (
              <div className="flex gap-3 flex-row-reverse animate-fade-in">
                <div className="flex-shrink-0 h-7 w-7 rounded-lg bg-primary/10 text-primary flex items-center justify-center mt-0.5">
                  <User className="h-3.5 w-3.5" />
                </div>
                <div className="rounded-2xl px-4 py-3 max-w-[80%] bg-primary text-primary-foreground rounded-tr-md shadow-md">
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {group.userMessage.content}
                  </p>
                  <p className="text-[10px] mt-1.5 text-primary-foreground/60">
                    {new Date(group.userMessage.created_at).toLocaleTimeString(
                      [],
                      { hour: "2-digit", minute: "2-digit" }
                    )}
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
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {group.assistantMessage.content}
                  </p>
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] mt-1.5 text-muted-foreground">
                      {new Date(
                        group.assistantMessage.created_at
                      ).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                    <RatingButtons runId={group.runId ?? group.assistantMessage.run_id} />
                  </div>
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

        {/* Approval request card — rendered from parent via slot */}
        {pendingApprovalSlot}

        {/* Ask-user card — rendered from parent via slot (OV8) */}
        {askUserSlot}

        {/* Streaming content */}
        {streamingContent && (
          <div
            className="flex gap-3 animate-fade-in"
            data-testid="streaming-content"
          >
            <div className="flex-shrink-0 h-7 w-7 rounded-lg gradient-primary text-primary-foreground flex items-center justify-center mt-0.5 shadow-sm animate-glow-pulse">
              <Sparkles className="h-3.5 w-3.5" />
            </div>
            <div className="rounded-2xl rounded-tl-md px-4 py-3 glass-strong max-w-[80%]">
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {streamingContent}
              </p>
              <span className="inline-block w-0.5 h-4 bg-primary animate-pulse-subtle rounded-full ml-0.5" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  );
}

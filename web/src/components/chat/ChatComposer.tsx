import { useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { ChatRequest, Provider, PrivacyMode, UserSettings } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { Send, Settings2, Mic, MicOff, Square } from "lucide-react";
import type { SSEClient } from "@/api/sse";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";

/** Derive a thread title from the first message content */
function deriveThreadTitle(message: string): string {
  const trimmed = message.trim();
  if (!trimmed) return "New Thread";
  if (trimmed.length <= 50) return trimmed;
  return trimmed.slice(0, 50) + "...";
}

interface ChatComposerProps {
  activeThread: string | null;
  isStreaming: boolean;
  settings: UserSettings | undefined;
  sseClientRef: React.MutableRefObject<SSEClient | null>;
  onThreadCreated: (threadId: string) => void;
  onSendStart: () => void;
  onSendError: () => void;
  onOptimisticUserMessage: (content: string) => void;
}

export function ChatComposer({
  activeThread,
  isStreaming,
  settings,
  sseClientRef,
  onThreadCreated,
  onSendStart,
  onSendError,
  onOptimisticUserMessage,
}: ChatComposerProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [input, setInput] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // VX1: Voice recording — insert transcription into text input
  const handleTranscription = useCallback((text: string) => {
    setInput((prev) => {
      const trimmed = prev.trimEnd();
      return trimmed ? `${trimmed} ${text}` : text;
    });
    toast({
      title: "Voice transcribed",
      description: "Transcription inserted into message.",
    });
  }, [toast]);

  const { state: recordingState, elapsedSeconds, errorMessage: recordingError, startRecording, stopRecording, cancelRecording } = useVoiceRecorder(handleTranscription);

  const isRecording = recordingState === "recording";
  const isProcessing = recordingState === "processing";
  const isRequesting = recordingState === "requesting";
  const hasRecordingError = recordingState === "error";
  const [temperature, setTemperature] = useState<number | null>(null);
  const [maxTokens, setMaxTokens] = useState<number | null>(null);
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);

  const model = settings?.default_model || "gpt-4.1";
  const provider = (settings?.default_provider || "openai") as Provider;
  const privacyMode = (settings?.default_privacy_mode || "external") as PrivacyMode;
  const effectiveTemperature = temperature ?? settings?.temperature ?? 0.7;
  const effectiveMaxTokens = maxTokens ?? settings?.max_tokens ?? 4096;
  const effectiveSystemPrompt = systemPrompt ?? settings?.system_prompt ?? "";

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
      apiRequest<{ id: string; title: string }>("/api/v1/threads", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      if (res.data) {
        onThreadCreated(res.data.id);
      }
    },
  });

  const handleSend = async () => {
    // UX-H2: Only block during active streaming
    if (isStreaming) return;
    if (!input.trim()) {
      toast({
        title: "Type a message",
        description: "Enter a message before sending.",
        variant: "destructive",
      });
      return;
    }

    const message = input.trim();
    setInput("");
    onSendStart();
    onOptimisticUserMessage(message);

    // UI-M5: Create a new thread and await its ID before connecting SSE
    let threadId = activeThread;
    if (!threadId) {
      try {
        const title = deriveThreadTitle(message);
        const res = await createThreadMutation.mutateAsync(title);
        threadId = res.data?.id ?? null;
        if (!threadId) {
          onSendError();
          toast({
            title: "Failed to create thread",
            description: "Server returned no thread ID",
            variant: "destructive",
          });
          return;
        }
      } catch (err) {
        onSendError();
        toast({
          title: "Failed to create thread",
          description:
            err instanceof Error ? err.message : "Unknown error",
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
      ...(effectiveSystemPrompt.trim()
        ? { system_prompt: effectiveSystemPrompt.trim() }
        : {}),
    };

    await sseClientRef.current!.connect("/api/v1/chat", body);
  };

  return (
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
                    onValueCommit={([v]) =>
                      saveChatDefaultsMutation.mutate({ temperature: v })
                    }
                    min={0}
                    max={2}
                    step={0.1}
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                    Max tokens: {effectiveMaxTokens}
                  </Label>
                  <Slider
                    value={[effectiveMaxTokens]}
                    onValueChange={([v]) => setMaxTokens(v)}
                    onValueCommit={([v]) =>
                      saveChatDefaultsMutation.mutate({ max_tokens: v })
                    }
                    min={256}
                    max={16384}
                    step={256}
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
                  placeholder="Override system prompt for this message (leave empty to use default from Settings)"
                  className="min-h-[60px] text-sm bg-background/50 border-border/40 resize-y"
                  rows={2}
                />
              </div>
            </div>
          </CollapsibleContent>

          {/* VX1: Recording error banner */}
          {hasRecordingError && recordingError && (
            <div className="mb-2 px-3 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2" data-testid="voice-error-banner">
              <MicOff className="h-3 w-3 shrink-0" />
              <span>{recordingError}</span>
              <button
                type="button"
                onClick={cancelRecording}
                className="ml-auto text-destructive/70 hover:text-destructive"
                aria-label="Dismiss error"
              >
                ✕
              </button>
            </div>
          )}

          {/* VX1: Recording indicator bar */}
          {(isRecording || isProcessing || isRequesting) && (
            <div className="mb-2 px-3 py-2 rounded-lg bg-muted/40 border border-border/30 flex items-center gap-2 text-xs" data-testid="voice-recording-bar">
              {isRequesting && (
                <>
                  <span className="h-2 w-2 rounded-full bg-muted-foreground animate-pulse" />
                  <span className="text-muted-foreground">Requesting microphone access…</span>
                </>
              )}
              {isRecording && (
                <>
                  <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" data-testid="voice-recording-dot" />
                  <span className="text-foreground font-medium">Recording</span>
                  <span className="text-muted-foreground tabular-nums" data-testid="voice-elapsed">
                    {String(Math.floor(elapsedSeconds / 60)).padStart(2, "0")}:
                    {String(elapsedSeconds % 60).padStart(2, "0")}
                  </span>
                  <button
                    type="button"
                    onClick={cancelRecording}
                    className="ml-auto text-muted-foreground hover:text-foreground text-xs"
                    aria-label="Cancel recording"
                    data-testid="voice-cancel"
                  >
                    Cancel
                  </button>
                </>
              )}
              {isProcessing && (
                <>
                  <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                  <span className="text-muted-foreground">Transcribing…</span>
                </>
              )}
            </div>
          )}

          <div className="flex gap-2 items-end">
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Advanced settings"
                className={cn(
                  "h-10 w-10 shrink-0 rounded-xl transition-all duration-200",
                  advancedOpen
                    ? "bg-accent text-primary"
                    : "hover:bg-accent/60"
                )}
              >
                <Settings2 className="h-4 w-4" />
              </Button>
            </CollapsibleTrigger>
            <div className="flex-1 relative">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" && !e.shiftKey && handleSend()
                }
                placeholder={isRecording ? "Recording… click stop when done" : "Message Noa…"}
                className="h-10 pr-12 rounded-xl bg-muted/40 border-border/40 focus:border-primary/40 focus:glow-sm transition-all placeholder:text-muted-foreground/50"
                disabled={isStreaming || isRecording || isProcessing}
                data-testid="chat-input"
              />
            </div>

            {/* VX1: Microphone button — toggles recording */}
            {isRecording ? (
              <Button
                onClick={stopRecording}
                variant="ghost"
                size="icon"
                aria-label="Stop recording"
                className="h-10 w-10 shrink-0 rounded-xl bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-all duration-200"
                data-testid="voice-stop"
              >
                <Square className="h-4 w-4 fill-red-500" />
              </Button>
            ) : (
              <Button
                onClick={() => void startRecording()}
                variant="ghost"
                size="icon"
                aria-label="Record voice message"
                disabled={isStreaming || isProcessing || isRequesting}
                className={cn(
                  "h-10 w-10 shrink-0 rounded-xl transition-all duration-200",
                  hasRecordingError
                    ? "text-destructive hover:bg-destructive/10"
                    : "hover:bg-accent/60 text-muted-foreground hover:text-foreground"
                )}
                data-testid="voice-mic"
              >
                <Mic className="h-4 w-4" />
              </Button>
            )}

            {/* UX-H2: Send is enabled at all times (only disabled during streaming) */}
            <Button
              onClick={handleSend}
              disabled={isStreaming || isRecording || isProcessing}
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
  );
}

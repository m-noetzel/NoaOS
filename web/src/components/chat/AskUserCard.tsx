/**
 * AskUserCard — renders an inline card when the agent asks the user a question.
 *
 * OV8: When the backend emits an ``ask_user`` SSE event, the agent has paused
 * the graph via LangGraph's interrupt() mechanism. This card collects the
 * user's response and POSTs it to the resume endpoint.
 *
 * The card shows:
 * - The question text
 * - Optional choice buttons (up to 3)
 * - Optional freetext input field
 */
import { useState } from "react";
import { apiRequest } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

export interface PendingAskUser {
  run_id: string;
  question: string;
  options: string[];
  allow_freetext: boolean;
}

interface AskUserCardProps {
  pendingAskUser: PendingAskUser;
  onResponded: () => void;
}

export function AskUserCard({ pendingAskUser, onResponded }: AskUserCardProps) {
  const { toast } = useToast();
  const [freetext, setFreetext] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (response: string) => {
    if (isSubmitting || !response.trim()) return;
    setIsSubmitting(true);
    try {
      await apiRequest(`/api/v1/runs/${pendingAskUser.run_id}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response }),
      });
      onResponded();
    } catch (err) {
      toast({
        title: "Could not send response",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
      setIsSubmitting(false);
    }
  };

  const handleOptionClick = (option: string) => {
    void submit(option);
  };

  const handleFreetextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void submit(freetext);
  };

  return (
    <div
      className="animate-fade-in mx-auto max-w-md"
      data-testid="ask-user-card"
    >
      <div className="rounded-xl border-2 border-primary/30 bg-primary/5 p-4 space-y-3">
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="text-primary text-lg">&#x3F;</span>
          <span className="font-semibold text-sm">Input needed</span>
        </div>

        {/* Question */}
        <p className="text-sm text-foreground leading-relaxed">
          {pendingAskUser.question}
        </p>

        {/* Option buttons */}
        {pendingAskUser.options.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {pendingAskUser.options.map((option) => (
              <Button
                key={option}
                size="sm"
                variant="outline"
                className="border-primary/40 text-primary hover:bg-primary/10"
                disabled={isSubmitting}
                onClick={() => handleOptionClick(option)}
                data-testid={`ask-user-option-${option}`}
              >
                {option}
              </Button>
            ))}
          </div>
        )}

        {/* Freetext input */}
        {pendingAskUser.allow_freetext && (
          <form onSubmit={handleFreetextSubmit} className="flex gap-2 pt-1">
            <input
              type="text"
              className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              placeholder="Type your answer…"
              value={freetext}
              onChange={(e) => setFreetext(e.target.value)}
              disabled={isSubmitting}
              data-testid="ask-user-freetext"
            />
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting || !freetext.trim()}
              data-testid="ask-user-submit"
            >
              {isSubmitting ? "Sending…" : "Send"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}

/**
 * PrivacySettings — PC1 user-configurable private keywords.
 *
 * Lets the user add custom keywords that trigger private domain routing.
 * The built-in keywords (journal, diary, private, etc.) are always active;
 * these are additions, not replacements.
 */

import { useState, useEffect, KeyboardEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { UserSettings } from "@/api/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";

// Built-in keywords shown read-only so users understand the baseline.
const BUILTIN_KEYWORDS = [
  "journal",
  "diary",
  "private",
  "personal",
  "my notes",
  "my files",
  "secret",
  "password",
  "confidential",
];

interface PrivacySettingsProps {
  settings?: UserSettings;
}

export function PrivacySettings({ settings }: PrivacySettingsProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [customKeywords, setCustomKeywords] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (settings && !initialized) {
      setCustomKeywords(settings.private_keywords ?? []);
      setInitialized(true);
    }
  }, [settings, initialized]);

  const saveMutation = useMutation({
    mutationFn: (keywords: string[]) =>
      apiRequest("/api/v1/settings", {
        method: "PATCH",
        body: JSON.stringify({ private_keywords: keywords }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast({ title: "Privacy keywords saved" });
    },
    onError: (err: Error) => {
      toast({
        title: "Failed to save keywords",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  function addKeyword() {
    const kw = inputValue.trim().toLowerCase();
    if (!kw) return;
    if (customKeywords.includes(kw) || BUILTIN_KEYWORDS.includes(kw)) {
      toast({ title: "Keyword already exists", variant: "destructive" });
      return;
    }
    const next = [...customKeywords, kw];
    setCustomKeywords(next);
    setInputValue("");
    saveMutation.mutate(next);
  }

  function removeKeyword(kw: string) {
    const next = customKeywords.filter((k) => k !== kw);
    setCustomKeywords(next);
    saveMutation.mutate(next);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addKeyword();
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Privacy Keywords</CardTitle>
        <CardDescription>
          Messages containing these words are routed to the private domain.
          Built-in keywords are always active; add your own below.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-xs text-muted-foreground mb-2">Built-in (read-only)</p>
          <div className="flex flex-wrap gap-1.5">
            {BUILTIN_KEYWORDS.map((kw) => (
              <Badge key={kw} variant="secondary" className="text-xs">
                {kw}
              </Badge>
            ))}
          </div>
        </div>

        {customKeywords.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Custom</p>
            <div className="flex flex-wrap gap-1.5">
              {customKeywords.map((kw) => (
                <Badge
                  key={kw}
                  variant="outline"
                  className="text-xs gap-1 pr-1"
                >
                  {kw}
                  <button
                    aria-label={`Remove keyword ${kw}`}
                    onClick={() => removeKeyword(kw)}
                    className="ml-0.5 rounded-sm opacity-70 hover:opacity-100"
                  >
                    &times;
                  </button>
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add keyword and press Enter"
            className="text-sm"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={addKeyword}
            disabled={!inputValue.trim() || saveMutation.isPending}
          >
            Add
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Press Enter or click Add. Keywords are case-insensitive.
        </p>
      </CardContent>
    </Card>
  );
}

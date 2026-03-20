/**
 * IntelligenceSettings — MC1 per-node model configuration.
 *
 * Lets the user choose which model runs for each orchestrator node:
 * Classifier, Planner (future), Agent, Evaluator (future).
 * Saves to `node_models` in user settings.
 */

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { NodeModelsConfig, UserSettings } from "@/api/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

// All models available for node selection (flat list across providers)
const ALL_NODE_MODELS: { value: string; label: string; provider: string }[] = [
  // Anthropic
  {
    value: "anthropic/claude-sonnet-4-20250514",
    label: "Claude Sonnet 4 (Anthropic)",
    provider: "anthropic",
  },
  {
    value: "anthropic/claude-opus-4-6",
    label: "Claude Opus 4.6 (Anthropic)",
    provider: "anthropic",
  },
  // OpenAI
  {
    value: "openai/gpt-4.1",
    label: "GPT-4.1 (OpenAI)",
    provider: "openai",
  },
  {
    value: "openai/gpt-4.1-mini",
    label: "GPT-4.1 Mini (OpenAI)",
    provider: "openai",
  },
  {
    value: "openai/gpt-4o",
    label: "GPT-4o (OpenAI)",
    provider: "openai",
  },
  {
    value: "openai/gpt-4o-mini",
    label: "GPT-4o Mini (OpenAI)",
    provider: "openai",
  },
  // Google
  {
    value: "google_ai/gemini-2.0-flash",
    label: "Gemini 2.0 Flash (Google)",
    provider: "google_ai",
  },
  // Ollama (local)
  {
    value: "ollama/llama-3.1-70b",
    label: "Llama 3.1 70B (Local)",
    provider: "ollama",
  },
];

// Defaults shown before user customises anything
const NODE_DEFAULTS: NodeModelsConfig = {
  classifier: "openai/gpt-4o-mini",
  agent: "openai/gpt-4.1",
};

interface NodeSelectorProps {
  label: string;
  description: string;
  value: string;
  onChange: (v: string) => void;
  "data-testid"?: string;
}

function NodeModelSelector({
  label,
  description,
  value,
  onChange,
  "data-testid": testId,
}: NodeSelectorProps) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger data-testid={testId}>
          <SelectValue placeholder="Select model" />
        </SelectTrigger>
        <SelectContent>
          {ALL_NODE_MODELS.map((m) => (
            <SelectItem key={m.value} value={m.value}>
              {m.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

interface IntelligenceSettingsProps {
  settings: UserSettings | undefined;
}

export function IntelligenceSettings({ settings }: IntelligenceSettingsProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [classifier, setClassifier] = useState(
    NODE_DEFAULTS.classifier ?? "openai/gpt-4o-mini"
  );
  const [agent, setAgent] = useState(NODE_DEFAULTS.agent ?? "openai/gpt-4.1");
  const [isDirty, setIsDirty] = useState(false);

  // Initialise from loaded settings
  useEffect(() => {
    if (settings?.node_models) {
      const nm = settings.node_models;
      if (nm.classifier) setClassifier(nm.classifier);
      if (nm.agent) setAgent(nm.agent);
    }
    setIsDirty(false);
  }, [settings]);

  const markDirty = () => setIsDirty(true);

  const saveMutation = useMutation({
    mutationFn: () => {
      const node_models: NodeModelsConfig = {
        classifier,
        agent,
      };
      return apiRequest<UserSettings>("/api/v1/settings", {
        method: "PATCH",
        body: JSON.stringify({ node_models }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setIsDirty(false);
      toast({ title: "Intelligence settings saved" });
    },
    onError: (err: Error) => {
      toast({
        title: "Failed to save intelligence settings",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Intelligence</CardTitle>
        <CardDescription>
          Choose which model runs for each orchestrator node. The agent node
          uses the selected model for all tool calls and responses.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <NodeModelSelector
          label="Classifier Model"
          description="Cheap model used to classify task type before execution."
          value={classifier}
          onChange={(v) => {
            setClassifier(v);
            markDirty();
          }}
          data-testid="node-model-classifier"
        />
        <NodeModelSelector
          label="Agent Model"
          description="Primary model for tool calls and responses."
          value={agent}
          onChange={(v) => {
            setAgent(v);
            markDirty();
          }}
          data-testid="node-model-agent"
        />
        <p className="text-xs text-muted-foreground">
          Note: In private mode, the agent model is always overridden to use
          the local Ollama model.
        </p>
        <Button
          size="sm"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || !isDirty}
          data-testid="intelligence-settings-save"
        >
          {saveMutation.isPending
            ? "Saving…"
            : isDirty
              ? "Save Intelligence Settings *"
              : "Save Intelligence Settings"}
        </Button>
      </CardContent>
    </Card>
  );
}

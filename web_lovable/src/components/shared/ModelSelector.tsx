import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";

const models = [
  { value: "claude-3.5-sonnet", label: "Claude 3.5 Sonnet", provider: "anthropic" },
  { value: "gpt-4o", label: "GPT-4o", provider: "openai" },
  { value: "llama-3.1-70b", label: "Llama 3.1 70B", provider: "ollama" },
];

export function ModelSelector() {
  const [model, setModel] = useState("claude-3.5-sonnet");

  return (
    <Select value={model} onValueChange={setModel}>
      <SelectTrigger className="h-8 w-[160px] text-xs rounded-lg bg-muted/40 border-border/40 hover:bg-accent/60 transition-colors">
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="glass-strong rounded-xl">
        {models.map((m) => (
          <SelectItem key={m.value} value={m.value} className="text-xs rounded-lg">
            <span>{m.label}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

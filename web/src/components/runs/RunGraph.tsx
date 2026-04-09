import { useState } from "react";
import type { RunEvent } from "@/api/types";
import { cn, asString, asRecord, asStringArray } from "@/lib/utils";
import {
  MessageSquare, Brain, Wrench, CheckCircle2, AlertCircle, Timer,
  ArrowDownRight, Zap, ChevronRight, X, Flame, Tag, Bot, BarChart2,
} from "lucide-react";
import { NodeReplayActions } from "@/components/runs/ReplayActions";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface GraphNode {
  id: string;
  label: string;
  type: "message" | "classifier" | "planner" | "agent" | "evaluator" | "tool" | "result" | "error";
  event: RunEvent;
  resultEvent?: RunEvent;
  children: GraphNode[];
  parallel?: boolean;
  groupLabel?: string;
  isCriticalPath?: boolean;
}

/* ------------------------------------------------------------------ */
/* Cost estimator                                                       */
/* ------------------------------------------------------------------ */

function estimateCost(tokensIn: number, tokensOut: number): number {
  return (tokensIn * 3 + tokensOut * 15) / 1_000_000;
}

/* ------------------------------------------------------------------ */
/* Graph builder                                                       */
/* ------------------------------------------------------------------ */

function getNodeDuration(node: GraphNode): number {
  if (node.type === "tool" && node.resultEvent?.data.duration_ms) {
    return node.resultEvent.data.duration_ms as number;
  }
  return (node.event.data.duration_ms as number) || 0;
}

function buildGraph(events: RunEvent[]): GraphNode | null {
  if (events.length === 0) return null;

  const messageEvent = events.find((e) => e.type === "message_received");
  const classificationEvent = events.find((e) => e.type === "classification_done");
  const plannerEvents = events.filter((e) => e.type === "planner_step");
  // step_started events for named graph nodes (classifier, planner, agent, evaluator)
  const stepEvents = events.filter((e) => e.type === "step_started");
  const toolCalledEvents = events.filter((e) => e.type === "tool_called");
  const toolResultEvents = events.filter((e) => e.type === "tool_result");
  const resultEvent = events.find((e) => e.type === "result_ready");
  const errorEvent = events.find((e) => e.type === "error");

  const toolNodes: GraphNode[] = toolCalledEvents.map((tc) => {
    const tcInner = asRecord(tc.data.tool_call);
    const toolName = asString(tcInner.name) || asString(tc.data.tool_name) || "tool";
    const matchingResult = toolResultEvents.find((tr) => {
      const trInner = asRecord(tr.data.tool_result);
      const trName = asString(trInner.name) || asString(tr.data.tool_name);
      return trName === toolName;
    });
    return {
      id: tc.id,
      label: toolName,
      type: "tool" as const,
      event: tc,
      resultEvent: matchingResult,
      children: [],
      parallel: !!(tc.data.parallel_group),
    };
  });

  // Group parallel tools
  const parallelGroups = new Map<string, GraphNode[]>();
  const sequentialTools: GraphNode[] = [];
  for (const tn of toolNodes) {
    const group = typeof tn.event.data.parallel_group === "string" ? tn.event.data.parallel_group : undefined;
    if (group) {
      if (!parallelGroups.has(group)) parallelGroups.set(group, []);
      parallelGroups.get(group)!.push(tn);
    } else {
      sequentialTools.push(tn);
    }
  }

  // Mark critical path within parallel groups
  for (const [groupName, nodes] of parallelGroups) {
    let maxDuration = 0;
    let criticalNode: GraphNode | null = null;
    for (const n of nodes) {
      n.parallel = true;
      n.groupLabel = groupName.charAt(0).toUpperCase() + groupName.slice(1);
      const dur = getNodeDuration(n);
      if (dur > maxDuration) {
        maxDuration = dur;
        criticalNode = n;
      }
    }
    if (criticalNode) criticalNode.isCriticalPath = true;
  }

  const plannerChildren: GraphNode[] = [];
  for (const [, nodes] of parallelGroups) {
    plannerChildren.push(...nodes);
  }
  plannerChildren.push(...sequentialTools);

  // Determine planner event: prefer planner_step event, fall back to
  // step_started with step="planner", otherwise use first available event.
  const plannerStepEvent = plannerEvents[0];
  const plannerStepStarted = stepEvents.find((e) => asString(e.data.step) === "planner");
  const firstPlanner = plannerStepEvent || plannerStepStarted || events[0];
  const plannerNode: GraphNode = {
    id: "planner",
    label: "Planner",
    type: "planner",
    event: firstPlanner,
    children: plannerChildren,
  };

  // Evaluator node: present when result_ready carries eval_verdict/eval_scores,
  // or when a step_started with step="evaluator" exists.
  const evaluatorStepEvent = stepEvents.find((e) => asString(e.data.step) === "evaluator");
  const hasEvalData = resultEvent && (
    resultEvent.data.eval_verdict !== undefined ||
    resultEvent.data.eval_scores !== undefined
  );
  const evaluatorNode: GraphNode | null = (evaluatorStepEvent || hasEvalData) ? {
    id: "evaluator",
    label: "Evaluator",
    type: "evaluator",
    event: evaluatorStepEvent || resultEvent || events[0],
    resultEvent: hasEvalData ? resultEvent : undefined,
    children: [],
  } : null;

  const endNode: GraphNode | null = errorEvent
    ? { id: errorEvent.id, label: "Error", type: "error", event: errorEvent, children: [] }
    : resultEvent
    ? { id: resultEvent.id, label: "Final Response", type: "result", event: resultEvent, children: [] }
    : null;

  if (evaluatorNode) plannerNode.children.push(evaluatorNode);
  if (endNode) plannerNode.children.push(endNode);

  // Mark critical path for sequential nodes (longest duration)
  const allSequentialNodes = [...sequentialTools, endNode].filter(Boolean) as GraphNode[];
  if (allSequentialNodes.length > 0) {
    let maxDur = 0;
    let critNode: GraphNode | null = null;
    for (const n of allSequentialNodes) {
      const dur = getNodeDuration(n);
      if (dur > maxDur) {
        maxDur = dur;
        critNode = n;
      }
    }
    if (critNode) critNode.isCriticalPath = true;
  }

  // Classifier node: present when classification_done event exists or
  // when a step_started with step="classifier" exists.
  const classifierStepEvent = stepEvents.find((e) => asString(e.data.step) === "classifier");
  const classifierNode: GraphNode | null = (classificationEvent || classifierStepEvent) ? {
    id: "classifier",
    label: "Classifier",
    type: "classifier",
    // Merge classification_done data with any step event data for the panel
    event: classificationEvent || classifierStepEvent || events[0],
    children: [plannerNode],
  } : null;

  const root: GraphNode = {
    id: "root",
    label: messageEvent
      ? (asString(messageEvent.data.message) || asString(messageEvent.data.text) || "User Message").slice(0, 50) + ((asString(messageEvent.data.message) || "").length > 50 ? "..." : "")
      : "User Message",
    type: "message",
    event: messageEvent || events[0],
    children: classifierNode ? [classifierNode] : [plannerNode],
  };

  return root;
}

/* ------------------------------------------------------------------ */
/* Icons & colors                                                      */
/* ------------------------------------------------------------------ */

function NodeIcon({ type }: { type: GraphNode["type"] }) {
  const cls = "h-3.5 w-3.5";
  switch (type) {
    case "message": return <MessageSquare className={cls} />;
    case "classifier": return <Tag className={cls} />;
    case "planner": return <Brain className={cls} />;
    case "agent": return <Bot className={cls} />;
    case "evaluator": return <BarChart2 className={cls} />;
    case "tool": return <Wrench className={cls} />;
    case "result": return <CheckCircle2 className={cls} />;
    case "error": return <AlertCircle className={cls} />;
  }
}

const nodeColors: Record<GraphNode["type"], string> = {
  message: "bg-primary/15 text-primary border-primary/30",
  classifier: "bg-purple-500/15 text-purple-400 border-purple-500/30",
  planner: "bg-info/15 text-info border-info/30",
  agent: "bg-primary/15 text-primary border-primary/30",
  evaluator: "bg-teal-500/15 text-teal-400 border-teal-500/30",
  tool: "bg-warning/15 text-warning border-warning/30",
  result: "bg-success/15 text-success border-success/30",
  error: "bg-destructive/15 text-destructive border-destructive/30",
};

const nodeGlowColors: Record<GraphNode["type"], string> = {
  message: "ring-primary/40",
  classifier: "ring-purple-500/40",
  planner: "ring-info/40",
  agent: "ring-primary/40",
  evaluator: "ring-teal-500/40",
  tool: "ring-warning/40",
  result: "ring-success/40",
  error: "ring-destructive/40",
};

const nodeTypeLabels: Record<GraphNode["type"], string> = {
  message: "User Message",
  classifier: "Classifier",
  planner: "Planner",
  agent: "Agent",
  evaluator: "Evaluator",
  tool: "Tool Node",
  result: "Final Response",
  error: "Error",
};

/* ------------------------------------------------------------------ */
/* Duration badge                                                      */
/* ------------------------------------------------------------------ */

function DurationBadge({ ms }: { ms: number }) {
  const label = ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
  return (
    <span className="inline-flex items-center gap-0.5 rounded-full bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
      <Timer className="h-2.5 w-2.5" />
      {label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Inspection panel                                                    */
/* ------------------------------------------------------------------ */

function InspectionPanel({ node, runId, onClose }: { node: GraphNode; runId: string; onClose: () => void }) {
  const data = node.type === "tool" && node.resultEvent
    ? { ...node.event.data, ...node.resultEvent.data }
    : node.event.data;

  const tokensIn = typeof data.tokens_in === "number" ? data.tokens_in : undefined;
  const tokensOut = typeof data.tokens_out === "number" ? data.tokens_out : undefined;
  const durationMs = typeof data.duration_ms === "number" ? data.duration_ms : undefined;
  const selectedTools = Array.isArray(data.selected_tools) ? asStringArray(data.selected_tools) : undefined;
  const strategySummary = typeof data.strategy_summary === "string" ? data.strategy_summary : undefined;
  const strategy = typeof data.strategy === "string" ? data.strategy : undefined;
  const parallelGroupsData = Array.isArray(data.parallel_groups) ? data.parallel_groups as Array<{ group_id: string; tools: string[] }> : undefined;
  const totalTokens = (tokensIn || 0) + (tokensOut || 0);
  const cost = tokensIn !== undefined || tokensOut !== undefined
    ? estimateCost(tokensIn || 0, tokensOut || 0)
    : null;

  return (
    <div className="rounded-xl border border-border/40 bg-card/80 backdrop-blur-xl p-4 space-y-3 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={cn("p-1.5 rounded-lg border", nodeColors[node.type])}>
            <NodeIcon type={node.type} />
          </span>
          <div>
            <p className="text-sm font-semibold">{node.label}</p>
            <p className="text-[10px] text-muted-foreground">{nodeTypeLabels[node.type]}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {node.isCriticalPath && (
            <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 text-destructive border border-destructive/20 px-2 py-0.5 text-[10px] font-medium">
              <Flame className="h-2.5 w-2.5" /> Critical path
            </span>
          )}
          <button onClick={onClose} className="p-1 rounded-md hover:bg-muted/50 text-muted-foreground">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Token + cost */}
      {(tokensIn !== undefined || tokensOut !== undefined) && (
        <div className="rounded-lg bg-muted/30 p-3 space-y-1.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
            <Zap className="h-3 w-3" /> Token Usage & Cost
          </p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
            {tokensIn !== undefined && (
              <div>
                <p className="text-[10px] text-muted-foreground">Input</p>
                <p className="text-sm font-mono font-semibold">{tokensIn.toLocaleString()}</p>
              </div>
            )}
            {tokensOut !== undefined && (
              <div>
                <p className="text-[10px] text-muted-foreground">Output</p>
                <p className="text-sm font-mono font-semibold">{tokensOut.toLocaleString()}</p>
              </div>
            )}
            <div>
              <p className="text-[10px] text-muted-foreground">Total</p>
              <p className="text-sm font-mono font-semibold">{totalTokens.toLocaleString()}</p>
            </div>
            {cost !== null && (
              <div>
                <p className="text-[10px] text-muted-foreground">Est. Cost</p>
                <p className="text-sm font-mono font-semibold text-success">${cost.toFixed(4)}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Duration */}
      {durationMs !== undefined && (
        <div className="rounded-lg bg-muted/30 p-3 space-y-1">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
            <Timer className="h-3 w-3" /> Execution Time
          </p>
          <div className="flex items-baseline gap-3">
            <p className="text-sm font-mono font-semibold">
              {durationMs < 1000 ? `${durationMs}ms` : `${(durationMs / 1000).toFixed(1)}s`}
            </p>
            <p className="text-[10px] text-muted-foreground font-mono">
              {new Date(node.event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </p>
          </div>
        </div>
      )}

      {/* Classifier detail — task_type + privacy_mode */}
      {node.type === "classifier" && (() => {
        const taskType = typeof data.task_type === "string" ? data.task_type : undefined;
        const privacyMode = typeof data.privacy_mode === "string" ? data.privacy_mode : undefined;
        const model = typeof data.model === "string" ? data.model : undefined;
        const hasData = taskType || privacyMode;
        return hasData ? (
          <div className="rounded-lg bg-muted/30 p-3 space-y-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
              <Tag className="h-3 w-3" /> Classification Result
            </p>
            <div className="space-y-2">
              {taskType && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Task type:</p>
                  <span className="inline-flex items-center rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 px-2 py-0.5 text-[11px] font-mono mt-1">
                    {taskType}
                  </span>
                </div>
              )}
              {privacyMode && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Privacy mode:</p>
                  <span className="inline-flex items-center rounded-full bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 text-[11px] font-mono mt-1">
                    {privacyMode}
                  </span>
                </div>
              )}
              {model && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Model:</p>
                  <p className="text-xs font-mono text-foreground/80">{model}</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-muted/20 p-3 text-center">
            <p className="text-[11px] text-muted-foreground">No classification data available</p>
          </div>
        );
      })()}

      {/* Planner decision */}
      {node.type === "planner" && (() => {
        const planText = typeof data.plan === "string" ? data.plan : undefined;
        const archetype = typeof data.archetype === "string" ? data.archetype : undefined;
        const hasData = selectedTools || strategySummary || strategy || planText || archetype;
        return hasData ? (
          <div className="rounded-lg bg-muted/30 p-3 space-y-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Planner Decision</p>
            <div className="space-y-2">
              {archetype && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Archetype:</p>
                  <span className="inline-flex items-center rounded-full bg-info/10 text-info border border-info/20 px-2 py-0.5 text-[11px] font-mono mt-1">
                    {archetype}
                  </span>
                </div>
              )}
              {planText && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Plan:</p>
                  <pre className="text-xs text-foreground/80 mt-1 whitespace-pre-wrap font-sans leading-relaxed">{planText}</pre>
                </div>
              )}
              {strategySummary && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Strategy:</p>
                  <p className="text-xs text-foreground/80">{strategySummary}</p>
                </div>
              )}
              {!strategySummary && strategy && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Strategy:</p>
                  <p className="text-xs text-foreground/80">{strategy}</p>
                </div>
              )}
              {selectedTools && selectedTools.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Selected tools:</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {selectedTools.map((t) => (
                      <span key={t} className="inline-flex items-center gap-1 rounded-md bg-warning/10 text-warning border border-warning/20 px-2 py-0.5 text-[11px] font-mono">
                        <Wrench className="h-2.5 w-2.5" />{t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {parallelGroupsData && parallelGroupsData.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Parallel groups:</p>
                  <div className="space-y-1 mt-1">
                    {parallelGroupsData.map((g) => (
                      <div key={g.group_id} className="flex items-center gap-1.5 text-[11px]">
                        <span className="rounded-full bg-info/10 text-info border border-info/20 px-1.5 py-0 text-[9px] font-mono">
                          ∥ {g.group_id}
                        </span>
                        <span className="font-mono text-muted-foreground">{g.tools.join(", ")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-muted/20 p-3 text-center">
            <p className="text-[11px] text-muted-foreground">No planning data available</p>
          </div>
        );
      })()}

      {/* Evaluator detail — eval scores and verdict */}
      {node.type === "evaluator" && (() => {
        const evalData = node.resultEvent?.data ?? data;
        const evalVerdict = typeof evalData.eval_verdict === "string" ? evalData.eval_verdict : undefined;
        const evalScores = evalData.eval_scores && typeof evalData.eval_scores === "object" && !Array.isArray(evalData.eval_scores)
          ? evalData.eval_scores as Record<string, number>
          : undefined;
        const hasData = evalVerdict || evalScores;
        return hasData ? (
          <div className="rounded-lg bg-muted/30 p-3 space-y-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
              <BarChart2 className="h-3 w-3" /> Evaluation Result
            </p>
            <div className="space-y-2">
              {evalVerdict && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Verdict:</p>
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold mt-1 border ${
                    evalVerdict === "pass"
                      ? "bg-success/10 text-success border-success/20"
                      : "bg-destructive/10 text-destructive border-destructive/20"
                  }`}>
                    {evalVerdict}
                  </span>
                </div>
              )}
              {evalScores && Object.keys(evalScores).length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground mb-1.5">Scores:</p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                    {Object.entries(evalScores).map(([dim, score]) => (
                      <div key={dim}>
                        <p className="text-[10px] text-muted-foreground capitalize">{dim.replace(/_/g, " ")}</p>
                        <p className="text-sm font-mono font-semibold">{typeof score === "number" ? score.toFixed(2) : String(score)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-muted/20 p-3 text-center">
            <p className="text-[11px] text-muted-foreground">No evaluation data available</p>
          </div>
        );
      })()}

      {/* Tool parameters — args may be top-level or nested inside tool_call */}
      {node.type === "tool" && (() => {
        const args = node.event.data.args ?? asRecord(node.event.data.tool_call)?.args;
        return args && Object.keys(args as object).length > 0 ? (
          <div className="rounded-lg bg-muted/30 p-3 space-y-1.5">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Parameters</p>
            <pre className="text-[11px] font-mono text-foreground/80 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(args, null, 2)}
            </pre>
          </div>
        ) : null;
      })()}

      {/* Tool result — result may be top-level or nested inside tool_result */}
      {node.type === "tool" && node.resultEvent && (() => {
        const result = node.resultEvent.data.result ?? node.resultEvent.data.tool_result;
        return result ? (
          <div className="rounded-lg bg-muted/30 p-3 space-y-1.5">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Result</p>
            <pre className="text-[11px] font-mono text-foreground/80 overflow-x-auto whitespace-pre-wrap max-h-48">
              {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
            </pre>
          </div>
        ) : null;
      })()}

      {/* Generic metadata */}
      {(node.type === "message" || node.type === "result" || node.type === "error") && (
        <div className="rounded-lg bg-muted/30 p-3 space-y-1">
          {Object.entries(node.event.data)
            .filter(([k]) => !["tokens_in", "tokens_out", "duration_ms"].includes(k))
            .map(([key, value]) => (
            <div key={key} className="flex gap-2 text-xs">
              <span className="text-muted-foreground/60 shrink-0">{key}:</span>
              <span className="font-mono text-foreground/80 truncate">
                {typeof value === "object" ? JSON.stringify(value) : String(value)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Replay from node */}
      {node.type !== "message" && (
        <NodeReplayActions runId={runId} nodeId={node.id} nodeLabel={node.label} />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Graph Node View                                                     */
/* ------------------------------------------------------------------ */

function GraphNodeView({
  node,
  depth = 0,
  selectedId,
  onSelect,
}: {
  node: GraphNode;
  depth?: number;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const isSelected = selectedId === node.id;
  const durationMs = (node.type === "tool" && node.resultEvent?.data.duration_ms as number)
    || (node.event.data.duration_ms as number | undefined);

  const parallelChildren = node.children.filter((c) => c.parallel);
  const sequentialChildren = node.children.filter((c) => !c.parallel);

  const groupLabel = parallelChildren[0]?.groupLabel;

  return (
    <div className="space-y-0">
      <div className="flex items-start gap-0">
        {depth > 0 && (
          <div className="flex flex-col items-center w-6 shrink-0">
            <div className="w-px h-3 bg-border/40" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          {/* Node button */}
          <button
            onClick={() => onSelect(isSelected ? null : node.id)}
            className={cn(
              "flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition-all w-full text-left group",
              nodeColors[node.type],
              isSelected && `ring-2 ${nodeGlowColors[node.type]} shadow-lg`,
              node.isCriticalPath && "ring-1 ring-destructive/30"
            )}
          >
            <NodeIcon type={node.type} />
            <div className="flex flex-col flex-1 min-w-0">
              <span className="truncate">{node.label}</span>
              <span className="text-[9px] opacity-60">{nodeTypeLabels[node.type]}</span>
            </div>
            {node.isCriticalPath && (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-destructive/10 px-1 py-0.5 text-[9px] text-destructive">
                <Flame className="h-2 w-2" />
              </span>
            )}
            {durationMs !== undefined && <DurationBadge ms={durationMs} />}
            <ChevronRight className={cn(
              "h-3 w-3 text-current/50 transition-transform shrink-0",
              isSelected && "rotate-90"
            )} />
          </button>

          {/* Parallel children block */}
          {parallelChildren.length > 0 && (
            <div className="ml-3 mt-0">
              <div className="flex items-center gap-1.5 ml-6 mt-1.5 mb-0.5">
                <ArrowDownRight className="h-3 w-3 text-muted-foreground/40" />
                <span className="text-[10px] text-muted-foreground/50 font-mono">
                  {groupLabel ? `parallel · ${groupLabel}` : "parallel"}
                </span>
              </div>
              <div className="border-l-2 border-dashed border-warning/20 ml-3 pl-0">
                {parallelChildren.map((child) => (
                  <GraphNodeView key={child.id} node={child} depth={depth + 1} selectedId={selectedId} onSelect={onSelect} />
                ))}
              </div>
            </div>
          )}

          {/* Sequential children */}
          {sequentialChildren.length > 0 && (
            <div className="ml-3 mt-0">
              {sequentialChildren.map((child) => (
                <GraphNodeView key={child.id} node={child} depth={depth + 1} selectedId={selectedId} onSelect={onSelect} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main export                                                         */
/* ------------------------------------------------------------------ */

export function RunGraph({ events, runId, onSelectNode }: { events: RunEvent[]; runId?: string; onSelectNode?: (label: string | null) => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const root = buildGraph(events);

  if (!root) return <p className="text-sm text-muted-foreground p-4">No events to visualize.</p>;

  const findNode = (node: GraphNode, id: string): GraphNode | null => {
    if (node.id === id) return node;
    for (const c of node.children) {
      const found = findNode(c, id);
      if (found) return found;
    }
    return null;
  };

  const selectedNode = selectedId ? findNode(root, selectedId) : null;

  const handleSelect = (id: string | null) => {
    setSelectedId(id);
    if (onSelectNode) {
      const node = id ? findNode(root, id) : null;
      onSelectNode(node?.label || null);
    }
  };

  return (
    <div className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div>
        <GraphNodeView node={root} selectedId={selectedId} onSelect={handleSelect} />
      </div>
      {selectedNode && (
        <div className="lg:sticky lg:top-4 self-start">
          <InspectionPanel node={selectedNode} runId={runId || ""} onClose={() => handleSelect(null)} />
        </div>
      )}
    </div>
  );
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { AuditEntry, AuditEntriesResponse, AuditVerifyResponse } from "@/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Download, ChevronDown, ChevronRight } from "lucide-react";

const PAGE_LIMIT = 50;

type DomainFilter = "all" | "private" | "external";
type PrivacyFilter = "all" | "private" | "public";

function buildUrl(params: {
  offset: number;
  domain: DomainFilter;
  toolName: string;
  privacy: PrivacyFilter;
  since: string;
  until: string;
}): string {
  const p = new URLSearchParams();
  p.set("limit", String(PAGE_LIMIT));
  p.set("offset", String(params.offset));
  if (params.domain !== "all") p.set("domain", params.domain);
  if (params.toolName) p.set("tool_name", params.toolName);
  if (params.privacy !== "all") p.set("privacy_classification", params.privacy);
  if (params.since) p.set("since", new Date(params.since).toISOString());
  if (params.until) {
    const d = new Date(params.until);
    d.setHours(23, 59, 59, 999);
    p.set("until", d.toISOString());
  }
  return `/api/v1/audit/entries?${p.toString()}`;
}

function buildExportUrl(params: {
  domain: DomainFilter;
  toolName: string;
  privacy: PrivacyFilter;
  since: string;
  until: string;
}): string {
  const p = new URLSearchParams();
  if (params.domain !== "all") p.set("domain", params.domain);
  if (params.toolName) p.set("tool_name", params.toolName);
  if (params.privacy !== "all") p.set("privacy_classification", params.privacy);
  if (params.since) p.set("since", new Date(params.since).toISOString());
  if (params.until) {
    const d = new Date(params.until);
    d.setHours(23, 59, 59, 999);
    p.set("until", d.toISOString());
  }
  return `/api/v1/audit/export?${p.toString()}`;
}

function classificationBadge(cls: string) {
  if (cls === "private") return <Badge variant="destructive" className="text-[10px] px-1.5 py-0">private</Badge>;
  return <Badge variant="secondary" className="text-[10px] px-1.5 py-0">{cls}</Badge>;
}

function domainBadge(domain: string) {
  if (domain === "private") return <Badge className="text-[10px] px-1.5 py-0 bg-violet-500/20 text-violet-400 border-0">private</Badge>;
  return <Badge className="text-[10px] px-1.5 py-0 bg-sky-500/20 text-sky-400 border-0">external</Badge>;
}

function ExpandedRow({ entry }: { entry: AuditEntry }) {
  return (
    <TableRow className="bg-muted/30 border-t-0">
      <TableCell colSpan={7} className="px-6 py-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div>
            <p className="text-muted-foreground font-medium mb-1">Trace ID</p>
            <p className="font-mono break-all">{entry.trace_id}</p>
          </div>
          <div>
            <p className="text-muted-foreground font-medium mb-1">Session ID</p>
            <p className="font-mono break-all">{entry.session_id}</p>
          </div>
          {entry.tool_args && (
            <div className="sm:col-span-2">
              <p className="text-muted-foreground font-medium mb-1">Tool Args</p>
              <pre className="font-mono bg-muted rounded p-2 text-[11px] overflow-auto max-h-32">
                {JSON.stringify(entry.tool_args, null, 2)}
              </pre>
            </div>
          )}
          {entry.tool_result_summary && (
            <div className="sm:col-span-2">
              <p className="text-muted-foreground font-medium mb-1">Result Summary</p>
              <p className="text-muted-foreground">{entry.tool_result_summary}</p>
            </div>
          )}
          {entry.classification_reasoning && (
            <div className="sm:col-span-2">
              <p className="text-muted-foreground font-medium mb-1">Classification Reasoning</p>
              <p className="text-muted-foreground">{entry.classification_reasoning}</p>
            </div>
          )}
          {entry.previous_entry_hash && (
            <div className="sm:col-span-2">
              <p className="text-muted-foreground font-medium mb-1">Previous Hash</p>
              <p className="font-mono text-[11px] text-muted-foreground break-all">{entry.previous_entry_hash}</p>
            </div>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = entry.tool_args || entry.tool_result_summary || entry.classification_reasoning || entry.previous_entry_hash;

  return (
    <>
      <TableRow
        className={hasDetails ? "cursor-pointer hover:bg-accent/30 transition-colors" : ""}
        onClick={hasDetails ? () => setExpanded((v) => !v) : undefined}
        data-testid={`audit-row-${entry.id}`}
      >
        <TableCell className="w-4 text-muted-foreground">
          {hasDetails ? (
            expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />
          ) : null}
        </TableCell>
        <TableCell className="text-xs font-mono text-muted-foreground whitespace-nowrap">
          {new Date(entry.timestamp).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </TableCell>
        <TableCell>{domainBadge(entry.domain)}</TableCell>
        <TableCell className="text-xs font-mono">{entry.tool_name ?? <span className="text-muted-foreground">—</span>}</TableCell>
        <TableCell>{classificationBadge(entry.privacy_classification)}</TableCell>
        <TableCell className="text-xs font-mono text-muted-foreground">
          {entry.model_name}
        </TableCell>
        <TableCell className="text-right text-xs font-mono text-muted-foreground">
          {Number(entry.cost_usd) === 0 ? "—" : `$${Number(entry.cost_usd).toFixed(4)}`}
        </TableCell>
      </TableRow>
      {expanded && hasDetails && <ExpandedRow entry={entry} />}
    </>
  );
}

export default function Audit() {
  const [offset, setOffset] = useState(0);
  const [domain, setDomain] = useState<DomainFilter>("all");
  const [toolName, setToolName] = useState("");
  const [toolNameInput, setToolNameInput] = useState("");
  const [privacy, setPrivacy] = useState<PrivacyFilter>("all");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  const entriesUrl = buildUrl({ offset, domain, toolName, privacy, since, until });

  const { data: verifyRes, isLoading: verifyLoading } = useQuery({
    queryKey: ["auditVerify"],
    queryFn: () => apiRequest<AuditVerifyResponse>("/api/v1/audit/verify"),
    retry: false,
    staleTime: 60_000,
  });

  const { data: entriesRes, isLoading: entriesLoading } = useQuery({
    queryKey: ["auditEntries", offset, domain, toolName, privacy, since, until],
    queryFn: () => apiRequest<AuditEntriesResponse>(entriesUrl),
    retry: false,
  });

  const verifyData = verifyRes?.data;
  const entriesData = entriesRes?.data;
  const entries = entriesData?.entries ?? [];
  const total = entriesData?.total ?? 0;

  function applyToolFilter() {
    setToolName(toolNameInput.trim());
    setOffset(0);
  }

  function resetFilters() {
    setDomain("all");
    setToolName("");
    setToolNameInput("");
    setPrivacy("all");
    setSince("");
    setUntil("");
    setOffset(0);
  }

  async function handleExport() {
    const url = buildExportUrl({ domain, toolName, privacy, since, until });
    const { getAccessToken } = await import("@/auth/tokens");
    const token = getAccessToken();
    const resp = await fetch(url, {
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) return;
    const blob = await resp.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = "audit_export.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Audit Trail</h1>
          <p className="text-sm text-muted-foreground">Complete log of all agent actions and decisions</p>
        </div>
        <button
          onClick={handleExport}
          className="inline-flex items-center gap-1.5 h-8 px-3 text-xs rounded-md border border-input bg-background hover:bg-accent transition-colors"
        >
          <Download className="h-3.5 w-3.5" />
          Export JSON
        </button>
      </div>

      {/* Chain Integrity */}
      <Card>
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-3">
            {verifyLoading ? (
              <div className="h-4 w-4 rounded-full bg-muted animate-pulse" />
            ) : verifyData?.error === "no database" ? (
              <>
                <div className="h-4 w-4 rounded-full bg-muted-foreground/30" />
                <span className="text-sm text-muted-foreground">Chain integrity: no data</span>
              </>
            ) : verifyData?.valid ? (
              <>
                <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                <span className="text-sm text-green-600 dark:text-green-400 font-medium">
                  Hash chain intact
                </span>
                <span className="text-xs text-muted-foreground">
                  ({verifyData.entries_checked} entries verified)
                </span>
              </>
            ) : (
              <>
                <XCircle className="h-4 w-4 text-destructive flex-shrink-0" />
                <span className="text-sm text-destructive font-medium">
                  Chain integrity violation
                </span>
                {verifyData?.broken_at_entry_id && (
                  <span className="text-xs text-muted-foreground font-mono">
                    at {verifyData.broken_at_entry_id}
                  </span>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3 items-end">
            {/* Date range */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">From</label>
              <input
                type="date"
                value={since}
                onChange={(e) => { setSince(e.target.value); setOffset(0); }}
                className="h-8 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">To</label>
              <input
                type="date"
                value={until}
                onChange={(e) => { setUntil(e.target.value); setOffset(0); }}
                className="h-8 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            {/* Domain */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">Domain</label>
              <Select value={domain} onValueChange={(v) => { setDomain(v as DomainFilter); setOffset(0); }}>
                <SelectTrigger className="h-8 w-[120px] text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="private">Private</SelectItem>
                  <SelectItem value="external">External</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Privacy classification */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">Classification</label>
              <Select value={privacy} onValueChange={(v) => { setPrivacy(v as PrivacyFilter); setOffset(0); }}>
                <SelectTrigger className="h-8 w-[130px] text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="private">Private</SelectItem>
                  <SelectItem value="public">Public</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Tool name */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground">Tool</label>
              <div className="flex gap-1">
                <input
                  type="text"
                  placeholder="e.g. web_search"
                  value={toolNameInput}
                  onChange={(e) => setToolNameInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && applyToolFilter()}
                  className="h-8 rounded-md border border-input bg-background px-2 text-sm w-36 focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <button
                  onClick={applyToolFilter}
                  className="h-8 px-2 rounded-md border border-input bg-background text-xs hover:bg-accent transition-colors"
                >
                  Apply
                </button>
              </div>
            </div>

            <button
              onClick={resetFilters}
              className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Reset
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Entries table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center justify-between">
            <span>Entries</span>
            {!entriesLoading && (
              <span className="text-xs text-muted-foreground font-normal">{total.toLocaleString()} total</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {entriesLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="animate-pulse h-9 bg-muted rounded" role="status" />
              ))}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-4" />
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Domain</TableHead>
                  <TableHead>Tool</TableHead>
                  <TableHead>Classification</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-10">
                      No audit entries found
                    </TableCell>
                  </TableRow>
                ) : (
                  entries.map((entry) => (
                    <AuditRow key={entry.id} entry={entry} />
                  ))
                )}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {total > 0 && (
            <div className="flex justify-between items-center px-4 py-2 border-t text-xs text-muted-foreground">
              <button
                className="hover:text-foreground disabled:opacity-40"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_LIMIT))}
              >
                Previous
              </button>
              <span>
                {offset + 1}–{Math.min(offset + PAGE_LIMIT, total)} of {total.toLocaleString()}
              </span>
              <button
                className="hover:text-foreground disabled:opacity-40"
                disabled={offset + PAGE_LIMIT >= total}
                onClick={() => setOffset(offset + PAGE_LIMIT)}
              >
                Next
              </button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

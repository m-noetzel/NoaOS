import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { Thread, PrivacyMode } from "@/api/types";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Pencil, Check, X } from "lucide-react";

type DomainFilter = PrivacyMode | "all";

interface ThreadSidebarProps {
  activeThread: string | null;
  onSelectThread: (id: string) => void;
  onThreadDeleted: () => void;
}

export function ThreadSidebar({
  activeThread,
  onSelectThread,
  onThreadDeleted,
}: ThreadSidebarProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [renamingThread, setRenamingThread] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [domainFilter, setDomainFilter] = useState<DomainFilter>("all");

  // Fetch threads for each domain separately (backend only accepts one domain at a time)
  const { data: externalThreadsRes } = useQuery({
    queryKey: ["threads", "external"],
    queryFn: () => apiRequest<Thread[]>("/api/v1/threads?privacy_mode=external"),
  });
  const { data: privateThreadsRes } = useQuery({
    queryKey: ["threads", "private"],
    queryFn: () => apiRequest<Thread[]>("/api/v1/threads?privacy_mode=private"),
  });

  const externalThreads = externalThreadsRes?.data || [];
  const privateThreads = privateThreadsRes?.data || [];

  const threads =
    domainFilter === "all"
      ? [...privateThreads, ...externalThreads]
      : domainFilter === "private"
        ? privateThreads
        : externalThreads;

  const createThreadMutation = useMutation({
    mutationFn: (title: string) =>
      apiRequest<Thread>("/api/v1/threads", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      if (res.data) {
        onSelectThread(res.data.id);
      }
    },
  });

  const deleteThreadMutation = useMutation({
    mutationFn: (threadId: string) =>
      apiRequest(`/api/v1/threads/${threadId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      onThreadDeleted();
    },
  });

  const renameThreadMutation = useMutation({
    mutationFn: ({ threadId, title }: { threadId: string; title: string }) =>
      apiRequest(`/api/v1/threads/${threadId}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      setRenamingThread(null);
      setRenameValue("");
    },
    onError: (err: Error) => {
      toast({
        title: "Failed to rename thread",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  const startRename = (
    threadId: string,
    currentTitle: string,
    e: React.MouseEvent
  ) => {
    e.stopPropagation();
    setRenamingThread(threadId);
    setRenameValue(currentTitle);
  };

  const commitRename = (threadId: string) => {
    const title = renameValue.trim();
    if (!title) return;
    renameThreadMutation.mutate({ threadId, title });
  };

  const cancelRename = () => {
    setRenamingThread(null);
    setRenameValue("");
  };

  return (
    <div className="h-full border-r border-border/50 flex flex-col bg-muted/20">
      <div className="p-3 flex items-center justify-between border-b border-border/30">
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          Threads
        </span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="New thread"
          className="h-7 w-7 rounded-lg hover:bg-accent/60 hover:text-primary transition-all"
          onClick={() => createThreadMutation.mutate("New Thread")}
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>
      {/* UI-H6: Domain filter pills */}
      <div className="px-2 py-1.5 flex items-center gap-1 border-b border-border/20" data-testid="domain-filter-pills">
        {(["all", "private", "external"] as DomainFilter[]).map((f) => (
          <button
            key={f}
            data-testid={`domain-filter-${f}`}
            onClick={() => setDomainFilter(f)}
            className={cn(
              "px-2 py-0.5 rounded-full text-[10px] font-medium capitalize transition-all",
              domainFilter === f
                ? f === "private"
                  ? "bg-purple-900/60 text-purple-200 border border-purple-700/40"
                  : f === "external"
                    ? "bg-blue-900/60 text-blue-200 border border-blue-700/40"
                    : "bg-accent text-accent-foreground border border-border/50"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
            )}
          >
            {f}
          </button>
        ))}
      </div>
      <ScrollArea className="flex-1">
        <div className="p-1.5 space-y-0.5">
          {threads.map((thread, i) => (
            <div
              key={thread.id}
              className={cn(
                "group w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all duration-200 animate-fade-in cursor-pointer",
                activeThread === thread.id
                  ? "bg-accent text-accent-foreground font-medium glow-sm border border-border/50"
                  : "hover:bg-accent/40 text-muted-foreground hover:text-foreground"
              )}
              style={{ animationDelay: `${i * 50}ms` }}
              onClick={() =>
                renamingThread !== thread.id && onSelectThread(thread.id)
              }
            >
              {/* UX-M3: Inline rename mode */}
              {renamingThread === thread.id ? (
                <div
                  className="flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    autoFocus
                    className="flex-1 text-[13px] bg-transparent border-b border-primary outline-none min-w-0"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitRename(thread.id);
                      if (e.key === "Escape") cancelRename();
                    }}
                    aria-label="Thread title"
                  />
                  <button
                    className="p-1 rounded hover:bg-green-500/20 hover:text-green-600 text-muted-foreground transition-all"
                    onClick={() => commitRename(thread.id)}
                    aria-label="Confirm rename"
                  >
                    <Check className="h-3 w-3" />
                  </button>
                  <button
                    className="p-1 rounded hover:bg-muted hover:text-foreground text-muted-foreground transition-all"
                    onClick={cancelRename}
                    aria-label="Cancel rename"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1 min-w-0">
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-[13px]">{thread.title}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {thread.message_count} messages
                    </p>
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity shrink-0 bg-inherit pl-1">
                    <button
                      className="p-1 rounded hover:bg-accent/60 hover:text-primary transition-all"
                      onClick={(e) => startRename(thread.id, thread.title, e)}
                      aria-label="Rename thread"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                    <button
                      className="p-1 rounded hover:bg-destructive/20 hover:text-destructive transition-all"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm("Delete this thread?")) {
                          deleteThreadMutation.mutate(thread.id);
                        }
                      }}
                      aria-label="Delete thread"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

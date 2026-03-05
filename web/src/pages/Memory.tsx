import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { MemoryFact } from "@/api/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Check, Pencil, X, Trash2, Search } from "lucide-react";

export default function Memory() {
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const queryClient = useQueryClient();

  const { data: factsRes, isLoading } = useQuery({
    queryKey: ["memory-facts"],
    queryFn: () => apiRequest<MemoryFact[]>("/api/v1/memory/facts"),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`/api/v1/memory/facts/${id}/approve`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
    },
  });

  const editMutation = useMutation({
    mutationFn: ({ id, fact }: { id: string; fact: string }) =>
      apiRequest<void>(`/api/v1/memory/facts/${id}/update`, {
        method: "POST",
        body: JSON.stringify({ fact }),
      }),
    onSuccess: () => {
      setEditingId(null);
      setEditText("");
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`/api/v1/memory/facts/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
    },
  });

  const facts = factsRes?.data || [];
  const pending = facts.filter((f) => f.status === "pending");
  const approved = facts.filter((f) => f.status === "approved");
  const filtered = approved.filter((f) =>
    f.fact.toLowerCase().includes(search.toLowerCase()) ||
    f.category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Memory Audit</h1>
        <p className="text-sm text-muted-foreground">Review long-term memory facts</p>
      </div>

      <Tabs defaultValue="pending">
        <TabsList>
          <TabsTrigger value="pending">Pending ({pending.length})</TabsTrigger>
          <TabsTrigger value="approved">Approved ({approved.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="mt-4">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fact</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Extracted</TableHead>
                  <TableHead className="w-[120px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pending.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      No pending facts
                    </TableCell>
                  </TableRow>
                ) : (
                  pending.map((fact) => (
                    <TableRow key={fact.id}>
                      <TableCell className="text-sm max-w-[300px]">
                        {editingId === fact.id ? (
                          <div className="flex gap-1 items-center">
                            <Input
                              value={editText}
                              onChange={(e) => setEditText(e.target.value)}
                              className="h-7 text-sm"
                              onKeyDown={(e) => {
                                if (e.key === "Enter") editMutation.mutate({ id: fact.id, fact: editText });
                                if (e.key === "Escape") setEditingId(null);
                              }}
                            />
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-success" onClick={() => editMutation.mutate({ id: fact.id, fact: editText })}>
                              <Check className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditingId(null)}>
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ) : (
                          fact.fact
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">{fact.category}</Badge>
                      </TableCell>
                      <TableCell className="text-xs font-mono text-muted-foreground">
                        {fact.source_thread_id}
                      </TableCell>
                      <TableCell>
                        {fact.auto_extracted ? (
                          <Badge variant="outline" className="text-xs">Auto</Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">Manual</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {editingId !== fact.id && (
                          <div className="flex gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-success" onClick={() => approveMutation.mutate(fact.id)}>
                              <Check className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => { setEditingId(fact.id); setEditText(fact.fact); }}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => deleteMutation.mutate(fact.id)}>
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="approved" className="mt-4 space-y-3">
          <div className="relative max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search facts…"
              className="pl-9"
            />
          </div>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fact</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-[60px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                      No facts found
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((fact) => (
                    <TableRow key={fact.id}>
                      <TableCell className="text-sm">{fact.fact}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">{fact.category}</Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {new Date(fact.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => deleteMutation.mutate(fact.id)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface Tool {
  name: string;
  capability: string;
  risk_tier: string;
  enabled: boolean;
  description?: string;
}

export default function Tools() {
  const { data: toolsRes, isLoading, isError } = useQuery({
    queryKey: ["tools"],
    queryFn: () => apiRequest<Tool[]>("/api/v1/tools"),
  });

  const tools = toolsRes?.data || [];

  if (isError) {
    return (
      <div className="p-6 space-y-4">
        <div>
          <h1 className="text-lg font-semibold">Tools</h1>
          <p className="text-sm text-muted-foreground">Registered tool capabilities</p>
        </div>
        <p className="text-sm text-destructive">Failed to load tools</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Tools</h1>
        <p className="text-sm text-muted-foreground">Registered tool capabilities</p>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : tools.length === 0 ? (
        <p className="text-sm text-muted-foreground">No tools registered</p>
      ) : (
        <div className="rounded-lg border border-border/50 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Capability</TableHead>
                <TableHead>Risk Tier</TableHead>
                <TableHead>Enabled</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tools.map((tool) => (
                <TableRow key={tool.name}>
                  <TableCell className="font-mono text-sm">{tool.name}</TableCell>
                  <TableCell className="text-sm">{tool.capability}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{tool.risk_tier}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={tool.enabled ? "default" : "secondary"}>
                      {tool.enabled ? "Yes" : "No"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

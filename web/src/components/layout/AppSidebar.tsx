import {
  MessageSquare, Play, ShieldCheck, ListOrdered,
  Brain, FileBox, DollarSign, Settings, LogOut,
  Sparkles, Wrench,
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";

const navItems = [
  { title: "Chat", url: "/", icon: MessageSquare },
  { title: "Runs", url: "/runs", icon: Play },
  { title: "Approvals", url: "/approvals", icon: ShieldCheck },
  { title: "Queue", url: "/queue", icon: ListOrdered },
  { title: "Memory", url: "/memory", icon: Brain },
  { title: "Artifacts", url: "/artifacts", icon: FileBox },
  { title: "Cost", url: "/cost", icon: DollarSign },
  { title: "Tools", url: "/tools", icon: Wrench },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const location = useLocation();
  const { logout } = useAuth();

  // UI-M9: Fetch pending approvals and queue counts for badges
  const { data: approvalsRes } = useQuery({
    queryKey: ["approvalsPending"],
    queryFn: () => apiRequest<unknown[]>("/api/v1/approvals/pending"),
    retry: false,
  });

  const { data: queueRes } = useQuery({
    queryKey: ["queueItems"],
    queryFn: () => apiRequest<unknown[]>("/api/v1/queue"),
    retry: false,
  });

  const approvalCount = approvalsRes?.data?.length ?? 0;
  const queueCount = queueRes?.data?.length ?? 0;

  const badgeCounts: Record<string, number> = {
    Approvals: approvalCount,
    Queue: queueCount,
  };

  const isActive = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2.5 px-2 py-1.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl gradient-primary shadow-md glow-sm">
            <Sparkles className="h-4 w-4 text-primary-foreground" />
          </div>
          {!collapsed && (
            <span className="text-sm font-bold tracking-tight text-gradient">Noa</span>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-medium">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={isActive(item.url)}>
                    <NavLink
                      to={item.url}
                      end={item.url === "/"}
                      className="group relative rounded-lg transition-all duration-200 hover:bg-accent/60"
                      activeClassName="bg-accent text-accent-foreground font-medium glow-sm"
                    >
                      <item.icon className="h-4 w-4 transition-colors group-hover:text-primary" />
                      {!collapsed && (
                        <>
                          <span>{item.title}</span>
                          {(badgeCounts[item.title] ?? 0) > 0 && (
                            <span className="ml-auto inline-flex items-center justify-center rounded-full bg-primary text-primary-foreground text-[10px] font-medium h-5 min-w-[20px] px-1">
                              {badgeCounts[item.title]}
                            </span>
                          )}
                        </>
                      )}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarSeparator className="opacity-50" />

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild isActive={location.pathname === "/settings"}>
              <NavLink
                to="/settings"
                className="rounded-lg transition-all duration-200 hover:bg-accent/60"
                activeClassName="bg-accent text-accent-foreground font-medium"
              >
                <Settings className="h-4 w-4" />
                {!collapsed && <span>Settings</span>}
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={logout} className="rounded-lg transition-all duration-200 hover:bg-destructive/10 hover:text-destructive">
              <LogOut className="h-4 w-4" />
              {!collapsed && <span>Sign out</span>}
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}

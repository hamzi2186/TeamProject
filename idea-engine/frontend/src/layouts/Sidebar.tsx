import { Link, useLocation } from "react-router-dom";
import { ChevronLeft, ChevronRight, FileText, LifeBuoy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const NAV_ITEM = { label: "Daily reports", path: "/reports", icon: FileText };

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const location = useLocation();
  const active = location.pathname.startsWith(NAV_ITEM.path);
  const Icon = NAV_ITEM.icon;

  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-screen flex-col border-r border-border bg-card xl:flex",
        collapsed ? "w-[68px]" : "w-56",
      )}
      style={{ transition: "width 200ms cubic-bezier(0.4, 0, 0.2, 1)" }}
    >
      <div className="flex h-[58px] shrink-0 items-center border-b border-border px-4">
        {collapsed ? (
          <div className="flex size-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
            T
          </div>
        ) : (
          <Link to="/reports" className="flex items-center gap-2">
            <div className="flex size-6 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
              T
            </div>
            <span className="text-[16px] font-bold tracking-tight text-foreground">
              T Rex <span className="text-[13px] font-normal text-muted-foreground">Idea</span>
            </span>
          </Link>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-2" aria-label="Main navigation">
        <Link
          to={NAV_ITEM.path}
          className={cn(
            "flex items-center gap-3 rounded-md text-[13px] transition-colors",
            collapsed ? "justify-center px-2 py-2.5" : "px-3 py-2",
            active
              ? "border-l-[3px] border-brand-deep bg-surface-subtle font-semibold text-foreground"
              : "border-l-[3px] border-transparent font-medium text-secondary-foreground hover:bg-surface-subtle",
          )}
          aria-current={active ? "page" : undefined}
          title={collapsed ? NAV_ITEM.label : undefined}
        >
          <Icon className="size-[18px] shrink-0" />
          {!collapsed && <span>{NAV_ITEM.label}</span>}
        </Link>
      </nav>

      <div className="flex shrink-0 items-center justify-between border-t border-border p-3">
        {!collapsed && (
          <div className="flex items-center gap-2 min-w-0">
            <LifeBuoy className="size-4 shrink-0 text-muted-foreground" />
            <div className="min-w-0 leading-tight">
              <p className="text-[11px] font-semibold text-foreground">Idea Engine</p>
              <p className="text-[10px] text-muted-foreground">v1.0, connected</p>
            </div>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className={cn(!collapsed && "ml-auto")}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
        </Button>
      </div>
    </aside>
  );
}
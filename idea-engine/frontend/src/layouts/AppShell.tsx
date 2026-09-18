import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { FileText } from "lucide-react";

import { cn } from "@/lib/utils";
import { Sidebar } from "@/layouts/Sidebar";
import { Topbar } from "@/layouts/Topbar";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((c) => !c)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenNavigation={() => setNavOpen(true)} />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>

      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Navigation</SheetTitle>
            <SheetDescription>Primary navigation for the Idea Engine</SheetDescription>
          </SheetHeader>
          <div className="flex h-[58px] items-center border-b border-border px-4">
            <Link to="/reports" onClick={() => setNavOpen(false)} className="flex items-center gap-2">
              <div className="flex size-6 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
                T
              </div>
              <span className="text-[16px] font-bold tracking-tight text-foreground">
                T Rex <span className="text-[13px] font-normal text-muted-foreground">Idea</span>
              </span>
            </Link>
          </div>
          <nav className="flex flex-col gap-1 p-2" aria-label="Mobile navigation">
            <Link
              to="/reports"
              onClick={() => setNavOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-md border-l-[3px] border-brand-deep bg-surface-subtle px-3 py-2 text-[13px] font-semibold text-foreground",
              )}
            >
              <FileText className="size-4" />
              Daily reports
            </Link>
          </nav>
        </SheetContent>
      </Sheet>
    </div>
  );
}
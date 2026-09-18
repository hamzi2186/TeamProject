import { Link, useLocation } from "react-router-dom";
import { Menu, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface TopbarProps {
  onOpenNavigation: () => void;
}

const BREADCRUMB: Record<string, string> = {
  "/reports": "Reports",
  "/reports/leads": "Lead journey",
};

function breadcrumbFor(pathname: string): string {
  if (pathname.startsWith("/reports/leads")) return BREADCRUMB["/reports/leads"];
  if (pathname.startsWith("/reports")) return BREADCRUMB["/reports"];
  return "Reports";
}

export function Topbar({ onOpenNavigation }: TopbarProps) {
  const location = useLocation();
  const page = breadcrumbFor(location.pathname);

  return (
    <header className="sticky top-0 z-30 flex h-[58px] shrink-0 items-center justify-between border-b border-border bg-card px-4 sm:px-7">
      <div className="flex min-w-0 items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="xl:hidden"
          onClick={onOpenNavigation}
          aria-label="Open navigation"
        >
          <Menu className="size-4" />
        </Button>
        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px]">
          <Link to="/reports" className="text-muted-foreground hover:text-foreground">
            T Rex
          </Link>
          <span className="text-muted-foreground" aria-hidden>
            /
          </span>
          <span className="truncate font-semibold text-foreground">{page}</span>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        <Badge variant="secondary" className="gap-1.5 px-2.5 py-1">
          <Sparkles className="size-3.5 text-brand-deep" />
          Lead intelligence active
        </Badge>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="hidden gap-1.5 sm:inline-flex"
              aria-label="Ask T Rex Assistant"
              disabled
            >
              <Sparkles className="size-4" />
              Ask T Rex
            </Button>
          </TooltipTrigger>
          <TooltipContent>T Rex Assistant is not available in standalone Idea mode.</TooltipContent>
        </Tooltip>
      </div>
    </header>
  );
}
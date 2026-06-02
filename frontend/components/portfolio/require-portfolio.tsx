"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { usePortfolios } from "./portfolio-context";
import { LoadingSkeleton, ErrorState, EmptyState } from "@/components/ui/states";
import type { Portfolio } from "@/lib/types";

/**
 * Gate page content on an active portfolio: shows loading/error/empty states
 * and otherwise hands the selected portfolio to the render function.
 */
export function RequirePortfolio({ children }: { children: (portfolio: Portfolio) => ReactNode }) {
  const { selected, loading, error, reload } = usePortfolios();

  if (loading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!selected)
    return (
      <EmptyState
        title="No portfolio selected"
        hint="Create a portfolio or load a preset to start running scenarios and risk analytics."
        action={
          <Link href="/portfolio-builder" className="rounded-full bg-ink px-4 py-2 text-sm text-white hover:bg-steel">
            Open portfolio builder
          </Link>
        }
      />
    );

  return <>{children(selected)}</>;
}

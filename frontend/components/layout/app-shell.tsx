import Link from "next/link";
import { ReactNode } from "react";
import { PortfolioProvider, PortfolioSelector } from "@/components/portfolio/portfolio-context";

const navigation = [
  { href: "/overview", label: "Overview" },
  { href: "/portfolio-builder", label: "Portfolio Builder" },
  { href: "/historical-scenarios", label: "Historical" },
  { href: "/hypothetical-scenarios", label: "Hypothetical" },
  { href: "/risk-analytics", label: "Risk" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <PortfolioProvider>
      <div className="min-h-screen">
        <header className="border-b border-ink/10 bg-panel/80 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <Link href="/" className="block">
                <p className="text-xs uppercase tracking-[0.24em] text-steel">Stress Workbench</p>
                <h1 className="font-serif text-3xl text-ink">Market Scenario &amp; Stress Testing</h1>
              </Link>
              <PortfolioSelector />
            </div>
            <nav className="flex flex-wrap gap-2 text-sm text-steel">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-full border border-ink/10 px-3 py-1.5 hover:border-signal hover:text-signal"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-10">{children}</main>
      </div>
    </PortfolioProvider>
  );
}

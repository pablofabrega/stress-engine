import Link from "next/link";
import { ReactNode } from "react";

const navigation = [
  { href: "/", label: "Home" },
  { href: "/overview", label: "Overview" },
  { href: "/portfolio-builder", label: "Portfolio Builder" },
  { href: "/historical-scenarios", label: "Historical Scenarios" },
  { href: "/hypothetical-scenarios", label: "Hypothetical Scenarios" },
  { href: "/risk-analytics", label: "Risk Analytics" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-ink/10 bg-panel/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-steel">Stress Workbench</p>
            <h1 className="font-serif text-3xl text-ink">Market Scenario and Stress Testing Workbench</h1>
          </div>
          <nav className="flex flex-wrap gap-3 text-sm text-steel">
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
  );
}


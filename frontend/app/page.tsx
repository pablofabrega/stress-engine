import Link from "next/link";

const modules = [
  "Provider abstraction for Polygon, Alpaca, and yfinance",
  "Historical crisis replay using real daily returns",
  "Hypothetical macro shock engine with explainable approximations",
  "Liquidity-adjusted stress losses and hedge suggestions",
];

export default function HomePage() {
  return (
    <section className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
      <div className="space-y-6 rounded-[2rem] border border-ink/10 bg-panel p-10 shadow-panel">
        <p className="text-xs uppercase tracking-[0.28em] text-signal">Phase 1 Scaffold</p>
        <h2 className="max-w-3xl font-serif text-6xl leading-tight text-ink">
          A serious portfolio stress-testing product, built to hold up in interviews.
        </h2>
        <p className="max-w-2xl text-lg leading-8 text-steel">
          This scaffold establishes the backend, frontend, persistence, worker, and deployment structure for an
          institutional-style scenario analysis application.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/overview" className="rounded-full bg-ink px-5 py-3 text-sm text-white hover:bg-steel">
            Open product shell
          </Link>
          <Link
            href="/portfolio-builder"
            className="rounded-full border border-ink/15 px-5 py-3 text-sm text-ink hover:border-signal hover:text-signal"
          >
            Review portfolio flow
          </Link>
        </div>
      </div>
      <div className="rounded-[2rem] border border-ink/10 bg-[#e8dfd0] p-8">
        <p className="text-xs uppercase tracking-[0.24em] text-steel">Planned Modules</p>
        <ul className="mt-5 space-y-4 text-sm leading-7 text-ink">
          {modules.map((module) => (
            <li key={module} className="border-b border-ink/10 pb-4 last:border-none last:pb-0">
              {module}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}


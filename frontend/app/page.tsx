import Link from "next/link";

const capabilities = [
  {
    title: "Historical stress replay",
    body: "Replay 2008, COVID, 2018 Q4, and 2022 against your holdings using real daily returns — with PnL attribution and correlation shifts.",
    href: "/historical-scenarios",
  },
  {
    title: "Hypothetical macro shocks",
    body: "Apply instantaneous equity, rate, tech, VIX, oil, and credit shocks through factor sensitivities and see liquidity-adjusted losses.",
    href: "/hypothetical-scenarios",
  },
  {
    title: "Risk analytics",
    body: "Historical VaR/CVaR, drawdown, concentration (HHI), and Fama-French factor exposures with plain-English explanations.",
    href: "/risk-analytics",
  },
  {
    title: "Explainable hedges",
    body: "Each recommendation cites the specific weakness it addresses and shows the hedge-ratio math step by step.",
    href: "/recommendations",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-10">
      <section className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6 rounded-[2rem] border border-ink/10 bg-panel p-10 shadow-panel">
          <p className="text-xs uppercase tracking-[0.28em] text-signal">Decision-support workbench</p>
          <h2 className="max-w-3xl font-serif text-5xl leading-tight text-ink">
            Understand how your portfolio behaves under crisis and macro shock.
          </h2>
          <p className="max-w-2xl text-lg leading-8 text-steel">
            Load a portfolio, stress it against real historical crises and hypothetical shocks, and read explainable
            risk analytics and hedge recommendations — every number traceable to first principles.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/overview" className="rounded-full bg-ink px-5 py-3 text-sm text-white hover:bg-steel">
              Open overview
            </Link>
            <Link
              href="/portfolio-builder"
              className="rounded-full border border-ink/15 px-5 py-3 text-sm text-ink hover:border-signal hover:text-signal"
            >
              Build a portfolio
            </Link>
          </div>
        </div>
        <div className="rounded-[2rem] border border-ink/10 bg-[#e8dfd0] p-8">
          <p className="text-xs uppercase tracking-[0.24em] text-steel">The three questions</p>
          <ul className="mt-5 space-y-4 text-sm leading-7 text-ink">
            <li className="border-b border-ink/10 pb-4">How much would I lose if 2008 or COVID happened again?</li>
            <li className="border-b border-ink/10 pb-4">What breaks first — and which positions drive the loss?</li>
            <li>What hedges would actually reduce my downside, and at what cost?</li>
          </ul>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {capabilities.map((cap) => (
          <Link
            key={cap.title}
            href={cap.href}
            className="group rounded-3xl border border-ink/10 bg-panel p-6 shadow-panel transition-colors hover:border-signal"
          >
            <h3 className="font-serif text-2xl text-ink group-hover:text-signal">{cap.title}</h3>
            <p className="mt-3 text-sm leading-7 text-steel">{cap.body}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}

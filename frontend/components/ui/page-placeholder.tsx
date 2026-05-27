type Metric = {
  label: string;
  value: string;
  helper: string;
};

type PagePlaceholderProps = {
  eyebrow: string;
  title: string;
  description: string;
  metrics: Metric[];
};

export function PagePlaceholder({
  eyebrow,
  title,
  description,
  metrics,
}: PagePlaceholderProps) {
  return (
    <section className="space-y-8">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.28em] text-signal">{eyebrow}</p>
        <h2 className="max-w-3xl font-serif text-5xl leading-tight text-ink">{title}</h2>
        <p className="max-w-3xl text-lg leading-8 text-steel">{description}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {metrics.map((metric) => (
          <article key={metric.label} className="rounded-3xl border border-ink/10 bg-panel p-6 shadow-panel">
            <p className="text-sm uppercase tracking-[0.2em] text-steel">{metric.label}</p>
            <p className="mt-4 font-serif text-4xl text-ink">{metric.value}</p>
            <p className="mt-3 text-sm leading-6 text-steel">{metric.helper}</p>
          </article>
        ))}
      </div>
      <div className="rounded-[2rem] border border-dashed border-ink/20 bg-white/50 p-8 text-steel">
        Phase 1 scaffold: loading states, explainability tooltips, live analytics, and scenario execution will be
        implemented in later modules.
      </div>
    </section>
  );
}


"use client";

import { api, API_BASE } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Card, SectionTitle } from "@/components/ui/card";
import { ErrorState, LoadingSkeleton } from "@/components/ui/states";
import { LabelWithTooltip } from "@/components/ui/tooltip";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import type { HealthResponse } from "@/lib/types";

export default function SettingsPage() {
  const health = useApi<HealthResponse>(() => api.dataStatus(), []);

  return (
    <div className="space-y-8">
      <SectionTitle
        eyebrow="Settings & data status"
        title="Service health and data freshness"
        description="Connectivity to the API and database, plus the freshness of each market-data source. The provider is configured via the DATA_PROVIDER environment variable."
      />

      <Card>
        <h3 className="font-serif text-2xl text-ink">Connection</h3>
        <dl className="mt-4 space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-steel">API base URL</dt>
            <dd className="font-mono text-xs text-ink">{API_BASE}</dd>
          </div>
        </dl>
      </Card>

      {health.loading && <LoadingSkeleton rows={2} />}
      {health.error && <ErrorState message={health.error} onRetry={health.reload} />}
      {health.data && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <p className="text-xs uppercase tracking-[0.18em] text-steel">Service</p>
              <p className="mt-2 flex items-center gap-2 font-serif text-2xl text-ink">
                <StatusIcon ok={health.data.status === "ok"} />
                {health.data.status}
              </p>
              <p className="mt-1 text-xs text-steel">{health.data.service}</p>
            </Card>
            <Card>
              <p className="text-xs uppercase tracking-[0.18em] text-steel">
                <LabelWithTooltip label="Database" tooltip="Whether the API can reach PostgreSQL for portfolio and scenario persistence." />
              </p>
              <p className="mt-2 flex items-center gap-2 font-serif text-2xl text-ink">
                <StatusIcon ok={health.data.database.connected} />
                {health.data.database.connected ? "connected" : "unreachable"}
              </p>
              <p className="mt-1 text-xs text-steel">checked {health.data.database.checked_at}</p>
            </Card>
            <Card>
              <p className="text-xs uppercase tracking-[0.18em] text-steel">Data sources</p>
              <p className="mt-2 font-serif text-2xl text-ink">{health.data.data_sources.length}</p>
              <p className="mt-1 text-xs text-steel">configured market/macro feeds</p>
            </Card>
          </div>

          <Card>
            <h3 className="font-serif text-2xl text-ink">
              <LabelWithTooltip label="Data source freshness" tooltip="Last successful fetch per source. Stale or errored sources surface here so analytics caveats are visible." />
            </h3>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-[0.15em] text-steel">
                    <th className="py-2">Source</th>
                    <th className="py-2">Status</th>
                    <th className="py-2">Last fetched</th>
                    <th className="py-2">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {health.data.data_sources.map((src) => (
                    <tr key={src.source_name} className="border-t border-ink/5">
                      <td className="py-2 font-medium text-ink">{src.source_name}</td>
                      <td className="py-2">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          {src.status === "ok" ? (
                            <CheckCircle2 size={14} className="text-[#3f6b4f]" />
                          ) : src.status === "stale" ? (
                            <AlertTriangle size={14} className="text-[#c08552]" />
                          ) : (
                            <XCircle size={14} className="text-[#9c3b2e]" />
                          )}
                          {src.status}
                        </span>
                      </td>
                      <td className="py-2 text-steel">{src.last_fetched ?? "—"}</td>
                      <td className="py-2 text-xs text-steel">{src.error_message ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function StatusIcon({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle2 size={20} className="text-[#3f6b4f]" />
  ) : (
    <XCircle size={20} className="text-[#9c3b2e]" />
  );
}

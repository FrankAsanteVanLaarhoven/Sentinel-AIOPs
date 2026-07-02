import { CommandBar } from "@/components/CommandBar";
import { StatCards } from "@/components/StatCard";
import { GoldenSignals } from "@/components/GoldenSignals";
import { TopologyGraph } from "@/components/TopologyGraph";
import { InvestigationPanel } from "@/components/InvestigationPanel";
import { ChangeRanking } from "@/components/ChangeRanking";
import { ErrorShareDonut } from "@/components/ErrorShareDonut";
import { HostHeatmap } from "@/components/HostHeatmap";
import { SpanThroughput } from "@/components/SpanThroughput";
import { TraceWaterfall } from "@/components/TraceWaterfall";
import { LatencyHeatmap } from "@/components/LatencyHeatmap";
import { ValidationPanel } from "@/components/ValidationPanel";

// The shell + the full 12-column board. Every panel is engine-wired and owns
// its own data fetch; the human-gated investigation anchors the left column.
export default function DashboardPage() {
  return (
    <main className="flex flex-col min-h-full">
      <CommandBar />
      <div className="board p-3">
        {/* Left column — P3 · the honest, human-gated investigation ★ */}
        <InvestigationPanel />

        {/* Right — the 12-column board */}
        <div className="board-panels">
          {/* P1 · four SLO-burn stat cards */}
          <StatCards />

          {/* P1 · golden signals */}
          <GoldenSignals />

          {/* P2 · causal service topology ★ */}
          <TopologyGraph />

          {/* P4 · change-correlation ranking ★ */}
          <ChangeRanking />

          {/* P5 · parity panels */}
          <ErrorShareDonut />
          <HostHeatmap />
          <SpanThroughput />
          <TraceWaterfall />
          <LatencyHeatmap />

          {/* Validation — the three-layer honesty story, engine-served ★ */}
          <ValidationPanel />
        </div>
      </div>
    </main>
  );
}

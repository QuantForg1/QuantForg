"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { displayMetric, formatRate, sampleStatus } from "@/lib/ops/sample-confidence";

function statusOf(row: Record<string, unknown>, fallbackN?: number): string {
  const labeled = str(row.status, "");
  if (labeled && labeled !== "—") return labeled;
  const n = Number.isFinite(fallbackN)
    ? Number(fallbackN)
    : num(row.sample_size, num(row.TOTAL_TRADES, 0));
  return sampleStatus(n);
}

export function StrategyResearchWorkspace() {
  const q = useQuery({
    queryKey: ["ite-ops-strategy-research-forensics"],
    queryFn: () => iteOpsApi.strategyResearchForensics(90),
    retry: false,
    refetchInterval: 60_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={10} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Strategy Research unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const market = asRecord(root.current_market);
  const forensics = asRecord(root.forensics);
  const overall = asRecord(forensics.overall);
  const buy = asRecord(forensics.BUY_EXPECTANCY);
  const sell = asRecord(forensics.SELL_EXPECTANCY);
  const report = asRecord(root.report);
  const shadow = asRecord(root.shadow_expansion);
  const vps = asRecord(root.vps);
  const candidates = asList(shadow.candidates).map(asRecord);
  const sessions = asRecord(forensics.SESSION_EXPECTANCY);
  const regimes = asRecord(forensics.REGIME_EXPECTANCY);
  const matchedN = num(forensics.matched_count, 0);
  const unmatchedN = num(forensics.unmatched_count, 0);
  const overallStatus = statusOf(overall, matchedN);
  const bottleneck = str(root.trade_frequency_bottleneck, "UNKNOWN");
  const histograms = asRecord(root.funnel_histograms);
  const windows = asRecord(histograms.windows);
  const hour = asRecord(windows["1h"]);
  const funnel1h = asRecord(hour.funnel);
  const rates1h = asRecord(hour.rates_pct);
  const loss = asRecord(asRecord(forensics.loss_contributors).contributors);
  const settingsAudit = asRecord(root.settings_audit);
  const settings = asList(settingsAudit.settings).map(asRecord);
  const liveCfg = asList(settingsAudit.LIVE_EFFECTIVE_CONFIG);
  const legacyCfg = asList(settingsAudit.LEGACY_CONFIG);
  const researchCfg = asList(settingsAudit.RESEARCH_ONLY_CONFIG);
  const unwiredCfg = asList(settingsAudit.UNWIRED_CONFIG);
  const shadowDataset = asRecord(root.shadow_dataset);
  const coreVsExpansion = asRecord(root.core_vs_expansion);
  const coreLayer = asRecord(coreVsExpansion.CORE);
  const expansionLayer = asRecord(coreVsExpansion.SHADOW_EXPANSION);
  const shadowCandidates = asList(shadowDataset.candidates).map(asRecord);
  const shadowVerdict = asRecord(shadowDataset.verdict);
  const shadowWalk = asRecord(shadowDataset.walk_forward);
  const shadowOos = asRecord(shadowDataset.oos);
  const shadowSessions = asRecord(shadowDataset.session_analysis);
  const shadowRegimes = asRecord(shadowDataset.regime_analysis);
  const families = asRecord(hour.families);
  const news = asRecord(root.news_protection);
  const workflow = asRecord(root.research_workflow);
  const paint = asRecord(root.conflict_paint);
  const matrix = asRecord(root.decision_matrix);
  const oos = str(report.OUT_OF_SAMPLE_RESULT, "INSUFFICIENT_SAMPLE");
  const stages = asRecord(hour.stage_rates_pct);
  const disclaimer = str(
    root.disclaimer,
    "Historical data does not guarantee future profitability.",
  );

  return (
    <div className="space-y-[var(--space-4)]">
      <p className="text-[12px] text-[var(--fg-muted)]">{disclaimer}</p>

      <OpsPanel title="PRODUCTION STATUS">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Opportunity" value={str(market.opportunity_score)} />
          <MetricCard label="Required Opportunity" value={str(market.required_opportunity, "70")} />
          <MetricCard label="Directional edge" value={str(market.directional_edge)} />
          <MetricCard label="Required edge" value={str(market.required_edge, "5")} />
          <MetricCard label="First blocker" value={str(market.first_authoritative_blocker)} />
          <MetricCard label="Scanner" value={str(market.scanner_status, "UNKNOWN")} />
          <MetricCard label="Execution" value={str(market.execution_status, "NOT_REACHED")} />
          <MetricCard label="Bottleneck" value={bottleneck} tone="warn" />
          <MetricCard label="Production SHA" value={str(root.production_sha, "2ca7793").slice(0, 12)} />
          <MetricCard label="Research stage" value={str(workflow.current, "COLLECT")} />
          <MetricCard label="Decision class" value={str(matrix.code, "A")} />
          <MetricCard label="Data age (s)" value={str(market.data_age_seconds, "—")} />
          <MetricCard label="Market data" value={str(market.market_data_valid, str(market.data, "UNKNOWN"))} />
        </div>
        <p className="mt-3 text-[12px] text-[var(--fg-muted)]">
          Risk / Safety / OMS = {str(market.risk)} / {str(market.safety)} / {str(market.oms)}.
          LIVE ORDER SENT = NO. Ticket = {str(market.mt5_ticket, "NONE")}.
          Workflow = {str(workflow.current, "COLLECT")}. Max automated = PROMOTION_CANDIDATE.
        </p>
      </OpsPanel>

      <OpsPanel title="SCORING PAINT">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Paint reason" value={str(paint.paint_reason, "NONE")} />
          <MetricCard label="Raw displacement" value={str(paint.raw_displacement)} />
          <MetricCard label="Effective displacement" value={str(paint.effective_displacement)} />
          <MetricCard label="Raw timing" value={str(paint.raw_timing)} />
          <MetricCard label="Effective timing" value={str(paint.effective_timing)} />
          <MetricCard label="Paint timing" value={str(paint.paint_timing)} />
          <MetricCard label="First blocker?" value={str(paint.paint_is_first_blocker, "false")} />
          <MetricCard label="TAKE→WAIT?" value={str(paint.changes_qualifying_take_into_wait, "false")} />
        </div>
        <p className="mt-3 text-[12px] text-[var(--fg-muted)]">
          Secondary observability/scoring paint. scoring.py decision path is unchanged.
          {str(paint.evidence, "")}
        </p>
      </OpsPanel>

      <OpsPanel title="TRADE FORENSICS">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Matched" value={String(matchedN)} />
          <MetricCard label="Unmatched" value={String(unmatchedN)} tone="warn" />
          <MetricCard label="Wins" value={matchedN < 10 ? `INSUFFICIENT SAMPLE n=${matchedN}` : String(num(overall.WIN_COUNT, 0))} />
          <MetricCard label="Losses" value={matchedN < 10 ? `INSUFFICIENT SAMPLE n=${matchedN}` : String(num(overall.LOSS_COUNT, 0))} />
          <MetricCard
            label="Last profitable trade"
            value={displayMetric(report.LAST_PROFITABLE_TRADE, overallStatus)}
          />
          <MetricCard
            label="Last profitable period"
            value={displayMetric(report.LAST_PROFITABLE_PERIOD, overallStatus)}
          />
          <MetricCard label="Sample status" value={overallStatus} tone="warn" />
        </div>
        <p className="mt-3 text-[12px] text-[var(--fg-muted)]">
          Unmatched broker activity is excluded from strategy PnL. STRATEGY_MATCHED n={matchedN}.
        </p>
      </OpsPanel>

      <OpsPanel title="PERFORMANCE">
        {matchedN < 10 ? (
          <DeskEmpty
            icon={FlaskConical}
            title="INSUFFICIENT SAMPLE"
            description={`${unmatchedN} broker round-trips classified UNMATCHED_BROKER_ACTIVITY and excluded. Win rate is never shown without n. STRATEGY_MATCHED n=${matchedN}.`}
          />
        ) : (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <MetricCard
              label={`Win rate · ${overallStatus}`}
              value={str(overall.WIN_RATE_DISPLAY, formatRate(overall.WIN_RATE, matchedN, overallStatus))}
            />
            <MetricCard label={`Expectancy · n=${matchedN}`} value={displayMetric(overall.EXPECTANCY, overallStatus)} />
            <MetricCard label={`PF · n=${matchedN}`} value={displayMetric(overall.PROFIT_FACTOR, overallStatus)} />
            <MetricCard label={`Average R · n=${matchedN}`} value={displayMetric(overall.AVERAGE_R, overallStatus)} />
            <MetricCard label={`Max DD · n=${matchedN}`} value={displayMetric(overall.MAX_DRAWDOWN, overallStatus)} />
            <MetricCard label={`Avg winner · n=${matchedN}`} value={displayMetric(overall.AVERAGE_WIN, overallStatus)} />
            <MetricCard label={`Avg loser · n=${matchedN}`} value={displayMetric(overall.AVERAGE_LOSS, overallStatus)} />
            <MetricCard
              label={`BUY expectancy · ${statusOf(buy)}`}
              value={displayMetric(buy.EXPECTANCY, statusOf(buy))}
              tone="buy"
            />
            <MetricCard
              label={`SELL expectancy · ${statusOf(sell)}`}
              value={displayMetric(sell.EXPECTANCY, statusOf(sell))}
              tone="sell"
            />
          </div>
        )}
      </OpsPanel>

      <OpsPanel title="LOSS ANALYSIS">
        {Object.keys(loss).length === 0 ? (
          <p className="text-[12px] text-[var(--fg-subtle)]">INSUFFICIENT SAMPLE</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {Object.entries(loss).map(([name, raw]) => {
              const row = asRecord(raw);
              return (
                <MetricCard
                  key={name}
                  label={`${str(row.factor, name)} · n=${str(row.sample_size, "0")}`}
                  value={`${str(row.classification, str(row.verdict, "INSUFFICIENT_SAMPLE"))} · losses=${str(row.loss_count, "0")}`}
                />
              );
            })}
          </div>
        )}
      </OpsPanel>

      <OpsPanel title="OPPORTUNITY">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Scans (1h)" value={str(hour.n, "0")} />
          <MetricCard label="% ≥60" value={`${str(rates1h.opp_ge_60, "0")}%`} />
          <MetricCard label="% ≥65" value={`${str(rates1h.opp_ge_65, "0")}%`} />
          <MetricCard label="% ≥70" value={`${str(rates1h.opp_ge_70, str(funnel1h.opp_ge_70, "0"))}%`} />
          <MetricCard label="% ≥75" value={`${str(rates1h.opp_ge_75, "0")}%`} />
          <MetricCard label="% ≥80" value={`${str(rates1h.opp_ge_80, "0")}%`} />
          <MetricCard label="% ≥85" value={`${str(rates1h.opp_ge_85, "0")}%`} />
          <MetricCard label="% ≥90" value={`${str(rates1h.opp_ge_90, "0")}%`} />
          <MetricCard label="Edge ≥3" value={`${str(rates1h.edge_ge_3, "0")}%`} />
          <MetricCard label="Edge ≥5" value={`${str(rates1h.edge_ge_5, "0")}%`} />
          <MetricCard label="Edge ≥7" value={`${str(rates1h.edge_ge_7, "0")}%`} />
          <MetricCard label="Edge ≥10" value={`${str(rates1h.edge_ge_10, "0")}%`} />
          <MetricCard label="WAIT" value={str(funnel1h.wait, "0")} />
          <MetricCard label="Direction %" value={`${str(stages.DIRECTION, "0")}%`} />
          <MetricCard label="Opportunity %" value={`${str(stages.OPPORTUNITY, "0")}%`} />
          <MetricCard label="Sniper %" value={`${str(stages.SNIPER, "0")}%`} />
          <MetricCard label="Risk %" value={`${str(stages.RISK, "0")}%`} />
          <MetricCard label="Safety %" value={`${str(stages.SAFETY, "0")}%`} />
          <MetricCard label="OMS %" value={`${str(stages.OMS, "0")}%`} />
          <MetricCard label="MT5 %" value={`${str(stages.MT5, "0")}%`} />
          <MetricCard label="BUY qualifying" value={str(funnel1h.buy_qualifying, "0")} />
          <MetricCard label="SELL qualifying" value={str(funnel1h.sell_qualifying, "0")} />
        </div>
        <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
          Windows: 1h / 6h / 12h / 24h / 3d / 7d / 14d / 30d. Incomplete windows are not zero opportunity.
          Thresholds are not changed by these histograms.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-5">
          {Object.entries(sessions).map(([name, raw]) => {
            const row = asRecord(raw);
            const st = statusOf(row);
            return (
              <MetricCard
                key={name}
                label={`${name} · ${st}`}
                value={displayMetric(row.EXPECTANCY, st)}
              />
            );
          })}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3">
          {Object.entries(regimes).map(([name, raw]) => {
            const row = asRecord(raw);
            const st = statusOf(row);
            return (
              <MetricCard
                key={name}
                label={`${name} · ${st}`}
                value={displayMetric(row.EXPECTANCY, st)}
              />
            );
          })}
        </div>
      </OpsPanel>

      <OpsPanel title="EDGE">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Edge now" value={str(market.directional_edge)} />
          <MetricCard label="Required" value="5" />
          <MetricCard label="% ≥3 (1h)" value={`${str(rates1h.edge_ge_3, "0")}%`} />
          <MetricCard label="% ≥5 (1h)" value={`${str(rates1h.edge_ge_5, "0")}%`} />
          <MetricCard label="% ≥7 (1h)" value={`${str(rates1h.edge_ge_7, "0")}%`} />
          <MetricCard label="% ≥10 (1h)" value={`${str(rates1h.edge_ge_10, "0")}%`} />
          <MetricCard label="Scans (1h)" value={str(hour.n, "0")} />
          <MetricCard label="Incomplete window" value={str(hour.incomplete, "true")} />
        </div>
      </OpsPanel>

      <OpsPanel title="SETUP FAMILIES">
        {Object.keys(families).length === 0 ? (
          <p className="text-[12px] text-[var(--fg-subtle)]">No family histogram yet. Presence is not expectancy.</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {Object.entries(families).map(([name, count]) => (
              <MetricCard key={name} label={name} value={String(count)} />
            ))}
          </div>
        )}
      </OpsPanel>

      <OpsPanel title="SHADOW LAB">
        <p className="mb-3 text-[12px] text-[var(--fg-muted)]">
          SHADOW_ONLY. Cannot send orders or bypass Risk / Safety / OMS.
          Best candidate: {str(shadow.best_expansion_candidate, "INSUFFICIENT SAMPLE")}.
          Promotion never reaches LIVE from this desk.
        </p>
        <div className="space-y-2">
          {candidates.map((c) => (
            <div
              key={str(c.candidate_id, str(c.candidate_name))}
              className="flex flex-wrap items-baseline justify-between gap-2 border border-[var(--border)] px-3 py-2"
            >
              <p className="font-mono text-[12px] text-[var(--fg)]">
                {str(c.candidate_id)} {str(c.candidate_name)}
              </p>
              <p className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
                n={str(c.sample_size, "0")} · {str(c.promotion_status, "INSUFFICIENT_SAMPLE")} ·{" "}
                {str(c.classification, "INSUFFICIENT_SAMPLE")} · OOS={str(c.out_of_sample_result, "INSUFFICIENT_SAMPLE")}
              </p>
            </div>
          ))}
        </div>
      </OpsPanel>

      <OpsPanel title="SHADOW PERFORMANCE">
        <p className="mb-3 text-[12px] text-[var(--fg-muted)]">
          SHADOW_VIRTUAL_TRADE only. Never mixed with STRATEGY_MATCHED or UNMATCHED broker activity.
          would_submit_order=false. ALLOW_LIVE_PROMOTION=false.
          Verdict: {str(shadowVerdict.text, "NO SAFE EXPANSION PROVEN — CONTINUE COLLECTING DATA")}.
        </p>
        <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Observations" value={str(shadowDataset.observations, "0")} />
          <MetricCard label="Virtual open" value={str(shadowDataset.virtual_open, "0")} />
          <MetricCard label="Virtual completed" value={str(shadowDataset.virtual_completed, "0")} />
          <MetricCard label="Sample confidence" value={str(shadowDataset.sample_status, "INSUFFICIENT_SAMPLE")} />
        </div>
        <div className="space-y-2">
          {shadowCandidates.map((c) => (
            <div
              key={str(c.candidate_id, str(c.candidate_name))}
              className="flex flex-wrap items-baseline justify-between gap-2 border border-[var(--border)] px-3 py-2"
            >
              <p className="font-mono text-[12px] text-[var(--fg)]">
                {str(c.candidate_id)} {str(c.candidate_name)}
              </p>
              <p className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
                obs={str(c.observations, "0")} · eligible={str(c.eligible, "0")} ·
                triggered={str(c.triggered, "0")} · completed={str(c.completed, "0")} ·{" "}
                {str(c.win_rate_display, `INSUFFICIENT SAMPLE n=${str(c.completed, "0")}`)} ·{" "}
                {str(c.sample_status, "INSUFFICIENT_SAMPLE")}
              </p>
            </div>
          ))}
        </div>
      </OpsPanel>

      <OpsPanel title="CORE VS EXPANSION">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="CORE n (opp≥70 & edge≥5)" value={str(coreLayer.n, "0")} />
          <MetricCard label="CORE confidence" value={str(coreLayer.sample_status, "INSUFFICIENT_SAMPLE")} />
          <MetricCard label="SHADOW eligible n" value={str(expansionLayer.n, "0")} />
          <MetricCard label="SHADOW confidence" value={str(expansionLayer.sample_status, "INSUFFICIENT_SAMPLE")} />
          <MetricCard label="Overlap" value={str(coreVsExpansion.overlap, "0")} />
          <MetricCard label="Unique expansion" value={str(coreVsExpansion.unique_expansion, "0")} />
          <MetricCard label="Additional opportunities" value={str(coreVsExpansion.additional_opportunities, "0")} />
          <MetricCard label="Merged?" value="NEVER" />
        </div>
        <p className="mt-3 text-[12px] text-[var(--fg-muted)]">
          More signals are not success. Expansion below Opportunity 70 or edge 5 stays
          SHADOW CANDIDATE OPERATES BELOW CORE THRESHOLD. Live gates unchanged.
        </p>
      </OpsPanel>

      <OpsPanel title="SAMPLE CONFIDENCE">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Matched live n" value={String(matchedN)} />
          <MetricCard label="Matched label" value={sampleStatus(matchedN)} />
          <MetricCard label="Shadow completed n" value={str(shadowDataset.virtual_completed, "0")} />
          <MetricCard label="Shadow label" value={str(shadowDataset.sample_status, "INSUFFICIENT_SAMPLE")} />
          <MetricCard label="Walk-forward" value={str(shadowWalk.status, str(report.WALK_FORWARD, "INSUFFICIENT_SAMPLE"))} />
          <MetricCard label="OOS n" value={str(shadowOos.n, "0")} />
          <MetricCard label="Unmatched broker" value={String(unmatchedN)} />
          <MetricCard label="Unmatched in PnL?" value="EXCLUDED" />
        </div>
      </OpsPanel>

      <OpsPanel title="SESSION ANALYSIS">
        <p className="mb-2 text-[12px] text-[var(--fg-muted)]">
          LIVE = STRATEGY_MATCHED. SHADOW = SHADOW_VIRTUAL_TRADE. Filters are not enabled.
        </p>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          {["sydney", "tokyo", "london", "london_ny_overlap", "new_york"].map((name) => {
            const live = asRecord(sessions[name]);
            const sh = asRecord(shadowSessions[name]);
            const liveSt = statusOf(live);
            const shSt = statusOf(sh);
            return (
              <MetricCard
                key={name}
                label={`${name}`}
                value={`LIVE ${displayMetric(live.EXPECTANCY, liveSt)} n=${str(live.sample_size, "0")} · SHADOW ${displayMetric(sh.EXPECTANCY, shSt)} n=${str(sh.sample_size, "0")}`}
              />
            );
          })}
        </div>
      </OpsPanel>

      <OpsPanel title="REGIME ANALYSIS">
        <p className="mb-2 text-[12px] text-[var(--fg-muted)]">
          LIVE vs SHADOW. Regime filters are research-only and not activated.
        </p>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {["TREND", "RANGE", "BREAKOUT", "REVERSAL", "NEWS_VOLATILITY", "LOW_VOLATILITY"].map((name) => {
            const live = asRecord(regimes[name]);
            const sh = asRecord(shadowRegimes[name]);
            const liveSt = statusOf(live);
            const shSt = statusOf(sh);
            return (
              <MetricCard
                key={name}
                label={name}
                value={`LIVE ${displayMetric(live.EXPECTANCY, liveSt)} n=${str(live.sample_size, "0")} · SHADOW ${displayMetric(sh.EXPECTANCY, shSt)} n=${str(sh.sample_size, "0")}`}
              />
            );
          })}
        </div>
      </OpsPanel>

      <OpsPanel title="CONFIG AUDIT">
        <p className="mb-2 text-[12px] text-[var(--fg-muted)]">
          News protection: {str(news.STATUS, str(report.NEWS_PROTECTION_STATUS, "UNKNOWN"))}.
          Duplicate / legacy values are documented. Nothing here changes live gates.
          LIVE_EFFECTIVE={liveCfg.length} · LEGACY={legacyCfg.length} · RESEARCH_ONLY={researchCfg.length} · UNWIRED={unwiredCfg.length}.
        </p>
        <div className="space-y-1">
          {settings.map((row) => (
            <p key={str(row.SETTING)} className="font-mono text-[11px] text-[var(--fg-muted)]">
              {str(row.SETTING)} · live={str(row.LIVE_VALUE)} · source={str(row.SOURCE)} ·
              consumer={str(row.ACTUAL_CONSUMER, str(row.CONSUMER))} ·
              legacy={str(row.LEGACY)} · dup={str(row.DUPLICATED)} · unused={str(row.UNUSED)} ·
              conflict={str(row.CONFLICT)}
            </p>
          ))}
        </div>
      </OpsPanel>

      <OpsPanel title="DIRECTION ANALYSIS">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="BUY" value={str(market.buy_score)} tone="buy" />
          <MetricCard label="SELL" value={str(market.sell_score)} tone="sell" />
          <MetricCard label="LTF BUY" value={str(market.ltf_buy)} tone="buy" />
          <MetricCard label="LTF SELL" value={str(market.ltf_sell)} tone="sell" />
          <MetricCard label="Edge" value={str(market.directional_edge)} />
          <MetricCard label="Required" value={str(market.required_edge, "5")} />
          <MetricCard
            label={`BUY expectancy · ${statusOf(buy)}`}
            value={displayMetric(buy.EXPECTANCY, statusOf(buy))}
            tone="buy"
          />
          <MetricCard
            label={`SELL expectancy · ${statusOf(sell)}`}
            value={displayMetric(sell.EXPECTANCY, statusOf(sell))}
            tone="sell"
          />
        </div>
      </OpsPanel>

      <OpsPanel title="EXECUTION ANALYSIS">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Sniper" value={str(market.sniper_state, "NOT_FIRST_BLOCKER")} />
          <MetricCard label="Risk" value={str(market.risk, "NOT_REACHED")} />
          <MetricCard label="Safety" value={str(market.safety, "NOT_REACHED")} />
          <MetricCard label="OMS" value={str(market.oms, "NOT_REACHED")} />
          <MetricCard label="Execution" value={str(market.execution_status, "NOT_REACHED")} />
          <MetricCard label="Ticket" value={str(market.mt5_ticket, "NONE")} />
          <MetricCard label="Autonomy" value={str(vps.vps_autonomy_status)} />
          <MetricCard label="MT5 recovery" value={str(vps.mt5_reboot_recovery)} tone="warn" />
        </div>
      </OpsPanel>

      <OpsPanel title="WALK-FORWARD">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Walk-forward" value={str(report.WALK_FORWARD, "INSUFFICIENT_SAMPLE")} />
          <MetricCard label="OOS" value={oos} tone="warn" />
          <MetricCard label="n matched" value={String(matchedN)} />
          <MetricCard label="n<20 rule" value="no OOS promotion conclusion" />
        </div>
      </OpsPanel>

      <OpsPanel title="OOS VALIDATION">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="OOS" value={oos} tone="warn" />
          <MetricCard label="Walk-forward" value={str(report.WALK_FORWARD, "INSUFFICIENT_SAMPLE")} />
          <MetricCard label="Best shadow" value={str(shadow.best_expansion_candidate, "INSUFFICIENT SAMPLE")} />
          <MetricCard label="Live expansion" value="NOT AUTHORIZED" />
        </div>
      </OpsPanel>

      <OpsPanel title="EXECUTION HEALTH">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard label="Gateway listeners" value={str(vps.gateway_listener_class)} />
          <MetricCard label="Execution path" value={str(vps.EXECUTION_PATH_READY)} />
          <MetricCard label="Session" value={str(vps.SESSION_VERIFIED)} />
          <MetricCard label="Blind retry" value={str(vps.blind_retry, "DISABLED")} />
          <MetricCard label="OMS" value={str(market.oms, "NOT_REACHED")} />
          <MetricCard label="Ticket" value={str(market.mt5_ticket, "NONE")} />
          <MetricCard label="MT5 recovery" value={str(vps.mt5_reboot_recovery)} tone="warn" />
          <MetricCard label="Risk" value={str(market.risk, "NOT_REACHED")} />
        </div>
      </OpsPanel>

      <OpsPanel title="VPS continuity">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          <MetricCard label="Autonomy" value={str(vps.vps_autonomy_status)} tone="warn" />
          <MetricCard label="MT5 reboot recovery" value={str(vps.mt5_reboot_recovery)} tone="warn" />
          <MetricCard label="Gateway listeners" value={str(vps.gateway_listener_class)} />
          <MetricCard label="Execution path" value={str(vps.EXECUTION_PATH_READY)} />
          <MetricCard label="Session" value={str(vps.SESSION_VERIFIED)} />
          <MetricCard label="Blind retry" value={str(vps.blind_retry, "DISABLED")} />
        </div>
      </OpsPanel>
    </div>
  );
}

# Threshold Sensitivity Report

- Generated at: `2026-07-23T10:01:22.571309+00:00`
- Advisory / statistics only — **live engines and thresholds unchanged**
- Baseline gates (live): Quality **80** · Confluence **80**
- Scored evaluations: **78**
- Average quality: **70.37** · Average confluence: **59.0**

## Quality Gate Sensitivity

_Confluence gate held at baseline 80._

| If Quality Gate | → Execution % | Would execute | Evaluations |
|---:|---:|---:|---:|
| 80 | 24.36% | 19 | 78 |
| 75 | 24.36% | 19 | 78 |
| 70 | 24.36% | 19 | 78 |
| 65 | 24.36% | 19 | 78 |
| 60 | 24.36% | 19 | 78 |

## Confluence Gate Sensitivity

_Quality gate held at baseline 80._

| If Confluence Gate | → Execution % | Would execute | Evaluations |
|---:|---:|---:|---:|
| 80 | 24.36% | 19 | 78 |
| 75 | 25.64% | 20 | 78 |
| 70 | 30.77% | 24 | 78 |
| 65 | 33.33% | 26 | 78 |
| 60 | 33.33% | 26 | 78 |

## Method

Counterfactual score-gate: would_execute iff quality >= quality_gate AND confluence >= confluence_gate. Scores come from unchanged historical replay pipeline; live ITEConfig gates remain 80/80.

This report does **not** lower thresholds, force trades, or modify strategy / risk / safety / OMS / MT5.

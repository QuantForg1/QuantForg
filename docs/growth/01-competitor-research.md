# 1. Competitor and market research

**Access date:** 19 November 2026.  
**Rule:** Prices and product facts below are quoted from the cited page on that date, or marked secondary. Search volumes, traffic, rankings, and user counts are omitted unless the source itself stated them. A vendor’s own user claim is a claim, not an audit.

This is not a ranking of who is “best.” It records positioning so QuantForg can choose gaps it can evidence.

## Market shape

Retail and prosumer trading software splits into five jobs. QuantForg currently sits in the last two, narrowly, on MT5 and XAUUSD.

| Job | What buyers compare | Examples reviewed |
| --- | --- | --- |
| Charting and idea discovery | Screens, alerts, community scripts | TradingView |
| Code-first research and live deployment | Backtest engine, data, broker nodes | QuantConnect |
| No-code rules and AI-assisted strategy drafts | Editor, paper/live automation, price | Composer, parts of TrendSpider |
| US-equity AI signals and scanners | Real-time scans, signal product, broker links | Trade Ideas |
| Retail FX/CFD automation on a broker terminal | EA or cBot, tester, VPS or cloud | MetaTrader 5, cTrader Algo |

Gold-specific “robots” are mostly Expert Advisors sold on broker-terminal marketplaces, not platforms with an evidence record. Those listings were not used as pricing evidence because marketplace claims are promotional and often unverifiable.

## Comparison matrix

Confidence: **H** = official page captured this date. **M** = official page incomplete or heading dropped in extraction. **S** = secondary article, do not republish as QuantForg’s rate card.

| Product | Positioning observed | Who it appears built for | Price evidence | Trial / free | Research / test | Live execution | Trust limit | SEO / acquisition note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TradingView | Multi-market charts, screeners, Pine, social scripts. Page headline claims “100 million traders” — vendor claim only | Discretionary and systematic traders across markets | Official pricing page: Basic $0. Essential special price $12.95/mo. Following blocks showed $29.95/mo and $59.95/mo. Comparison table names Basic, Essential, Plus, Premium, Ultimate. Heading text for the $29.95 and $59.95 blocks was dropped in extraction; sequence matches Plus and Premium. **M** for the name mapping, **H** for the dollar figures that rendered | Free Basic plan | Bar replay, Pine strategies, screeners. AI Copilot listed as a paid add-on on Essential | Broker connections vary; not an MT5 gold-robot host | Large educational and social surface. Not a custody or risk-ceiling product | Dominant informational SEO and YouTube presence. Do not try to out-publish them on generic “how to trade” |
| QuantConnect | LEAN research, backtest, paper and live nodes. Plans are customizable “recommended setups,” not one card price | Quants and firms who write Python/C# | Official pricing page on this date did **not** expose a single dollar price; seats, nodes, and data are configured. A secondary snapshot (DeskTested, 10 Nov 2026) reported Free $0, Researcher $84/mo, Team $168/user/mo (min 2), Trading Firm $480/user/mo, Institution $1,272/user/mo. **S** for dollars. **H** for “price is a configured setup” | Free plan exists on the official table. Live trading nodes on Free are listed as 0 | Full backtest, research nodes, tick data on higher tiers | IB, Alpaca, Tradier, TradeStation, several crypto venues, FX brokerages on paid tiers | Users own IP. Paper trading is a listed paid capability | Documentation SEO. Different buyer from an MT5 gold subscriber |
| Trade Ideas | US stock scanner. Holly AI signals sit in Premium only | Active US equity traders | Official FAQ: Standard $127/mo or $1,068/yr. Premium $254/mo or $2,136/yr. Free web dashboards on 15-minute delayed data. **H** | Free delayed dashboards. No card required for that tier | OddsMaker backtests last 60 trading days, Premium only | Auto trading of the user’s own strategies at IB, E*TRADE, TradeStation, Alpaca on Premium. Money Machine simulator places no live orders | Holly is a signal product with stated entry and stop. OddsMaker window is short | They publish comparison content. Their market is US stocks, not XAUUSD |
| Composer | No-code strategy automation, “Trade with AI” to draft ideas | US-style portfolio automation, not FX EAs | Official pricing: Starter $0, Advanced $10/mo. Pro is a third tier on the same page; the dollar amount was not retained in the capture. A secondary comparison stated Pro $32/mo billed yearly. **H** for $0 and $10. **S** for $32 | Starter includes one automated strategy, limited size, unlimited backtests | No-code backtests | Automated strategies inside Composer’s investing product, not MT5 | Rules are inspectable. Asset list is not gold-CFD | Low price, free start. Weak overlap with MT5 gold |
| TrendSpider | Automated technical analysis, scans, bots, Sidekick messages | Technical traders who want chart work automated | Official pricing page rendered “7 days for $49” and “$74.90/month” on one tier, and “7 days for $29” on Premium. The rest of the card did not render cleanly. **M**. Do not fill the gaps from memory | Paid short trials, not a $0 robot | Backtests and scans are plan-gated | Trading bots are a listed feature; broker coverage was not verified here | Sidekick is an assistant with a message cap | Charting SEO. Overlaps education, not broker-held gold execution |
| MetaTrader 5 | Broker terminal plus MQL5 EAs and Strategy Tester | Retail FX/CFD traders whose broker offers MT5 | Secondary: terminal described as $0 to the trader; spreads, commission, VPS extra ([Offbeat Forex](https://offbeatforex.com/best-algorithmic-trading-software/), accessed 19 Nov 2026). **S** | Terminal use is not a QuantForg-style subscription | Built-in tester, tick and multi-currency claimed by secondary sources | EA runs on the customer’s broker account. Local terminal needs an always-on machine or VPS | Marketplace quality is uneven. Grid and martingale products are common and are the opposite of QuantForg’s public ceiling policy | Huge long-tail SEO around “EA”, “XAUUSD robot”, “MT5”. Much of it is thin or promotional |
| cTrader Algo | C# or Python cBots, cloud run where the broker supports it | Traders who want a modern FX IDE and cloud uptime | cTrader documents cloud hosting for eligible cBots; secondary sources describe that hosting as $0 and broker costs as separate. **S** for the $0 claim. Official FAQ confirms cloud cBots, C#/Python, and that MT5 EAs do not run in cTrader. **H** for product facts from https://ctrader.com/faq/platforms | Platform route is broker-dependent | cBot backtests | Cloud instance rules differ for demo vs live. A secondary source says a demo cloud instance stops after seven days unless restarted | Execution transparency (depth of market) is the usual pitch | Smaller content footprint than MT5. Not QuantForg’s current terminal |

## Feature notes that matter for QuantForg

**Onboarding.** TradingView, Trade Ideas, Composer, and QuantConnect all let a person do something useful before paying the full product. QuantForg lets a person create an account, connect and verify MT5, and view account and research surfaces without a subscription. The robot does not start until a paid plan is active (`UNPAID_ACCESS` in `plans.ts`, and the production homepage on 19 Nov 2026).

**Trust.** Trade Ideas states that its simulator does not place live orders. QuantForg’s homepage states that analysis is not an order, performance comes from the broker’s own history, and sample numbers are not published. That is a stronger public promise than most EA marketing. It is also a constraint: the growth program cannot invent a track record to “catch up.”

**Risk.** QuantConnect and TradingView leave risk policy to the user’s code or broker. QuantForg’s homepage describes platform ceilings the customer can tighten and cannot loosen, a mandatory protective stop, and disabled grid, martingale, and averaging-down. Those are product facts already on https://www.quantforg.com. They are the differentiation. They are not a performance claim.

**Broker integrations.** QuantConnect lists equities, futures, options, and crypto venues. QuantForg’s homepage lists MT5 at Weltrade, XM, Exness, HFM, JustMarkets, IC Markets, Pepperstone, and FP Markets. Listing a broker is not an endorsement and is not an execution-quality ranking.

**Support.** Trade Ideas lists email, chat, and screen share on paid Windows plans. QuantForg’s plan catalog lists email on Starter and priority support on Professional and Premium. No public support SLA was found.

**Weaknesses observed in the category, not claimed as QuantForg victories.**

- Signal products rarely show the conditions that failed.
- EA marketplaces mix high-risk recovery systems with serious research.
- Backtests are often shown without the spread, slippage, and session assumptions.
- “AI” is used for scanners, scorecards, and chat, often without a link to an order record.
- Broker rankings in affiliate articles are commercial, not comparable execution studies.

## Sources

| Source | URL | Used for | Confidence |
| --- | --- | --- | --- |
| TradingView pricing | https://www.tradingview.com/pricing/ | $0, $12.95, $29.95, $59.95 special monthly prices; plan names in comparison table | H for figures; M for Plus/Premium label mapping |
| QuantConnect pricing | https://www.quantconnect.com/pricing | Plan names, free tier, live-node gate, broker list, custom pricing | H for capabilities; dollars not on the captured page |
| DeskTested QuantConnect pricing | https://desktested.com/posts/quantconnect-pricing/ | Dollar snapshot dated 10 Nov 2026 in the article | S |
| Trade Ideas pricing | https://www.trade-ideas.com/pricing/ | $127 / $254 and annual figures, free tier, Holly vs simulator | H |
| Trade Ideas comparison article | https://www.trade-ideas.com/best-ai-trading-software/ | Category map. Their prices for other vendors were not treated as primary | S |
| Composer pricing | https://www.composer.trade/pricing | Starter $0, Advanced $10/mo, Pro feature list | H for $0 and $10 |
| TrendSpider pricing | https://trendspider.com/pricing/ | Partial card only | M |
| cTrader platforms FAQ | https://ctrader.com/faq/platforms | MT5 vs cTrader product facts | H |
| Offbeat Forex algo software | https://offbeatforex.com/best-algorithmic-trading-software/ | MT5 terminal cost description, cTrader cloud note, NinjaTrader/TradeStation mentions | S |
| TickDepo MT5 vs cTrader | https://www.tickdepo.com/blog/mt5-vs-ctrader-automation | Qualitative comparison. Market-share percentages in that article were **not** adopted | S, and unused for statistics |
| QuantForg production homepage | https://www.quantforg.com | Own positioning, broker list, risk language, no-profit language | H as of 19 Nov 2026 |
| QuantForg plan catalog | `frontend/src/lib/billing/plans.ts` | $49 / $99 / $199, unpaid access, no free trial flag | H for the code the site renders |

## What this research does not know

- Organic traffic, keyword rankings, or ad spend for any competitor.
- Whether TrendSpider’s half-rendered prices are the prices a buyer is charged after the trial.
- QuantConnect’s current dollar amount for a default Researcher seat.
- Composer Pro’s official dollar price on this access.
- How many of the named MT5 brokers actually clear QuantForg orders in production. The homepage lists them. This research did not query live gateway status.

# 3. Keyword and SEO opportunity map

**Search volumes, keyword difficulty, and rank positions are not in this document.** No Search Console property, keyword API, or rank tracker is connected to this repository. Inventing those numbers would violate the program. The next measurement step is an owner-authorized Search Console connection. Until then, this is an intent map and a publishing filter.

**Access date:** 19 November 2026.

## How a topic gets a page

A topic is eligible only when all of these are true:

1. A searcher can finish a job QuantForg actually helps with.
2. The page can be written from product behavior, primary documents, or cited sources.
3. A person reviews any sentence about performance, risk, brokers, or regulation before publish.
4. The page is not a synonym swap of another URL.
5. It does not exist to rank for “gold robot profit.”

Google’s scaled-content policy treats large volumes of low-value pages as spam, including pages made with generative tools. Source: https://developers.google.com/search/docs/essentials/spam-policies (accessed 19 Nov 2026). Generative drafts are allowed in the pipeline. Unreviewed financial pages are not. Guidance: https://developers.google.com/search/docs/fundamentals/using-gen-ai-content.

## Intent segments

| Segment | Example queries to investigate later in Search Console | Job to be done | QuantForg page that could earn it | Publish now? |
| --- | --- | --- | --- | --- |
| Brand | QuantForg, QuantForg login, QuantForg pricing | Reach the product | Home, pricing, login | Already exist |
| Commercial investigation | AI trading platform, automated gold trading software, MT5 robot software | Compare approaches and see price | Platform, pricing, “what it does not do” | After a reviewed outline. Do not write “best” |
| Comparison | QuantForg vs MT5 EA, QuantForg vs signal service | Understand the difference | One honest comparison: software with risk ceilings vs a marketplace EA | Only with dated sources and no performance table |
| Transactional | QuantForg plans, subscribe QuantForg | Pay or register | Pricing, register | Exists. Do not add fake urgency |
| Informational | what is XAUUSD, what is slippage, what is a stop loss | Learn a term as this platform uses it | Short glossary tied to how QuantForg checks that thing | First wave, human reviewed |
| Educational workflow | how to connect MT5, why a robot stays flat | Complete setup or interpret silence | Docs mirrored from the homepage’s three steps and eight stages | First wave. The homepage already has the facts |
| Decision intelligence | why did the system wait, trading decision evidence | Trust an automated decision | Product doc pointing at `/decision-evidence` for signed-in users. Public page explains the record shape, not a live call | First wave, no sample trades |
| Risk | automated trading risk management, daily loss limit | See what is enforced | Risk education using the ceiling language already on the homepage | First wave |
| Execution | broker execution quality, spread and slippage | Learn the measures | Education page. No broker ranking | First wave, definitions only |
| Unsupported | best gold robot 2026, guaranteed XAUUSD profit, pass prop firm | Find a promise | None | Never |

## First wave, in order

These topics reuse facts already public on https://www.quantforg.com or already implemented behind login. They do not need new market data.

1. What QuantForg does and does not do.
2. Analysis, signal, and order are different objects.
3. How a protective stop and a daily-loss halt are applied, including the gap limitation already disclosed.
4. How to connect an MT5 account, and that disconnect does not close the broker account.
5. How performance is calculated (broker history, costs included) and why sample P/L is absent.
6. What a decision record contains, and what an empty field means.
7. What shadow or simulated results are, and why they are not account P/L.
8. How spread, slippage, reject, and latency would be read, without naming a winner.
9. Pricing: $199 / $399 / $799, crypto invoice, no automatic renewal charge, robot requires a paid plan.
10. Risk disclosure and who to contact.

## Later wave, only with new evidence

- XAUUSD session notes, if they cite the engine’s actual session logic and a review date.
- Broker connectivity case notes, if they use real aggregated measurements and a sample size.
- Strategy explainers for trend, breakout, mean reversion, momentum, and SMC, only if each section matches what the live engine is allowed to do. The homepage names those setups. A guide must not add entry rules the code does not use.

## International

The site is English, `en_US` in the root metadata. Do not launch locale clones until a market is eligible to be promoted and a person can maintain that language. Translating thin pages into ten languages would trip the scaled-content policy and the country rules in [10-regulatory-matrix.md](./10-regulatory-matrix.md).

## Measurement once Search Console exists

Record, per query cluster: impressions, clicks, CTR, average position, landing URL, date range, and the Search Console property. Do not forecast traffic. Do not promise a rank.

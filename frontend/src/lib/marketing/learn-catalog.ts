/**
 * Public education pages. Copy is limited to behavior already implemented:
 * the marketing site, the billing catalog, and the decision-evidence report.
 * No sample performance, no trial, no invented confidence.
 */

export type LearnFaq = { question: string; answer: string };

export type LearnSection = { heading: string; paragraphs: string[] };

export type LearnPage = {
  slug: string;
  title: string;
  description: string;
  sections: LearnSection[];
  faqs: LearnFaq[];
};

export const LEARN_UPDATED = "19 November 2026";

export const LEARN_PAGES: readonly LearnPage[] = [
  {
    slug: "analysis-versus-order",
    title: "Analysis is not an order",
    description:
      "How QuantForg separates a market reading, a strategy intention, a risk check, and an order sent to your MT5 broker.",
    sections: [
      {
        heading: "Four different events",
        paragraphs: [
          "QuantForg can analyze XAUUSD, record a strategy intention, check risk, and send an order to the MetaTrader 5 account you connected. Those are separate events. A chart reading, an assistant answer, or a BUY or SELL intention is not an executed trade.",
          "Execution still depends on the engine, your risk settings, the platform ceilings, a working broker connection, and you having started the robot. If a risk check fails, the order is not submitted.",
        ],
      },
      {
        heading: "What the desk does, in order",
        paragraphs: [
          "The public product describes eight stages: market scanning, analysis, strategy evaluation, risk validation, order execution, trade management, closure, and a performance review taken from your broker’s history.",
          "Scanning and analysis happen before any order. Risk validation sits in front of execution. A quiet market is allowed to produce no trade.",
        ],
      },
      {
        heading: "What this page does not claim",
        paragraphs: [
          "An analysis is not a prediction of profit. A connected account is not a promise that an order will be accepted by the broker. QuantForg does not hold your funds. Your broker holds the account.",
        ],
      },
    ],
    faqs: [
      {
        question: "If the assistant describes a bullish scenario, is that a buy order?",
        answer:
          "No. The assistant explains and analyzes. Only the robot can trade, and only after you start it, the broker connection is usable, and the risk checks pass.",
      },
      {
        question: "What happens when a risk check fails?",
        answer:
          "A failed check means no order is submitted for that decision. It does not close positions that are already open at your broker.",
      },
    ],
  },
  {
    slug: "stops-and-daily-loss",
    title: "Stops and the daily-loss halt",
    description:
      "Why QuantForg requires a protective stop and a daily-loss halt, and what those checks do not guarantee.",
    sections: [
      {
        heading: "What the checks are for",
        paragraphs: [
          "A new QuantForg order needs a protective stop. The platform also halts new entries when the effective daily-loss threshold is reached. Your own limits can be stricter than the platform ceilings. They cannot loosen those ceilings, and a subscription does not bypass the check.",
          "Spread is checked before an order is submitted. A wide spread blocks the send. Volume is capped by the platform maximum. The autonomous desk’s public trading universe is XAUUSD.",
        ],
      },
      {
        heading: "What a stop does not promise",
        paragraphs: [
          "A stop is an instruction to exit. It is not a guarantee of the price you will be filled at. If the market gaps, a realized loss can exceed the planned amount. Grid, martingale, and averaging-down stay disabled. Those absences are limits, not a claim that losses cannot occur.",
          "This page does not publish private multipliers, lot ceilings, or account settings.",
        ],
      },
    ],
    faqs: [
      {
        question: "Can a plan raise my risk ceiling?",
        answer:
          "No. Starter, Professional, and Premium are software access. A plan cannot make a failed risk check pass.",
      },
      {
        question: "If the daily-loss halt triggers, are open positions closed?",
        answer:
          "The halt stops new entries. Positions already open remain at your broker with the stop and take-profit that were placed. QuantForg does not describe the halt as a guarantee against further loss on those positions.",
      },
    ],
  },
  {
    slug: "decision-record",
    title: "The decision record",
    description:
      "What a QuantForg decision report can show when the engine stored it, and how missing fields stay missing.",
    sections: [
      {
        heading: "A report copies stored evidence",
        paragraphs: [
          "The decision report reads an existing signal record. It does not invent a reason, a confidence score, or a price. If the engine did not store a field, the report says that the field is not available.",
          "When the record has them, the report can include the decision (BUY, SELL, WAIT, HOLD, REJECT, or a recorded block), the instrument, the timestamp, the strategy, a recorded reason, session, price, trend, structure, ATR, spread, market regime, timeframe, and the market-data state.",
        ],
      },
      {
        heading: "Risk and execution stay separate lines",
        paragraphs: [
          "Risk results on the report are copied from the signal record. The report does not recalculate risk and does not replace the risk check that runs before an order.",
          "A BUY or SELL value is a research or strategy decision. It is not proof that an order was sent or filled. An execution outcome appears only when the record contains one, such as an order lifecycle or a ticket.",
        ],
      },
    ],
    faqs: [
      {
        question: "Why is a field blank or marked not available?",
        answer:
          "Because the source record did not contain it. The report is not allowed to fill the gap with an estimate.",
      },
      {
        question: "Is the decision record my broker statement?",
        answer:
          "No. It explains a decision the software recorded. Fills, commission, swap, and net profit come from your broker’s trade history.",
      },
    ],
  },
  {
    slug: "simulation",
    title: "Simulation and broker results",
    description:
      "Why a simulated QuantForg outcome is not your live account profit and loss.",
    sections: [
      {
        heading: "Two records that must not be added together",
        paragraphs: [
          "A simulation asks what a decision would have implied under stated assumptions. Your live result is the history on the MT5 account you connected: entry, exit, commission, swap, and net profit as the broker recorded them.",
          "QuantForg does not publish sample or simulated statistics as customer performance. A simulated row, when the product shows one, has to stay labeled as simulated. It is not added to broker profit and loss.",
        ],
      },
      {
        heading: "Assumptions are part of the result",
        paragraphs: [
          "A simulation depends on the prices, spread, and fill assumptions it was given. Those assumptions can differ from the spread, slippage, and rejects on a live account. The difference is the point of the comparison. It is not a forecast.",
          "Nothing on this page is a track record. QuantForg does not promise that a simulated path will repeat.",
        ],
      },
    ],
    faqs: [
      {
        question: "Where do live results come from?",
        answer:
          "From your broker’s own trade history after a real order. QuantForg does not custody the account and does not replace the broker statement.",
      },
      {
        question: "Can I treat a simulation as proof the robot is profitable?",
        answer:
          "No. A simulation is a hypothetical record. It is not live account performance, and this site does not publish example profits.",
      },
    ],
  },
  {
    slug: "decision-lifecycle",
    title: "What a decision word means",
    description:
      "How QuantForg uses BUY, SELL, WAIT, ORDER_SENT, FILLED, and NOT_REACHED, and why a missing history field stays missing.",
    sections: [
      {
        heading: "A decision word is not a fill",
        paragraphs: [
          "BUY and SELL on a decision report are recorded research or strategy intentions. WAIT, HOLD, and NO_TRADE are recorded decisions to stand aside. EXECUTION_BLOCKED is a recorded block. None of those words means the broker filled an order.",
          "ORDER_SENT means the record says an order was sent. It is not a fill. FILLED is the only lifecycle word this report treats as an executed order, and only when the stored lifecycle says so. A ticket number is shown only when the record contains one.",
        ],
      },
      {
        heading: "NOT_REACHED is not a pass",
        paragraphs: [
          "If the risk or safety gate on the record is NOT_REACHED, the check was not performed for that decision. The report does not rewrite that into a pass, and it does not calculate a replacement risk value.",
          "When the record has no risk limit attached, the report says the limit is not available. A limit from today’s settings is not shown as the limit that applied to an older decision.",
        ],
      },
      {
        heading: "Older rows are thinner on purpose",
        paragraphs: [
          "Signal history stores fewer fields than the current live signal. If an older row has no ATR, spread, risk gate, or ticket, those lines stay unavailable. QuantForg does not fill them from the current gold price or from a later cycle.",
        ],
      },
    ],
    faqs: [
      {
        question: "Does ORDER_SENT mean the trade made money?",
        answer:
          "No. ORDER_SENT is not FILLED, and neither word is a profit figure. Broker profit and loss come from the broker’s own history.",
      },
      {
        question: "Why can today’s signal show a spread when yesterday’s row does not?",
        answer:
          "Because the historical record did not keep that field. The report does not copy the current quote backward.",
      },
    ],
  },
  {
    slug: "mt5-and-broker-history",
    title: "MT5 connection and broker history",
    description:
      "How a QuantForg account relates to the MT5 broker account you choose to connect, and where live results come from.",
    sections: [
      {
        heading: "The broker still holds the account",
        paragraphs: [
          "QuantForg is software for XAUUSD on MetaTrader 5. Customer funds stay at the broker. This guide does not collect a broker password, and connecting a broker is a separate action you take in the broker screen.",
          "Closing this website does not close a position at the broker. An open position remains on the MT5 account, with whatever stop or take-profit was already placed there.",
        ],
      },
      {
        heading: "Live results are the broker’s history",
        paragraphs: [
          "A number that counts as account profit or loss comes from the broker’s own trade history: entry, exit, commission, swap, and net result as that account recorded them.",
          "A decision report, a chart, and a simulation are not that history. They are not added to it.",
        ],
      },
    ],
    faqs: [
      {
        question: "Does reading this page connect my broker?",
        answer:
          "No. Nothing on this page starts a connection or sends an order. Broker connection stays on the broker screen, and only when you choose it.",
      },
      {
        question: "If QuantForg is closed, what happens to an open trade?",
        answer:
          "The trade remains at the broker. This page does not claim that a stop will fill at a particular price.",
      },
    ],
  },
  {
    slug: "spread-slippage-and-rejects",
    title: "Spread, slippage, and rejects",
    description:
      "What those words mean on QuantForg, and why this page does not rank a broker.",
    sections: [
      {
        heading: "A wide spread can block a new order",
        paragraphs: [
          "Before a new order is sent, QuantForg checks the spread. If the spread is too wide for the existing rule, the order is not submitted. That check is a gate. It is not a measurement of a broker’s average spread, and this page does not publish one.",
        ],
      },
      {
        heading: "Slippage and a reject are broker outcomes",
        paragraphs: [
          "Slippage means the filled price can differ from the price you saw when the order was sent. A gap can make a loss larger than the planned stop. A reject means the broker did not accept the order. Neither word is a profit figure.",
          "QuantForg does not rank brokers here, and it does not show a sample slippage statistic. If a live measurement is not stored, the product should say it is unavailable rather than substitute zero.",
        ],
      },
    ],
    faqs: [
      {
        question: "Does a passed spread check guarantee the fill price?",
        answer:
          "No. The spread check decides whether an order may be sent. The broker’s fill can still differ from the requested price.",
      },
      {
        question: "Where would a real reject count come from?",
        answer:
          "From the broker or gateway record of that order. This page does not invent a reject rate.",
      },
    ],
  },
] as const;

export function learnPath(slug: string): string {
  return `/learn/${slug}`;
}

export function getLearnPage(slug: string): LearnPage | undefined {
  return LEARN_PAGES.find((page) => page.slug === slug);
}

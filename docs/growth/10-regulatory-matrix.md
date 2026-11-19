# 10. Regulatory and advertising restrictions

**This is a research note for operators. It is not legal advice, not a license opinion, and not a conclusion that QuantForg may or may not market in a country.** Approval or silence in one country does not travel. A lawyer in the target country has to apply the firm’s actual activity: software vendor, signal publisher, investment advice, broker solicitation, or some mix.

**Access date:** 19 November 2026.

## Rules that showed up repeatedly

| Topic | What the source requires | Source |
| --- | --- | --- |
| UK financial promotions | The FCA regulates promotions for many investments, including CFDs. Promotions must be fair, clear, and not misleading. A website or a social post can be a promotion | https://www.fca.org.uk/firms/financial-promotions-adverts |
| UK retail CFD marketing | Firms that market leveraged CFDs, spread bets, or rolling spot forex to retail clients must use the standardised risk warning, including the provider’s own loss percentage. Leverage caps, margin close-out, negative-balance protection, and a ban on monetary inducements are part of the CFD regime for those firms | https://handbook.fca.org.uk/handbook/cobs22/cobs22s5 and https://www.fca.org.uk/publications/policy-statements/ps19-18-restricting-contract-difference-products |
| UK mainstream investments | “Capital at risk” is not a universal required phrase. The promotion still has to give a balanced picture. Image-only brand advertising is treated differently from a product promotion | https://www.fca.org.uk/firms/risk-warnings-mainstream-investments |
| Google Ads, financial products | Disclosures must be visible without a click: physical address of the business, associated fees, and proof of any claimed accreditation. Advertisers follow the law of every targeted location | https://support.google.com/adspolicy/answer/2464998?hl=en |
| Google Ads, complex speculative products | CFDs, spread bets, and rolling spot forex may be advertised only by a licensed provider or aggregator, only in eligible locations, only in line with local law, and only after Google certification. **Ad destinations that provide signals, tips, or speculative trading information are disallowed.** Examples include signal sites and affiliate sites with broker reviews | https://support.google.com/adspolicy/answer/15188218?hl=en |
| Google country list | The policy page lists specific countries and an “Other” bucket. Chile and Denmark were called out in an October 2026 update as additions, each with its own licensing body | https://support.google.com/adspolicy/answer/15188218?hl=en and https://support.google.com/adspolicy/answer/18546412?hl=en |
| Search spam | Scaled low-value pages, including generative pages that do not help users, can be dropped from Search. Third-party content published to borrow a site’s rankings can be site-reputation abuse | https://developers.google.com/search/docs/essentials/spam-policies |
| Generative content | AI may help research and structure. Financial and metadata claims need a person to check them before publish | https://developers.google.com/search/docs/fundamentals/using-gen-ai-content |

QuantForg’s public product is software that analyzes gold and can send orders to the user’s MT5 broker, plus an assistant. A strict reading of Google’s examples puts “signals” and “gold robot” landing pages in the disapproved destination category even before the license test. **Paid search for the current homepage is not a safe default.** Organic pages that educate and do not urge a CFD trade still need a local-law review before they are aimed at a country.

## Country matrix

“Google eligible” means the country appears on Google’s complex-speculative location list as captured on 19 Nov 2026. It does **not** mean QuantForg may advertise there. “Organic” means a public English page might be visible; it does not mean the promotion is lawful.

| Market | Google complex-speculative ads | Local gate cited | Organic site | Operating stance until counsel says otherwise |
| --- | --- | --- | --- | --- |
| United States | On the eligible list, with limitations and certification | Retail forex is a regulated activity for the firm that deals it. This research did not review CFTC/NFA registration against QuantForg’s facts | Visible | No paid ads. No statement that the product is offered to US retail forex customers |
| United Kingdom | On the list. Certification. FCA-related license tests are on the policy page | Financial promotions regime. CFD risk warning if the activity is in that regime | Visible | No UK-targeted ads. Do not use the FCA warning with a made-up loss percentage. That percentage is the provider’s own figure |
| EEA examples on Google’s list (Austria, Bulgaria, Croatia, Cyprus, Czechia, Denmark, Estonia, Finland, Germany, Greece, Hungary, Iceland, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Norway, Poland, Portugal, Romania, Slovakia, Slovenia, Sweden) | Allowed with limitations. EEA license, leverage caps, risk warnings, Google certification | National authority plus ESMA-style retail CFD limits where they apply to the firm | Visible | Treat each country separately. Do not geo-target the set |
| Australia | On the list, with limitations | ASIC’s CFD rules apply to CFD issuers. Not reviewed against this product | Visible | No AU-targeted ads |
| Singapore, Hong Kong, Japan, UAE, Switzerland, Canada, New Zealand, South Africa, and the other named countries on the Google page | On the list only with the license the policy names for that country | Each policy row names a regulator | Visible | No paid ads |
| Everyone else, including Google’s “Other” | Not an approval | Unknown | The site is on the public internet | Do not buy ads. Do not translate the site into that market |

The full Google list captured in search on this date also included Brazil, Chile, Indonesia, Israel, Kenya, Malaysia, Russia, Taiwan, Türkiye, and the United States, among others. Use the live policy page before any campaign. The list changes. Chile and Denmark were updated in October 2026.

## Other obligations the growth system must leave room for

| Topic | Stance |
| --- | --- |
| Affiliate disclosure | Any paid referral is labeled on the page that receives the click |
| Privacy and consent | The privacy policy of 8 Nov 2026 is the current public notice. Analytics and email need a basis that notice actually describes. Do not add trackers in a growth patch |
| Email | Consent and an unsubscribe path before any newsletter. Service mail about an invoice is not a newsletter |
| Cookies | A consent banner is a product change. Do not add non-essential cookies until the notice and the banner match |
| Data protection | Customer broker data stays in the existing tenancy model. Growth aggregates do not copy it out |
| Performance advertising | “Past results” pages are not allowed without a real, reviewed record. There is no such public record |
| Testimonials | Only with permission and the underlying evidence. None are cleared |
| Risk warning on site | `/risk-disclosure` exists and says capital can be lost. Keep it linked from commercial pages |

## Kill switch for ads

Until a certification record and a country memo exist, the ads kill switch is **stopped**, and there is no ad account integration to turn on. Building the integration is a later Level 3 project, not part of Phase 0.

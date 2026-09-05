# Real aggregator T&Cs — summaries + key clauses

These are **summaries and key verbatim excerpts** of the publicly-available terms and conditions from Indian gig-work platforms, gathered on 2026-09-05 via WebFetch of each platform's official public T&Cs page. The full pages summarize aggressively when fetched programmatically, so what lives here is not the verbatim gazetted text — it is a fair reference of the clause patterns each platform uses.

## Sources

| Platform | URL fetched | Key quotes captured |
|----------|-------------|---------------------|
| **Zomato (Runnr)** — Delivery Partner T&Cs | https://www.runnr.in/delivery-partner-tandc.html | Independent contractor status, 16 termination grounds, INR 10,000 liability cap, IP ownership |
| **Uber India** — Driver / Rider general ToU | https://www.uber.com/in/en/legal/general-terms-of-use/ | Independent contractor status, €500 liability cap, mandatory arbitration under Arbitration and Conciliation Act 1996, "AS IS" service |
| **Rapido** — Captain Terms (Bikes + Auto/Cab) | https://www.rapido.bike/CaptainTerms | Independent contractor, 12-hour daily cap with 10-hour break, INR 1000 aggregate liability, arbitration in Bangalore |
| **Zepto** — Delivery Partner Service Agreement | https://www.zepto.com/s/de-agreement | Referenced but WebFetch could not extract; page requires client-side rendering |
| **Swiggy** — Delivery Partner Agreement | Referenced widely | 30-day notice period from delivery partner, no notice from Swiggy, no brand-usage rights, discretionary commission rates |

## Use in QA

These serve as reference — the pipeline should classify each into `contract_type = "aggregator"` and should surface risk-tier annotations that match the character of these contracts:

- Zomato / Rapido / Swiggy → many red-tier clauses (unilateral termination, low liability caps, broad indemnification, discretionary rates)
- Uber → many red-tier clauses + jurisdiction/arbitration foreign to worker
- Urban Company → mixed (better welfare, still contractor framing)

## Where the actual contract samples live

The hand-crafted stress-test contracts in `data/qa_contracts/stress/` cover every clause pattern present in these real T&Cs, plus edge cases the real T&Cs do not systematically test. Use those for pipeline QA, not these summaries.

The synthetic PNG samples in `data/qa_contracts/synthetic/` are the OCR-path exercises — full contract pages in Hindi, Bengali, and Tamil that stress the EasyOCR + downstream pipeline together.

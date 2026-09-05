# Rights Guide — Content Draft (v0.1)

**Status:** DRAFT — awaiting your review before it lands in a migration.
**Bind to:** [`RIGHTS_GUIDE_CONTENT_GUIDELINES.md`](RIGHTS_GUIDE_CONTENT_GUIDELINES.md)
**Author:** Surajit Chaudhuri
**Date:** 2026-08-23

---

## Multilingual rollout plan

- **English is canonical.** Every card is authored, cited, and legally
  reviewed in English first.
- **Hindi, Bengali, Tamil ship in v0.1** using Sarvam Mayura via the
  existing [`app/translate`](../app/translate) service, with the idiom
  library ([`app/idioms`](../app/idioms)) applied.
- **Publication gate.** English seeds at `is_active = true`. Each
  translation seeds at `is_active = false` and only flips to `true`
  after a native speaker has run the [content review
  checklist](RIGHTS_GUIDE_CONTENT_GUIDELINES.md#content-review-checklist-per-card-per-language).
- **UI behaviour.** The Rights Guide list on `/rights` only shows
  cards where `is_active = true` for the worker's selected language.
  Until Hindi is reviewed, a Hindi-preference worker sees a language
  switcher note ("Available in English while we finish translation
  review"), not a broken Hindi card.

---

## Card 1 — Minimum wage protection for gig workers

**Topic key:** `minimum_wage`
**Icon:** `IndianRupee`
**Sort:** 10

### Title
Minimum wage protection for gig workers.

### Summary
Central and state minimum wage laws have historically applied to
formal employees. Platforms have argued that gig workers are
"partners" rather than employees, keeping the Minimum Wages Act 1948
at arm's length.

The Code on Social Security 2020 changed the framing. Sections 113
and 114 create the category "platform-based gig worker" and mandate a
national social security fund. This does not automatically bring gig
workers under the Minimum Wages Act, but it establishes a legal basis
for state-level welfare schemes with floor-price protections.

Karnataka and Rajasthan have operational welfare boards. These boards
are the practical route to state-mandated benefits today. Other
states are drafting similar legislation.

### Citation
Code on Social Security, 2020 (Act No. 36 of 2020), Sections 113-114.
Ministry of Labour and Employment, Government of India.
[Gazette PDF](https://labour.gov.in/sites/default/files/ss_code_gazette.pdf).

### Action steps
1. **Register on e-Shram.** The portal issues a Universal Account
   Number that unlocks central welfare schemes. Registration is free.
   [eshram.gov.in](https://eshram.gov.in)
2. **Check your state welfare board.** Karnataka and Rajasthan have
   gig-worker-specific boards. Search "[your state] gig workers
   welfare board" for the office in your state.
3. **Call India Labourline.** For any complaint about wage theft or
   pay that is lower than what your agreement documents. Phone:
   1800-419-1550.

---

## Card 2 — Injury while working on a platform

**Topic key:** `injury_on_the_job`
**Icon:** `HeartPulse`
**Sort:** 20

### Title
Injury while working on a platform.

### Summary
Traffic and workplace injuries are a documented risk for delivery
riders, cab drivers, and gig workers in trades. Research from the
Ola Mobility Institute on working conditions of delivery workers
records heat exhaustion and road-safety incidents as common
occurrences.

Aggregator platforms may offer accident insurance, typically
underwritten by IRDAI-registered insurers. Coverage terms are set by
the platform's policy document, which the worker is entitled to see.
The Ministry of Road Transport and Highways amended the Central
Motor Vehicles Rules in 2024 to place explicit responsibility on
aggregators for driver welfare, including safety training and
insurance obligations.

The Employees' State Insurance Corporation (ESIC) provides medical
and cash benefits to covered employees. Whether a gig worker
qualifies under ESIC depends on the classification question that is
actively being litigated. State welfare boards (Karnataka, Rajasthan)
run separate accident schemes for platform-based gig workers.

### Citation
Central Motor Vehicles Rules, 2024 amendment. Ministry of Road
Transport and Highways. Code on Social Security, 2020 (Act No. 36 of
2020), Chapter IX (ESIC provisions).

### Action steps
1. **Ask the platform for the insurance policy document.** It is
   your right to see the coverage terms. Keep a copy in a place you
   can find later.
2. **Register on e-Shram.**
   [eshram.gov.in](https://eshram.gov.in) — some accident-related
   benefits attach to registered workers.
3. **Call India Labourline.** For guidance on filing under state
   welfare board schemes or ESIC where applicable. Phone:
   1800-419-1550.

---

## Card 3 — How to file a grievance about platform work

**Topic key:** `grievance_escalation`
**Icon:** `MessageSquareWarning`
**Sort:** 30

### Title
How to file a grievance about platform work.

### Summary
Every gig worker has multiple parallel routes to escalate a grievance
about pay, safety, dismissal, or platform policy. These are not
mutually exclusive channels. Most disputes benefit from starting with
the platform's own customer support so there is a documented ticket
history, then escalating to statutory authorities.

The Ministry of Labour and Employment operates India Labourline, a
national helpline for labour issues. State Labour Commissioners
handle wage disputes and workplace grievances at the state level. The
e-Shram grievance cell handles issues related to registration and
central welfare schemes.

For workplace harassment, the Sexual Harassment of Women at Workplace
(Prevention, Prohibition and Redressal) Act 2013 requires most
workplaces to have an Internal Committee. The Act's application to
gig work is being tested; the aggregator platform's own Internal
Committee is a starting point for complaints against platform staff.

### Citation
Sexual Harassment of Women at Workplace (Prevention, Prohibition and
Redressal) Act, 2013. Ministry of Women and Child Development. India
Labourline, Ministry of Labour and Employment.

### Action steps
1. **Start with the platform's in-app support.** Document the ticket
   number, the exact time you filed, and every response. Screenshots
   are the strongest evidence for later escalation.
2. **Call India Labourline.** 1800-419-1550. National helpline;
   guides workers on the next escalation step based on the specific
   complaint.
3. **File with your State Labour Commissioner.** Search "[your
   state] labour commissioner" for the office contact. Every state
   has one.

---

## Card 4 — e-Shram registration for gig workers (NEW)

**Topic key:** `e_shram_registration`
**Icon:** `BadgeCheck`
**Sort:** 40

### Title
e-Shram registration for gig workers.

### Summary
e-Shram is the central government's registry of unorganised workers,
launched in 2021 by the Ministry of Labour and Employment. Over 30
crore workers were registered on the portal as of 2024.

Registration is free. It issues each worker a Universal Account
Number (UAN), a 12-digit identifier that ties together central welfare
scheme eligibility. State welfare boards and future gig-worker
schemes reference this UAN.

Gig workers are explicitly recognised on the e-Shram portal following
the Code on Social Security 2020's category recognition. Registration
on e-Shram is typically a prerequisite for state welfare board
benefits (Karnataka, Rajasthan) and for central schemes like PM
Suraksha Bima Yojana.

### Citation
e-Shram portal, Ministry of Labour and Employment, Government of
India. [eshram.gov.in](https://eshram.gov.in).

### Action steps
1. **Register on e-Shram.** The portal requires an Aadhaar-linked
   mobile number. Registration takes about 10 minutes.
   [eshram.gov.in](https://eshram.gov.in)
2. **Keep your UAN safe.** You will need it for state welfare board
   applications and for many scheme applications later.
3. **Never pay a fee.** Registration is entirely free. Refuse anyone
   who asks for money to "help" you register.

---

## Card 5 — How to read a platform contract (NEW)

**Topic key:** `contract_fairness`
**Icon:** `FileText`
**Sort:** 50

### Title
How to read a platform contract.

### Summary
Platform agreements often run 40 to 90 clauses, drafted by the
platform's legal team. Fairwork India, a research collaboration led
by IIIT-Bangalore and the University of Oxford, has published annual
ratings of major Indian gig platforms since 2020 across five
principles: fair pay, fair conditions, fair contracts, fair
management, and fair representation.

The "fair contracts" principle asks whether workers can access the
agreement they signed, whether it is in a language they can read,
and whether unilateral changes give them meaningful notice. These are
the same signals a worker can look for in their own agreement.

Sreshtha's Contract Reader (available on this account) walks through
a contract clause by clause in the worker's language, flags
unfavourable terms with a colour code, and notes when a clause
references or contradicts Indian labour statutes.

### Citation
Fairwork India, Annual Ratings of Digital Labour Platforms in India.
IIIT-Bangalore and University of Oxford.
[fair.work/en/ratings/india/](https://fair.work/en/ratings/india/).

### Action steps
1. **Use Contract Reader.** Upload your platform agreement (PDF or
   phone photo) and get a clause-by-clause explanation in your
   language.
2. **Ask for a copy in writing.** If your platform has never given
   you a downloadable copy of your agreement, ask their customer
   support in-app. Save the screenshot of your request.
3. **Read Fairwork India's latest India report.**
   [fair.work/en/ratings/india/](https://fair.work/en/ratings/india/)
   — see how the platforms in your city rate.

---

## Rendered footer (auto-appended by UI, not per-card)

Every fact card detail page, in every language, ends with:

> **Not legal advice.** This page shares publicly documented
> information about your rights under Indian law. It is not legal
> advice. For formal help, call **India Labourline: 1800-419-1550**.

And a persistent list-page header:

> Rights Guide gives you plain-language summaries of laws and schemes
> that apply to Indian gig workers, with citations to the source. It
> is not legal advice. Call India Labourline (1800-419-1550) for
> formal help.

---

## Review asks — please confirm before I code the migration

1. **Card 2 (injury)** — I have deliberately not stated any benefit
   amounts or claim procedures. Is that safe enough, or do you want
   me to strip even the mention of ESIC / state welfare board
   accident schemes and route entirely to Labourline?

2. **Card 5 (contract fairness)** — this card promotes Contract
   Reader as an action step. Is that acceptable cross-module
   marketing, or should Contract Reader stay out of the Rights Guide
   copy?

3. **Statute references** — I have used numeric section numbers
   (Section 113, Section 114) rather than descriptive titles. Confirm
   this is the format you want.

4. **The Sexual Harassment Act** — Card 3 mentions it because the
   PRD's harassment topic was folded into grievance escalation for
   v0.1. If you would rather cut this reference (since gig-work
   application is legally ambiguous), tell me and I'll remove it and
   route harassment complaints purely to Labourline + platform IC
   without naming the Act.

5. **Translation timing** — English seeds active on Day 10; Mayura
   produces Hindi / Bengali / Tamil at `is_active = false`; those
   flip to true only after your native-speaker review. Confirm this
   ordering.

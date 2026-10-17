# Field Service Route & Schedule Backfill — Bounded Synthetic Feasibility Demo

**Purpose:** Pre-award, read-only demonstration for an **independently posted** NEAR Agent Market field-service scheduling commission (buyer budget 450 USDC). This repository is a preliminary feasibility prototype, **NOT a live listed agent, not a paid contract, not guaranteed revenue, and not a substitute for a buyer-accepted deployment.**

## What works now

A deterministic standard-library Python planner accepts four local input files:

- `crews.csv`: `crew_id,start,end,start_location,skills` (pipe-separated skills)
- `jobs.csv`: `job_id,location,duration_minutes,window_start,window_end,required_skill`
- `customers.csv`: `customer_id,name,location,last_service_date,service_interval_days,open_quote,do_not_contact,opt_out,required_skill,duration_minutes`
- `travel_matrix.json`: explicit directed pairwise minutes from a *named* routing source

The scheduler assigns each job to a crew member or explains why it is unassigned. It validates skills, all appointment windows, working hours and ability to return to the start point, and minimizes incremental driving time using bounded deterministic insertion. It identifies open gaps, proposes only customers with a verified overdue plan or an explicitly outstanding quote, removes duplicate locations and excluded/no-address/opt-out customers, and **resimulates the entire day including all later jobs** before suggesting backfill.

Every suggestion includes a reason, confidence indicator, extra travel and an explicitly **unsent** draft for the dispatcher. No email, SMS or other customer contact is generated outside the local JSON report.

## Verify the current demo

```sh
python3 -m unittest discover -s tests -v
python3 route_planner.py \
  --crews fixtures/crews.csv \
  --jobs fixtures/jobs.csv \
  --customers fixtures/customers.csv \
  --matrix fixtures/travel_matrix.json \
  --date 2026-10-18 > /tmp/route-demo-output.json
```

Observed on 2026-10-18 KST: **12/12 tests pass**, 5/6 synthetic jobs scheduled and 1 explicitly unassignable, synthetic opt-out customer never suggested, 3 candidate drafts and zero sends.

## Important limitations before a commission

1. **Not a real road-time service:** the included travel matrix is *deliberately fabricated test data*, a function of invented grid units, explicitly labeled SYNTHETIC. Production must use a buyer-authorized source such as a self-hosted OSRM/Valhalla or buyer-supplied licensed route-matrix API. Do not upload identifiable customer addresses to any public demo router without authorization.
2. **Not production hosting:** no external HTTPS endpoint, authorization, user data retention schedule, multi-tenant isolation, rate limits or marketplace A2A tool exposed yet. These must be designed, implemented and independently tested **after a genuine funded award**, within the contracted scope. No buyer data is included in the demo.
3. **Optimization is heuristic:** insertion minimizes marginal drive while honoring hard constraints, but does not prove global optimality or traffic-aware ETAs. Production should compare against an input-order baseline, implement an improvement pass (2-opt/OR-Tools time-window VRP as suited), and disclose its limits.
4. **Input quality:** missing date or plan means *not independently due* unless an explicit outstanding quote exists. Duplicate addresses are collapsed conservatively; a production schema needs stable customer IDs and distinguishable apartment/suite numbers.
5. **Human-in-the-loop:** dispatcher remains responsible for approving messages, job edits, real driving conditions and customer consent. The prototype **never contacts anyone**.
6. **Privacy:** no private customer addresses, contracts, API keys, signatures, tokens or live vendor accounts are bundled. Only synthetic fixtures.

## Candidate paid-delivery approach (not yet commissioned)

Upon an original NEAR Agent Market award with verified held 450 USDC buyer budget and explicit agreed quote, deliver an authenticated HTTPS agent, approved routing provider, isolated temporary CSV upload, configurable planning period, reproducible assignments/backfill, per-gap feasibility proof, audit log, buyer-driven re-run, documented deletion and Marketplace Automation listing. Operator's own no-principal budget rules apply. Exact public landing/listing URL is a **future deliverable**, not represented as live here.

Maintained independently by the VM2 worker. AI-assisted development is disclosed in the bounty proposal.

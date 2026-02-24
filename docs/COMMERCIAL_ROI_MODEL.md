# Commercial ROI Model (Pilot-to-Subscription)

This is a practical, auditable way to answer:

- what cost share we affect,
- how much we can save,
- whether pricing is justified.

## Cost Structure (Bottom-up)

Treat site-level pest-control cost as four buckets:

1. External service and call-out work
2. Consumables and hardware replacement
3. Internal labor for planning/repositioning/handover/reporting
4. Loss/risk events (contamination, stock loss, compliance disruption)

BioPath's near-term measurable impact is strongest in bucket 3, then bucket 1.

## Quantifiable Savings Formula

Define:

- `n_visit`: visits per year
- `t_visit`: hours per visit (planning + on-site placement decisions)
- `t_rework`: annual rework/handover hours
- `c_hour`: blended labor cost per hour
- `r_time`: time reduction ratio from reproducible optimization workflow

Then:

- `annual_saving = (n_visit * t_visit + t_rework) * c_hour * r_time`

Use conservative ranges for early-stage communication (`r_time` often 0.15 to 0.30 pre-calibration).

## Pricing Anchor

A simple stage-safe anchor sentence:

- "If we save ~1 technician day per month in re-positioning, handover, and audit reporting, subscription economics are already defensible."

## Packaging Guidance

To reduce pricing friction, keep three packaging lanes:

- Operator plan (primary): multi-site usage through pest-control operators
- Farm group plan: multi-site enterprise farm operations
- Single-site pilot: conversion entry with evidence generation

Operator plans generally improve ROI because software cost can be spread across client sites.

## Evidence Requirements Before Hard Claims

Before making strong risk-loss claims, collect pilot evidence for:

- baseline labor time per visit
- rework frequency
- incident frequency (if available)
- pre/post comparison over fixed horizon

Use `run_id`-tied artifacts as traceable evidence in commercial conversations.

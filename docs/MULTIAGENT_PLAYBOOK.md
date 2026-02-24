# BioPath Multi-Agent Playbook (OpenClaw + Codex)

This playbook is for parallelizing BioPath work safely and merging with low conflict risk.

## Objective

Run multiple Codex agents in parallel, each with a narrow scope, then merge into one integration branch with reproducible checks.

## Recommended Agent Split

- Agent A: solver/API logic (`biopath/`, `api/`, `scripts/run_benchmark.py`)
- Agent B: site UX and pitch content (`site/`)
- Agent C: docs and reproducibility (`README.md`, `SPEC.md`, `TECH_REPORT.md`, `docs/`)
- Agent D: regression/tests and release checks (`tests/`, publish validation)

## Branching Pattern

Create one integration branch and one branch per agent:

```bash
git checkout -b codex/integration-proof

git checkout -b codex/agent-a-solver
git checkout -b codex/agent-b-site
git checkout -b codex/agent-c-docs
git checkout -b codex/agent-d-qa
```

## Task Contract for Each Agent

Each agent must deliver:

1. Focused diffs in assigned paths only.
2. Short change note with assumptions.
3. Reproduction commands used.
4. Test results for touched components.

## Merge Order

1. Merge solver/API first.
2. Merge site second.
3. Merge docs third.
4. Merge QA fixes last.

Reason: docs and QA should converge on final behavior, not intermediate behavior.

## Conflict Control Rules

- Do not let multiple agents edit the same file unless explicitly planned.
- Keep numeric claims in pitch pages tied to latest published artifacts.
- If two agents need `site/data/latest*`, only QA agent updates those files at the end.

## Final Integration Checklist

```bash
python3 scripts/run_benchmark.py \
  --map site/data/cambridge-photo-informed-map.json \
  --k 6 --objective capture_prob --mc-runs 140 --time-horizon-steps 48 --seed 7 \
  --baseline-mode heuristic --baseline-samples 40

bash scripts/publish_site.sh
python3 scripts/sync_pitch_from_latest.py
python3 -P -m pytest -q tests
```

Consistency gate:

- `site/data/latest.json` run_id == `site/data/latest-benchmark.json` run_id
- `site/data/latest-summary.md` corresponds to that same run
- pitch numbers match published benchmark values

## Suggested OpenClaw Prompt Seed

Use one short prompt per agent, for example:

- Agent A: "Implement solver/API changes only; no site copy changes."
- Agent B: "Update site pitch text and UI safeguards; no algorithm changes."
- Agent C: "Align SPEC/TECH docs with current implementation; add reproducibility docs."
- Agent D: "Run regression checks, refresh curated artifacts, verify run_id consistency."

This keeps responsibilities clear and mergeable.

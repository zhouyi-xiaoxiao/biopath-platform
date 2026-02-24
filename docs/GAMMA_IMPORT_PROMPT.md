# Gamma Import Prompt (BioPath 10-min Pitch)

Use this prompt in `gamma.app` to generate a professional bold deck:

```text
Create a 10-slide investor-style pitch deck in English for "BioPath".
Audience: mixed judges + potential pilot customers.
Tone: scientific credibility + practical commercial execution.
Visual style: professional bold, clean, high contrast, no purple theme.

Core message:
BioPath is decision-support software that takes a farm layout and outputs optimized rodent trap placement coordinates, then validates performance with Monte Carlo benchmarking versus random placement.

Must include these sections:
1) Title + one-liner value proposition.
2) Chosen delivery plan: 7 min narrative + 2 min live demo + 1 min ask.
3) Problem: manual trap placement is inconsistent and inefficient.
4) Technical implementation: map representation, optimization objective, Monte Carlo validation, API + web stack.
5) Cambridge synthetic layout image (placeholder).
6) Optimization heatmap with traps (placeholder).
7) Proof metrics:
   - robust score 0.5167
   - random baseline mean 0.2933
   - uplift +0.2233 absolute (+76.1% relative)
8) Market + business + funding context: farms + pest control operators, pilot-first model, Cambridge farm funding application in progress.
9) Explicit mapping to 5 judging criteria:
   - Clarity of communicating idea
   - Market and customer understanding
   - Appropriateness of business model
   - Logic of deck and presentation quality
   - Robustness and reality of finance
10) Ask: 2 pilot introductions + small PoC budget + practical farm data access.

For each slide provide:
- clear headline
- 2-4 bullets max
- one sentence speaker note

Do not add fabricated customer names, legal claims, or unverified financial projections.
```

Suggested images to upload into Gamma:
- `site/assets/cambridge-layout.png`
- `site/assets/cambridge-heatmap.png`

# Example Run: Ambiguous Goal

No company is named in the goal. The planner's heuristic subject extractor falls back to the first content word, and competitor discovery falls back to placeholder competitor names rather than failing the run outright.

```text
╭────────────────────────────────╮
│ MarketScout                    │
│ Competitive Intelligence Agent │
╰────────────────────────────────╯

GOAL
competitive landscape review

PLAN
  1. Identify major competitors
  2. Find recent developments per competitor
  3. Fetch primary sources for evidence
  4. Validate extracted evidence
  5. Estimate illustrative pricing cost
  6. Generate the competitive brief

STEP 1 / 6 — Identify major competitors
  → web_search('competitive competitors')
  ✓ 1 results returned
STEP 2 / 6 — Research recent developments per competitor
  → web_search('Overview: competitive competitors recent product developments pricing')
  ✓ 1 results returned
STEP 3 / 6 — Fetch primary sources
  → web_fetch('https://example.com/overview')
  ✓ 62 characters extracted
STEP 4 / 6 — Validate extracted evidence
  ✓ 1 claims validated
STEP 5 / 6 — Estimate illustrative pricing cost
  ✓ No explicit percentage-fee mentions found in fetched sources
STEP 6 / 6 — Generate competitive brief
  ✓ Report synthesized

✓ Complete

# Competitive Landscape: competitive

## Executive Summary

competitive operates in a competitive market alongside Overview: competitive competitors. 1 
evidence-backed claims were gathered from public sources; see the comparison and evidence tables 
below for sourced detail.

## Competitors

### Overview: competitive competitors
- Focus: No evidence gathered
- Evidence:
  - No claims validated
- Sources:

## Comparison

| Dimension | Overview: competitive competitors |
|---|---|
| Evidence claims gathered | 0 |
| Illustrative cost per $100,000 processed | n/a (no rate % found in sources) |

## Evidence & Confidence

| Claim | Source | Confidence |
|---|---|---|
| No offline content available for https://example.com/overview. | https://example.com/overview | 
Low |


```

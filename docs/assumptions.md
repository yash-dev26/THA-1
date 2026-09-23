# Assumptions & Mock Data Used

The assignment explicitly provides no dataset. This is exactly what
MarketScout is built around: it sources everything live at inference
time by default, and falls back to deterministic offline data only when
no external credentials are configured — so it's runnable and gradeable
with zero setup. Every piece of non-live data is listed here.

## 1. Offline search/fetch fixtures

**What:** `src/tools/fixtures.py` contains real, human-written public
information about four companies (Stripe as the example subject, plus
Adyen, Paddle, and Braintree as competitors) — the kind of thing you'd
find on their own marketing/pricing pages. Used automatically when no
`TAVILY_API_KEY` is set.

**Why:** to make the whole system, and its test suite, runnable without
any API keys, and to make tests deterministic (no live network flakiness
in CI). When `TAVILY_API_KEY` is set, `TavilySearchProvider`/
`HttpFetchProvider` replace these entirely — the fixtures are a fallback
path, not a permanent mock layer.

**Coverage limit:** only these four companies have real fixture content.
Any other subject falls through to a generic, single-result fixture
(`OfflineFixtureSearchProvider`'s fallback branch) — enough to prove the
pipeline runs end-to-end, not informative on its own.

## 2. Illustrative pricing percentages

**What:** two fixture documents (Adyen's and Paddle's pricing pages) each
contain one sentence stating an illustrative percentage fee — "approximately
2.9%" for Adyen, "approximately 5%" for Paddle — explicitly labeled
in-text as *"illustrative comparison purposes only... not a verified
real-world rate."*

**Why:** these exist specifically to give the `calculator` tool something
real to compute on. Real per-merchant processing rates are privately
negotiated and not publicly listed for either company, so no genuine
figure could be sourced from a public page even in live mode — using a
clearly-labeled illustrative rate was the honest alternative to either
fabricating a real-looking number or leaving the calculator step
permanently idle in the offline demo.

**Where it surfaces:** the resulting report's comparison table shows
"Illustrative cost per $100,000 processed" — the $100,000 volume is
also a fixed, made-up demo figure, not a claim about any real merchant.

## 3. Heuristic subject extraction (no LLM configured)

**What:** `_extract_subject_heuristic()` in `src/agent/planner.py` — a
small regex chain (possessive → "for X" → "of X" → first non-stopword
capitalized token) used only when `GROQ_API_KEY` is not set.

**Why:** keeps planning fully deterministic and testable without an LLM
call. It's intentionally simple and will misfire on unusual phrasing
("Compare payment APIs for startups using Paddle" picks the acronym
"APIs" before falling through to "Paddle" in one tested edge case) — with
an LLM configured, subject extraction is model-based instead.

## 4. Evidence claim extraction (no LLM configured)

**What:** `node_validate_evidence` takes the first sentence of a fetched
document as the "claim," with confidence `MEDIUM` if the document has
more than one sentence, else `LOW`.

**Why:** a placeholder for real claim extraction, deterministic so it's
testable. With an LLM configured, `node_synthesize`'s prose (executive
summary, per-competitor focus) is model-written from this same evidence
instead of templated — but claim *extraction* itself stays heuristic in
both modes; only claim *synthesis* changes.

## 5. Competitor name parsing

**What:** competitor names are derived by splitting each search result's
title on " - " and taking the first segment (`node_identify_competitors`).

**Why:** offline fixture titles follow that shape ("Adyen - Financial
technology platform"); this is a simplification that works for the
fixtures and for many real search results, but isn't robust to every
title format a live search API could return.

## 6. No sandboxed code execution or file reading

**Why:** the assignment's tool list is "e.g." (examples, not a required
set). `web_search`, `web_fetch`, and `calculator` were chosen because
they map directly onto the chosen domain (competitive intelligence) —
a code executor or file reader wouldn't have a natural role here without
being forced in.

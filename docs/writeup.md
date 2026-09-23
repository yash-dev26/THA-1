# MarketScout — Write-Up

*(For the full architecture rationale, see [`docs/design.md`](design.md).
For offline data and assumptions, see [`docs/assumptions.md`](assumptions.md).)*

## What it does

MarketScout takes a goal like *"Analyze Stripe's competitive landscape"*
and runs it through a fixed LangGraph pipeline — plan → identify
competitors → research developments → fetch evidence → validate evidence
→ estimate pricing → synthesize — producing a Markdown report where every
claim traces back to a fetched URL, not a search snippet or model memory.

## Design decisions

**A state machine, not a free-form agent loop.** The research lifecycle
is predictable (you can't validate evidence before fetching it), so a
fixed LangGraph sequence over a typed `AgentState` makes execution
observable and testable, at the cost of the agent not being able to
improvise a research direction nobody planned for.

**Types enforce "fetch before you cite."** `Evidence` can only be built
from a fetched `WebDocument`, never from a `SearchResult` snippet — this
is enforced by which constructor exists, not by a docstring.

**Recovery is deterministic, not LLM-decided.** `RecoveryPolicy` is a
plain lookup table (`error_type`, `attempt_number`) → retry / backoff /
fallback / give up. The LLM decides *what* to research; the application
decides *how* infrastructure failures are handled. Demonstrated via
`--inject-failure malformed_search_response`, which corrupts one search
response's schema; Pydantic validation rejects it, the policy retries,
and the run completes normally — covered by a dedicated integration test.

**All three tools are genuinely orchestrated.** `web_search` and
`web_fetch` drive the search→fetch→validate chain. `calculator` computes
an illustrative cost estimate whenever a fetched source mentions a
percentage-based fee — a deliberate choice to keep numeric computation
out of the LLM's hands, the same principle behind the recovery policy.

**Runs with zero API keys.** `web_search`/`web_fetch` fall back to
offline fixtures (real public info about Stripe/Adyen/Paddle/Braintree);
planning/synthesis fall back to deterministic templates with no
`GROQ_API_KEY`. This is also why the 32-test suite runs in under a second
with no network calls.

## Limitations

- Offline fixtures cover four companies; anything else gets a generic,
  uninformative result.
- Evidence extraction without an LLM is a first-sentence heuristic, not
  real claim extraction.
- Pricing estimates only appear when a source explicitly states a
  percentage; the volume and demo rates are illustrative, not verified
  real-world pricing.
- Competitor discovery is capped at 3, no dedup against near-duplicate
  names.
- Recovery is a fixed table — a genuinely novel failure mode falls
  through to a generic fallback, not an adaptive response.
- No cross-run memory or caching.

## What I'd do differently with more time

- Make recovery a visible graph node (not just an inline retry loop) so a
  future human-in-the-loop approval step has somewhere to attach.
- Add source credibility scoring instead of confidence-by-sentence-count.
- Parallelize per-competitor research (LangGraph supports fan-out).
- Build a larger, adversarial eval set: dead links, paywalled sources,
  contradictory evidence across competitors, sources with no clean
  percentage to extract.
- Add a `--format json` output option alongside Markdown.

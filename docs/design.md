# MarketScout — Design Document

## 1. Problem & Goal

MarketScout answers a specific kind of request: *"analyze company X's
competitive landscape."* The naive implementation is `prompt → LLM →
answer` — fast, but unfalsifiable. The model would happily assert pricing
figures, product features, and market positioning from parametric memory,
with no way for a reader to check any of it.

MarketScout instead treats the request as a small **research pipeline**:
find competitors, gather public evidence about each one, fetch the actual
source documents (not just search snippets), and only then write a report
— where every claim in the report traces back to a fetched URL. The
system is deliberately narrow in scope (one domain, three tools, one
state machine) rather than a general-purpose autonomous agent; the goal
is to make every component reliable, testable, and explainable, not to
maximize feature count.

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                    USER INTERFACE                    │
│                 CLI  (python -m src.main)             │
└────────────────────────┬─────────────────────────────┘
                          │ goal (str)
                          ▼
┌─────────────────────────────────────────────────────┐
│               AGENT ORCHESTRATOR                     │
│            LangGraph state machine                   │
│                                                       │
│  plan → identify_competitors → research_developments  │
│         → fetch_evidence → validate_evidence          │
│         → estimate_pricing → synthesize                │
│                                                       │
│      ┌─────────────┐       ┌────────────────────┐    │
│      │  Validation  │◄────►│  RecoveryPolicy     │    │
│      │ (Pydantic)   │      │  (deterministic)    │    │
│      └─────────────┘       └────────────────────┘    │
└────────────────────────┬─────────────────────────────┘
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌───────────┐
        │web_search│ │ web_fetch│ │calculator │
        └────┬─────┘ └────┬─────┘ └─────┬─────┘
             │            │             │ (estimate_pricing node only)
             └─────┬──────┘             │
                   ▼                    │
           Evidence & Failure log  (typed AgentState)
                   │                    │
                   └──────────┬─────────┘
                               ▼
           CompetitiveReport → report.md

Cross-cutting: Logging/Tracing · Settings/Config · Tests · Eval harness
```

See [`docs/architecture.png`](architecture.png) for the rendered version.

Four layers, each with one job:

1. **CLI** — parses arguments, wires up `Settings`, prints the trace and
   final report. No business logic lives here.
2. **Orchestrator** — a LangGraph `StateGraph` over a typed `AgentState`.
   This is the only place that decides *what happens next*.
3. **Tools** — `web_search`, `web_fetch`, `calculator`. Each is a thin,
   typed wrapper around either a real provider (Tavily / HTTP) or a
   deterministic offline fixture, behind a shared `Tool` protocol. All
   three are genuinely invoked in the graph: `calculator` is called by
   the `estimate_pricing` node whenever a fetched document mentions a
   percentage-based fee, to compute an illustrative cost figure — the
   number is computed by the tool, never asked of the LLM (see §4.6 and
   [`docs/assumptions.md`](assumptions.md)).
4. **Cross-cutting** — structured logging (`AgentLogger`), env-driven
   config (`Settings`), tests, and the eval harness. None of these are
   optional extras; they're what make the other three layers checkable.

## 3. Component Breakdown

### 3.1 Models (`src/models/`)

Everything that crosses a boundary — planner output, tool input/output,
final report — is a Pydantic model, not a dict. Three models carry the
core design decision of the whole system:

- **`SearchResult`** — a title/url/snippet triple. This is *never*
  evidence on its own.
- **`WebDocument`** — the result of actually fetching a URL (title, full
  text, fetch timestamp).
- **`Evidence`** — a claim, always constructed from a `WebDocument`, never
  from a `SearchResult`. There's no constructor path that lets a snippet
  become evidence; the type system enforces the "fetch before you cite"
  rule rather than a docstring asking nicely.

`Plan` and `PlanStep` make the planning trace inspectable (`tool` is a
`ToolName` enum, not a free string). `CompetitiveReport` owns its own
`to_markdown()` — rendering is a property of the data, not scattered
string-formatting in the CLI.

### 3.2 Tools (`src/tools/`)

Each tool implements:

```python
class Tool(Protocol):
    name: str
    async def execute(self, input: BaseModel) -> BaseModel: ...
```

and raises a typed `ToolError(error_type, message)` on failure instead of
a bare exception — `error_type` is a fixed vocabulary (`SCHEMA_ERROR`,
`RATE_LIMIT`, `TIMEOUT`, `NOT_FOUND`, `UNKNOWN`) that `RecoveryPolicy`
switches on directly, so recovery logic never has to string-match an
exception message.

Every tool separates **provider** (what actually talks to the outside
world) from the **tool wrapper** (validation + error translation +
failure injection). Concretely, `WebSearchTool` takes a `SearchProvider`;
in production that's `TavilySearchProvider`, in tests and offline runs
it's `OfflineFixtureSearchProvider`. This is the seam where three things
happen without the graph nodes knowing which mode is active:

- **Online/offline switching** — no `TAVILY_API_KEY`/`GROQ_API_KEY`?
  Fixture providers kick in automatically. The whole system, including
  the test suite and eval harness, runs with zero external credentials.
- **Schema validation** — the provider returns a raw dict; the tool
  wrapper is what tries to parse it into `SearchResults`/`WebDocument`
  and turns a `ValidationError` into a `ToolError("SCHEMA_ERROR", ...)`.
- **Failure injection** — `_maybe_inject_failure()` deliberately corrupts
  the raw response shape (see §5) before validation runs, so the failure
  path is exercised through the exact same validation code a real
  provider drift would hit.

### 3.3 Agent Core (`src/agent/`)

- **`state.py`** — `AgentState` is a `TypedDict`, not a raw dict. Every
  field the graph reads or writes is declared: `goal`, `subject`,
  `competitors`, `plan`, `search_results`, `documents`, `evidence`,
  `failures`, `retries`, `final_report`. This is what makes a test able
  to assert `state["failures"][0].recovered is True` instead of
  inspecting log output.
- **`planner.py`** — extracts the subject company and produces a `Plan`.
  LLM-backed when `GROQ_API_KEY` is set; otherwise a small regex
  heuristic (possessive → "for X" → "of X" → first non-stopword
  capitalized token) plus a fixed five-step template plan. The heuristic
  exists so planning is still typed and testable with zero setup — it's
  intentionally not trying to be clever.
- **`llm.py`** — a single `LLMClient` wrapper around Groq's
  OpenAI-compatible chat completions API. `planner.py` and `nodes.py`
  depend on this thin interface, not on Groq directly — swapping
  providers again (OpenAI, Anthropic, a local model server) only touches
  this one file. `complete_json()` asks for JSON-only output and parses
  it; callers catch failures and fall back to their deterministic path,
  so a bad or missing LLM response degrades the report's prose quality,
  it never crashes the run.
- **`recovery.py`** — `RecoveryPolicy` (§5).
- **`nodes.py`** — the actual LangGraph node functions, each
  `(state, deps) -> partial state update`. Dependencies (tools, recovery
  policy, LLM client, logger) are bound with `functools.partial` at graph
  build time, so a node can be unit-tested by calling it directly with a
  fake state and fake tool, no graph required.
- **`graph.py`** — wires the seven nodes into a `StateGraph` with a linear
  edge sequence (see §4 for why it's linear rather than
  conditionally-branching at the graph level).

### 3.4 Cross-Cutting

- **`config.py`** — one `Settings` object, loaded from environment
  variables (`.env.example` documents every one). `FailureInjectionMode`
  is an enum, not a string flag scattered through the code.
- **`logging.py`** — `AgentLogger` renders the human-readable CLI trace
  (plan, step headers, tool calls, failures, recoveries). It's a *view*:
  everything it prints is backed by a typed value elsewhere (`Plan`,
  `ToolFailure`, `RecoveryDecision`) that a test can assert on
  independently of the printed text.

## 4. Key Design Decisions

### 4.1 LangGraph state machine over a free-form ReAct loop

**Decision:** fixed node sequence (`plan → identify_competitors →
research_developments → fetch_evidence → validate_evidence →
estimate_pricing → synthesize`), not an agent that decides its own
control flow turn by turn.

**Why:** the research task has a predictable lifecycle — you can't
validate evidence before fetching it, and you can't fetch before you know
which URLs to fetch. A ReAct loop would spend tokens re-deriving that
ordering on every run and could nondeterministically skip a step. A fixed
graph makes the lifecycle explicit and impossible to skip, and makes
`state["failures"]` and `state["evidence"]` assertable in a test without
first inferring what the model decided to do.

**Trade-off:** MarketScout can't decide to research a dimension nobody
planned for (e.g. discovering it should also check a competitor's funding
history). That flexibility was deliberately traded for reliability and
testability.

### 4.2 Snippet ≠ Evidence, enforced by types

**Decision:** `Evidence` can only be constructed with a `source_url`
that's real, and the only code path that builds `Evidence` (§3.3,
`node_validate_evidence`) consumes `state["documents"]`
(`WebDocument`s) — never `state["search_results"]` directly.

**Why:** the single easiest way for a "research agent" to cut corners is
to synthesize a report straight from search snippets, which are short,
biased toward marketing copy, and not something a reader can click
through to verify in the same way a fetched page is. Forcing a `search →
candidate URL → fetch → extract` path is what makes the tool
orchestration real instead of decorative.

**Trade-off:** more tool calls per run (every candidate URL gets fetched,
not just read as a snippet), and a design that funnels many URLs through
`web_fetch` needs deduplication (`node_fetch_evidence` tracks `seen_urls`)
to avoid refetching the same page from multiple search results.

### 4.3 Deterministic recovery, not LLM-decided recovery

**Decision:** `RecoveryPolicy.decide(error_type, attempt_number)` is a
plain lookup table:

| error_type | action |
|---|---|
| `SCHEMA_ERROR` | retry once |
| `RATE_LIMIT` | retry with exponential backoff (capped at 8s) |
| `TIMEOUT` | retry with exponential backoff |
| `NOT_FOUND` | fall back to an alternate query immediately |
| retry budget exhausted (any type) | fall back, then give up |

**Why:** infrastructure failures (a 429, a timeout, a provider's response
shape drifting) have well-understood, boring, correct responses. Asking
an LLM "what should I do about this 429?" adds latency, cost, and
nondeterminism to a decision that doesn't need any of the three. This is
the crux of the design: **the LLM decides what to research; the
application decides how infrastructure failures are handled.**

**Trade-off:** the policy can't adapt to a failure mode nobody
anticipated — an unrecognized `error_type` falls through to `UNKNOWN` →
fallback, which is a safe default but not a smart one. Extending the
policy means editing code, not writing a better prompt.

### 4.4 Node-level retry loop, not a graph-level recovery node

**Decision:** the retry loop (`_search_with_recovery` in `nodes.py`) lives
*inside* the `identify_competitors`/`research_developments` node
functions, not as a separate `recovery_controller` node with its own
graph edges.

**Why (and the trade-off, honestly stated):** the original plan sketch
diagrams recovery as its own graph node with conditional edges looping
back to the failing step. I chose an inline retry loop instead, because
LangGraph's conditional-edge machinery is built for *coarse* branching
(which node runs next), while this recovery is fundamentally a *tight*
loop over one tool call (retry the same query up to N times). Modeling
every retry as a full graph transition would mean re-entering node setup
on every attempt and would make the "loop budget" implicit in graph
topology rather than an explicit `attempt_number` parameter. The
`RecoveryPolicy` class and the `ToolFailure`/`retries` fields on
`AgentState` still make every decision and every attempt fully typed,
logged, and testable — recovery is observable in `state["failures"]`
exactly as it would be if it were a separate graph node, just without the
extra hops. If a future version needs the graph to visibly pause and
resume at a recovery boundary (e.g. for a human-in-the-loop approval), a
real `recovery_controller` node is the natural next step — see §8.

### 4.5 Offline-first: fixtures and heuristics as first-class fallbacks

**Decision:** every external dependency (search API, fetch, LLM) has a
deterministic offline/no-key fallback that's exercised by default, not
just a `mock.patch` used only in tests.

**Why:** a take-home reviewer shouldn't need to provision three API keys
to run the code. More importantly, this makes the *test suite itself*
fast, free, and deterministic — `pytest -q` runs 31 tests in well under a
second with zero network calls, because the same offline path production
code takes when no keys are configured is what the tests exercise.

**Trade-off:** the offline fixtures are a fixed snapshot of a handful of
companies (Stripe/Adyen/Paddle/Braintree); any other subject falls
through to a generic single-result fixture, which is enough to prove the
pipeline works end-to-end but isn't informative. This is a deliberate
scope cut, not an oversight.

### 4.6 Swappable LLM provider (Groq)

**Decision:** `LLMClient` wraps Groq's OpenAI-compatible chat completions
API (`AsyncGroq`), used for subject extraction, plan-step wording, and
report prose. Planner and synthesis code depend only on
`LLMClient.available` / `LLMClient.complete_json()`.

**Why Groq specifically:** fast inference on open-weight models
(`llama-3.3-70b-versatile` by default, overridable via
`MARKETSCOUT_MODEL`) keeps the LLM-backed path snappy for an interactive
CLI tool, and the OpenAI-compatible surface (`chat.completions.create`,
`choices[0].message.content`) is a common shape most providers implement,
which is precisely why swapping it in only touched `llm.py`,
`config.py`, `.env.example`, and `pyproject.toml` — no changes to
`planner.py`, `nodes.py`, or `graph.py` were needed.

**Trade-off:** open-weight models are generally less reliable at strict
JSON-only output than frontier closed models, which is part of why
`complete_json()`'s callers always have a deterministic fallback path
rather than trusting the LLM call to succeed. This trade-off existed
before the swap too (the previous Anthropic-backed version had the same
fallback for the same reason) — it's a property of "any LLM in the loop
for structured output," not specific to Groq.

### 4.7 Calculator wired for a real step, not left idle

**Decision:** a dedicated `estimate_pricing` node runs between evidence
validation and synthesis. It scans each fetched `WebDocument` for an
explicit percentage-fee mention (e.g. "approximately 2.9% of transaction
volume") and, when found, calls `CalculatorTool.execute()` — not the LLM —
to compute an illustrative cost on a fixed representative volume
($100,000). The result is written straight into the report's comparison
table by `_pricing_comparison_row()`, bypassing the LLM entirely for that
row even on the LLM-backed synthesis path.

**Why:** an earlier version of this system had `calculator` implemented
and tested but never called anywhere in the graph — three tools existed,
but only two were genuinely orchestrated. That's a real weakness a
reviewer reading the code would notice: a tool that exists purely to hit
a tool count. Giving it an actual job (numeric computation the LLM
shouldn't be trusted to do reliably) also reinforces the system's central
principle from a different angle: the LLM decides *what* to research and
writes prose *about* the evidence; deterministic code computes *exact
numbers* from it. Recovery decisions and pricing arithmetic are both kept
out of the model's hands for the same reason.

**Trade-off:** the offline fixtures needed an explicit, clearly-labeled
illustrative percentage added to two of the four company fixtures (Adyen,
Paddle) so there's something real to extract and compute on — see
[`docs/assumptions.md`](assumptions.md). Real fetched pages won't always
state a clean percentage this way, so in live mode this step is
best-effort: competitors whose sources don't mention an explicit rate get
`"n/a (no rate % found in sources)"` in the comparison table rather than a
fabricated number.

## 5. Failure Injection & Recovery Walkthrough

`--inject-failure malformed_search_response` deliberately corrupts one
`web_search` response's schema — field names drift from
`results`/`title`/`url` to `items`/`headline`/`link` — mirroring a real
upstream API contract break, not a random `raise Exception()`. The
injection budget is one-shot (`injection_budget=1` by default): it fires
once, mimicking a transient provider glitch, so the retry path has
something to actually succeed against.

```
web_search("Stripe competitors")
  → provider returns malformed shape
  → SearchResults(**raw) raises ValidationError
  → WebSearchTool catches it, raises ToolError("SCHEMA_ERROR", ...)
  → RecoveryPolicy.decide(SCHEMA_ERROR, attempt=1) → RETRY
  → node retries the same query
  → injection budget spent → provider returns the normal shape
  → SearchResults validates → run continues normally
```

Every step of this is recorded as a typed `ToolFailure` in
`state["failures"]` with `recovered=True` and `recovery_action="retry"`,
and asserted directly in
`tests/integration/test_agent.py::test_malformed_search_response_triggers_recovery_and_still_completes`.
Two other modes exercise the other branches: `fetch_timeout` (backoff
retry on `web_fetch`) and `rate_limit` (backoff retry on `web_search`).

## 6. Testing & Evaluation Strategy

Three layers, all offline by default:

- **Unit** (`tests/unit/`) — models reject malformed shapes (including
  the exact malformed-injection shape), the planner's heuristic and
  fallback paths, each tool's success/injected-failure behavior, and
  every branch of `RecoveryPolicy.decide()` in isolation.
- **Integration** (`tests/integration/`) — the full compiled graph,
  always against mocked/offline providers: a normal run, the
  schema-failure recovery path, the fetch-timeout path, and an
  ambiguous-goal path (no named company) that still completes via
  fallback competitors rather than crashing.
- **Eval harness** (`evals/run_evals.py`) — 6 scenarios from
  `evals/datasets/scenarios.json` run against the real graph, scored on
  `planning_success`, `tool_success_rate`, `recovery_success`,
  `citation_coverage`, `final_schema_valid`. Not a benchmark in the
  rigorous sense — a small, reproducible sanity check that's cheap enough
  to run on every change (`python -m evals.run_evals --inject-failure
  malformed_search_response` currently scores 6/6 on
  `recovery_success` and `final_schema_valid`).

## 7. Trade-offs Summary

| Choice | Gained | Given up |
|---|---|---|
| Fixed LangGraph sequence over free-form ReAct | Predictable, testable, debuggable execution | Can't adapt research scope mid-run |
| Types enforce snippet ≠ evidence | Grounded, citable reports | More tool calls, needs URL dedup |
| Deterministic `RecoveryPolicy` | Fast, testable, reproducible recovery | Can't adapt to unanticipated failure modes without a code change |
| Inline node-level retry loop | Simple, explicit attempt budget | Recovery isn't its own graph node/hop (see §4.4) |
| Offline fixtures + heuristics by default | Zero-setup, fast, free test suite | Fixture data is a fixed snapshot, generic for unknown subjects |
| LLM behind a thin `LLMClient` interface | Swapping providers (Anthropic → Groq) touched one file | Open-weight JSON output is less reliable, so heuristic fallbacks are load-bearing, not decorative |
| Calculator wired to `estimate_pricing`, not left idle | All three tools are genuinely orchestrated; numeric pricing comes from code, not the LLM | Only fires when a source states an explicit percentage; fixtures needed illustrative rates added (see assumptions doc) |

## 8. Limitations

- Offline fixtures cover a handful of companies; anything else gets a
  generic, uninformative fixture result.
- Evidence extraction without an LLM is a first-sentence heuristic, not
  real claim extraction.
- Competitor discovery is capped at 3 with no dedup against near-duplicate
  company names.
- The pricing estimate only appears for a competitor when a fetched
  source explicitly states a percentage fee; it's illustrative (fixed
  $100,000 volume, demo-only rates in the offline fixtures), not verified
  real-world pricing — see [`docs/assumptions.md`](assumptions.md).
- No long-term memory or caching across runs — every run starts cold.
- Recovery is a fixed table, not adaptive; a genuinely novel failure mode
  falls through to the generic `UNKNOWN` → fallback path.

## 9. Future Work

- A real `recovery_controller` graph node (§4.4) if a future requirement
  needs recovery to be a visible pause/resume point, e.g. for
  human-in-the-loop approval before a fallback query runs.
- Persistent research cache across runs.
- Source credibility scoring instead of confidence-by-sentence-count.
- Parallel competitor research (LangGraph supports fan-out/fan-in).
- A larger, adversarial evaluation benchmark: dead links, paywalled
  sources, contradictory evidence across competitors.

# Example Run: Induced Schema Failure + Recovery

Run with: `python -m src.main --goal "Analyze Stripe's competitive landscape" --inject-failure malformed_search_response`

```text
╭────────────────────────────────╮
│ MarketScout                    │
│ Competitive Intelligence Agent │
╰────────────────────────────────╯

GOAL
Analyze Stripe's competitive landscape

PLAN
  1. Identify major competitors
  2. Find recent developments per competitor
  3. Fetch primary sources for evidence
  4. Validate extracted evidence
  5. Estimate illustrative pricing cost
  6. Generate the competitive brief

STEP 1 / 6 — Identify major competitors
  → web_search('Stripe competitors')
  ⚠ SCHEMA_ERROR: Search response failed schema validation: 'results'
  RECOVERY → retry ✓
  → web_search('Stripe competitors')
  ✓ 3 results returned
STEP 2 / 6 — Research recent developments per competitor
  → web_search('Adyen recent product developments pricing')
  ✓ 2 results returned
  → web_search('Paddle recent product developments pricing')
  ✓ 2 results returned
  → web_search('Braintree recent product developments pricing')
  ✓ 1 results returned
STEP 3 / 6 — Fetch primary sources
  → web_fetch('https://www.adyen.com/')
  ✓ 315 characters extracted
  → web_fetch('https://www.paddle.com/')
  ✓ 285 characters extracted
  → web_fetch('https://www.braintreepayments.com/')
  ✓ 306 characters extracted
  → web_fetch('https://www.adyen.com/press-and-media/adyen-update')
  ✓ 84 characters extracted
  → web_fetch('https://www.adyen.com/pricing')
  ✓ 566 characters extracted
  → web_fetch('https://www.paddle.com/blog/paddle-billing')
  ✓ 76 characters extracted
  → web_fetch('https://www.paddle.com/pricing')
  ✓ 484 characters extracted
  → web_fetch('https://developer.paypal.com/braintree/docs')
  ✓ 77 characters extracted
STEP 4 / 6 — Validate extracted evidence
  ✓ 8 claims validated
STEP 5 / 6 — Estimate illustrative pricing cost
  → calculator('100000 * 2.9 / 100')
  ✓ $2,900.00 on $100,000 illustrative volume
  → calculator('100000 * 5.0 / 100')
  ✓ $5,000.00 on $100,000 illustrative volume
STEP 6 / 6 — Generate competitive brief
  ✓ Report synthesized

✓ Complete

# Competitive Landscape: Stripe

## Executive Summary

Stripe operates in a competitive market alongside Adyen, Paddle, Braintree. 8 evidence-backed claims
were gathered from public sources; see the comparison and evidence tables below for sourced detail.

## Competitors

### Adyen
- Focus: Adyen provides a single platform to accept payments anywhere and manage the enti
- Evidence:
  - Adyen provides a single platform to accept payments anywhere and manage the entire flow of 
money.
  - No offline content available for https://www.adyen.com/press-and-media/adyen-update.
  - Adyen's pricing model is interchange++, meaning merchants pay the underlying card network 
interchange fee plus a transparent Adyen markup, plus a fixed processing fee per transaction.
- Sources:
  - https://www.adyen.com/
  - https://www.adyen.com/press-and-media/adyen-update
  - https://www.adyen.com/pricing

### Paddle
- Focus: Paddle positions itself as a merchant of record for software companies, handling
- Evidence:
  - Paddle positions itself as a merchant of record for software companies, handling global 
payments, sales tax, VAT compliance, and subscription billing in one product.
  - No offline content available for https://www.paddle.com/blog/paddle-billing.
  - Paddle charges a flat percentage fee per transaction, inclusive of payment processing, tax 
handling, and billing infrastructure.
- Sources:
  - https://www.paddle.com/
  - https://www.paddle.com/blog/paddle-billing
  - https://www.paddle.com/pricing

### Braintree
- Focus: Braintree, owned by PayPal, offers a developer-friendly payments platform with d
- Evidence:
  - Braintree, owned by PayPal, offers a developer-friendly payments platform with drop-in UI 
components and direct API access.
  - No offline content available for https://developer.paypal.com/braintree/docs.
- Sources:
  - https://www.braintreepayments.com/
  - https://developer.paypal.com/braintree/docs

## Comparison

| Dimension | Adyen | Paddle | Braintree |
|---|---|---|---|
| Evidence claims gathered | 3 | 3 | 2 |
| Illustrative cost per $100,000 processed | ~$2,900 per $100,000 processed (illustrative, based on 
a 2.9% rate mentioned in sources) | ~$5,000 per $100,000 processed (illustrative, based on a 5% rate
mentioned in sources) | n/a (no rate % found in sources) |

## Evidence & Confidence

| Claim | Source | Confidence |
|---|---|---|
| Adyen provides a single platform to accept payments anywhere and manage the entire flow of money. 
| https://www.adyen.com/ | Medium |
| Paddle positions itself as a merchant of record for software companies, handling global payments, 
sales tax, VAT compliance, and subscription billing in one product. | https://www.paddle.com/ | 
Medium |
| Braintree, owned by PayPal, offers a developer-friendly payments platform with drop-in UI 
components and direct API access. | https://www.braintreepayments.com/ | Medium |
| No offline content available for https://www.adyen.com/press-and-media/adyen-update. | 
https://www.adyen.com/press-and-media/adyen-update | Low |
| Adyen's pricing model is interchange++, meaning merchants pay the underlying card network 
interchange fee plus a transparent Adyen markup, plus a fixed processing fee per transaction. | 
https://www.adyen.com/pricing | Medium |
| No offline content available for https://www.paddle.com/blog/paddle-billing. | 
https://www.paddle.com/blog/paddle-billing | Low |
| Paddle charges a flat percentage fee per transaction, inclusive of payment processing, tax 
handling, and billing infrastructure. | https://www.paddle.com/pricing | Medium |
| No offline content available for https://developer.paypal.com/braintree/docs. | 
https://developer.paypal.com/braintree/docs | Low |


1 tool failure(s) encountered and recovered during this run.

```

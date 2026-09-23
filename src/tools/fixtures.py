"""Offline fixture data.

These fixtures let MarketScout run end-to-end, and let the test suite run
deterministically in CI, without any external API keys. When
TAVILY_API_KEY is set, the real provider is used instead and this file is
never consulted.
"""

from __future__ import annotations

from typing import Any

OFFLINE_SEARCH_FIXTURES: dict[str, dict[str, Any]] = {
    "stripe competitors": {
        "results": [
            {
                "title": "Adyen - Financial technology platform",
                "url": "https://www.adyen.com/",
                "snippet": "Adyen is a single platform for accepting payments anywhere, "
                "used by enterprise merchants for unified commerce.",
                "source": "adyen.com",
            },
            {
                "title": "Paddle - Payments infrastructure for SaaS",
                "url": "https://www.paddle.com/",
                "snippet": "Paddle is a merchant of record handling payments, tax, and "
                "subscriptions for software companies.",
                "source": "paddle.com",
            },
            {
                "title": "Braintree - A PayPal service",
                "url": "https://www.braintreepayments.com/",
                "snippet": "Braintree provides a full-stack payments platform with "
                "developer-friendly SDKs, owned by PayPal.",
                "source": "braintreepayments.com",
            },
        ]
    },
    "adyen": {
        "results": [
            {
                "title": "Adyen Q2 update: unified commerce growth",
                "url": "https://www.adyen.com/press-and-media/adyen-update",
                "snippet": "Adyen reported continued growth in unified commerce, "
                "expanding platform capabilities for enterprise merchants.",
                "source": "adyen.com",
            },
            {
                "title": "Adyen pricing - interchange++ model",
                "url": "https://www.adyen.com/pricing",
                "snippet": "Adyen uses interchange++ pricing, passing through card scheme "
                "fees plus a transparent markup, geared to large-volume merchants.",
                "source": "adyen.com",
            },
        ]
    },
    "paddle": {
        "results": [
            {
                "title": "Paddle launches new billing engine",
                "url": "https://www.paddle.com/blog/paddle-billing",
                "snippet": "Paddle introduced Paddle Billing, a rebuilt subscription and "
                "invoicing engine aimed at SaaS companies selling globally.",
                "source": "paddle.com",
            },
            {
                "title": "Paddle pricing - flat percentage, merchant of record",
                "url": "https://www.paddle.com/pricing",
                "snippet": "Paddle charges a flat percentage fee per transaction and acts as "
                "merchant of record, absorbing tax and compliance burden.",
                "source": "paddle.com",
            },
        ]
    },
    "braintree": {
        "results": [
            {
                "title": "Braintree developer documentation",
                "url": "https://developer.paypal.com/braintree/docs",
                "snippet": "Braintree offers SDKs for major mobile and web platforms, with "
                "a drop-in UI and direct API access for custom checkout flows.",
                "source": "developer.paypal.com",
            }
        ]
    },
}


OFFLINE_FETCH_FIXTURES: dict[str, dict[str, str]] = {
    "https://www.adyen.com/": {
        "title": "Adyen - Financial technology platform",
        "text": (
            "Adyen provides a single platform to accept payments anywhere and manage "
            "the entire flow of money. It targets large enterprise merchants and "
            "focuses heavily on unified commerce across online, in-store, and "
            "in-app channels. Adyen's developer experience centers on a unified "
            "API rather than many product-specific SDKs."
        ),
    },
    "https://www.adyen.com/pricing": {
        "title": "Adyen pricing - interchange++ model",
        "text": (
            "Adyen's pricing model is interchange++, meaning merchants pay the "
            "underlying card network interchange fee plus a transparent Adyen "
            "markup, plus a fixed processing fee per transaction. This model is "
            "typically favorable for large-volume merchants who can negotiate "
            "rates, but is more complex than a flat-rate model. For illustrative "
            "comparison purposes only, this demo models Adyen's blended cost at "
            "approximately 2.9% of transaction volume; this is not a verified "
            "real-world rate, since actual interchange++ pricing is negotiated "
            "per-merchant and not publicly listed."
        ),
    },
    "https://www.paddle.com/": {
        "title": "Paddle - Payments infrastructure for SaaS",
        "text": (
            "Paddle positions itself as a merchant of record for software "
            "companies, handling global payments, sales tax, VAT compliance, "
            "and subscription billing in one product. This differs from Stripe, "
            "which requires merchants to handle their own tax compliance "
            "(or use Stripe Tax as an add-on)."
        ),
    },
    "https://www.paddle.com/pricing": {
        "title": "Paddle pricing - flat percentage, merchant of record",
        "text": (
            "Paddle charges a flat percentage fee per transaction, inclusive of "
            "payment processing, tax handling, and billing infrastructure. This "
            "is simpler to reason about than interchange++ pricing but generally "
            "more expensive per-transaction for high-volume merchants. For "
            "illustrative comparison purposes only, this demo models Paddle's "
            "flat fee at approximately 5% of transaction volume; this is not a "
            "verified real-world rate and is used solely to exercise the "
            "calculator tool in this demo."
        ),
    },
    "https://www.braintreepayments.com/": {
        "title": "Braintree - A PayPal service",
        "text": (
            "Braintree, owned by PayPal, offers a developer-friendly payments "
            "platform with drop-in UI components and direct API access. It "
            "supports major card networks plus PayPal and Venmo, and is "
            "commonly used by mid-market and enterprise merchants who want "
            "PayPal's backing without a fully custom-built integration."
        ),
    },
}

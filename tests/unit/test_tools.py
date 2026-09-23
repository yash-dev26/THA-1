import pytest

from src.config import FailureInjectionMode, Settings
from src.models.evidence import SearchResults, WebDocument
from src.tools.base import ToolError
from src.tools.calculator import CalculatorTool
from src.tools.web_fetch import WebFetchTool
from src.tools.web_search import WebSearchTool


async def test_web_search_returns_valid_typed_results_offline():
    settings = Settings()
    tool = WebSearchTool(settings)
    result = await tool.execute("Stripe competitors")
    assert isinstance(result, SearchResults)
    assert len(result.results) >= 1
    assert all(str(r.url).startswith("http") for r in result.results)


async def test_web_search_raises_schema_error_on_malformed_response():
    settings = Settings(failure_injection_mode=FailureInjectionMode.MALFORMED_SEARCH_RESPONSE)
    tool = WebSearchTool(settings, injection_budget=1)
    with pytest.raises(ToolError) as exc_info:
        await tool.execute("Stripe competitors")
    assert exc_info.value.error_type == "SCHEMA_ERROR"


async def test_web_search_recovers_after_one_injected_failure():
    """The injection budget is exhausted after one failure, matching a
    transient provider glitch rather than a permanently broken API."""
    settings = Settings(failure_injection_mode=FailureInjectionMode.MALFORMED_SEARCH_RESPONSE)
    tool = WebSearchTool(settings, injection_budget=1)

    with pytest.raises(ToolError):
        await tool.execute("Stripe competitors")

    # second call succeeds because the injection budget is spent
    result = await tool.execute("Stripe competitors")
    assert isinstance(result, SearchResults)


async def test_web_search_rate_limit_injection_raises_rate_limit_error():
    settings = Settings(failure_injection_mode=FailureInjectionMode.RATE_LIMIT)
    tool = WebSearchTool(settings, injection_budget=1)
    with pytest.raises(ToolError) as exc_info:
        await tool.execute("Stripe competitors")
    assert exc_info.value.error_type == "RATE_LIMIT"


async def test_web_fetch_returns_typed_document_offline():
    settings = Settings()
    tool = WebFetchTool(settings)
    doc = await tool.execute("https://www.adyen.com/")
    assert isinstance(doc, WebDocument)
    assert doc.title
    assert doc.text


async def test_web_fetch_timeout_injection_raises_timeout_error():
    settings = Settings(failure_injection_mode=FailureInjectionMode.FETCH_TIMEOUT)
    tool = WebFetchTool(settings, injection_budget=1)
    with pytest.raises(ToolError) as exc_info:
        await tool.execute("https://www.adyen.com/")
    assert exc_info.value.error_type == "TIMEOUT"


@pytest.mark.parametrize(
    "expression,expected",
    [("2.90 * 10000", 29000.0), ("(3 + 4) * 2", 14.0), ("10 / 4", 2.5)],
)
async def test_calculator_evaluates_arithmetic(expression, expected):
    tool = CalculatorTool()
    result = await tool.execute(expression)
    assert result == pytest.approx(expected)


async def test_calculator_rejects_disallowed_expressions():
    tool = CalculatorTool()
    with pytest.raises(ToolError):
        await tool.execute("__import__('os').system('echo hi')")

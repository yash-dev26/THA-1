import pytest

from src.agent.llm import LLMClient
from src.agent.planner import Planner, _extract_subject_heuristic
from src.config import Settings
from src.models.plan import ToolName


@pytest.mark.parametrize(
    "goal,expected_subject",
    [
        ("Analyze Stripe's competitive landscape", "Stripe"),
        ("Analyze the competitive landscape for Adyen", "Adyen"),
        ("Compare payment infrastructure for startups using Paddle", "Paddle"),
    ],
)
def test_subject_heuristic_extracts_company_not_the_verb(goal, expected_subject):
    assert _extract_subject_heuristic(goal) == expected_subject


async def test_planner_falls_back_to_deterministic_plan_without_llm_key():
    settings = Settings()  # no groq_api_key set
    planner = Planner(LLMClient(settings))
    subject, plan = await planner.plan("Analyze Stripe's competitive landscape")

    assert subject == "Stripe"
    assert plan.steps[0].tool == ToolName.WEB_SEARCH
    assert plan.steps[-1].tool == ToolName.LLM
    assert plan.steps[-2].tool == ToolName.CALCULATOR
    assert len(plan.steps) == 6


async def test_plan_step_ids_are_sequential():
    settings = Settings()
    planner = Planner(LLMClient(settings))
    _, plan = await planner.plan("Analyze Netflix's competitive landscape")
    assert [s.id for s in plan.steps] == list(range(1, len(plan.steps) + 1))

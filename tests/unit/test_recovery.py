from src.agent.recovery import RecoveryAction, RecoveryPolicy
from src.models.evidence import FailureType


def test_schema_error_retries_within_budget():
    policy = RecoveryPolicy(max_retries=2)
    decision = policy.decide(FailureType.SCHEMA_ERROR, attempt_number=1)
    assert decision.action == RecoveryAction.RETRY


def test_rate_limit_retries_with_backoff():
    policy = RecoveryPolicy(max_retries=2)
    decision = policy.decide(FailureType.RATE_LIMIT, attempt_number=1)
    assert decision.action == RecoveryAction.RETRY_WITH_BACKOFF
    assert decision.backoff_seconds > 0


def test_timeout_retries_with_backoff():
    policy = RecoveryPolicy(max_retries=2)
    decision = policy.decide(FailureType.TIMEOUT, attempt_number=1)
    assert decision.action == RecoveryAction.RETRY_WITH_BACKOFF


def test_not_found_falls_back_immediately_rather_than_retrying():
    policy = RecoveryPolicy(max_retries=2)
    decision = policy.decide(FailureType.NOT_FOUND, attempt_number=1)
    assert decision.action == RecoveryAction.FALLBACK_ALTERNATE_QUERY


def test_exceeding_retry_budget_falls_back_regardless_of_error_type():
    policy = RecoveryPolicy(max_retries=1)
    decision = policy.decide(FailureType.SCHEMA_ERROR, attempt_number=2)
    assert decision.action == RecoveryAction.FALLBACK_ALTERNATE_QUERY


def test_backoff_grows_with_attempt_number_but_is_capped():
    policy = RecoveryPolicy(max_retries=5)
    d1 = policy.decide(FailureType.RATE_LIMIT, attempt_number=1)
    d2 = policy.decide(FailureType.RATE_LIMIT, attempt_number=2)
    assert d2.backoff_seconds >= d1.backoff_seconds
    assert d2.backoff_seconds <= 8

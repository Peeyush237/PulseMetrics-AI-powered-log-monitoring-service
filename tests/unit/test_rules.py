import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.rules.threshold import ThresholdRule
from app.rules.novelty import NoveltyRule
from app.rules.regex import RegexRule
from app.rules.base import EvaluationContext


def make_ctx(log_repo=None, cluster_repo=None):
    now = datetime.now(timezone.utc)
    ctx = EvaluationContext(
        log_repo=log_repo or AsyncMock(),
        cluster_repo=cluster_repo or AsyncMock(),
        window_start=now - timedelta(minutes=5),
        window_end=now,
        application_id=uuid.uuid4(),
    )
    return ctx


class TestThresholdRule:
    @pytest.mark.asyncio
    async def test_fires_when_count_exceeds_threshold(self):
        log_repo = AsyncMock()
        log_repo.count_matching.return_value = 25
        log_repo.sample_matching.return_value = []

        rule = ThresholdRule(
            rule_id=uuid.uuid4(),
            application_id=uuid.uuid4(),
            config={"threshold": 10, "window_seconds": 300, "filters": {"level": ">=ERROR"}},
        )
        ctx = make_ctx(log_repo=log_repo)
        outcome = await rule.evaluate(ctx)
        assert outcome.fired is True
        assert outcome.payload["count"] == 25

    @pytest.mark.asyncio
    async def test_does_not_fire_below_threshold(self):
        log_repo = AsyncMock()
        log_repo.count_matching.return_value = 5

        rule = ThresholdRule(
            rule_id=uuid.uuid4(),
            application_id=uuid.uuid4(),
            config={"threshold": 10, "window_seconds": 300, "filters": {}},
        )
        outcome = await rule.evaluate(make_ctx(log_repo=log_repo))
        assert outcome.fired is False


class TestNoveltyRule:
    @pytest.mark.asyncio
    async def test_fires_when_new_cluster_exists(self):
        cluster_repo = AsyncMock()
        mock_cluster = MagicMock()
        mock_cluster.id = uuid.uuid4()
        mock_cluster.representative_message = "New error never seen before"
        cluster_repo.find_created_after.return_value = [mock_cluster]

        rule = NoveltyRule(
            rule_id=uuid.uuid4(),
            application_id=uuid.uuid4(),
            config={"min_severity": "WARNING"},
        )
        outcome = await rule.evaluate(make_ctx(cluster_repo=cluster_repo))
        assert outcome.fired is True
        assert len(outcome.payload["new_cluster_ids"]) == 1

    @pytest.mark.asyncio
    async def test_no_fire_when_no_new_clusters(self):
        cluster_repo = AsyncMock()
        cluster_repo.find_created_after.return_value = []

        rule = NoveltyRule(
            rule_id=uuid.uuid4(),
            application_id=uuid.uuid4(),
            config={"min_severity": "WARNING"},
        )
        outcome = await rule.evaluate(make_ctx(cluster_repo=cluster_repo))
        assert outcome.fired is False

"""Unit tests for the AI client wrapper (no live API).

Only the configuration/guard behaviour is unit-testable without a network call;
the actual generation path is exercised in integration tests with a fake client.
"""

from __future__ import annotations

import pytest
from app.schemas.ai import ProjectClassification
from app.services.ai.client import AiClient, AiNotConfiguredError


class TestAiClientConfiguration:
    def test_unconfigured_client_reports_not_configured(self) -> None:
        client = AiClient(api_key=None)
        assert client.configured is False

    def test_configured_client_reports_configured(self) -> None:
        client = AiClient(api_key="sk-test-key")
        assert client.configured is True

    async def test_generate_without_key_raises(self) -> None:
        client = AiClient(api_key=None)
        with pytest.raises(AiNotConfiguredError):
            await client.generate(
                system="s", prompt="p", schema=ProjectClassification
            )

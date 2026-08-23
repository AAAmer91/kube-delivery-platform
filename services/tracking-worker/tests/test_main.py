"""Startup retry and readiness tests for the worker process."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src import main as worker_main


@pytest.mark.asyncio
async def test_connect_database_with_retry_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    repo.connect = AsyncMock(side_effect=[RuntimeError("not ready"), None])
    sleep = AsyncMock()
    monkeypatch.setattr(worker_main.asyncio, "sleep", sleep)

    await worker_main.connect_database_with_retry(repo, retry_backoff_sec=0)

    assert repo.connect.await_count == 2
    sleep.assert_awaited_once_with(0)


def test_dependencies_ready_requires_live_database_and_nats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = MagicMock(is_connected=True)
    consumer = MagicMock(is_connected=True)
    monkeypatch.setattr(worker_main, "_global_repo", repo)
    monkeypatch.setattr(worker_main, "_global_consumer", consumer)

    assert worker_main.dependencies_ready() is True

    repo.is_connected = False
    assert worker_main.dependencies_ready() is False

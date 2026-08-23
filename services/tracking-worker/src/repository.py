"""PostgreSQL repository for tracking-worker."""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

from src.metrics import DATABASE_UPDATES_TOTAL

logger = logging.getLogger("tracking-worker.repository")


class PostgresRepository:
    """Async PostgreSQL repository managing shipment status updates."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None
        self._healthy = False

    @property
    def is_connected(self) -> bool:
        """Returns the latest actively probed database state."""
        return self._pool is not None and self._healthy

    async def connect(self) -> None:
        """Initializes the asyncpg connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=2,
                max_size=20,
                timeout=5.0,
            )
            self._healthy = True
            logger.info("PostgreSQL connection pool established.")

    async def ping(self) -> bool:
        """Pings the database to verify connectivity."""
        if self._pool is None:
            self._healthy = False
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                self._healthy = True
                return True
        except Exception as err:
            self._healthy = False
            logger.warning("Database ping failed: %s", err)
            return False

    async def update_shipment_status(
        self,
        shipment_id: str,
        new_status: str,
    ) -> bool:
        """Idempotently updates the status of a shipment."""
        if self._pool is None:
            raise RuntimeError("Database connection pool not initialized")

        query = """
        UPDATE shipments
        SET status = $2, updated_at = NOW()
        WHERE id = $1 AND status != $2;
        """
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(query, shipment_id, new_status)
                # 'UPDATE 1' if changed, 'UPDATE 0' if already at status
                updated = result == "UPDATE 1"
                DATABASE_UPDATES_TOTAL.labels(status=new_status, result="success").inc()
                return bool(updated)

        except Exception as err:
            DATABASE_UPDATES_TOTAL.labels(status=new_status, result="error").inc()
            logger.error("Failed to update shipment %s to %s: %s", shipment_id, new_status, err)
            raise

    async def get_shipment(self, shipment_id: str) -> dict[str, Any] | None:
        """Retrieves a single shipment by ID."""
        if self._pool is None:
            raise RuntimeError("Database connection pool not initialized")

        query = """
        SELECT id, tracking_number, sender_name, recipient_name, origin, destination, status, weight_kg, created_at, updated_at
        FROM shipments
        WHERE id = $1;
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, shipment_id)
            if row:
                return dict(row)
            return None

    async def close(self) -> None:
        """Closes the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._healthy = False
            logger.info("PostgreSQL connection pool closed.")

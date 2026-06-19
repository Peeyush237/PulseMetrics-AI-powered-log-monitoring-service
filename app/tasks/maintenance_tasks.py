import asyncio
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.tasks.celery_app import celery_app
from sqlalchemy import text

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.maintenance_tasks.maintain_partitions")
def maintain_partitions() -> dict:
    return asyncio.get_event_loop().run_until_complete(_maintain_partitions_async())


async def _maintain_partitions_async() -> dict:
    """Ensure monthly partitions exist for the next 3 months."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        created: list[str] = []

        for months_ahead in range(0, 4):
            # Calculate target month
            month = (now.month + months_ahead - 1) % 12 + 1
            year = now.year + (now.month + months_ahead - 1) // 12
            start = f"{year:04d}-{month:02d}-01"
            next_month = month % 12 + 1
            next_year = year + (1 if month == 12 else 0)
            end = f"{next_year:04d}-{next_month:02d}-01"
            partition_name = f"logs_{year:04d}_{month:02d}"

            check_stmt = text("""
                SELECT 1 FROM pg_tables WHERE tablename = :name
            """)
            result = await session.execute(check_stmt, {"name": partition_name})
            if result.fetchone() is None:
                create_stmt = text(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF logs
                    FOR VALUES FROM ('{start}') TO ('{end}')
                """)
                await session.execute(create_stmt)
                await session.commit()
                created.append(partition_name)
                logger.info("partition_created", partition=partition_name)

        return {"created": created}


@celery_app.task(name="app.tasks.maintenance_tasks.drop_expired_logs")
def drop_expired_logs() -> dict:
    return asyncio.get_event_loop().run_until_complete(_drop_expired_async())


async def _drop_expired_async() -> dict:
    """Drop log partitions older than application retention_days."""
    async with AsyncSessionLocal() as session:
        stmt = text("""
            SELECT id, retention_days FROM applications
        """)
        result = await session.execute(stmt)
        apps = result.fetchall()

        dropped: list[str] = []
        now = datetime.now(timezone.utc)

        for app_id, retention_days in apps:
            cutoff = now.replace(day=1)
            for i in range(retention_days // 30 + 2):
                month = (cutoff.month - i - 1) % 12 + 1
                year = cutoff.year - (i + cutoff.month - 1) // 12
                if i >= (retention_days // 30 + 1):
                    partition_name = f"logs_{year:04d}_{month:02d}"
                    try:
                        drop_stmt = text(f"DROP TABLE IF EXISTS {partition_name}")
                        await session.execute(drop_stmt)
                        await session.commit()
                        dropped.append(partition_name)
                    except Exception as exc:
                        logger.warning("partition_drop_failed", partition=partition_name, error=str(exc))

        return {"dropped": dropped}

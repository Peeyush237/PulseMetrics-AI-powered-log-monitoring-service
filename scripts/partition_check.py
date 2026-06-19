"""Check and list all log table partitions and their sizes."""
import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def check_partitions():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT
                child.relname AS partition_name,
                pg_size_pretty(pg_total_relation_size(child.oid)) AS total_size,
                pg_total_relation_size(child.oid) AS size_bytes
            FROM pg_inherits
            JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
            JOIN pg_class child ON pg_inherits.inhrelid = child.oid
            WHERE parent.relname = 'logs'
            ORDER BY child.relname
        """))
        rows = result.fetchall()
        if not rows:
            print("No partitions found. Run migrations first.")
            return
        print(f"{'Partition':<25} {'Size':>15}")
        print("-" * 42)
        total = 0
        for row in rows:
            print(f"{row.partition_name:<25} {row.total_size:>15}")
            total += row.size_bytes
        print("-" * 42)
        from sqlalchemy import func
        total_size = await session.execute(text("SELECT pg_size_pretty(SUM(pg_total_relation_size(child.oid))) FROM pg_inherits JOIN pg_class parent ON pg_inherits.inhparent = parent.oid JOIN pg_class child ON pg_inherits.inhrelid = child.oid WHERE parent.relname = 'logs'"))
        print(f"{'TOTAL':<25} {total_size.scalar():>15}")


if __name__ == "__main__":
    asyncio.run(check_partitions())

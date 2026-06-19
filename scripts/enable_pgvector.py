"""Run this once on a fresh database to enable the pgvector extension.
Useful if your hosting provider (Neon, Supabase, Render) needs it enabled
before Alembic migrations run.

Usage: python scripts/enable_pgvector.py
"""
import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pgvector"))
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await session.commit()
        print("pgvector and citext extensions enabled.")


if __name__ == "__main__":
    asyncio.run(main())

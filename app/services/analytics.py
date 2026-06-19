import io
from datetime import datetime, timedelta, timezone
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.log_repo import LogRepository

_LEVEL_COLORS = {
    "DEBUG": "#aaaaaa",
    "INFO": "#4CAF50",
    "WARNING": "#FF9800",
    "ERROR": "#F44336",
    "CRITICAL": "#9C27B0",
}


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.log_repo = LogRepository(session)

    async def timeline_png(
        self,
        application_id: Any,
        from_dt: datetime,
        to_dt: datetime,
    ) -> bytes:
        rows = await self.log_repo.get_hourly_counts(application_id, from_dt, to_dt)

        hours: dict[str, dict[str, int]] = {}
        for row in rows:
            h = row["hour"].strftime("%H:%M")
            hours.setdefault(h, {})[row["level"]] = row["count"]

        all_hours = sorted(hours.keys())
        levels = ["INFO", "WARNING", "ERROR", "CRITICAL"]

        fig, ax = plt.subplots(figsize=(12, 5))
        bottom = np.zeros(len(all_hours))

        for level in levels:
            counts = [hours.get(h, {}).get(level, 0) for h in all_hours]
            color = _LEVEL_COLORS.get(level, "#888888")
            ax.bar(all_hours, counts, bottom=bottom, label=level, color=color)
            bottom += np.array(counts)

        ax.set_xlabel("Hour (UTC)")
        ax.set_ylabel("Log count")
        ax.set_title("Log Volume Over Time")
        ax.legend(loc="upper right")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    async def top_errors_png(
        self,
        application_id: Any,
        from_dt: datetime,
        to_dt: datetime,
    ) -> bytes:
        rows = await self.log_repo.get_top_errors(application_id, from_dt, to_dt)

        messages = [r["message"][:60] + ("..." if len(r["message"]) > 60 else "") for r in rows]
        counts = [r["count"] for r in rows]

        fig, ax = plt.subplots(figsize=(12, max(4, len(messages) * 0.5)))
        y_pos = range(len(messages))
        ax.barh(y_pos, counts, color="#F44336")
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(messages, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("Occurrences")
        ax.set_title("Top Error Messages")
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    async def summary(
        self,
        application_id: Any,
        from_dt: datetime,
        to_dt: datetime,
    ) -> dict[str, Any]:
        from app.schemas.log import SearchFilters
        error_count = await self.log_repo.count_matching(
            application_id=application_id,
            filters=SearchFilters(level=">=ERROR"),
            window_start=from_dt,
            window_end=to_dt,
        )
        total_count = await self.log_repo.count_matching(
            application_id=application_id,
            filters=SearchFilters(),
            window_start=from_dt,
            window_end=to_dt,
        )
        return {
            "total_logs": total_count,
            "error_logs": error_count,
            "error_rate": round(error_count / total_count, 4) if total_count > 0 else 0,
            "from": from_dt.isoformat(),
            "to": to_dt.isoformat(),
        }

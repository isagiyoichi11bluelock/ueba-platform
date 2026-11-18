"""Context event generation (benign-explanation contexts)."""
from __future__ import annotations
import random
import uuid
from dataclasses import dataclass
from datetime import date, timedelta, datetime
from .org import OrgStructure, User


@dataclass
class ContextEvent:
    context_id: str
    user_id: str
    context_type: str  # approved_travel, month_end_close, on_call, project_deadline, new_joiner, role_change
    start_time: datetime
    end_time: datetime
    approved_by_role: str
    notes: str


def generate_context_events(
    org: OrgStructure,
    start_date: date,
    end_date: date,
    seed: int = 42,
) -> list[ContextEvent]:
    """Generate realistic context events over the period."""
    rng = random.Random(seed + 100)
    events = []

    finance_users = [u for u in org.users if u.role == "Finance"]
    it_admin_users = [u for u in org.users if u.role == "IT Admin"]

    # Month-end close: last 3 days of each month for Finance
    current = start_date
    while current <= end_date:
        import calendar
        last_day = calendar.monthrange(current.year, current.month)[1]
        if current.day >= last_day - 2:
            for user in finance_users:
                events.append(ContextEvent(
                    context_id=str(uuid.uuid4()),
                    user_id=user.user_id,
                    context_type="month_end_close",
                    start_time=datetime(current.year, current.month, last_day - 2, 0, 0),
                    end_time=datetime(current.year, current.month, last_day, 23, 59),
                    approved_by_role="Finance Manager",
                    notes="Scheduled month-end financial close process",
                ))
        current += timedelta(days=1)

    # Approved travel for some users
    for user in rng.sample(org.users, min(8, len(org.users))):
        travel_start = start_date + timedelta(days=rng.randint(5, 60))
        travel_end = travel_start + timedelta(days=rng.randint(2, 7))
        events.append(ContextEvent(
            context_id=str(uuid.uuid4()),
            user_id=user.user_id,
            context_type="approved_travel",
            start_time=datetime.combine(travel_start, datetime.min.time()),
            end_time=datetime.combine(min(travel_end, end_date), datetime.max.time().replace(microsecond=0)),
            approved_by_role="Manager",
            notes=f"Approved business travel to {rng.choice(['London', 'New York', 'Singapore', 'Tokyo'])}",
        ))

    # On-call windows for IT Admins
    for it_user in it_admin_users:
        for week in range(0, (end_date - start_date).days // 7):
            on_call_day = start_date + timedelta(days=week * 7 + rng.randint(0, 6))
            if on_call_day <= end_date:
                events.append(ContextEvent(
                    context_id=str(uuid.uuid4()),
                    user_id=it_user.user_id,
                    context_type="on_call",
                    start_time=datetime.combine(on_call_day, datetime.min.time()),
                    end_time=datetime.combine(on_call_day, datetime.max.time().replace(microsecond=0)),
                    approved_by_role="IT Manager",
                    notes="Scheduled on-call shift",
                ))

    return events

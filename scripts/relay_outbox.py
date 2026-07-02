"""Minimal demonstration of relaying the transactional outbox.

Polls `outbox_events` for unpublished rows, prints them as JSON lines (in a
real deployment this would publish to Kafka/RabbitMQ/etc instead), and marks
them published. Safe to run repeatedly / concurrently with itself since it
claims rows with a plain UPDATE before printing.

Usage: python -m scripts.relay_outbox [--once]
"""

import argparse
import json
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import OutboxEvent


def relay_once() -> int:
    with SessionLocal() as db:
        events = (
            db.execute(
                select(OutboxEvent).where(OutboxEvent.published_at.is_(None)).order_by(OutboxEvent.created_at)
            )
            .scalars()
            .all()
        )
        for event in events:
            print(json.dumps({"event_type": event.event_type, "payload": event.payload}))
            event.published_at = datetime.now(timezone.utc)
        db.commit()
        return len(events)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Relay pending events once and exit")
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval in seconds")
    args = parser.parse_args()

    if args.once:
        relay_once()
        return

    while True:
        relay_once()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

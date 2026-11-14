"""One-off migration of the old one-JSON-blob-per-user rows (`user_data`) into the normalized tables."""
import json
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FoodEntry, LegacyDoc, Profile, User, Workout
from app.services import legacy


@dataclass
class Report:
    migrated: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)


def already_migrated(db: Session, uid: int) -> bool:
    if db.get(Profile, uid):
        return True
    return bool(db.scalar(select(func.count()).select_from(FoodEntry).where(FoodEntry.user_id == uid))
                or db.scalar(select(func.count()).select_from(Workout).where(Workout.user_id == uid)))


def migrate_legacy(db: Session, force: bool = False, dry_run: bool = False) -> Report:
    """Each user is migrated in its own transaction, so one bad blob can't block the rest.
    Users that already have new-schema data are skipped unless `force` (which replaces it)."""
    rep = Report()
    for user in db.scalars(select(User).order_by(User.id)).all():
        docs = {d.kind: d for d in db.scalars(select(LegacyDoc).where(LegacyDoc.user_id == user.id)).all()}
        if not docs:
            rep.skipped.append((user.email, "no legacy data"))
            continue
        if already_migrated(db, user.id) and not force:
            rep.skipped.append((user.email, "already migrated"))
            continue
        try:
            if "tracker" in docs:
                legacy.write_tracker(db, user.id, json.loads(docs["tracker"].body), commit=False)
            if "workouts" in docs:
                legacy.write_workouts(db, user.id, json.loads(docs["workouts"].body), commit=False)
            db.rollback() if dry_run else db.commit()
            rep.migrated.append(user.email)
        except Exception as e:  # noqa: BLE001 - report and carry on with the next user
            db.rollback()
            rep.failed.append((user.email, repr(e)))
    return rep

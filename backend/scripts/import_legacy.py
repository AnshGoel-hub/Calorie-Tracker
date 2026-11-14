#!/usr/bin/env python3
"""Move old JSON-blob data (user_data table) into the normalized tables.

    alembic upgrade head
    python scripts/import_legacy.py --dry-run
    python scripts/import_legacy.py
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import db as database  # noqa: E402
from app.core.config import load_settings  # noqa: E402
from app.services.legacy_import import migrate_legacy  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="do everything, then roll back")
    ap.add_argument("--force", action="store_true", help="re-import users that already have new-schema data")
    a = ap.parse_args()
    database.configure(load_settings().database_url)
    with database.SessionLocal() as db:
        rep = migrate_legacy(db, force=a.force, dry_run=a.dry_run)
    print(("DRY RUN: " if a.dry_run else "") + f"migrated {len(rep.migrated)}, skipped {len(rep.skipped)}, "
          f"failed {len(rep.failed)}")
    for email, why in rep.skipped:
        print(f"  skipped {email}: {why}")
    for email, why in rep.failed:
        print(f"  FAILED  {email}: {why}", file=sys.stderr)
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())

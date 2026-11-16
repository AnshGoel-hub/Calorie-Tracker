#!/usr/bin/env python3
"""Admin CLI for the Calorie Tracker database. Run `python scripts/admin.py --help`."""
import argparse
import getpass
import json
import os
import re
import secrets
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
paint = lambda t, c: f"\033[{c}m{t}\033[0m" if COLOR else str(t)  # noqa: E731
bold, dim, red, green, yellow = (lambda t: paint(t, "1"), lambda t: paint(t, "2"), lambda t: paint(t, "31"),
                                 lambda t: paint(t, "32"), lambda t: paint(t, "33"))


def die(msg, code=1):
    print(red(msg), file=sys.stderr)
    sys.exit(code)


def dotenv_value(key: str) -> str:
    f = Path(__file__).resolve().parents[1] / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            k, _, v = line.strip().partition("=")
            if k.strip() == key:
                return v.strip().strip("\"'")
    return ""


def describe(url):
    u = urlparse(url)
    return "sqlite file " + u.path if u.scheme.startswith("sqlite") else f"{u.hostname}/{u.path.lstrip('/')}"


def connect(choice):
    """Pick the live or local database, then configure the app's engine for it."""
    from app.core import db as database
    from app.core.config import normalize_db_url
    live = os.environ.get("ADMIN_DATABASE_URL") or dotenv_value("ADMIN_DATABASE_URL")
    if choice == "live" and not live:
        die("No live database set. Add this line to backend/.env:\n  ADMIN_DATABASE_URL=postgresql://...")
    use_live = bool(live) and choice != "local"
    url = normalize_db_url(live if use_live else "")
    database.configure(url)
    print(f"{dim('database:')} {red(bold('LIVE')) if use_live else green(bold('LOCAL'))} {dim(describe(url))}",
          file=sys.stderr)
    return database


def table(rows, cols):
    if not rows:
        print(dim("(none)"))
        return
    data = [[str(r[k]) for _, k in cols] for r in rows]
    w = [max([len(h)] + [len(d[i]) for d in data]) for i, (h, _) in enumerate(cols)]
    print(bold("  ".join(h.ljust(w[i]) for i, (h, _) in enumerate(cols))))
    for d in data:
        print("  ".join(x.ljust(w[i]) for i, x in enumerate(d)))


def confirm(prompt, assume_yes=False, must_type=None):
    if assume_yes:
        return True
    try:
        if must_type:
            return input(f"{prompt}\nType {bold(must_type)} to confirm: ").strip().lower() == must_type.lower()
        return input(f"{prompt} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        die("This needs a confirmation. Run it in a terminal, or pass --yes.")


def when(ms=None, secs=None):
    v = secs if secs is not None else (ms / 1000 if ms else 0)
    return datetime.fromtimestamp(v).strftime("%Y-%m-%d") if v else "never"


def find_user(db, email):
    from sqlalchemy import select

    from app.models import User
    email = email.strip().lower()
    u = db.scalar(select(User).where(User.email == email))
    if u:
        return u
    near = [e for (e,) in db.execute(select(User.email)).all() if email.split("@")[0] in e]
    die(f"No account with email {email}." + (f"\nDid you mean: {', '.join(near[:5])}?" if near else
        "\nRun `python scripts/admin.py list` to see all accounts."))


def summary(db, uid):
    from sqlalchemy import func, select

    from app.models import DayLog, Food, FoodEntry, Workout
    n = lambda col, *where: db.scalar(select(func.count(col)).where(*where))  # noqa: E731
    return {"days_logged": n(DayLog.date, DayLog.user_id == uid),
            "food_entries": n(FoodEntry.id, FoodEntry.user_id == uid, FoodEntry.deleted_at.is_(None)),
            "workouts": n(Workout.id, Workout.user_id == uid, Workout.deleted_at.is_(None)),
            "custom_foods": n(Food.id, Food.owner_id == uid)}


def database_session():
    from app.core import db as database
    return database.SessionLocal()


# ------------------------------------------------------------ commands
def cmd_status(a):
    from sqlalchemy import func, select, text

    from app.models import User
    connect(a.db)
    t0 = time.time()
    with database_session() as db:
        db.execute(text("select 1"))
        n = db.scalar(select(func.count()).select_from(User))
    print(green("connected") + f" in {(time.time() - t0) * 1000:.0f} ms, {n} account(s)")


def cmd_list(a):
    from sqlalchemy import select

    from app.models import Profile, Usage, User
    connect(a.db)
    with database_session() as db:
        rows = []
        for u in db.scalars(select(User).order_by(User.id)).all():
            p = db.get(Profile, u.id)
            used = db.get(Usage, (u.id, date.today()))
            rows.append({"id": u.id, "email": u.email, "joined": when(secs=u.created),
                         "last_active": when(ms=max(p.tracker_updated, p.workouts_updated) if p else 0),
                         "estimates_today": used.n if used else 0})
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    table(rows, [("ID", "id"), ("EMAIL", "email"), ("JOINED", "joined"), ("LAST ACTIVE", "last_active"),
                 ("GEMINI TODAY", "estimates_today")])
    print(dim(f"{len(rows)} account(s)"))


def cmd_show(a):
    connect(a.db)
    with database_session() as db:
        u = find_user(db, a.email)
        s = summary(db, u.id)
        print(f"{bold(u.email)}  {dim('id ' + str(u.id))}\n  joined        {when(secs=u.created)}")
        for k, v in s.items():
            print(f"  {k.replace('_', ' '):<13} {v}")


def cmd_reset(a):
    from app.core.security import hash_pw
    connect(a.db)
    with database_session() as db:
        u = find_user(db, a.email)
        if a.set:
            pw = getpass.getpass("New password (min 8 characters): ")
            if len(pw) < 8:
                die("Password must be at least 8 characters.")
            if pw != getpass.getpass("Repeat it: "):
                die("Passwords don't match.")
        else:
            alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alike characters
            pw = "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))
        if not confirm(f"Reset the password for {bold(u.email)}? They will be signed out everywhere.", a.yes):
            die("Cancelled.")
        u.pw_hash = hash_pw(pw)
        db.commit()
    print(green("Password reset.") + " All their sessions are signed out.")
    if not a.set:
        print(f"Temporary password: {bold(pw)}")
        print(dim("Send it privately and ask them to change it on the Account page."))


def cmd_delete(a):
    from sqlalchemy import delete

    from app.models import LegacyDoc, Usage
    connect(a.db)
    with database_session() as db:
        u = find_user(db, a.email)
        s = summary(db, u.id)
        print(yellow(f"{u.email}: {s['days_logged']} days, {s['food_entries']} entries, {s['workouts']} workouts."))
        if not confirm(red("This permanently deletes the account and all its data."), a.yes, must_type=u.email):
            die("Cancelled.")
        db.execute(delete(Usage).where(Usage.user_id == u.id))
        db.execute(delete(LegacyDoc).where(LegacyDoc.user_id == u.id))
        db.delete(u)  # all other tables cascade
        db.commit()
    print(green("Deleted."))


def cmd_export(a):
    from app.services import legacy
    connect(a.db)
    with database_session() as db:
        u = find_user(db, a.email)
        slug = re.sub(r"[^a-z0-9]+", "-", u.email.split("@")[0]) or "user"
        out = Path(a.output or f"export-{slug}-{date.today().isoformat()}.json")
        if out.exists():
            die(f"{out} already exists. Choose another name with -o.")
        doc = {"email": u.email, "exported": datetime.now().isoformat(timespec="seconds"),
               "tracker": legacy.read_tracker(db, u.id), "workouts": legacy.read_workouts(db, u.id)}
    out.write_text(json.dumps(doc, indent=1))
    print(green("Saved ") + str(out) + dim("  (contains personal data, keep it private)"))


EXAMPLES = """examples:
  python scripts/admin.py status
  python scripts/admin.py list
  python scripts/admin.py show friend@example.com
  python scripts/admin.py reset friend@example.com        prints a temporary password
  python scripts/admin.py export friend@example.com -o friend.json
  python scripts/admin.py delete friend@example.com
  python scripts/admin.py list --db local                 your local test database

setup (once): add to backend/.env (git-ignored)
  ADMIN_DATABASE_URL=postgresql://...your Neon string...
Keep DATABASE_URL empty there so the dev server still uses local.db.
"""


def build():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", choices=["live", "local"],
                        help="database to use (default: live if ADMIN_DATABASE_URL is set, else local)")
    p = argparse.ArgumentParser(prog="admin.py", description="Manage Calorie Tracker accounts.", epilog=EXAMPLES,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", metavar="command", required=True)

    def add(name, fn, help_, email=False):
        sp = sub.add_parser(name, parents=[common], help=help_, description=help_)
        if email:
            sp.add_argument("email")
        sp.set_defaults(fn=fn)
        return sp

    add("status", cmd_status, "check the connection and count accounts")
    add("list", cmd_list, "list all accounts").add_argument("--json", action="store_true")
    add("show", cmd_show, "show one account's details", True)
    sp = add("reset", cmd_reset, "reset a password (signs them out everywhere)", True)
    sp.add_argument("--set", action="store_true", help="type the new password yourself")
    sp.add_argument("-y", "--yes", action="store_true")
    sp = add("delete", cmd_delete, "permanently delete an account and its data", True)
    sp.add_argument("-y", "--yes", action="store_true", help="skip the confirmation (be careful)")
    sp = add("export", cmd_export, "save one account's data to a JSON file", True)
    sp.add_argument("-o", "--output")
    return p


def main():
    args = build().parse_args()
    try:
        args.fn(args)
    except KeyboardInterrupt:
        die("\nCancelled.", 130)
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ in ("OperationalError", "InterfaceError", "ArgumentError"):
            die(f"Couldn't connect to the database ({type(e).__name__}). Check ADMIN_DATABASE_URL and your network.")
        raise


if __name__ == "__main__":
    main()

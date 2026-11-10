#!/usr/bin/env python3
"""Admin CLI for the Calorie Tracker database."""
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

BASE = Path(__file__).parent
if os.name == "nt":
    os.system("")  # turns on ANSI colours in the Windows console
COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def paint(text, code):
    return f"\033[{code}m{text}\033[0m" if COLOR else str(text)


bold = lambda t: paint(t, "1")
dim = lambda t: paint(t, "2")
red = lambda t: paint(t, "31")
green = lambda t: paint(t, "32")
yellow = lambda t: paint(t, "33")


def die(msg, code=1):
    print(red(msg), file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------ choosing the database
def read_dotenv():
    vals, f = {}, BASE / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip("\"'")
    return vals


def describe(url):
    if not url:
        return "local.db (on this computer)"
    u = urlparse(url)
    if u.scheme.startswith("sqlite"):
        return "sqlite file " + u.path
    return f"{u.hostname}/{u.path.lstrip('/')}"


def connect(choice):
    """Pick the live or local database BEFORE importing the app, then import it."""
    live = os.environ.get("ADMIN_DATABASE_URL") or read_dotenv().get("ADMIN_DATABASE_URL", "")
    if choice == "live" and not live:
        die("No live database set. Add this line to your .env file:\n"
            "  ADMIN_DATABASE_URL=postgresql://...your Neon string...")
    use_live = bool(live) and choice != "local"
    os.environ["DATABASE_URL"] = live if use_live else ""
    os.environ.setdefault("JWT_SECRET", "admin-cli-unused")
    import main  # noqa: E402  (creates the engine from DATABASE_URL)
    label = red(bold("LIVE")) if use_live else green(bold("LOCAL"))
    print(f"{dim('database:')} {label} {dim(describe(os.environ['DATABASE_URL']))}", file=sys.stderr)
    return main


# ------------------------------------------------------------ helpers
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


def find_user(m, email):
    from sqlalchemy import select
    email = email.strip().lower()
    with m.engine.connect() as c:
        row = c.execute(select(m.users.c.id, m.users.c.email, m.users.c.created)
                        .where(m.users.c.email == email)).first()
        if row:
            return row
        near = [r.email for r in c.execute(select(m.users.c.email)).all() if email.split("@")[0] in r.email]
    die(f"No account with email {email}." + (f"\nDid you mean: {', '.join(near[:5])}?" if near else
        "\nRun `python admin.py list` to see all accounts."))


def summary(m, uid):
    t, w = m.read_doc(uid, "tracker"), m.read_doc(uid, "workouts")
    log = t.get("log", {})
    return {"days_logged": len(log), "food_entries": sum(len(d.get("e", [])) for d in log.values()),
            "workouts": len(w.get("workouts", [])), "custom_foods": len(t.get("custom", []))}


def temp_password():
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alike characters, easy to send in a chat
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


def when(ms=None, secs=None):
    v = secs if secs is not None else (ms / 1000 if ms else 0)
    return datetime.fromtimestamp(v).strftime("%Y-%m-%d") if v else "never"


# ------------------------------------------------------------ commands
def cmd_status(a):
    from sqlalchemy import func, select, text
    m = connect(a.db)
    t0 = time.time()
    with m.engine.connect() as c:
        c.execute(text("select 1"))
        n = c.execute(select(func.count()).select_from(m.users)).scalar()
    print(green("connected") + f" in {(time.time() - t0) * 1000:.0f} ms, {n} account(s)")


def cmd_list(a):
    from sqlalchemy import func, select
    m = connect(a.db)
    U, D, G = m.users, m.user_data, m.usage
    with m.engine.connect() as c:
        users = c.execute(select(U.c.id, U.c.email, U.c.created).order_by(U.c.id)).all()
        last = {r[0]: r[1] for r in c.execute(select(D.c.user_id, func.max(D.c.updated)).group_by(D.c.user_id)).all()}
        used = {r[0]: r[1] for r in c.execute(select(G.c.user_id, G.c.n).where(G.c.day == date.today())).all()}
    rows = [{"id": u.id, "email": u.email, "joined": when(secs=u.created),
             "last_active": when(ms=last.get(u.id)), "estimates_today": used.get(u.id, 0)} for u in users]
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    table(rows, [("ID", "id"), ("EMAIL", "email"), ("JOINED", "joined"),
                 ("LAST ACTIVE", "last_active"), ("GEMINI TODAY", "estimates_today")])
    print(dim(f"{len(rows)} account(s)"))


def cmd_show(a):
    m = connect(a.db)
    u = find_user(m, a.email)
    s = summary(m, u.id)
    print(f"{bold(u.email)}  {dim('id ' + str(u.id))}")
    print(f"  joined        {when(secs=u.created)}")
    for k, v in s.items():
        print(f"  {k.replace('_', ' '):<13} {v}")


def cmd_reset(a):
    m = connect(a.db)
    u = find_user(m, a.email)
    if a.set:
        pw = getpass.getpass("New password (min 8 characters): ")
        if len(pw) < 8:
            die("Password must be at least 8 characters.")
        if pw != getpass.getpass("Repeat it: "):
            die("Passwords don't match.")
    else:
        pw = temp_password()
    if not confirm(f"Reset the password for {bold(u.email)}? They will be signed out everywhere.", a.yes):
        die("Cancelled.")
    with m.engine.begin() as c:
        c.execute(m.users.update().where(m.users.c.id == u.id).values(pw_hash=m.hash_pw(pw)))
    print(green("Password reset.") + " All their sessions are signed out.")
    if not a.set:
        print(f"Temporary password: {bold(pw)}")
        print(dim("Send it to them privately and ask them to change it on the Account page."))


def cmd_delete(a):
    from sqlalchemy import delete
    m = connect(a.db)
    u = find_user(m, a.email)
    s = summary(m, u.id)
    print(yellow(f"{u.email}: {s['days_logged']} days logged, {s['food_entries']} food entries, {s['workouts']} workouts."))
    if not confirm(red("This permanently deletes the account and all its data."), a.yes, must_type=u.email):
        die("Cancelled.")
    with m.engine.begin() as c:
        for t, col in ((m.user_data, m.user_data.c.user_id), (m.usage, m.usage.c.user_id), (m.users, m.users.c.id)):
            c.execute(delete(t).where(col == u.id))
    print(green("Deleted."))


def cmd_export(a):
    m = connect(a.db)
    u = find_user(m, a.email)
    slug = re.sub(r"[^a-z0-9]+", "-", u.email.split("@")[0]) or "user"
    out = Path(a.output or f"export-{slug}-{date.today().isoformat()}.json")
    if out.exists():
        die(f"{out} already exists. Choose another name with -o.")
    doc = {"email": u.email, "exported": datetime.now().isoformat(timespec="seconds"),
           "tracker": m.read_doc(u.id, "tracker"), "workouts": m.read_doc(u.id, "workouts")}
    out.write_text(json.dumps(doc, indent=1))
    print(green("Saved ") + str(out) + dim("  (contains personal data, keep it private)"))


# ------------------------------------------------------------ entry point
EXAMPLES = """examples:
  python admin.py status
  python admin.py list
  python admin.py show friend@example.com
  python admin.py reset friend@example.com        prints a temporary password
  python admin.py reset friend@example.com --set  type a password yourself
  python admin.py export friend@example.com -o friend.json
  python admin.py delete friend@example.com
  python admin.py list --db local                 your local test database

setup (once): add this line to your .env file (it is git-ignored)
  ADMIN_DATABASE_URL=postgresql://...your Neon string...
Keep DATABASE_URL empty there so `python main.py` still uses local.db.
"""


def build():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", choices=["live", "local"],
                        help="which database to use (default: live if ADMIN_DATABASE_URL is set, else local)")
    p = argparse.ArgumentParser(prog="admin.py", description="Manage Calorie Tracker accounts.",
                                epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", metavar="command", required=True)

    def add(name, fn, help_, email=False):
        sp = sub.add_parser(name, parents=[common], help=help_, description=help_)
        if email:
            sp.add_argument("email")
        sp.set_defaults(fn=fn)
        return sp

    add("status", cmd_status, "check the connection and count accounts")
    add("list", cmd_list, "list all accounts").add_argument("--json", action="store_true", help="machine-readable output")
    add("show", cmd_show, "show one account's details", True)
    sp = add("reset", cmd_reset, "reset a password (signs them out everywhere)", True)
    sp.add_argument("--set", action="store_true", help="type the new password yourself instead of generating one")
    sp.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    sp = add("delete", cmd_delete, "permanently delete an account and its data", True)
    sp.add_argument("-y", "--yes", action="store_true", help="skip the confirmation (be careful)")
    sp = add("export", cmd_export, "save one account's data to a JSON file", True)
    sp.add_argument("-o", "--output", help="output file name")
    return p


def main_cli():
    args = build().parse_args()
    try:
        args.fn(args)
    except KeyboardInterrupt:
        die("\nCancelled.", 130)
    except Exception as e:  # database unreachable, bad connection string, etc.
        if type(e).__name__ in ("OperationalError", "InterfaceError", "ArgumentError"):
            die(f"Couldn't connect to the database ({type(e).__name__}). Check ADMIN_DATABASE_URL in .env "
                "and your internet connection.")
        raise


if __name__ == "__main__":
    main_cli()

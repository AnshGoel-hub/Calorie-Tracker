"""Copy your existing tracker_data.json / workouts_data.json into a user's account.
Usage: sign up in the app first, then run
    DATABASE_URL=<your neon url> python import_local.py you@example.com
"""
import json, sys
from pathlib import Path
from sqlalchemy import select
import main

email = sys.argv[1].strip().lower()
with main.engine.connect() as c:
    row = c.execute(select(main.users.c.id).where(main.users.c.email == email)).first()
if not row:
    sys.exit("No such user. Create the account in the app first.")
for kind, fname in (("tracker", "tracker_data.json"), ("workouts", "workouts_data.json")):
    p = Path(fname)
    if p.exists():
        doc = json.loads(p.read_text())
        doc["updated"] = int(__import__("time").time() * 1000)  # make it win over any cached copy
        main.write_doc(row.id, kind, doc)
        print("imported", fname)

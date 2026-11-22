# DSA Tracker

A local, single-user spaced-repetition tracker for SDE-3 DSA interview prep.
Two full rounds across the syllabus: Round 1 is pen-and-paper/approach-only,
Round 2 is full implementation. No round-2 questions surface until every
question in every unlocked topic has graduated round 1.

## Start the app

**Windows:** double-click `start.bat`.
**macOS / Linux:** run `./start.sh`.

The first run sets everything up -- it creates the virtualenv, installs the
dependencies, builds `dsa_tracker.db` from `seed_data.py`, starts the server at
**http://localhost:8000** and opens it in your browser. Later runs skip straight
to starting the server. Stop it by closing the window or pressing `Ctrl+C`.

New here? `GUIDE.md` is a fuller walkthrough of what the app does and how to
use it day to day.

If you'd rather drive it by hand, or the launcher misbehaves:

```
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe app.py
```

(On macOS and Linux that interpreter is `./venv/bin/python`.) Deleting the
`venv` folder and re-running the launcher rebuilds it from scratch.

## Tech stack

- Backend: Python + FastAPI + SQLite (stdlib `sqlite3`, no ORM)
- Frontend: single static page, vanilla JS + CSS, served by FastAPI (no build step)
- Data: `dsa_tracker.db`, a single SQLite file in this folder

## Project structure

```
start.bat       One-click launcher for Windows (sets up on first run)
start.sh        Same, for macOS and Linux
app.py          FastAPI routes, static file serving, entrypoint (python app.py)
db.py           Schema definition + first-run seeding
logic.py        All scheduling/spaced-repetition rules (pure functions, no HTTP)
seed_data.py    The syllabus loaded into the DB the first time it's created
static/         index.html, app.js, style.css -- the whole frontend
dsa_tracker.db  Your actual data. Back this up if you care about your progress.
GUIDE.md        Walkthrough for someone picking the app up for the first time
venv/           Local virtualenv (fastapi, uvicorn) -- not synced/committed
```

## Resetting your data

Close the running app, delete `dsa_tracker.db`, and restart -- it will be
recreated from `seed_data.py` on next launch. There's no undo, so copy the
file somewhere first if you want a backup.

## How the scheduling works (quick reference)

- **Today's 5**: 2 revision questions (earliest `next_due_date`, ties broken
  by highest `fail_count`) + 3 fresh questions (never attempted this round,
  spread round-robin across topics). Backfills either side if one pool is
  short. Assignments are cached per day, so re-opening the app the same day
  shows the same 5 -- use "Regenerate" to force a new pull.
- **Solving a question**: streak stage 0→1 (+1 day), 1→2 (+3 days),
  2→3 (+5 days), 3→graduated (removed from rotation for that round).
- **Failing a question**: streak resets to 0, `fail_count` increments, the
  question becomes immediately eligible again as a fresh pull (no due date).
- **Round 1 → Round 2**: once every question in every active/done topic has
  graduated round 1, `round1_complete` flips globally and all future daily
  pulls switch to round 2 for those topics.
- **Unlocking topics**: only allowed on a Saturday or Sunday. Unlocking sets
  a topic to "pending" (visible in Topic Manager); it only enters the daily
  rotation once you confirm you've done a first pen-and-paper pass over all
  its questions ("Confirm first pass done").

## If something breaks or you want a change

Paste this into a Claude Code session in this project directory:

> I'm using the DSA Tracker app in this directory (FastAPI + SQLite backend
> in `app.py`/`db.py`/`logic.py`, vanilla JS frontend in `static/`). Read
> `README.md` for how it works. [Describe the bug you're seeing, or the
> change/feature you want.] Start the app with
> `start.bat` (or `./start.sh`) to test your fix before confirming
> it's done.

Being specific helps a lot -- e.g. "the 'Regenerate' button on Today's 5
doesn't refresh the revision picks" or "add a CSV export of daily_log" will
get fixed/built faster than a vague "it's broken."

A few things worth knowing if you're the one debugging:
- All scheduling logic lives in `logic.py` and is decoupled from FastAPI --
  it can be tested directly with a plain Python script and a throwaway
  SQLite file (point `db.DB_PATH` at a temp path before calling
  `db.init_db()`), without touching your real `dsa_tracker.db`.
- The server logs to stdout/stderr wherever you launched it from; if the
  browser tab shows an error, check that terminal first.
- Schema changes need a fresh `dsa_tracker.db` (see "Resetting your data")
  since there's no migration system -- this is intentional, given it's a
  single-user local tool.

# DSA Tracker — a guide for getting started

A small app that decides which five data-structures questions you practise
today, and quietly remembers when to show each one again.

## What it actually is

It's a spaced-repetition tracker built for SDE-3 interview prep. You don't
browse a question bank and hope you picked well — you open it, it gives you
exactly five questions, you mark each one solved or not solved, and you close
it. The scheduling is the whole point.

It runs entirely on your own laptop. There's no account, no server, no
syncing. Your progress lives in a single SQLite file in this folder, so nobody
else can see what you've solved.

The syllabus that ships with it is **152 questions across 22 topics**, from
Sliding Window and Binary Search through nine separate dynamic-programming
families, Segment Trees and Tries. Nine topics start unlocked; the other
thirteen stay out of your way until you open them.

## Getting it running

You need **Python 3.12 or newer** installed. On Windows, get it from
<https://www.python.org/downloads/> and tick "Add Python to PATH" in the
installer.

Then:

- **Windows** — double-click **`start.bat`**.
- **macOS / Linux** — run **`./start.sh`** in a terminal.

That's it. The first run creates a virtual environment, installs the two
dependencies, builds your database with the full syllabus, starts the server
and opens <http://localhost:8000> in your browser. It takes a minute or so.
Every run after that starts immediately.

Stop the app by closing its window, or pressing `Ctrl+C` in it.

## Your first session

The app opens on **Today's 5**. Each card shows the question, its topic, your
current streak and how many times you've failed it, plus a green **Solved**
button, a red **Not solved** button, and an optional notes field.

Answer honestly. "Not solved" isn't a penalty — it's the signal the scheduler
needs, and marking something solved when you only half-remembered it is the
one way to break this tool.

**Round 1 is pen and paper.** You're not writing code yet. For each question
you work out the approach on paper — the data structure, the invariant, the
complexity — and that's what counts as solved. Round 2, where you actually
implement everything, only unlocks after every question in every open topic
has graduated Round 1.

## How the scheduling works

Your daily five are two revision questions — whatever is most overdue, with
repeatedly-failed questions jumping the queue — plus three you've never seen
this round, spread round-robin so you're not hammering one topic. If either
pool runs dry it backfills from the other.

Solve a question and it comes back on a widening schedule:

| Solve        | Next shown  |
| ------------ | ----------- |
| First        | +1 day      |
| Second       | +3 days     |
| Third        | +5 days     |
| Fourth       | graduated   |

Mark one *not solved* and the streak drops to zero, the fail count ticks up,
and it goes straight back into the fresh pool to be served again soon.

The same five stay put if you reopen the app later in the day — that's
deliberate, so you can't reroll your way to easier questions. **Regenerate**
forces a new pull if you genuinely need one.

## Adding topics

New topics can only be unlocked **on a Saturday or Sunday**. On weekends a
banner appears at the top with an Unlock button for each locked topic.

Unlocking doesn't drop the questions straight into your rotation. The topic
sits as *pending first pass* until you've read through all its questions on
paper once and clicked **Confirm first pass done** in Topic Manager. Only then
does it start feeding your daily five.

## The other tabs

| Tab                 | What it's for                                                                 |
| ------------------- | ----------------------------------------------------------------------------- |
| **Today's 5**       | Your daily queue. The only tab you need most days.                            |
| **Progress**        | Where you stand per topic — what's graduated, what's still in rotation.       |
| **Topic Manager**   | Unlock topics, confirm first passes, add your own topics.                     |
| **Question Editor** | Add or edit questions, if your target companies lean somewhere the stock syllabus doesn't. |

## Worth knowing

- **Back up `dsa_tracker.db`.** It is your entire progress and it is not in
  the repository. Copy it somewhere occasionally.
- **Starting over** means closing the app, deleting `dsa_tracker.db`, and
  relaunching. There's no undo.
- **If something breaks**, look at the window you launched from first — the
  server logs its errors there.
- **Pulling updates** is safe: `git pull` never touches your database, since
  it's excluded from the repo.

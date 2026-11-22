"""Scheduling / spaced-repetition business logic. Pure functions over a
sqlite3 connection -- no FastAPI/HTTP concerns here."""

import datetime

WEEKEND_DAYS = (5, 6)  # Saturday, Sunday (datetime.weekday())


def is_weekend(d: datetime.date) -> bool:
    return d.weekday() in WEEKEND_DAYS


def today_str(d: datetime.date) -> str:
    return d.isoformat()


# ---------------------------------------------------------------- settings

def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def is_round1_complete(conn) -> bool:
    return get_setting(conn, "round1_complete", "0") == "1"


def current_round(conn) -> int:
    return 2 if is_round1_complete(conn) else 1


# ------------------------------------------------------------ topic status

def unlocked_topic_ids(conn):
    rows = conn.execute("SELECT id FROM topics WHERE status IN ('active','done')").fetchall()
    return [r["id"] for r in rows]


def unlock_topic(conn, topic_id: int, today: datetime.date):
    if not is_weekend(today):
        raise ValueError("Locked topics can only be unlocked on a Saturday or Sunday. Wait for the weekend.")
    topic = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
    if topic is None:
        raise LookupError("Topic not found")
    if topic["status"] != "locked":
        raise ValueError(f"Topic is '{topic['status']}', not locked -- nothing to unlock.")
    conn.execute(
        "UPDATE topics SET status='pending', unlocked_weekend=1, started_at=? WHERE id=?",
        (today_str(today), topic_id),
    )
    conn.commit()


def confirm_first_pass(conn, topic_id: int):
    topic = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
    if topic is None:
        raise LookupError("Topic not found")
    if topic["status"] != "pending":
        raise ValueError("Topic has no unlock pending confirmation.")
    conn.execute("UPDATE topics SET status='active' WHERE id=?", (topic_id,))
    conn.commit()


# ------------------------------------------------------------- daily pull

def _row_to_question(row, round_num, slot_type=None):
    d = dict(row)
    d["round"] = round_num
    if slot_type:
        d["slot_type"] = slot_type
    return d


def get_today_five(conn, today: datetime.date):
    ds = today_str(today)
    existing = conn.execute(
        "SELECT da.slot_type, da.round, q.*, t.name AS topic_name "
        "FROM daily_assignment da "
        "JOIN questions q ON q.id = da.question_id "
        "JOIN topics t ON t.id = q.topic_id "
        "WHERE da.date=? ORDER BY (da.slot_type='revision') DESC, da.id ASC",
        (ds,),
    ).fetchall()
    if existing:
        return [dict(r) for r in existing]
    return _generate_today_five(conn, today)


def regenerate_today_five(conn, today: datetime.date):
    ds = today_str(today)
    conn.execute("DELETE FROM daily_assignment WHERE date=?", (ds,))
    conn.commit()
    return _generate_today_five(conn, today)


def _generate_today_five(conn, today: datetime.date):
    ds = today_str(today)
    round_num = current_round(conn)
    status_field = f"round{round_num}_status"

    revision_pool = conn.execute(
        f"SELECT q.*, t.name AS topic_name FROM questions q JOIN topics t ON t.id=q.topic_id "
        f"WHERE t.status='active' AND q.{status_field} != 'solved' "
        f"AND q.next_due_date IS NOT NULL AND q.next_due_date <= ? "
        f"ORDER BY q.next_due_date ASC, q.fail_count DESC, q.id ASC",
        (ds,),
    ).fetchall()

    fresh_rows = conn.execute(
        f"SELECT q.*, t.name AS topic_name FROM questions q JOIN topics t ON t.id=q.topic_id "
        f"WHERE t.status='active' AND q.{status_field}='not_started' AND q.next_due_date IS NULL "
        f"ORDER BY t.id, q.id",
        (),
    ).fetchall()

    # Spread fresh picks round-robin across topics instead of draining one
    # topic's whole list first.
    by_topic = {}
    order = []
    for r in fresh_rows:
        tid = r["topic_id"]
        if tid not in by_topic:
            by_topic[tid] = []
            order.append(tid)
        by_topic[tid].append(r)
    fresh_pool = []
    while any(by_topic[t] for t in order):
        for tid in order:
            if by_topic[tid]:
                fresh_pool.append(by_topic[tid].pop(0))

    chosen = []  # list of (row, slot_type)
    selected_ids = set()

    for r in revision_pool:
        if sum(1 for _, s in chosen if s == "revision") >= 2:
            break
        chosen.append((r, "revision"))
        selected_ids.add(r["id"])

    for r in fresh_pool:
        if sum(1 for _, s in chosen if s == "fresh") >= 3:
            break
        if r["id"] in selected_ids:
            continue
        chosen.append((r, "fresh"))
        selected_ids.add(r["id"])

    if len(chosen) < 5:
        for r in revision_pool:
            if len(chosen) >= 5:
                break
            if r["id"] in selected_ids:
                continue
            chosen.append((r, "revision"))
            selected_ids.add(r["id"])

    if len(chosen) < 5:
        for r in fresh_pool:
            if len(chosen) >= 5:
                break
            if r["id"] in selected_ids:
                continue
            chosen.append((r, "fresh"))
            selected_ids.add(r["id"])

    for r, slot_type in chosen:
        conn.execute(
            "INSERT OR IGNORE INTO daily_assignment (date, question_id, slot_type, round) VALUES (?,?,?,?)",
            (ds, r["id"], slot_type, round_num),
        )
    conn.commit()

    return [_row_to_question(r, round_num, slot_type) for r, slot_type in chosen]


# -------------------------------------------------------------- marking

def check_round1_complete(conn) -> bool:
    if is_round1_complete(conn):
        return False  # already completed earlier, nothing new happened
    ids = unlocked_topic_ids(conn)
    if not ids:
        return False
    placeholders = ",".join("?" * len(ids))
    row = conn.execute(
        f"SELECT COUNT(*) AS c FROM questions WHERE topic_id IN ({placeholders}) AND round1_status != 'solved'",
        ids,
    ).fetchone()
    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM questions WHERE topic_id IN ({placeholders})",
        ids,
    ).fetchone()
    if total["c"] > 0 and row["c"] == 0:
        set_setting(conn, "round1_complete", "1")
        conn.commit()
        return True
    return False


def _maybe_mark_topic_done(conn, topic_id: int):
    row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN round2_status='solved' THEN 1 ELSE 0 END) AS graduated "
        "FROM questions WHERE topic_id=?",
        (topic_id,),
    ).fetchone()
    if row["total"] > 0 and row["graduated"] == row["total"]:
        conn.execute("UPDATE topics SET status='done' WHERE id=? AND status='active'", (topic_id,))
        conn.commit()


def mark_question(conn, question_id: int, result: str, notes: str, today: datetime.date):
    q = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    if q is None:
        raise LookupError("Question not found")
    if result not in ("solved", "not_solved"):
        raise ValueError("result must be 'solved' or 'not_solved'")

    round_num = current_round(conn)
    status_field = f"round{round_num}_status"
    ds = today_str(today)
    graduated = False

    if result == "solved":
        stage = q["streak_stage"]
        if stage == 0:
            new_stage, next_due = 1, ds_plus(today, 1)
        elif stage == 1:
            new_stage, next_due = 2, ds_plus(today, 3)
        elif stage == 2:
            new_stage, next_due = 3, ds_plus(today, 5)
        else:  # stage 3 -> graduate
            new_stage, next_due = 4, None
            graduated = True

        new_status = "solved" if graduated else q[status_field]
        conn.execute(
            f"UPDATE questions SET streak_stage=?, next_due_date=?, last_attempt_date=?, {status_field}=? "
            f"WHERE id=?",
            (new_stage, next_due, ds, new_status, question_id),
        )
    else:
        conn.execute(
            "UPDATE questions SET streak_stage=0, next_due_date=NULL, last_attempt_date=?, "
            "fail_count=fail_count+1 WHERE id=?",
            (ds, question_id),
        )

    conn.execute(
        "INSERT INTO daily_log (date, question_id, result, notes) VALUES (?,?,?,?)",
        (ds, question_id, result, notes),
    )
    conn.commit()

    round1_just_completed = False
    if graduated:
        if round_num == 2:
            _maybe_mark_topic_done(conn, q["topic_id"])
        if round_num == 1:
            round1_just_completed = check_round1_complete(conn)

    updated = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    return {
        "question": dict(updated),
        "graduated": graduated,
        "round1_just_completed": round1_just_completed,
    }


def ds_plus(today: datetime.date, days: int) -> str:
    return (today + datetime.timedelta(days=days)).isoformat()


# ------------------------------------------------------------- progress

def progress_overview(conn):
    topics = conn.execute("SELECT * FROM topics ORDER BY unlock_order IS NULL DESC, unlock_order, id").fetchall()
    out = []
    overall_r1_total = overall_r1_done = 0
    overall_r2_total = overall_r2_done = 0
    for t in topics:
        qs = conn.execute("SELECT * FROM questions WHERE topic_id=?", (t["id"],)).fetchall()
        total = len(qs)
        r1_done = sum(1 for q in qs if q["round1_status"] == "solved")
        r2_done = sum(1 for q in qs if q["round2_status"] == "solved")
        out.append({
            "id": t["id"],
            "name": t["name"],
            "status": t["status"],
            "note": t["note"],
            "unlock_order": t["unlock_order"],
            "started_at": t["started_at"],
            "total_questions": total,
            "round1_done": r1_done,
            "round2_done": r2_done,
        })
        if t["status"] in ("active", "done"):
            overall_r1_total += total
            overall_r1_done += r1_done
            overall_r2_total += total
            overall_r2_done += r2_done

    return {
        "topics": out,
        "overall": {
            "round1_total": overall_r1_total,
            "round1_done": overall_r1_done,
            "round1_pct": round(100 * overall_r1_done / overall_r1_total, 1) if overall_r1_total else 0,
            "round2_total": overall_r2_total,
            "round2_done": overall_r2_done,
            "round2_pct": round(100 * overall_r2_done / overall_r2_total, 1) if overall_r2_total else 0,
        },
    }

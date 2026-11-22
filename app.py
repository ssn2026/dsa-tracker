"""DSA spaced-repetition tracker -- run with: python app.py
Serves the API + static frontend on http://localhost:8000
"""

import datetime
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import logic

BASE_DIR = Path(__file__).parent

db.init_db()

app = FastAPI(title="DSA Tracker")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def today() -> datetime.date:
    return datetime.date.today()


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


# --------------------------------------------------------------- schemas

class MarkBody(BaseModel):
    result: str  # 'solved' | 'not_solved'
    notes: Optional[str] = None


class TopicCreate(BaseModel):
    name: str
    status: Optional[str] = "locked"
    note: Optional[str] = None


class TopicUpdate(BaseModel):
    name: Optional[str] = None
    note: Optional[str] = None


class QuestionCreate(BaseModel):
    topic_id: int
    title: str
    url: Optional[str] = None
    difficulty: Optional[str] = None


class QuestionUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    difficulty: Optional[str] = None
    topic_id: Optional[int] = None


# ----------------------------------------------------------------- state

@app.get("/api/state")
def get_state():
    conn = db.get_conn()
    t = today()
    locked = conn.execute(
        "SELECT id, name, unlock_order FROM topics WHERE status='locked' ORDER BY unlock_order IS NULL, unlock_order, id"
    ).fetchall()
    pending = conn.execute(
        "SELECT id, name, started_at FROM topics WHERE status='pending' ORDER BY started_at"
    ).fetchall()
    overall = logic.progress_overview(conn)["overall"]
    state = {
        "today": t.isoformat(),
        "is_weekend": logic.is_weekend(t),
        "current_round": logic.current_round(conn),
        "round1_complete": logic.is_round1_complete(conn),
        "locked_topics": [dict(r) for r in locked],
        "pending_topics": [dict(r) for r in pending],
        "overall": overall,
    }
    conn.close()
    return state


# ----------------------------------------------------------------- today

@app.get("/api/today")
def get_today():
    conn = db.get_conn()
    result = logic.get_today_five(conn, today())
    conn.close()
    return {"questions": result}


@app.post("/api/today/regenerate")
def regenerate_today():
    conn = db.get_conn()
    result = logic.regenerate_today_five(conn, today())
    conn.close()
    return {"questions": result}


@app.post("/api/questions/{question_id}/mark")
def mark_question(question_id: int, body: MarkBody):
    conn = db.get_conn()
    try:
        result = logic.mark_question(conn, question_id, body.result, body.notes, today())
    except LookupError as e:
        conn.close()
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return result


# ---------------------------------------------------------------- topics

@app.get("/api/topics")
def list_topics():
    conn = db.get_conn()
    data = logic.progress_overview(conn)
    conn.close()
    return data["topics"]


@app.post("/api/topics")
def create_topic(body: TopicCreate):
    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, status, note) VALUES (?, ?, ?)",
            (body.name, body.status or "locked", body.note),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@app.put("/api/topics/{topic_id}")
def update_topic(topic_id: int, body: TopicUpdate):
    conn = db.get_conn()
    topic = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
    if topic is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Topic not found")
    name = body.name if body.name is not None else topic["name"]
    note = body.note if body.note is not None else topic["note"]
    conn.execute("UPDATE topics SET name=?, note=? WHERE id=?", (name, note, topic_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/topics/{topic_id}")
def delete_topic(topic_id: int):
    conn = db.get_conn()
    conn.execute("DELETE FROM topics WHERE id=?", (topic_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/topics/{topic_id}/unlock")
def unlock_topic(topic_id: int):
    conn = db.get_conn()
    try:
        logic.unlock_topic(conn, topic_id, today())
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        conn.close()
        raise HTTPException(status_code=404, detail=str(e))
    conn.close()
    return {"ok": True}


@app.post("/api/topics/{topic_id}/confirm-first-pass")
def confirm_first_pass(topic_id: int):
    conn = db.get_conn()
    try:
        logic.confirm_first_pass(conn, topic_id)
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        conn.close()
        raise HTTPException(status_code=404, detail=str(e))
    conn.close()
    return {"ok": True}


# ------------------------------------------------------------- questions

@app.get("/api/questions")
def list_questions(topic_id: Optional[int] = None):
    conn = db.get_conn()
    if topic_id is not None:
        rows = conn.execute(
            "SELECT q.*, t.name AS topic_name FROM questions q JOIN topics t ON t.id=q.topic_id "
            "WHERE q.topic_id=? ORDER BY q.id",
            (topic_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT q.*, t.name AS topic_name FROM questions q JOIN topics t ON t.id=q.topic_id ORDER BY q.id"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/questions")
def create_question(body: QuestionCreate):
    conn = db.get_conn()
    topic = conn.execute("SELECT id FROM topics WHERE id=?", (body.topic_id,)).fetchone()
    if topic is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Topic not found")
    cur = conn.execute(
        "INSERT INTO questions (topic_id, title, url, difficulty) VALUES (?,?,?,?)",
        (body.topic_id, body.title, body.url, body.difficulty),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@app.put("/api/questions/{question_id}")
def update_question(question_id: int, body: QuestionUpdate):
    conn = db.get_conn()
    q = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    if q is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Question not found")
    title = body.title if body.title is not None else q["title"]
    url = body.url if body.url is not None else q["url"]
    difficulty = body.difficulty if body.difficulty is not None else q["difficulty"]
    topic_id = body.topic_id if body.topic_id is not None else q["topic_id"]
    conn.execute(
        "UPDATE questions SET title=?, url=?, difficulty=?, topic_id=? WHERE id=?",
        (title, url, difficulty, topic_id, question_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/questions/{question_id}")
def delete_question(question_id: int):
    conn = db.get_conn()
    conn.execute("DELETE FROM questions WHERE id=?", (question_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# -------------------------------------------------------------- progress

@app.get("/api/progress")
def get_progress():
    conn = db.get_conn()
    data = logic.progress_overview(conn)
    conn.close()
    return data


# ----------------------------------------------------------------- main

def _open_browser():
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    threading.Timer(1.0, _open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

import hashlib
import os
from html import escape
import psycopg
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

DATABASE_URL = os.environ["DATABASE_URL"]


def db():
    return psycopg.connect(DATABASE_URL, connect_timeout=3)


# Create the table once, when the app starts.
with db() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            code   TEXT PRIMARY KEY,
            url    TEXT NOT NULL,
            clicks INTEGER NOT NULL DEFAULT 0
        )""")

app = FastAPI()

def page(request: Request, message: str = "") -> HTMLResponse:
    with db() as conn:
        rows = conn.execute("SELECT code, url, clicks FROM links").fetchall()
    links = "".join(
        f'<li><a href="/{c}">{request.base_url}{c}</a> → {escape(u)} ({n} clicks)</li>'
        for c, u, n in rows
    )
    return HTMLResponse(f"""
        <h1>URL Shortener</h1>
        <form method="post" action="/shorten">
          <input name="url" type="url" placeholder="https://example.com" required>
          <button>Shorten</button>
        </form>
        <p>{message}</p>
        <ul>{links}</ul>
        <a href="/health">/health</a>""")


@app.get("/")
def home(request: Request):
    return page(request)

@app.post("/shorten")
def shorten(request: Request, url: str = Form(...)):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    code = hashlib.sha256(url.encode()).hexdigest()[:7]

    with db() as conn:
        conn.execute(
            "INSERT INTO links (code, url) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
            (code, url),
        )
        saved = conn.execute("SELECT url FROM links WHERE code = %s", (code,)).fetchone()[0]

    if saved != url:
        raise HTTPException(409, "Hash collision with another URL")

    return page(request, f'Short link: <a href="/{code}">{request.base_url}{code}</a>')

# Must come BEFORE /{code}, or "health" would be treated as a short code.
@app.get("/health")
def health():
    try:
        with db() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "database": "ok"}
    except Exception:
        return JSONResponse({"status": "error", "database": "unreachable"}, status_code=503)


@app.get("/{code}")
def follow(code: str):
    with db() as conn:
        row = conn.execute(
            "UPDATE links SET clicks = clicks + 1 WHERE code = %s RETURNING url", (code,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Short link not found")
    return RedirectResponse(row[0], status_code=302)


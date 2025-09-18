import re, sqlite3
from datetime import datetime

DB_PATH = "chatbot_tickets.db"
with sqlite3.connect(DB_PATH) as _c:
    _c.execute("""CREATE TABLE IF NOT EXISTS tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        date TEXT NOT NULL
    )""")

_context = {}  # session_id -> {state,name,date}

_PATTERNS = [
    (r'\b(hello|hi|hey)\b', "Hello! How can I assist you today?"),
    (r'\b(help|support)\b', "You can ask: book ticket, my bookings, cancel ticket <id>, pricing, timings, policies."),
    (r'pricing|price|cost', "Each ticket costs Rs 100."),
    (r'timing|time|hours', "Museum hours: 9 AM - 7 PM (online 24x7)."),
    (r'policies|guidelines', (
        "1. Person below age of 18 not allowed to book ticket.\n"
        "2. Ticekts can be cancelled within 48hrs of booking.\n"
        "3. Same person cannot book multiple tickets.\n"
        "4. Refund will be not allowed if you are unable to visit museum.")),
    (r'services?', "Services: Booking | Cancellation | View Bookings.")
]
_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in _PATTERNS]
FALLBACK = "I'm sorry, I don't understand that. Could you please clarify?"

def _save_ticket(name, date_str):
    with sqlite3.connect(DB_PATH) as c:
        cur = c.cursor()
        cur.execute("INSERT INTO tickets(name,date) VALUES(?,?)", (name, date_str))
        return cur.lastrowid

def _delete_ticket(tid):
    with sqlite3.connect(DB_PATH) as c:
        cur = c.cursor()
        cur.execute("DELETE FROM tickets WHERE id=?", (tid,))
        return cur.rowcount > 0

def _list_tickets():
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("SELECT id,name,date FROM tickets ORDER BY id DESC").fetchall()
    if not rows:
        return "📭 No bookings yet."
    return "🗂 Your bookings:\n" + "\n".join(f"🎟 {r[0]} | {r[1]} on {r[2]}" for r in rows)

def _start_flow(sid):
    _context[sid] = {"state": "need_name"}

def _reset_flow(sid):
    _context.pop(sid, None)

def _process_flow(sid, msg):
    if sid not in _context:
        return None
    st = _context[sid]["state"]
    if st == "need_name":
        nm = msg.strip()
        if not nm:
            return "Please enter a valid name."\
        
        _context[sid]["name"] = nm
        _context[sid]["state"] = "need_date"
        return "Enter visit date (YYYY-MM-DD)."
    if st == "need_date":
        dt = msg.strip()
        try:
            datetime.strptime(dt, "%Y-%m-%d")
        except ValueError:
            return "Invalid date. Use YYYY-MM-DD."
        _context[sid]["date"] = dt
        _context[sid]["state"] = "confirm"
        return f"Confirm booking for {_context[sid]['name']} on {dt}? (yes/no)"
    if st == "confirm":
        low = msg.lower()
        if low in ("yes", "y"):
            tid = _save_ticket(_context[sid]["name"], _context[sid]["date"])
            _reset_flow(sid)
            return f"✅ Booking confirmed! Ticket ID: {tid}"
        if low in ("no", "n"):
            _reset_flow(sid)
            return "❌ Booking cancelled. Type 'book ticket' to start again."
        return "Please reply yes or no."
    return None

def get_chatbot_response(message: str, session_id: str) -> str:
    msg = message.strip()
    low = msg.lower()

    # Disable inline chatbot booking flow; direct users to login page
    if re.search(r'\bbook\s+ticket\b', low):
        return "Please login first at /login to book a ticket."

    flow_reply = _process_flow(session_id, msg)
    if flow_reply:
        return flow_reply

    m = re.match(r'cancel\s+ticket\s+(\d+)', low)
    if m:
        return f"🗑 Ticket {m.group(1)} cancelled." if _delete_ticket(int(m.group(1))) else "Ticket not found."

    if low == "my bookings":
        return _list_tickets()

    for rx, rep in _COMPILED:
        if rx.search(low):
            return rep

    return FALLBACK


# Museum Chatbot Ticket System

A Flask-based museum ticket booking web app with a chatbot assistant, PDF + QR ticket generation, email delivery, and PostgreSQL persistence.

## Features
- User registration & login (email-based)
- Ticket booking (age validation)
- PDF ticket generation with QR code (saved under `static/tickets/`)
- Email ticket delivery (SMTP via `.env` config)
- Chatbot integrated with booking/cancellation/listing commands
- Templates in `templates/` and styling in `static/css/style.css`

## Repo Layout (key files)
- `app.py` — main Flask app and routes
- `models.py` — SQLAlchemy models (`User`, `Ticket`) and DB init
- `chatbot.py` — chatbot logic
- `templates/` — HTML templates
- `static/` — static assets, generated `tickets/` lives here
- `requirements.txt` — Python dependencies

## Quick Start (Windows PowerShell)

1. Open PowerShell and go to the project folder:

```powershell
cd "C:\Users\Krati Patidar\Desktop\museum ticket booking\museum-chatbot-ticket-system"
```

2. Create and activate a virtual environment:

```powershell
py -m venv venv
# PowerShell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add environment variables (example):

```
DATABASE_URL=postgresql+psycopg2://museum_user:krati123@localhost:5432/museum_chatbot
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=your_smtp_password
FROM_EMAIL=tickets@yourdomain.com
```

Do NOT commit `.env` to version control.

5. Create the Postgres user and database (psql or pgAdmin):

```sql
CREATE USER museum_user WITH PASSWORD 'krati123';
CREATE DATABASE museum_chatbot OWNER museum_user;
GRANT ALL PRIVILEGES ON DATABASE museum_chatbot TO museum_user;
```

6. Run the app:

```powershell
.\venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000/ in your browser.

## View Tickets (pgAdmin and psql)

- pgAdmin: connect → Databases → `museum_chatbot` → Schemas → public → Tables → `ticket` → Right-click → View/Edit Data → All Rows.

- psql (PowerShell):

```powershell
$env:PGPASSWORD = 'krati123'
psql -h localhost -U museum_user -d museum_chatbot -p 5432
# inside psql:
\dt
\d+ ticket
SELECT * FROM ticket ORDER BY id DESC LIMIT 50;
\q
```

## Flask / SQLAlchemy quick inspection

```powershell
$env:FLASK_APP='app.py'
.\venv\Scripts\python.exe -m flask shell
# then inside shell
from models import User, Ticket
Ticket.query.order_by(Ticket.id.desc()).limit(20).all()
```

## Common Troubleshooting
- If activation fails: run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force` in PowerShell then activate.
- If DB connection fails: verify `DATABASE_URL`, user, password, host and that Postgres is running.
- If email doesn't send: check SMTP settings and use an app password for Gmail.
- If model/column mismatch errors occur: database schema may differ from models; consider using Flask-Migrate/Alembic for migrations.

## Security Notes
- Replace `SECRET_KEY` with a secure value from `.env` for production.
- Do not use `debug=True` in production.
- Use proper password hashing (currently plaintext password storage is a TODO).

## Next Steps I can help with
- Add this `README.md` to the repository (done).
- Add a small `/admin/tickets` route (login-protected) to view tickets in the browser.
- Add Flask-Migrate for safe schema migrations.

---

If you want, I can also add a short PowerShell script to automate venv setup and run steps.

Run instructions (Windows / macOS / Linux)

1. Create .env
   cp .env.example .env
   # Edit .env and paste your Neon/Supabase DATABASE_URL and set JWT_SECRET.

2. Create & activate a Python virtualenv
   Windows (PowerShell):
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1

   macOS / Linux:
     python3 -m venv .venv
     source .venv/bin/activate

3. Upgrade pip & install deps
   python -m pip install --upgrade pip
   pip install -r requirements.txt

4. (If you use local Postgres) Start Postgres.
   If using Neon/Supabase skip this step.

5. Create DB tables and admin
   python -m app.create_admin
   # follow prompt to create admin userid/password

6. Start backend
   uvicorn app.main:app --reload --port 8000

7. Open API docs
   http://localhost:8000/docs

8. Serve frontend (recommended)
   cd frontend
   python -m http.server 8080
   Open http://localhost:8080/login.html

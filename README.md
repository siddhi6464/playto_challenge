# Playto Payout Engine

This is the Playto Founding Engineer Challenge submission. 

## Features
- **Database level locks**: Uses `select_for_update()` to prevent concurrent overdraws.
- **Append-only Ledger**: Calculated dynamically via `SUM(credits) - SUM(debits)` avoiding sync and float errors.
- **Strict Idempotency**: DB-backed constraints scope UUID keys to merchants and instantly reject duplicate in-flight network requests.
- **Background Retry Logic**: Uses Celery to transition payouts logically, simulating hangs and successes with exponential backoff on retry.
- **State Machine Rules**: Prevents backwards transitions at the ORM layer level.

## Local Setup

1. **Start Services** (PostgreSQL & Redis):
   ```bash
   docker-compose up -d
   ```

2. **Initialize Backend**:
   ```bash
   python -m venv venv
   source venv/Scripts/activate # Windows
   pip install -r requirements.txt
   
   python manage.py makemigrations core
   python manage.py migrate
   python seed.py
   python manage.py runserver
   ```

3. **Run Celery Worker**:
   In a separate terminal, and with postgres/redis running:
   ```bash
   source venv/Scripts/activate
   celery -A playto_payouts worker -l info --pool=solo
   ```
   *(Note: `--pool=solo` is used on Windows. Omit on Linux/Mac)*

4. **Initialize Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Running Tests
Run the concurrency and idempotency tests:
```bash
python manage.py test core
```

## Deployment to Railway
1. Push this repository to GitHub.
2. In Railway Dashboard, click "New Project" -> "Deploy from GitHub repo".
3. **Important**: Railway will detect the `Procfile` and let you spawn a `web` and a `worker` process. 
4. Add a `PostgreSQL` and `Redis` plugin from the Railway UI.
5. In your Railway service variables, configure `DATABASE_URL` and `REDIS_URL` using the internal variables provided by the plugins.
6. Trigger a deployment.
7. For the frontend, create a separate Railway service linked to the same repo but set the "Root Directory" to `/frontend`.

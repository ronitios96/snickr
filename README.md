# Snickr

Local web application for CS 6083 Project Part 2. Snickr is a small Slack-like collaboration system backed by PostgreSQL.

## Local Setup

```bash
createdb snickr_dev
psql -d snickr_dev -f schema.sql
psql -d snickr_dev -f seed.sql
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5001`.

The app also accepts `DATABASE_URL`, for example:

```bash
DATABASE_URL=postgresql:///snickr_dev python app.py
```

## Demo Accounts

All seed users use password `password123`.

- `aarav`
- `priya`
- `rohan`
- `kavya`
- `vikram`

## Features

- Register, log in, log out with cookie-backed sessions.
- Create workspaces and automatically become the first administrator.
- Invite users to workspaces and accept or decline invitations.
- Create public, private, and direct channels.
- Join public channels; invite users to private/public channels.
- Accept or decline channel invitations.
- Browse only accessible channels and messages.
- Post messages to joined channels.
- Search messages that are accessible to the logged-in user.
- Uses parameterized SQL queries and Jinja autoescaping.
- Uses transactions for multi-step writes such as workspace creation, channel creation, invitation acceptance, and message posting.
- Uses database triggers to protect core invariants if a future code path bypasses the application checks.


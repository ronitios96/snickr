# Snickr Demo Checklist

## Setup

1. Start PostgreSQL.
2. From the project root:

```bash
createdb snickr_dev
psql -d snickr_dev -f schema.sql
psql -d snickr_dev -f seed.sql
python app.py
```

3. Open `http://127.0.0.1:5001`.

## Seed Accounts

All seed accounts use password `password123`.

- `aarav`: FinPlex admin, Lotus member
- `priya`: FinPlex admin
- `rohan`: FinPlex member, Lotus admin
- `kavya`: FinPlex member with a pending invite to `#releases`
- `vikram`: Lotus member with a pending invite to FinPlex

## Required Flow Coverage

- Register a new user from the auth page.
- Log in and log out.
- Create a workspace; verify creator becomes admin.
- Invite a user to a workspace; accept as that user.
- Create public, private, and direct channels.
- Join a public channel.
- Invite a workspace member to a channel; accept as that user.
- Browse a channel and post a message.
- Search `perpendicular` as `aarav`; verify two accessible results.
- Search `perpendicular` as `rohan`; verify only the public engineering result appears until the private invite is accepted.

## Security and Concurrency Notes

- SQL injection protection: all application SQL uses psycopg2 placeholders, never string concatenation.
- Cross-site scripting protection: templates use Jinja autoescaping for user-provided text.
- Session state: Flask signs the browser session cookie and stores only the authenticated `user_id`.
- Access control: every workspace/channel route checks membership before returning rows.
- Transactions: multi-step writes use a single database transaction and commit only after all related changes succeed.
- Database hardening: triggers reject channel membership without workspace membership, messages from non-members, and direct channels with more than two members.


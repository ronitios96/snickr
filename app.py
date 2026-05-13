import os
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql:///snickr_dev")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "snickr-local-dev-secret")


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(DATABASE_URL)
        g.db.autocommit = False
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        if error:
            db.rollback()
        db.close()


def query_all(sql, params=()):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=()):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=()):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        try:
            return cur.fetchone()
        except psycopg2.ProgrammingError:
            return None


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query_one(
        """
        SELECT user_id, email, username, nickname
        FROM users
        WHERE user_id = %s AND is_active = TRUE
        """,
        (user_id,),
    )


@app.before_request
def load_user():
    g.user = current_user()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth"))
        return view(*args, **kwargs)

    return wrapped


def wants_post():
    if request.method != "POST":
        abort(405)


def require_workspace_member(workspace_id):
    member = query_one(
        """
        SELECT wm.*, w.name AS workspace_name
        FROM workspace_members wm
        JOIN workspaces w ON w.workspace_id = wm.workspace_id
        WHERE wm.workspace_id = %s AND wm.user_id = %s
        """,
        (workspace_id, g.user["user_id"]),
    )
    if not member:
        abort(403)
    return member


def require_channel_member(channel_id):
    channel = query_one(
        """
        SELECT c.*, w.name AS workspace_name
        FROM channels c
        JOIN workspaces w ON w.workspace_id = c.workspace_id
        JOIN workspace_members wm ON wm.workspace_id = w.workspace_id AND wm.user_id = %s
        JOIN channel_members cm ON cm.channel_id = c.channel_id AND cm.user_id = %s
        WHERE c.channel_id = %s
        """,
        (g.user["user_id"], g.user["user_id"], channel_id),
    )
    if not channel:
        abort(403)
    return channel


def find_user(identifier):
    return query_one(
        """
        SELECT user_id, username, email, nickname
        FROM users
        WHERE is_active = TRUE
          AND (lower(username) = lower(%s) OR lower(email) = lower(%s))
        """,
        (identifier, identifier),
    )


@app.route("/", methods=["GET", "POST"])
def auth():
    if g.user:
        return redirect(url_for("dashboard"))

    mode = request.form.get("mode", "login")
    if request.method == "POST" and mode == "login":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = query_one(
            """
            SELECT user_id, username, password_hash
            FROM users
            WHERE is_active = TRUE
              AND (lower(username) = lower(%s) OR lower(email) = lower(%s))
            """,
            (identifier, identifier),
        )
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["user_id"]
            flash(f"Welcome back, {user['username']}.", "success")
            get_db().commit()
            return redirect(url_for("dashboard"))
        flash("Invalid username/email or password.", "error")
        get_db().rollback()

    if request.method == "POST" and mode == "register":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        nickname = request.form.get("nickname", "").strip() or None
        password = request.form.get("password", "")
        if not email or not username or not password:
            flash("Email, username, and password are required.", "error")
        else:
            try:
                row = execute(
                    """
                    INSERT INTO users (email, username, nickname, password_hash)
                    VALUES (%s, %s, %s, %s)
                    RETURNING user_id
                    """,
                    (email, username, nickname, generate_password_hash(password)),
                )
                get_db().commit()
                session.clear()
                session["user_id"] = row["user_id"]
                flash("Account created.", "success")
                return redirect(url_for("dashboard"))
            except psycopg2.IntegrityError:
                get_db().rollback()
                flash("That email or username is already taken.", "error")

    return render_template("auth.html", mode=mode)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("auth"))


@app.route("/dashboard")
@login_required
def dashboard():
    workspaces = query_all(
        """
        SELECT w.workspace_id, w.name, w.description, wm.is_admin,
               COUNT(DISTINCT c.channel_id) FILTER (WHERE cm.user_id IS NOT NULL) AS joined_channels,
               COUNT(DISTINCT m.message_id) FILTER (WHERE cm.user_id IS NOT NULL) AS visible_messages
        FROM workspaces w
        JOIN workspace_members wm ON wm.workspace_id = w.workspace_id AND wm.user_id = %s
        LEFT JOIN channels c ON c.workspace_id = w.workspace_id
        LEFT JOIN channel_members cm ON cm.channel_id = c.channel_id AND cm.user_id = %s
        LEFT JOIN messages m ON m.channel_id = c.channel_id
        GROUP BY w.workspace_id, w.name, w.description, wm.is_admin
        ORDER BY w.name
        """,
        (g.user["user_id"], g.user["user_id"]),
    )
    workspace_invites = query_all(
        """
        SELECT wi.invitation_id, wi.invited_at, w.name AS workspace_name, inviter.username AS inviter
        FROM workspace_invitations wi
        JOIN workspaces w ON w.workspace_id = wi.workspace_id
        JOIN users inviter ON inviter.user_id = wi.inviter_id
        WHERE wi.invitee_id = %s AND wi.status = 'pending'
        ORDER BY wi.invited_at DESC
        """,
        (g.user["user_id"],),
    )
    channel_invites = query_all(
        """
        SELECT ci.invitation_id, ci.invited_at, c.name AS channel_name, c.type,
               w.name AS workspace_name, inviter.username AS inviter
        FROM channel_invitations ci
        JOIN channels c ON c.channel_id = ci.channel_id
        JOIN workspaces w ON w.workspace_id = c.workspace_id
        JOIN users inviter ON inviter.user_id = ci.inviter_id
        WHERE ci.invitee_id = %s AND ci.status = 'pending'
        ORDER BY ci.invited_at DESC
        """,
        (g.user["user_id"],),
    )
    get_db().commit()
    return render_template(
        "dashboard.html",
        workspaces=workspaces,
        workspace_invites=workspace_invites,
        channel_invites=channel_invites,
    )


@app.post("/workspaces")
@login_required
def create_workspace():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    if not name:
        flash("Workspace name is required.", "error")
        return redirect(url_for("dashboard"))
    try:
        workspace = execute(
            """
            INSERT INTO workspaces (name, description, creator_id)
            VALUES (%s, %s, %s)
            RETURNING workspace_id
            """,
            (name, description, g.user["user_id"]),
        )
        execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, is_admin)
            VALUES (%s, %s, TRUE)
            """,
            (workspace["workspace_id"], g.user["user_id"]),
        )
        get_db().commit()
        flash("Workspace created.", "success")
        return redirect(url_for("workspace", workspace_id=workspace["workspace_id"]))
    except psycopg2.Error as error:
        get_db().rollback()
        flash(f"Could not create workspace: {error.diag.message_primary or error}", "error")
        return redirect(url_for("dashboard"))


@app.route("/workspaces/<int:workspace_id>")
@login_required
def workspace(workspace_id):
    membership = require_workspace_member(workspace_id)
    workspace_row = query_one("SELECT * FROM workspaces WHERE workspace_id = %s", (workspace_id,))
    channels = query_all(
        """
        SELECT c.*,
               cm.user_id IS NOT NULL AS is_joined,
               COUNT(m.message_id) AS message_count
        FROM channels c
        LEFT JOIN channel_members cm ON cm.channel_id = c.channel_id AND cm.user_id = %s
        LEFT JOIN messages m ON m.channel_id = c.channel_id
        WHERE c.workspace_id = %s
          AND (c.type = 'public' OR cm.user_id IS NOT NULL)
        GROUP BY c.channel_id, cm.user_id
        ORDER BY c.type, c.name
        """,
        (g.user["user_id"], workspace_id),
    )
    members = query_all(
        """
        SELECT u.user_id, u.username, u.nickname, wm.is_admin, wm.joined_at
        FROM workspace_members wm
        JOIN users u ON u.user_id = wm.user_id
        WHERE wm.workspace_id = %s
        ORDER BY wm.is_admin DESC, u.username
        """,
        (workspace_id,),
    )
    pending_workspace_invites = query_all(
        """
        SELECT wi.invitation_id, wi.invited_at, invitee.username AS invitee, inviter.username AS inviter
        FROM workspace_invitations wi
        JOIN users invitee ON invitee.user_id = wi.invitee_id
        JOIN users inviter ON inviter.user_id = wi.inviter_id
        WHERE wi.workspace_id = %s AND wi.status = 'pending'
        ORDER BY wi.invited_at DESC
        """,
        (workspace_id,),
    )
    get_db().commit()
    return render_template(
        "workspace.html",
        workspace=workspace_row,
        membership=membership,
        channels=channels,
        members=members,
        pending_workspace_invites=pending_workspace_invites,
    )


@app.post("/workspaces/<int:workspace_id>/invite")
@login_required
def invite_workspace(workspace_id):
    membership = require_workspace_member(workspace_id)
    if not membership["is_admin"]:
        abort(403)
    identifier = request.form.get("identifier", "").strip()
    invitee = find_user(identifier)
    if not invitee:
        flash("No user found with that username or email.", "error")
        return redirect(url_for("workspace", workspace_id=workspace_id))
    if invitee["user_id"] == g.user["user_id"]:
        flash("You are already in this workspace.", "error")
        return redirect(url_for("workspace", workspace_id=workspace_id))
    try:
        if query_one(
            "SELECT 1 FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
            (workspace_id, invitee["user_id"]),
        ):
            flash(f"{invitee['username']} is already a member.", "error")
        else:
            execute(
                """
                INSERT INTO workspace_invitations (workspace_id, invitee_id, inviter_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (workspace_id, invitee_id) WHERE status = 'pending' DO NOTHING
                """,
                (workspace_id, invitee["user_id"], g.user["user_id"]),
            )
            flash(f"Workspace invitation sent to {invitee['username']}.", "success")
        get_db().commit()
    except psycopg2.Error as error:
        get_db().rollback()
        flash(f"Could not send invitation: {error.diag.message_primary or error}", "error")
    return redirect(url_for("workspace", workspace_id=workspace_id))


@app.post("/workspace-invitations/<int:invitation_id>/<action>")
@login_required
def respond_workspace_invitation(invitation_id, action):
    if action not in {"accept", "decline"}:
        abort(404)
    invitation = query_one(
        """
        SELECT *
        FROM workspace_invitations
        WHERE invitation_id = %s AND invitee_id = %s AND status = 'pending'
        FOR UPDATE
        """,
        (invitation_id, g.user["user_id"]),
    )
    if not invitation:
        abort(404)
    try:
        status = "accepted" if action == "accept" else "declined"
        execute(
            """
            UPDATE workspace_invitations
            SET status = %s, responded_at = CURRENT_TIMESTAMP
            WHERE invitation_id = %s
            """,
            (status, invitation_id),
        )
        if action == "accept":
            execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, is_admin)
                VALUES (%s, %s, FALSE)
                ON CONFLICT (workspace_id, user_id) DO NOTHING
                """,
                (invitation["workspace_id"], g.user["user_id"]),
            )
        get_db().commit()
        flash("Invitation updated.", "success")
    except psycopg2.Error as error:
        get_db().rollback()
        flash(f"Could not update invitation: {error.diag.message_primary or error}", "error")
    return redirect(url_for("dashboard"))


@app.post("/workspaces/<int:workspace_id>/channels")
@login_required
def create_channel(workspace_id):
    require_workspace_member(workspace_id)
    name = request.form.get("name", "").strip()
    channel_type = request.form.get("type", "public")
    direct_identifier = request.form.get("direct_identifier", "").strip()
    if channel_type not in {"public", "private", "direct"}:
        abort(400)
    if not name:
        flash("Channel name is required.", "error")
        return redirect(url_for("workspace", workspace_id=workspace_id))
    if channel_type == "direct" and not direct_identifier:
        flash("Direct channels require a second workspace member.", "error")
        return redirect(url_for("workspace", workspace_id=workspace_id))
    try:
        channel = execute(
            """
            INSERT INTO channels (workspace_id, name, type, creator_id)
            VALUES (%s, %s, %s, %s)
            RETURNING channel_id
            """,
            (workspace_id, name, channel_type, g.user["user_id"]),
        )
        execute(
            "INSERT INTO channel_members (channel_id, user_id) VALUES (%s, %s)",
            (channel["channel_id"], g.user["user_id"]),
        )
        if channel_type == "direct" and direct_identifier:
            other = find_user(direct_identifier)
            if not other:
                raise ValueError("No user found for the direct channel.")
            if not query_one(
                "SELECT 1 FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, other["user_id"]),
            ):
                raise ValueError("Direct-message user must belong to this workspace.")
            execute(
                "INSERT INTO channel_members (channel_id, user_id) VALUES (%s, %s)",
                (channel["channel_id"], other["user_id"]),
            )
        get_db().commit()
        flash("Channel created.", "success")
        return redirect(url_for("channel", channel_id=channel["channel_id"]))
    except (psycopg2.Error, ValueError) as error:
        get_db().rollback()
        message = error.diag.message_primary if isinstance(error, psycopg2.Error) else str(error)
        flash(f"Could not create channel: {message}", "error")
        return redirect(url_for("workspace", workspace_id=workspace_id))


@app.post("/channels/<int:channel_id>/join")
@login_required
def join_channel(channel_id):
    channel = query_one("SELECT * FROM channels WHERE channel_id = %s", (channel_id,))
    if not channel or channel["type"] != "public":
        abort(404)
    require_workspace_member(channel["workspace_id"])
    try:
        execute(
            """
            INSERT INTO channel_members (channel_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (channel_id, user_id) DO NOTHING
            """,
            (channel_id, g.user["user_id"]),
        )
        get_db().commit()
        flash("Joined channel.", "success")
    except psycopg2.Error as error:
        get_db().rollback()
        flash(f"Could not join channel: {error.diag.message_primary or error}", "error")
    return redirect(url_for("channel", channel_id=channel_id))


@app.route("/channels/<int:channel_id>")
@login_required
def channel(channel_id):
    channel_row = require_channel_member(channel_id)
    messages = query_all(
        """
        SELECT m.message_id, m.body, m.posted_at, u.username, u.nickname, u.user_id = %s AS is_mine
        FROM messages m
        JOIN users u ON u.user_id = m.sender_id
        WHERE m.channel_id = %s
        ORDER BY m.posted_at ASC, m.message_id ASC
        """,
        (g.user["user_id"], channel_id),
    )
    members = query_all(
        """
        SELECT u.username, u.nickname
        FROM channel_members cm
        JOIN users u ON u.user_id = cm.user_id
        WHERE cm.channel_id = %s
        ORDER BY u.username
        """,
        (channel_id,),
    )
    pending_invites = query_all(
        """
        SELECT ci.invitation_id, ci.invited_at, invitee.username AS invitee, inviter.username AS inviter
        FROM channel_invitations ci
        JOIN users invitee ON invitee.user_id = ci.invitee_id
        JOIN users inviter ON inviter.user_id = ci.inviter_id
        WHERE ci.channel_id = %s AND ci.status = 'pending'
        ORDER BY ci.invited_at DESC
        """,
        (channel_id,),
    )
    get_db().commit()
    return render_template(
        "channel.html",
        channel=channel_row,
        messages=messages,
        members=members,
        pending_invites=pending_invites,
    )


@app.post("/channels/<int:channel_id>/messages")
@login_required
def post_message(channel_id):
    require_channel_member(channel_id)
    body = request.form.get("body", "").strip()
    if not body:
        flash("Message cannot be empty.", "error")
        return redirect(url_for("channel", channel_id=channel_id))
    try:
        execute(
            """
            INSERT INTO messages (channel_id, sender_id, body)
            VALUES (%s, %s, %s)
            """,
            (channel_id, g.user["user_id"], body),
        )
        get_db().commit()
    except psycopg2.Error as error:
        get_db().rollback()
        flash(f"Could not post message: {error.diag.message_primary or error}", "error")
    return redirect(url_for("channel", channel_id=channel_id))


@app.post("/channels/<int:channel_id>/invite")
@login_required
def invite_channel(channel_id):
    channel_row = require_channel_member(channel_id)
    identifier = request.form.get("identifier", "").strip()
    invitee = find_user(identifier)
    if not invitee:
        flash("No user found with that username or email.", "error")
        return redirect(url_for("channel", channel_id=channel_id))
    try:
        if not query_one(
            "SELECT 1 FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
            (channel_row["workspace_id"], invitee["user_id"]),
        ):
            flash("Invitee must already belong to this workspace.", "error")
        elif query_one(
            "SELECT 1 FROM channel_members WHERE channel_id = %s AND user_id = %s",
            (channel_id, invitee["user_id"]),
        ):
            flash(f"{invitee['username']} is already in this channel.", "error")
        else:
            execute(
                """
                INSERT INTO channel_invitations (channel_id, invitee_id, inviter_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (channel_id, invitee_id) WHERE status = 'pending' DO NOTHING
                """,
                (channel_id, invitee["user_id"], g.user["user_id"]),
            )
            flash(f"Channel invitation sent to {invitee['username']}.", "success")
        get_db().commit()
    except psycopg2.Error as error:
        get_db().rollback()
        flash(f"Could not invite user: {error.diag.message_primary or error}", "error")
    return redirect(url_for("channel", channel_id=channel_id))


@app.post("/channel-invitations/<int:invitation_id>/<action>")
@login_required
def respond_channel_invitation(invitation_id, action):
    if action not in {"accept", "decline"}:
        abort(404)
    invitation = query_one(
        """
        SELECT ci.*, c.workspace_id
        FROM channel_invitations ci
        JOIN channels c ON c.channel_id = ci.channel_id
        WHERE ci.invitation_id = %s AND ci.invitee_id = %s AND ci.status = 'pending'
        FOR UPDATE
        """,
        (invitation_id, g.user["user_id"]),
    )
    if not invitation:
        abort(404)
    try:
        status = "accepted" if action == "accept" else "declined"
        execute(
            """
            UPDATE channel_invitations
            SET status = %s, responded_at = CURRENT_TIMESTAMP
            WHERE invitation_id = %s
            """,
            (status, invitation_id),
        )
        if action == "accept":
            execute(
                """
                INSERT INTO channel_members (channel_id, user_id)
                VALUES (%s, %s)
                ON CONFLICT (channel_id, user_id) DO NOTHING
                """,
                (invitation["channel_id"], g.user["user_id"]),
            )
        get_db().commit()
        flash("Channel invitation updated.", "success")
        if action == "accept":
            return redirect(url_for("channel", channel_id=invitation["channel_id"]))
    except psycopg2.Error as error:
        get_db().rollback()
        flash(f"Could not update channel invitation: {error.diag.message_primary or error}", "error")
    return redirect(url_for("dashboard"))


@app.route("/search")
@login_required
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        results = query_all(
            """
            SELECT m.message_id, m.body, m.posted_at, c.channel_id, c.name AS channel_name,
                   w.workspace_id, w.name AS workspace_name, sender.username AS sender
            FROM messages m
            JOIN channels c ON c.channel_id = m.channel_id
            JOIN workspaces w ON w.workspace_id = c.workspace_id
            JOIN users sender ON sender.user_id = m.sender_id
            JOIN workspace_members wm ON wm.workspace_id = w.workspace_id AND wm.user_id = %s
            JOIN channel_members cm ON cm.channel_id = c.channel_id AND cm.user_id = %s
            WHERE m.body ILIKE %s
            ORDER BY m.posted_at DESC
            LIMIT 100
            """,
            (g.user["user_id"], g.user["user_id"], f"%{q}%"),
        )
    get_db().commit()
    return render_template("search.html", q=q, results=results)


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", title="Not allowed", message="You do not have access to that page."), 403


@app.errorhandler(404)
def missing(_error):
    return render_template("error.html", title="Not found", message="That page or record does not exist."), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5001)), debug=True)

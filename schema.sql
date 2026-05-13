DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS channel_invitations CASCADE;
DROP TABLE IF EXISTS channel_members CASCADE;
DROP TABLE IF EXISTS channels CASCADE;
DROP TABLE IF EXISTS workspace_invitations CASCADE;
DROP TABLE IF EXISTS workspace_members CASCADE;
DROP TABLE IF EXISTS workspaces CASCADE;
DROP TABLE IF EXISTS users CASCADE;

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    username      VARCHAR(50) NOT NULL UNIQUE,
    nickname      VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (trim(email) <> ''),
    CHECK (trim(username) <> ''),
    CHECK (deleted_at IS NULL OR is_active = FALSE)
);

CREATE TABLE workspaces (
    workspace_id SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    description  TEXT,
    creator_id   INT NOT NULL REFERENCES users(user_id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (trim(name) <> '')
);

CREATE TABLE workspace_members (
    workspace_id INT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    user_id      INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    is_admin     BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE workspace_invitations (
    invitation_id SERIAL PRIMARY KEY,
    workspace_id  INT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    invitee_id    INT NOT NULL REFERENCES users(user_id),
    inviter_id    INT NOT NULL REFERENCES users(user_id),
    invited_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at  TIMESTAMPTZ,
    status        VARCHAR(10) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'accepted', 'declined')),
    CHECK (invitee_id <> inviter_id),
    CHECK ((status = 'pending' AND responded_at IS NULL) OR (status <> 'pending' AND responded_at IS NOT NULL))
);

CREATE UNIQUE INDEX uq_workspace_pending_invitation
    ON workspace_invitations(workspace_id, invitee_id)
    WHERE status = 'pending';

CREATE TABLE channels (
    channel_id   SERIAL PRIMARY KEY,
    workspace_id INT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    type         VARCHAR(10) NOT NULL CHECK (type IN ('public', 'private', 'direct')),
    creator_id   INT NOT NULL REFERENCES users(user_id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workspace_id, name),
    CHECK (trim(name) <> '')
);

CREATE TABLE channel_members (
    channel_id INT NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    user_id    INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id, user_id)
);

CREATE TABLE channel_invitations (
    invitation_id SERIAL PRIMARY KEY,
    channel_id    INT NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    invitee_id    INT NOT NULL REFERENCES users(user_id),
    inviter_id    INT NOT NULL REFERENCES users(user_id),
    invited_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at  TIMESTAMPTZ,
    status        VARCHAR(10) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'accepted', 'declined')),
    CHECK (invitee_id <> inviter_id),
    CHECK ((status = 'pending' AND responded_at IS NULL) OR (status <> 'pending' AND responded_at IS NOT NULL))
);

CREATE UNIQUE INDEX uq_channel_pending_invitation
    ON channel_invitations(channel_id, invitee_id)
    WHERE status = 'pending';

CREATE TABLE messages (
    message_id BIGSERIAL PRIMARY KEY,
    channel_id INT NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    sender_id  INT NOT NULL REFERENCES users(user_id),
    body       TEXT NOT NULL CHECK (length(trim(body)) > 0),
    posted_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workspace_members_user ON workspace_members(user_id, workspace_id);
CREATE INDEX idx_channel_members_user ON channel_members(user_id, channel_id);
CREATE INDEX idx_messages_channel_time ON messages(channel_id, posted_at, message_id);
CREATE INDEX idx_messages_sender ON messages(sender_id);
CREATE INDEX idx_channel_invitations_invitee ON channel_invitations(invitee_id, status);
CREATE INDEX idx_workspace_invitations_invitee ON workspace_invitations(invitee_id, status);

CREATE OR REPLACE FUNCTION require_channel_member_workspace_member()
RETURNS TRIGGER AS $$
DECLARE
    channel_workspace_id INT;
BEGIN
    SELECT workspace_id INTO channel_workspace_id
    FROM channels
    WHERE channel_id = NEW.channel_id;

    IF NOT EXISTS (
        SELECT 1
        FROM workspace_members
        WHERE workspace_id = channel_workspace_id
          AND user_id = NEW.user_id
    ) THEN
        RAISE EXCEPTION 'user % must belong to workspace % before joining channel %',
            NEW.user_id, channel_workspace_id, NEW.channel_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_channel_member_workspace_member
BEFORE INSERT OR UPDATE ON channel_members
FOR EACH ROW EXECUTE FUNCTION require_channel_member_workspace_member();

CREATE OR REPLACE FUNCTION require_message_sender_channel_member()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM channel_members
        WHERE channel_id = NEW.channel_id
          AND user_id = NEW.sender_id
    ) THEN
        RAISE EXCEPTION 'sender % must belong to channel % before posting',
            NEW.sender_id, NEW.channel_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_message_sender_channel_member
BEFORE INSERT OR UPDATE ON messages
FOR EACH ROW EXECUTE FUNCTION require_message_sender_channel_member();

CREATE OR REPLACE FUNCTION enforce_direct_channel_limit()
RETURNS TRIGGER AS $$
DECLARE
    channel_type VARCHAR(10);
    current_count INT;
BEGIN
    SELECT type INTO channel_type
    FROM channels
    WHERE channel_id = NEW.channel_id;

    IF channel_type = 'direct' THEN
        SELECT COUNT(*) INTO current_count
        FROM channel_members
        WHERE channel_id = NEW.channel_id
          AND NOT (channel_id = NEW.channel_id AND user_id = NEW.user_id);

        IF current_count >= 2 THEN
            RAISE EXCEPTION 'direct channel % cannot have more than two members', NEW.channel_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_direct_channel_limit
BEFORE INSERT OR UPDATE ON channel_members
FOR EACH ROW EXECUTE FUNCTION enforce_direct_channel_limit();


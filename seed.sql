INSERT INTO users (user_id, email, username, nickname, password_hash) VALUES
    (1, 'aarav.sharma@finplex.in',  'aarav',  'AS',  'scrypt:32768:8:1$QVY8KJ4Um8xI9E14$8e78fb3a31a67a493ed8a8a9d7ca59bfca028d3532cb80f6a9da517760425ea1d718dbc73a0d42d9eb4d463af4a5b25363fc4c2304f69a3d06ff4d21d3b37f44'),
    (2, 'priya.patel@finplex.in',   'priya',  'Pri', 'scrypt:32768:8:1$QVY8KJ4Um8xI9E14$8e78fb3a31a67a493ed8a8a9d7ca59bfca028d3532cb80f6a9da517760425ea1d718dbc73a0d42d9eb4d463af4a5b25363fc4c2304f69a3d06ff4d21d3b37f44'),
    (3, 'rohan.iyer@gmail.com',     'rohan',  'Ro',  'scrypt:32768:8:1$QVY8KJ4Um8xI9E14$8e78fb3a31a67a493ed8a8a9d7ca59bfca028d3532cb80f6a9da517760425ea1d718dbc73a0d42d9eb4d463af4a5b25363fc4c2304f69a3d06ff4d21d3b37f44'),
    (4, 'kavya.reddy@finplex.in',   'kavya',  'Kav', 'scrypt:32768:8:1$QVY8KJ4Um8xI9E14$8e78fb3a31a67a493ed8a8a9d7ca59bfca028d3532cb80f6a9da517760425ea1d718dbc73a0d42d9eb4d463af4a5b25363fc4c2304f69a3d06ff4d21d3b37f44'),
    (5, 'vikram.singh@gmail.com',   'vikram', 'Vik', 'scrypt:32768:8:1$QVY8KJ4Um8xI9E14$8e78fb3a31a67a493ed8a8a9d7ca59bfca028d3532cb80f6a9da517760425ea1d718dbc73a0d42d9eb4d463af4a5b25363fc4c2304f69a3d06ff4d21d3b37f44');

INSERT INTO workspaces (workspace_id, name, description, creator_id, created_at) VALUES
    (1, 'FinPlex-Engineering', 'FinPlex backend and mobile engineering team', 1, CURRENT_TIMESTAMP - INTERVAL '30 days'),
    (2, 'Lotus-RWA', 'Lotus Heights Resident Welfare Association', 3, CURRENT_TIMESTAMP - INTERVAL '40 days');

INSERT INTO workspace_members (workspace_id, user_id, is_admin, joined_at) VALUES
    (1, 1, TRUE,  CURRENT_TIMESTAMP - INTERVAL '30 days'),
    (1, 2, TRUE,  CURRENT_TIMESTAMP - INTERVAL '28 days'),
    (1, 3, FALSE, CURRENT_TIMESTAMP - INTERVAL '25 days'),
    (1, 4, FALSE, CURRENT_TIMESTAMP - INTERVAL '20 days'),
    (2, 3, TRUE,  CURRENT_TIMESTAMP - INTERVAL '40 days'),
    (2, 1, FALSE, CURRENT_TIMESTAMP - INTERVAL '35 days'),
    (2, 5, FALSE, CURRENT_TIMESTAMP - INTERVAL '10 days');

INSERT INTO workspace_invitations (workspace_id, invitee_id, inviter_id, invited_at, status) VALUES
    (1, 5, 1, CURRENT_TIMESTAMP - INTERVAL '3 days', 'pending');

INSERT INTO workspace_invitations (workspace_id, invitee_id, inviter_id, invited_at, responded_at, status) VALUES
    (2, 4, 3, CURRENT_TIMESTAMP - INTERVAL '8 days', CURRENT_TIMESTAMP - INTERVAL '7 days', 'declined');

INSERT INTO channels (channel_id, workspace_id, name, type, creator_id, created_at) VALUES
    (1, 1, 'engineering',     'public',  1, CURRENT_TIMESTAMP - INTERVAL '20 days'),
    (2, 1, 'releases',        'public',  2, CURRENT_TIMESTAMP - INTERVAL '18 days'),
    (3, 1, 'hiring',          'private', 1, CURRENT_TIMESTAMP - INTERVAL '15 days'),
    (4, 1, 'dm-aarav-priya',  'direct',  1, CURRENT_TIMESTAMP - INTERVAL '10 days'),
    (5, 2, 'general',         'public',  3, CURRENT_TIMESTAMP - INTERVAL '30 days'),
    (6, 2, 'dm-rohan-vikram', 'direct',  3, CURRENT_TIMESTAMP - INTERVAL '5 days');

INSERT INTO channel_members (channel_id, user_id, joined_at) VALUES
    (1, 1, CURRENT_TIMESTAMP - INTERVAL '20 days'),
    (1, 2, CURRENT_TIMESTAMP - INTERVAL '20 days'),
    (1, 3, CURRENT_TIMESTAMP - INTERVAL '19 days'),
    (1, 4, CURRENT_TIMESTAMP - INTERVAL '18 days'),
    (2, 1, CURRENT_TIMESTAMP - INTERVAL '18 days'),
    (2, 2, CURRENT_TIMESTAMP - INTERVAL '18 days'),
    (2, 3, CURRENT_TIMESTAMP - INTERVAL '17 days'),
    (3, 1, CURRENT_TIMESTAMP - INTERVAL '15 days'),
    (3, 2, CURRENT_TIMESTAMP - INTERVAL '15 days'),
    (4, 1, CURRENT_TIMESTAMP - INTERVAL '10 days'),
    (4, 2, CURRENT_TIMESTAMP - INTERVAL '10 days'),
    (5, 3, CURRENT_TIMESTAMP - INTERVAL '30 days'),
    (5, 1, CURRENT_TIMESTAMP - INTERVAL '29 days'),
    (5, 5, CURRENT_TIMESTAMP - INTERVAL '10 days'),
    (6, 3, CURRENT_TIMESTAMP - INTERVAL '5 days'),
    (6, 5, CURRENT_TIMESTAMP - INTERVAL '5 days');

INSERT INTO channel_invitations (channel_id, invitee_id, inviter_id, invited_at, status) VALUES
    (2, 4, 1, CURRENT_TIMESTAMP - INTERVAL '7 days', 'pending'),
    (3, 3, 1, CURRENT_TIMESTAMP - INTERVAL '8 days', 'pending');

INSERT INTO channel_invitations (channel_id, invitee_id, inviter_id, invited_at, responded_at, status) VALUES
    (1, 4, 1, CURRENT_TIMESTAMP - INTERVAL '2 days', CURRENT_TIMESTAMP - INTERVAL '1 day', 'accepted');

INSERT INTO messages (channel_id, sender_id, body, posted_at) VALUES
    (1, 1, 'Welcome to the engineering channel. Let us use this as our default async space.',
        CURRENT_TIMESTAMP - INTERVAL '19 days'),
    (1, 2, 'Reminder: sprint review on Friday at 4 PM IST.',
        CURRENT_TIMESTAMP - INTERVAL '18 days'),
    (1, 3, 'Reviewing yesterday''s incident: the payments and notifications services have perpendicular failure modes. That is why retries kept thrashing.',
        CURRENT_TIMESTAMP - INTERVAL '17 days'),
    (2, 2, 'Release v2.3 is going out tomorrow at 11 PM IST. Code freeze tonight 8 PM.',
        CURRENT_TIMESTAMP - INTERVAL '17 days'),
    (2, 1, 'We have 412 migration transactions queued for the cutover so far.',
        CURRENT_TIMESTAMP - INTERVAL '16 days'),
    (3, 1, 'Shortlist for the senior backend role is ready for review.',
        CURRENT_TIMESTAMP - INTERVAL '14 days'),
    (3, 2, 'The two finalists have perpendicular strengths: one is a systems specialist, the other is more product-leaning.',
        CURRENT_TIMESTAMP - INTERVAL '13 days'),
    (4, 1, 'Dosa at the new place near MG Road tomorrow?',
        CURRENT_TIMESTAMP - INTERVAL '9 days'),
    (4, 2, 'Sounds good, 1 PM works.',
        CURRENT_TIMESTAMP - INTERVAL '9 days'),
    (5, 3, 'Society AGM is scheduled for next Saturday, 6 PM in the clubhouse.',
        CURRENT_TIMESTAMP - INTERVAL '20 days'),
    (5, 1, 'I will bring printouts of the maintenance accounts.',
        CURRENT_TIMESTAMP - INTERVAL '19 days'),
    (5, 5, 'Can someone share the agenda on the WhatsApp group as well?',
        CURRENT_TIMESTAMP - INTERVAL '8 days'),
    (6, 3, 'Did you receive the new lift maintenance contract draft from the vendor?',
        CURRENT_TIMESTAMP - INTERVAL '4 days'),
    (6, 5, 'Yes, going through it now.',
        CURRENT_TIMESTAMP - INTERVAL '3 days');

SELECT setval(pg_get_serial_sequence('users', 'user_id'), 5);
SELECT setval(pg_get_serial_sequence('workspaces', 'workspace_id'), 2);
SELECT setval(pg_get_serial_sequence('channels', 'channel_id'), 6);
SELECT setval(pg_get_serial_sequence('workspace_invitations', 'invitation_id'), COALESCE((SELECT MAX(invitation_id) FROM workspace_invitations), 1));
SELECT setval(pg_get_serial_sequence('channel_invitations', 'invitation_id'), COALESCE((SELECT MAX(invitation_id) FROM channel_invitations), 1));
SELECT setval(pg_get_serial_sequence('messages', 'message_id'), 14);

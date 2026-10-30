-- Which agents are at work on an artifact now, and at what (louvre.core.presence, REQUIREMENTS U14): one row an agent
-- and an artifact, kept until its expiry and read only before it. Never edit a migration that has shipped.
CREATE TABLE presence (
  artifact_id text NOT NULL REFERENCES artifacts (id) ON DELETE CASCADE,
  -- The agent, as its comments name it (agent:ACCOUNT:NAME), its name, and the person it works for.
  author_id text NOT NULL,
  display_name text NOT NULL,
  on_behalf_of text NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
  activity text NOT NULL CHECK (activity IN ('here', 'reading', 'revising', 'replying')),
  note text NOT NULL,
  -- The thread it is replying in; NULL for any other activity.
  thread_id text REFERENCES threads (id) ON DELETE SET NULL,
  -- Since when it has been at this activity, when it last called, and when it is gone unless it calls again.
  since timestamptz NOT NULL,
  seen_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (artifact_id, author_id)
);

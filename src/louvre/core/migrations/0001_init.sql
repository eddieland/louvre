-- Louvre's first schema: people and their sessions and tokens, and the artifacts contract's records.
-- Never edit a migration that has shipped; add the next one.

-- A person who signs in. The id is the identity provider's, stable for the life of the account (gh:ID, dev:LOGIN).
CREATE TABLE accounts (
  id text PRIMARY KEY,
  login text NOT NULL,
  display_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- A signed-in browser. Only the token's sha256 is kept.
CREATE TABLE sessions (
  token_hash text PRIMARY KEY,
  account_id text NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL
);

-- A token a person minted for an agent: bound to the person and one namespace, with scopes. Only its sha256 is kept.
CREATE TABLE tokens (
  id text PRIMARY KEY,
  secret_hash text NOT NULL UNIQUE,
  account_id text NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
  name text NOT NULL,
  namespace text NOT NULL,
  scopes text [] NOT NULL CHECK (scopes <@ ARRAY['read', 'publish', 'comment']::text []),
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz,
  revoked_at timestamptz
);

-- Who wrote a comment or made a change: a person, or an agent on a person's behalf.
CREATE TABLE authors (
  id text PRIMARY KEY,
  display_name text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('person', 'agent')),
  on_behalf_of text
);

CREATE TABLE artifacts (
  n bigserial UNIQUE,
  id text PRIMARY KEY,
  namespace text NOT NULL,
  title text NOT NULL,
  origin jsonb NOT NULL,
  latest_version integer NOT NULL,
  -- The person whose token published it, who may delete it.
  owner_id text REFERENCES accounts (id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  deleted_at timestamptz
);

CREATE TABLE versions (
  artifact_id text NOT NULL REFERENCES artifacts (id) ON DELETE CASCADE,
  n integer NOT NULL,
  content_type text NOT NULL CHECK (content_type IN ('text/html', 'text/markdown')),
  sha256 text NOT NULL,
  content text NOT NULL,
  text text NOT NULL,
  created_at timestamptz NOT NULL,
  PRIMARY KEY (artifact_id, n)
);

CREATE TABLE threads (
  n bigserial UNIQUE,
  id text PRIMARY KEY,
  artifact_id text NOT NULL REFERENCES artifacts (id) ON DELETE CASCADE,
  exact text,
  prefix text,
  suffix text,
  anchored_version integer NOT NULL,
  state text NOT NULL CHECK (state IN ('open', 'resolved')),
  created_at timestamptz NOT NULL
);

CREATE TABLE comments (
  n bigserial UNIQUE,
  id text PRIMARY KEY,
  thread_id text NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
  seq bigint NOT NULL,
  author_id text NOT NULL REFERENCES authors (id),
  body text NOT NULL,
  created_at timestamptz NOT NULL,
  edited_at timestamptz,
  deleted_at timestamptz,
  via text NOT NULL CHECK (via IN ('web', 'mcp'))
);

-- Every change to a comment or a thread, in commit order: writes take one lock first, so seq never commits out of order.
CREATE TABLE changes (
  seq bigserial PRIMARY KEY,
  kind text NOT NULL CHECK (
    kind IN ('comment_created', 'comment_edited', 'comment_deleted', 'thread_resolved', 'thread_reopened')
  ),
  thread_id text NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
  comment_id text REFERENCES comments (id) ON DELETE CASCADE,
  author_id text NOT NULL REFERENCES authors (id),
  via text NOT NULL CHECK (via IN ('web', 'mcp')),
  at timestamptz NOT NULL
);

CREATE INDEX artifacts_by_namespace ON artifacts (namespace, n DESC);
CREATE INDEX artifacts_origin ON artifacts USING gin (origin jsonb_path_ops);
CREATE INDEX threads_by_artifact ON threads (artifact_id);
CREATE INDEX comments_by_thread ON comments (thread_id);
CREATE INDEX tokens_by_account ON tokens (account_id);

-- Decisions: a question asked on an artifact, its options, and people's answers (REQUIREMENTS U7).

-- A question, asked by an agent or a person, for people to answer by choosing among its options.
CREATE TABLE decisions (
  n bigserial UNIQUE,
  id text PRIMARY KEY,
  artifact_id text NOT NULL REFERENCES artifacts (id) ON DELETE CASCADE,
  question text NOT NULL,
  -- Each option: its id (o1, o2, ...), label, detail, and the passage it is about, or none.
  options jsonb NOT NULL,
  -- Whether an answer may choose more than one option.
  multiple boolean NOT NULL,
  -- The logins of the people asked, lowercase; anyone who reads the artifact may answer.
  asked text [] NOT NULL,
  author_id text NOT NULL REFERENCES authors (id),
  -- The person the asker acts for, who may close it as well as the asker.
  account_id text REFERENCES accounts (id) ON DELETE SET NULL,
  -- The artifact's latest version when it was asked.
  version integer NOT NULL,
  state text NOT NULL CHECK (state IN ('open', 'closed')),
  -- The option the closer named as what was decided, if any, and what they said.
  outcome text,
  outcome_note text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL,
  closed_at timestamptz
);

-- A person's answer to a decision: one each, changed in place while the decision is open.
CREATE TABLE answers (
  decision_id text NOT NULL REFERENCES decisions (id) ON DELETE CASCADE,
  account_id text NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
  author_id text NOT NULL REFERENCES authors (id),
  choices text [] NOT NULL,
  note text NOT NULL,
  answered_at timestamptz NOT NULL,
  PRIMARY KEY (decision_id, account_id)
);

-- Every event in a decision's life, in commit order, as `decision_feed` reads them: each keeps what it said then, so an
-- answer changed is two events. Writes take the store's lock first, as the comment feed's do.
CREATE TABLE decision_events (
  seq bigserial PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN ('decision_asked', 'decision_answered', 'decision_closed')),
  decision_id text NOT NULL REFERENCES decisions (id) ON DELETE CASCADE,
  author_id text NOT NULL REFERENCES authors (id),
  choices text [] NOT NULL DEFAULT '{}',
  note text NOT NULL DEFAULT '',
  at timestamptz NOT NULL
);

CREATE INDEX decisions_by_artifact ON decisions (artifact_id, n);
CREATE INDEX decisions_asked_open ON decisions USING gin (asked) WHERE state = 'open';

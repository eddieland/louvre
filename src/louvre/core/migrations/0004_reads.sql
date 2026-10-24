-- What each person has read of an artifact, for their inbox (louvre.core.inbox): the latest version they opened, and
-- the change to its threads (changes.seq) through which they have seen them. Never edit a migration that has shipped.
CREATE TABLE reads (
  account_id text NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
  artifact_id text NOT NULL REFERENCES artifacts (id) ON DELETE CASCADE,
  version integer NOT NULL,
  seq bigint NOT NULL,
  read_at timestamptz NOT NULL,
  PRIMARY KEY (account_id, artifact_id)
);

-- The inbox finds the artifacts a person takes part in by what they own and what they wrote, and what is new on them
-- by each thread's changes.
CREATE INDEX artifacts_by_owner ON artifacts (owner_id);
CREATE INDEX comments_by_author ON comments (author_id);
CREATE INDEX authors_by_person ON authors (on_behalf_of);
CREATE INDEX changes_by_thread ON changes (thread_id, seq);

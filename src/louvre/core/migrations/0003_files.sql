-- Files beside a version: what its page shows besides its content, such as images and data (REQUIREMENTS L8, M9).

-- The key in the path a version's page and files are served at, for a version that has files. Only a person who may
-- read the version learns it, and a request for one of its files needs it (D012): a sandboxed page's requests carry
-- no session.
ALTER TABLE versions ADD COLUMN files_key text;

-- Each file's bytes, once, by their hash: a new version that names a file unchanged stores nothing new.
CREATE TABLE blobs (
  sha256 text PRIMARY KEY,
  data bytea NOT NULL
);

-- A version's files, by their path relative to its page, as immutable as its content.
CREATE TABLE files (
  artifact_id text NOT NULL,
  n integer NOT NULL,
  path text NOT NULL,
  content_type text NOT NULL,
  size integer NOT NULL,
  sha256 text NOT NULL REFERENCES blobs (sha256),
  PRIMARY KEY (artifact_id, n, path),
  FOREIGN KEY (artifact_id, n) REFERENCES versions (artifact_id, n) ON DELETE CASCADE
);

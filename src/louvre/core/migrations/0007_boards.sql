-- Boards an agent publishes with board_publish (louvre.core.boards, REQUIREMENTS U5): several of its namespace's
-- artifacts on one canvas, each a frame at a screen's size. Never edit a migration that has shipped.
CREATE TABLE boards (
  n bigserial UNIQUE,
  id text PRIMARY KEY,
  namespace text NOT NULL,
  title text NOT NULL,
  origin jsonb NOT NULL,
  -- Each frame, in the board's order: its id, its label, the artifact it shows at its latest version, and where it is
  -- on the canvas and at what size, in CSS pixels.
  frames jsonb NOT NULL,
  -- The person whose token published it.
  owner_id text REFERENCES accounts (id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE INDEX boards_by_namespace ON boards (namespace, n DESC);

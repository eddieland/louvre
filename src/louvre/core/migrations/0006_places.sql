-- A thread may be on a place on a map rather than on words (louvre.core.geodata, REQUIREMENTS U10, M12): a feature
-- by its layer and id, or a point, as JSON. Its exact still holds its words, the feature's label or the point's
-- coordinates, for a reader that knows only words. Never edit a migration that has shipped.
ALTER TABLE threads ADD COLUMN place jsonb;

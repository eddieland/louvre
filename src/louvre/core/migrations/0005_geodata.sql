-- A version may be GeoJSON, which Louvre draws as a map (louvre.core.geodata, REQUIREMENTS U9, M11). Never edit a
-- migration that has shipped.
ALTER TABLE versions DROP CONSTRAINT versions_content_type_check;
ALTER TABLE versions ADD CONSTRAINT versions_content_type_check
  CHECK (content_type IN ('text/html', 'text/markdown', 'application/geo+json'));

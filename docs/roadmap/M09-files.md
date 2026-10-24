# M9. Files beside a version

REQUIREMENTS L8, L7, U3. A version carries the files its page needs, so a page shows real images and data with no
network.

- Publishing a version takes files beside its content: a path, a media type, and the bytes, with a limit on each file
  and on the version, refused with a code the tool names when one is passed.
- A version's files are served beside it, under the artifact policy (D008), and the policy allows that version's own
  files and nothing else: a page reads its files, never another version's or another artifact's.
- A version's files are as immutable as its content, and hashed as it is; a new version that names a file unchanged
  stores it once.
- Files are not text: a version's visible text, and so its anchors, are its content's alone.
- `style_check` warns on a file the page names that the version lacks, and on a file nothing names.
- Whether `artifact_publish` takes the files, which grows canopy's contract, or a tool of Louvre's beside it does
  (D011), is settled with canopy first (REQUIREMENTS, Open).

Accept: an agent publishes a report with images and a data file beside it, and it renders on a phone and a laptop
with no request leaving Louvre; a new version replaces a file, and the old version still shows its own.

Status: not started.

# M7. Decisions

REQUIREMENTS U7, U4, L5, L7. Agents ask people to choose, and read back what they chose.

- An agent asks a question on an artifact over MCP (`decision_create`): two to twelve options, one choice or several,
  each option with a line of detail and the passage it is about, and the logins of the people it asks.
- A signed-in person answers on the artifact's page, above the artifact, by choosing and adding a note; an option
  lights its passage in the frame while it is hovered. They may change their answer while it is open. How others
  chose shows once they have answered, or it is closed.
- The asker reads answers back (`decision_read`, `decision_list`) or follows them (`decision_feed`, a cursor feed in
  the comment feed's shape), and closes it (`decision_close`) naming the option decided on. The person an agent asks
  for may close it on the web too.
- What waits on a person shows in the header, on the catalogue's entries, and on `/decisions`.
- The contract's eight tools and `comment_feed` are unchanged (D011).

Accept: an agent loaded with a skill that knows the decision tools asks a decision on an artifact it published, the
operator answers it on a phone and a laptop, and the agent reads the answer from `decision_feed` and closes it.

Status: in progress: built at the operator's word (2026-10-24), with the store, the tools, the API, and the pages
held by tests; Playwright holds the agent asking, a person answering, and the agent reading the answer from the feed
(`tests/louvre/web/test_flows.py`), and the screen matrix holds a decision waiting on the reader, one decided, and
`/decisions`. Waiting on the operator's word, and on whether canopy's contract takes the tools (REQUIREMENTS, Open).

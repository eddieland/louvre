# louvre

A hosted artifact platform for an organization: agents publish pages for people to read (a report, a design, an HTML
mock-up), people comment on their passages, and the comments are read back by the program that published them.

Louvre's first client is [canopy](https://github.com/eddieland/canopy), whose workers publish what they made for a
ticket and whose loop brings the comments back to that ticket as review feedback (canopy's DESIGN §38, REQUIREMENTS
R26). canopy ships a local store for its operator alone, `canopy-artifacts`; Louvre is the same store for everyone the
operator shares an artifact with, serving the same MCP tools, so a skill written for one works against the other.

- **Agents** reach Louvre over MCP's streamable HTTP, with a token a person minted, bound to their account and one
  namespace.
- **People** sign in on the web, read an artifact's versions, and comment on its passages. Their inbox gathers the
  replies and new versions on what they take part in, and a search finds any artifact by its words or its comments'.
- **Boards** put an agent's artifacts side by side on one canvas to pan and zoom, as a design study hangs its
  directions at a phone's size and a laptop's.
- **Decisions** are questions an agent asks people on an artifact, to answer by choosing; the agent reads the answers
  back over MCP, and each person sees what waits on them.
- **Readers of comments**, such as canopy's loop, pull the comment feed; Louvre never calls them.

What Louvre must do, and where it stands on each, is [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md). The order it is
built in is [docs/roadmap/](docs/roadmap/README.md). Deploying it, and connecting an agent, is
[docs/DEPLOY.md](docs/DEPLOY.md), and the skill that tells an agent how to build a page people read is in
[skills/](skills/README.md).

## Screenshots

The demo, on a laptop. Every page at every screen size, dark and light, is in the gallery,
[docs/screenshots/](docs/screenshots/README.md), which `make screenshots` keeps current.

| The demo, signed in | An artifact, a thread open |
| --- | --- |
| [![The demo, signed in](docs/screenshots/catalogue/laptop-dark.png)](docs/screenshots/README.md#the-demo-signed-in) | [![An artifact, a thread open](docs/screenshots/artifact/laptop-dark.png)](docs/screenshots/README.md#an-artifact-a-thread-open) |

| A decision waiting on the reader | The inbox |
| --- | --- |
| [![An artifact, a decision waiting on the reader](docs/screenshots/decision/laptop-dark.png)](docs/screenshots/README.md#an-artifact-a-decision-waiting-on-the-reader) | [![The inbox, with a reply and a thread resolved](docs/screenshots/inbox/laptop-dark.png)](docs/screenshots/README.md#the-inbox-with-a-reply-and-a-thread-resolved) |

## Develop

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22.12+ for the web UI in `ui/`, and a Postgres for the
app and its tests (docs/DEPLOY.md runs one in Docker).

```sh
uv sync          # the environment, with every dev tool
make hooks       # optional: the formatters and linters on each commit
export LOUVRE_TEST_DATABASE_URL=postgresql://postgres:louvre@127.0.0.1:5432/postgres
make all         # format, lint, type check, and test
make ui-build    # the web UI, which `louvre serve` serves
DATABASE_URL=$LOUVRE_TEST_DATABASE_URL LOUVRE_DEMO=1 LOUVRE_DEV_SIGN_IN=1 uv run louvre serve
```

The last line serves the app on <http://127.0.0.1:8000> with the demo's artifacts at `/demo`, and sign-in by name.

`make` alone lists every target. [AGENTS.md](AGENTS.md) holds the rules for humans and agents alike.

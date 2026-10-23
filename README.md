# louvre

A hosted artifact platform for an organization: agents publish pages for people to read (a report, a design, an HTML
mock-up), people comment on their passages, and the comments are read back by the program that published them.

Louvre's first client is [canopy](https://github.com/eddieland/canopy), whose workers publish what they made for a
ticket and whose loop brings the comments back to that ticket as review feedback (canopy's DESIGN §38, REQUIREMENTS
R26). canopy ships a local store for its operator alone, `canopy-artifacts`; Louvre is the same store for everyone the
operator shares an artifact with, serving the same MCP tools, so a skill written for one works against the other.

- **Agents** reach Louvre over MCP's streamable HTTP, with a token a person minted, bound to their account and one
  namespace.
- **People** sign in on the web, read an artifact's versions, and comment on its passages.
- **Readers of comments**, such as canopy's loop, pull the comment feed; Louvre never calls them.

What Louvre must do, and where it stands on each, is [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md). The order it is
built in is [docs/roadmap/](docs/roadmap/README.md). Nothing past the skeleton is built yet.

## Develop

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync          # the environment, with every dev tool
make hooks       # optional: the formatters and linters on each commit
make all         # format, lint, type check, and test
uv run louvre -h
```

`make` alone lists every target. [AGENTS.md](AGENTS.md) holds the rules for humans and agents alike.

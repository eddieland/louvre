# louvre

What louvre is and who it is for is not written yet.

## Develop

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync          # the environment, with every dev tool
make hooks       # optional: the formatters and linters on each commit
make all         # format, lint, type check, and test
uv run louvre -h
```

`make` alone lists every target. [AGENTS.md](AGENTS.md) holds the rules for humans and agents alike.

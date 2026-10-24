# Skills

Skills for agents that publish to Louvre, to install beside the agent's connection to Louvre's MCP server
([docs/DEPLOY.md](../docs/DEPLOY.md#connecting-an-agent)). A skill here says when and how to do a thing; what it needs
from Louvre, such as the house style, comes from the server, so a skill never lags the Louvre it reaches.

| Skill | For |
|---|---|
| [louvre-artifacts](louvre-artifacts/SKILL.md) | Building a page people read and comment on: when, in what form, and in Louvre's house style |

For Claude Code, copy a skill's directory into a project's `.claude/skills/`, or into `~/.claude/skills/` for every
project:

```sh
cp -r skills/louvre-artifacts ~/.claude/skills/
```

An agent that publishes for canopy also loads canopy's `canopy-artifacts` skill, which says how its workers publish
and whose comments count.

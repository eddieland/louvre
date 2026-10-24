# Louvre roadmap

Milestones are sequential. Each has acceptance criteria that must be met before the next begins. Acceptance criteria
that involve running against real systems are the operator's job; the agent building the repo stops and asks.

Each milestone is a file in this directory, `MNN-slug.md`, its number padded to two digits so the directory lists in
order. Each ends with a `Status:` line, the only place its progress is told, and the list below repeats its first
sentence. Once its acceptance criteria are met:

```text
Status: done YYYY-MM-DD.
Learned: what surprised us or turned out different from the plan.
Next: how that changes later milestones, docs, or open questions.
```

The milestones after M0 were written down 2026-10-23 from [REQUIREMENTS](../REQUIREMENTS.md): the UI and the
interaction first, over mock data, then the store under them, at the operator's word.

## Milestones

- [M0. Skeleton](M00-skeleton.md): done 2026-10-23.
- [M1. Directions](M01-directions.md): done 2026-10-23.
- [M2. Reading and commenting, over mock data](M02-experience.md): in progress: built over the store; waiting on the
  operator's word on the running page.
- [M3. Boards, over mock data](M03-boards.md): in progress: built; waiting on the operator's pass on a phone and a
  laptop.
- [M4. The contract on Postgres, under the UI](M04-contract.md): done 2026-10-23.
- [M5. Sign-in, and MCP behind tokens](M05-signin-mcp.md): in progress: built, and held to the official MCP
  client; an agent loaded with canopy's skill is the operator's check.
- [M6. Deployed for the organization](M06-deploy.md): not started. The preview runs the whole app.
- [M7. Decisions](M07-decisions.md): in progress: built; waiting on the operator's word, and on canopy's for its
  contract.

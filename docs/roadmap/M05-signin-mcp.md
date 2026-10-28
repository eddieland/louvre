# M5. Sign-in, and MCP behind tokens

REQUIREMENTS L1, L4, L5, L6, U6. People sign in, and agents reach the same store over MCP's streamable HTTP, each call
scoped by its token.

- Sign-in, by REQUIREMENTS' open question, and who may read an artifact.
- Minting and revoking tokens on the web, bound to the person's account and one namespace, with scopes `read`,
  `publish`, and `comment`, stored hashed; a comment written with one is `kind: agent`, on behalf of its owner.
- Louvre's style over MCP, at a version, for an agent that wants it (U6).
- `out_of_scope` and `read_only` refused in code from the token, never from the caller's arguments.

Accept: canopy's `canopy-artifacts` skill, pointed at a local Louvre, publishes an artifact, reads its threads, and
replies; a `read` token's writes are refused; a person's comment on the web and the agent's reply sit in one thread;
the artifact's HTML cannot read the person's session.

Status: done 2026-10-28.
Learned: Claude Code, given canopy's `canopy-artifacts` skill and Louvre's `/mcp` alone, took a ticket to an artifact
and back on a local Louvre with no word of Louvre's own: it published for the ticket, read a person's comment from the
web, published a version that answered it, replied in that thread, and resolved it; with a `read` token, both writes
were refused `read_only` and it stopped, as the skill says. A page that tried the person's cookie, storage, parent,
and `/api/session` got a `SecurityError` or a CSP refusal for each. The skill's agent opened a thread of its own on
the whole report, asking for review, which it was not told to; it is the skill's to say, not Louvre's. It names the
url Louvre returns, built from `LOUVRE_BASE_URL`, so a deployment's must be the address its readers reach.
Next: M6 runs the same loop against a deployment, as canopy's M62 live check, with GitHub's sign-in in place of the
dev sign-in used here. `tests/louvre/web/test_mcp_client.py` keeps the loop's calls held in CI.

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

Status: not started.

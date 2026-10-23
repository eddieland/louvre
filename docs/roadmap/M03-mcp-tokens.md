# M3. MCP over HTTP, behind tokens

REQUIREMENTS L1, L4, L5. M1's tools served over MCP's streamable HTTP, each call scoped by its token.

- Minting and revoking tokens on the web, bound to the person's account and one namespace, with scopes `read`,
  `publish`, and `comment`, stored hashed; a comment written with one is `kind: agent`, on behalf of its owner.
- `out_of_scope` and `read_only` refused in code from the token, never from the caller's arguments.

Accept: canopy's `canopy-artifacts` skill, pointed at a local Louvre, publishes an artifact, reads its threads, and
replies; a `read` token's writes are refused; a person's comment on the web and the agent's reply sit in one thread.

Status: not started.

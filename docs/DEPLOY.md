# Deploying Louvre

Louvre is one Python web app (`vercel_app.py` imports `louvre.web.app`) and one Postgres database. It runs on Vercel
as the preview does, or anywhere that runs `louvre serve` behind HTTPS. It makes its tables itself, on the first
request after a deploy.

## On Vercel

1. **A database.** In the project's Storage tab, connect a Postgres store from the Marketplace (Neon, say). It sets
   `POSTGRES_URL` on the project, which Louvre reads; `DATABASE_URL` wins if both are set.
2. **A GitHub OAuth app** for signing in: GitHub, Settings, Developer settings, OAuth Apps, New. Its homepage is the
   deployment's URL, and its callback URL is that URL with `/auth/github/callback`. Copy its client id, and generate a
   client secret.
3. **The project's environment variables**, then redeploy:

   | Variable | Value |
   |---|---|
   | `LOUVRE_BASE_URL` | The deployment's URL, such as `https://louvre.example.com`, with no trailing slash |
   | `LOUVRE_GITHUB_CLIENT_ID` | The OAuth app's client id |
   | `LOUVRE_GITHUB_CLIENT_SECRET` | Its client secret (mark it sensitive) |
   | `LOUVRE_ALLOWED_LOGINS` | The GitHub logins who may sign in, comma-separated; `*` lets anyone in |
   | `LOUVRE_DEMO` | `1` to publish the demo's artifacts, which anyone may read without signing in |

4. Open the deployment, sign in with GitHub, and mint a token for an agent on the Tokens page.

A preview with no database still serves its pages, and says what is missing. `LOUVRE_DEV_SIGN_IN=1` lets anyone sign
in as anyone by typing a name: it is for a local run and the tests, never a deployment people use.

## Anywhere else

```sh
export DATABASE_URL=postgresql://user:password@host:5432/louvre
uv run louvre migrate                       # optional: the app migrates on its first request anyway
uv run louvre serve --host 0.0.0.0 --port 8000
```

Put it behind HTTPS, and set `LOUVRE_SECURE_COOKIES=1` so the session cookie is sent over HTTPS only (Vercel's own
deployments set it by themselves). The other variables are as on Vercel.

## Connecting an agent

A token is bound to the person who minted it and one namespace, with scopes `read`, `publish`, and `comment`. The
Tokens page shows it once, with the commands to give an agent; for Claude Code:

```sh
claude mcp add --transport http louvre https://louvre.example.com/mcp --header "Authorization: Bearer lvt_..."
```

The server speaks MCP's streamable HTTP at `/mcp`, one JSON-RPC message a request, answered as JSON. Its tools are
canopy's artifacts contract's eight, so canopy's `canopy-artifacts` skill works against it unchanged, and
`style_get`, Louvre's house style for HTML an agent wants to look like Louvre's own pages.

## Locally, for development

```sh
docker run -d --name louvre-db -e POSTGRES_PASSWORD=louvre -p 5432:5432 postgres:17
export DATABASE_URL=postgresql://postgres:louvre@127.0.0.1:5432/postgres
make ui-build
LOUVRE_DEMO=1 LOUVRE_DEV_SIGN_IN=1 uv run louvre serve
```

The tests that need Postgres read `LOUVRE_TEST_DATABASE_URL` (a database they may create others beside, as the one
above), and are skipped without it, except in CI.

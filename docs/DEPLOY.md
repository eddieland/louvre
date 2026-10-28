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
   | `LOUVRE_DEMO` | `1` to publish the demo's artifacts at `/demo`, which anyone may read without signing in |
   | `LOUVRE_STREETS` | Optional: the TileJSON of the street tiles maps draw, OpenFreeMap's unless set; empty for none |
   | `LOUVRE_NAME`, `LOUVRE_BANNER`, ... | Optional: your organization's words on Louvre's pages (below) |

4. Open the deployment, sign in with GitHub, and mint a token for an agent on the Tokens page.

A preview with no database still serves its pages, and says what is missing. `LOUVRE_DEV_SIGN_IN=1` lets anyone sign
in as anyone by typing a name: it is for a local run and the tests, never a deployment people use.

## Your organization's words

A deployment can say what is its own on Louvre's pages: whose it is, what may be posted to it, where to ask for help,
and its conventions for agents. Each variable is optional, and each is shown only when set.

| Variable | Shown |
|---|---|
| `LOUVRE_NAME` | In every page's title, in place of Louvre, such as `Inbox · Acme Louvre`: to tell deployments apart in tabs |
| `LOUVRE_BANNER` | A line over every page, an artifact's and a board's too, such as whose deployment it is |
| `LOUVRE_FOOTER` | At the foot of the catalogue, the demo, the inbox, decisions, tokens, and signing in |
| `LOUVRE_SIGN_IN_NOTE` | Wherever a person is asked to sign in, above the ways to: who may, and how to ask for access |
| `LOUVRE_TOKENS_NOTE` | On the Tokens page, under what a token is: how to name a namespace, which agents to give one |

All but the name are Markdown, of which Louvre keeps paragraphs (a blank line between them), line breaks (a new line),
`**bold**`, `_italics_`, `` `code` ``, and links to `https://`, `http://`, `mailto:`, or a path of Louvre's own such as
`/demo`. Anything else, HTML included, is shown as the text it is: what you write is never run as markup on the pages
that hold people's sessions. A link to another site opens in a tab of its own. For example:

```sh
LOUVRE_NAME="Acme Louvre"
LOUVRE_BANNER="For work inside Acme. Read the [publishing policy](https://wiki.acme.example/louvre) first."
LOUVRE_FOOTER="Run by Platform. Help: **#louvre**, or [louvre@acme.example](mailto:louvre@acme.example)."
LOUVRE_SIGN_IN_NOTE="Sign in with the GitHub account in Acme's organization. Not on the list? Ask in **#louvre**."
LOUVRE_TOKENS_NOTE="Name a namespace for your team and its tool, such as \`payments/canopy\`."
```

Inside its frame an artifact is its author's page alone: none of this is added to it (REQUIREMENTS L7).

## Anywhere else

```sh
export DATABASE_URL=postgresql://user:password@host:5432/louvre
uv run louvre migrate                       # optional: the app migrates on its first request anyway
uv run louvre serve --host 0.0.0.0 --port 8000
```

Put it behind HTTPS, and set `LOUVRE_SECURE_COOKIES=1` so the session cookie is sent over HTTPS only (Vercel's own
deployments set it by themselves). The other variables are as on Vercel.

## On Kubernetes

The `Dockerfile` builds Louvre's image, which the Image workflow pushes to `ghcr.io/eddieland/louvre`, and the Helm
chart in [charts/louvre](../charts/louvre/README.md) runs it: its `config` values set the variables above, with a
bundled PostgreSQL for a local cluster (`make kind-up`) or a managed one in production.

## Connecting an agent

A token is bound to the person who minted it and one namespace, with scopes `read`, `publish`, and `comment`. The
Tokens page shows it once, with the commands to give an agent; for Claude Code:

```sh
claude mcp add --transport http louvre https://louvre.example.com/mcp --header "Authorization: Bearer lvt_..."
```

The server speaks MCP's streamable HTTP at `/mcp`, one JSON-RPC message a request, answered as JSON. Its tools are
canopy's artifacts contract's eight, so canopy's `canopy-artifacts` skill works against it unchanged, and
`style_get`, Louvre's house style for HTML an agent wants to look like Louvre's own pages, with a starter page for a
report, a decision, or a plan; `style_chart`, which draws a chart in it from data; and `style_check`, which checks a
page against the style's guide before it is published; and `files_publish`, which publishes a page with its images
and data beside it. The style is also resources, its stylesheet, its guide, and
each starter page (`louvre://style/louvre-1/...`, which Claude Code attaches with `@`), and a prompt, `style`, that
asks for a page of a kind in it (`/mcp__louvre__style` in Claude Code).

Give the agent the [louvre-artifacts](../skills/README.md) skill too: it says when to publish a page, in what form,
and how to build one in the house style.

## Locally, for development

```sh
docker run -d --name louvre-db -e POSTGRES_PASSWORD=louvre -p 5432:5432 postgres:17
export DATABASE_URL=postgresql://postgres:louvre@127.0.0.1:5432/postgres
make ui-build
LOUVRE_DEMO=1 LOUVRE_DEV_SIGN_IN=1 uv run louvre serve
```

The tests that need Postgres read `LOUVRE_TEST_DATABASE_URL` (a database they may create others beside, as the one
above), and are skipped without it, except in CI.

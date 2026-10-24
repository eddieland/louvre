# Louvre's Helm chart

Runs Louvre on Kubernetes: its web app as a Deployment behind a Service and an optional Ingress, and its database
either bundled, a single PostgreSQL in a StatefulSet for local clusters and trials, or run elsewhere, a managed
PostgreSQL for production (D007). The image is the repository's `Dockerfile`, which the Image workflow pushes to
`ghcr.io/eddieland/louvre`.

Louvre's settings are the environment variables [docs/DEPLOY.md](../../docs/DEPLOY.md) names, which the chart sets
from `config` and from whichever database is in use: `DATABASE_URL`, with the password in libpq's `PGPASSWORD` so it is
never spliced into the URL. Louvre makes its tables itself, on its first request. The chart's `helm test` checks that
Louvre answers and has its database, and that the database takes those credentials.

## Local

Needs Docker, [kind](https://kind.sigs.k8s.io/), helm, and kubectl.

```sh
make kind-up      # build the image, load it into a kind cluster named louvre, install, and run helm test
kubectl --context kind-louvre port-forward svc/louvre 8000:80   # then open http://127.0.0.1:8000/
make kind-down    # delete the cluster, and the bundled database with it
```

`examples/local.yaml` publishes the demo's artifacts and lets anyone sign in by typing a name, with cookies over
plain HTTP for the port-forward. `make kind-up` again after a change rebuilds the image and rolls it out. Another
local cluster (k3d, minikube) takes the same values once the image is loaded into it.

## Production

Start from `examples/production.yaml`: a pinned image, two replicas spread across nodes, an Ingress with TLS, sign-in
with a GitHub OAuth app, and a managed PostgreSQL, with their secrets in Secrets made outside the chart.

```sh
kubectl create secret generic louvre-database --from-literal=password='...'
kubectl create secret generic louvre-github --from-literal=client-secret='...'
helm upgrade --install louvre charts/louvre -f my-values.yaml --wait
helm test louvre --logs
```

- **Image.** Pin `image.tag` to a released version, or `image.digest`. A new GHCR package is private: make it public,
  or give the cluster a pull secret through `imagePullSecrets`.
- **Sign-in.** `config.baseUrl` is the Ingress's URL, the OAuth app's callback is that URL with
  `/auth/github/callback`, and `config.allowedLogins` names who may sign in. `config.secureCookies` stays on behind TLS.
- **Database.** With `postgresql.enabled: false`, `externalDatabase.host` and a password (`existingSecret`, or
  `password`, which is stored in the release) are required; the chart refuses to render without them. A provider's
  whole URL goes in a Secret instead, named by `existingSecret` and `existingSecretUrlKey`. `sslMode`
  defaults to `require`; `verify-full` also needs the provider's CA, through `PGSSLROOTCERT` in `extraEnv`.
- **Backups** are the managed database's. The bundled PostgreSQL has none, no replicas, and no upgrade between major
  versions, which is why production does not use it.

## The bundled PostgreSQL

The official `postgres` image, as one replica with its own volume (`postgresql.persistence`), running as its postgres
user on a read-only root filesystem. Its password is `postgresql.auth.password`, a Secret of your own
(`postgresql.auth.existingSecret`), or, left empty, generated at install and kept across upgrades. The volume and the
generated password's Secret outlive `helm uninstall`, so reinstalling the release reads the same data; delete both to
start empty. `postgresql.networkPolicy.enabled` lets only Louvre's pods, and the chart's test, reach it.

## Values

`values.yaml` documents each one. The ones most installs set:

| Value | Default | What it does |
| --- | --- | --- |
| `image.repository`, `image.tag`, `image.digest` | `ghcr.io/eddieland/louvre`, the chart's appVersion | The image Louvre runs. |
| `replicaCount` | `1` | Louvre's replicas. |
| `ingress.enabled`, `ingress.hosts`, `ingress.tls` | off | Serve Louvre on a host name. |
| `podDisruptionBudget.enabled` | off | Keep `minAvailable` replicas through a node drain. |
| `config.baseUrl`, `config.allowedLogins` | empty | Louvre's URL, and who may sign in. |
| `config.github.*` | off | The GitHub OAuth app people sign in with. |
| `config.secureCookies` | on | The session cookie over HTTPS only. |
| `config.demo`, `config.devSignIn` | off | The demo's artifacts, and sign-in by name, for a local cluster. |
| `postgresql.enabled` | `true` | Run the bundled PostgreSQL. |
| `externalDatabase.*` | | The database to use when the bundled one is off. |
| `extraEnv` | `[]` | More environment variables for Louvre's container. |

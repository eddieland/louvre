# Louvre's Helm chart

Runs Louvre on Kubernetes: its web app as a Deployment behind a Service and an optional Ingress, and its database
either bundled, a single PostgreSQL in a StatefulSet for local clusters and trials, or run elsewhere, a managed
PostgreSQL for production (D007). The image is the repository's `Dockerfile`, which the Image workflow pushes to
`ghcr.io/eddieland/louvre`.

Louvre reads its database from libpq's standard variables, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`,
and `PGSSLMODE`, which the chart sets from whichever database is in use. Until the store is built (roadmap M4) the app
does not connect yet; the chart's `helm test` checks the database takes those credentials all the same.

## Local

Needs Docker, [kind](https://kind.sigs.k8s.io/), helm, and kubectl.

```sh
make kind-up      # build the image, load it into a kind cluster named louvre, install, and run helm test
kubectl --context kind-louvre port-forward svc/louvre 8000:80   # then open http://127.0.0.1:8000/
make kind-down    # delete the cluster, and the bundled database with it
```

`make kind-up` again after a change rebuilds the image and rolls it out. Another local cluster (k3d, minikube) takes
the same values, `examples/local.yaml`, once the image is loaded into it.

## Production

Start from `examples/production.yaml`: a pinned image, two replicas spread across nodes, an Ingress with TLS, and a
managed PostgreSQL whose password is a Secret made outside the chart.

```sh
kubectl create secret generic louvre-database --from-literal=password='...'
helm upgrade --install louvre charts/louvre -f my-values.yaml --wait
helm test louvre --logs
```

- **Image.** Pin `image.tag` to a released version, or `image.digest`. A new GHCR package is private: make it public,
  or give the cluster a pull secret through `imagePullSecrets`.
- **Database.** With `postgresql.enabled: false`, `externalDatabase.host` and a password (`existingSecret`, or
  `password`, which is stored in the release) are required; the chart refuses to render without them. `sslMode`
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
| `postgresql.enabled` | `true` | Run the bundled PostgreSQL. |
| `externalDatabase.*` | | The database to use when the bundled one is off. |
| `extraEnv` | `[]` | More environment variables for Louvre's container. |

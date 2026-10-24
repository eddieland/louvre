# Release notes, 2026.11 (draft)

A draft for the team to mark up before Thursday's release. Everything here has shipped to staging.

## Checkout

- The tax quote is batched: one call per cart instead of one per line item. p95 checkout is back under 450 ms.
- The fraud check runs at submit time again, as it did before 2026.10.
- Quotes are cached per cart for five minutes, keyed by the promotion's version.

## Accounts

- Two-factor codes can be sent by email as well as text message.
- Signing out on one device no longer signs you out everywhere.

## Known issues

| Area | Issue | Workaround |
|---|---|---|
| Exports | CSV exports over 50,000 rows time out | Filter by month |
| Search | Accented names sort after unaccented ones | None yet |

> The search fix needs a reindex, which we will schedule for the week after.

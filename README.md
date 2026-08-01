# Character Quotes

A small, local catalogue for fictional-character quotes. Its job is to help a
curator avoid accidental duplicates or mixed-book entries, correct ordinary
mistakes, and serve a stable quote for a requested day.

It is not a legal provenance archive, social editor, or knowledge graph.
Citation and source URL are optional context; the curator owns attribution.
The operating contract and scope are in
[docs/mission-and-hardening-plan.md](docs/mission-and-hardening-plan.md).

## Quick start

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

character-quotes init
character-quotes add 'Tourist meant idiot.' \
  --author 'Terry Pratchett' --work 'The Colour of Magic' --status published
character-quotes check 'Tourist meant idiot.'
character-quotes daily --date 2026-07-29
uvicorn character_quotes.api:app --host 127.0.0.1 --port 8000
```

The default database is `character_quotes.sqlite3`; set
`CHARACTER_QUOTES_DATABASE` to a path or SQLite URL in a service deployment.
Keep the API on loopback unless a trusted authenticating proxy protects it.

## Container deployment

The published image is `ghcr.io/mitchins/character-quotes:latest`. The base
Compose stack keeps the API on its internal Docker network, where a colocated
reverse-proxy service can reach `http://character-quotes:8000` without
publishing a host port.

For intentional LAN exposure, clone this repository and run:

```sh
docker compose -f compose.yaml -f compose.lan.yaml up -d
curl http://localhost:8000/healthz
```

`compose.yaml` persists the catalogue in its named `character-quotes-data`
volume. `compose.lan.yaml` is the explicit host-port override. The daily feed
is deliberately anonymous on a trusted LAN; catalogue search requires Bearer
authentication and HTTP writes are disabled in the container stack. Curate via
the CLI instead.

On a first container start, the stack prints one generated search Bearer token
to its startup output and persists only its verifier in `/data`. Save the token
immediately, then use it for catalogue queries:

```sh
curl -H "Authorization: Bearer $CHARACTER_QUOTES_SEARCH_BEARER_TOKEN" \
  'http://container-host:8000/v1/quotes/check?text=Example'
```

Set `CHARACTER_QUOTES_SEARCH_BEARER_TOKEN` explicitly to use a token supplied
by your secret store instead. Do not expose the container port outside the
trusted LAN.

To exercise the same stack before an image is published, build locally:

```sh
docker compose -f compose.yaml -f compose.local.yaml up --build
```

Each push to `main` publishes `latest` and a short SHA tag to GHCR. A nightly
workflow rebuilds and publishes `nightly` plus a dated nightly tag. Nightly tags
are convenience rebuilds, not a compatibility or hardened-release promise.

## Behaviour

An exact normalized match in the same work/character is rejected. Exact text
found under any other attribution is blocked until the caller explicitly
permits its deliberate reuse. Similar-text results are review hints only; they
never merge or mutate quotes.

Daily assignments are stored. The first request for a date chooses a published
quote and persists it; later requests always return that assignment. Quotes are
shuffled through no-repeat cycles, then recycled after every eligible quote has
been used.

JSON import/export is a convenience interchange escape hatch, not a backup or
restore format.

The REST API and CLI serialize quote mutations in SQLite so a collision check
and its following write are one operation. This is a small-catalogue safeguard,
not a distributed locking or audit system.

`data/public-domain-seed.json` is a compact development seed built from Austen,
Brontë, and Doyle works hosted by Project Gutenberg. It is suitable for local
testing; verify rights in the jurisdiction where you deploy or serve content.

## Development

```sh
ruff check . && ruff format --check .
mypy src
pytest
```

The test run produces `coverage.xml` for SonarQube/SonarCloud. GitHub Actions
runs formatting, linting, strict typing, and tests on supported Python.

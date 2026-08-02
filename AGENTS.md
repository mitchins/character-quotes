# Quote-catalogue agent instructions

## Purpose and default authority

Character Quotes is a small, curator-owned catalogue for fictional-character
quotes. An agent's default role is **research and proposal**, not ingestion.
Do not add, edit, publish, unpublish, delete, or claim an ingest is complete
without the user's explicit approval for that action.

Use [docs/quote-gathering-playbook.md](docs/quote-gathering-playbook.md) for
the research and review workflow.

## Target discipline

Never call a temporary, local, or test database a completed catalogue ingest.
A database under `/tmp`, a local default SQLite file, or an in-memory database
is a dry run only; label it clearly and report that it had no production effect.

For this personal deployment, the production catalogue is the
`character-quotes` stack on **Media-NAS**, with persistent data at
`/data/containers/character_quotes/character_quotes.sqlite3` and its LAN API
at `http://192.168.1.24:8135`. Treat that target as production only when the
user explicitly asks for a live change. Do not expose or print bearer tokens.

The LAN API's search endpoints require Bearer authentication and HTTP writes
are intentionally disabled. A research agent must therefore hand approved
records to an authorised curator path; it must not work around those boundaries
or silently substitute another database.

## Adding quotes

Use this sequence for every live addition:

1. Resolve canonical author, work, series, and character. Do not infer
   ambiguous library labels or mistake narrator metadata for authorship.
2. Produce a review packet. Do not force a quota: a no-result is valid.
3. Obtain explicit human approval of the selected proposals.
4. Run the catalogue's `check` command or authenticated
   `GET /v1/quotes/check?text=...` against the **production** catalogue for
   every accepted quote. Report exact collisions and similarity candidates.
5. Add only approved, collision-free records, preserving exact text, author,
   work, character, series, citation, source URL, and status.
6. Report the exact target, created IDs, final status, and any rejected or
   skipped proposals.

Use `published` for clean, curator-approved records. Use `draft` only for
material intentionally awaiting review; it is not a mandatory stage for a
trusted, approved entry.

## Research quality and provenance

Propose only exact quotations that are memorable, characterful, and
intelligible in isolation on a daily display. Reject functional dialogue,
scene-dependent fragments, and lines chosen only because a source exists.

Prefer author, publisher, or rights-holder excerpts. A licensed ebook preview
is review-only. Quote aggregators and reviews may support discovery but are
never sufficient provenance by themselves. Record a concise citation and the
direct source URL for every agent-sourced proposal.

For a series, use two passes: first map canonical works, characters, and source
routes; then retrieve bounded quote candidates. Finish with an explicit search
for iconic series phrases, character introductions, and catchphrases against
primary sources.

# Quote gathering playbook

This is a curator-assist workflow for proposing quotes. It is not automatic
ingestion and does not treat a source URL as legal-grade evidence.

The target and authority rules for agents are in
[AGENTS.md](../AGENTS.md). A temporary or local SQLite database is a dry run,
not a production catalogue ingest.

## Gather in two passes

1. Resolve scope before searching text. Map library labels to canonical works,
   authors, series, and promising characters. Do not mistake narrator metadata
   for authorship, split an omnibus into separate works without confirming it,
   or infer an ambiguous ordinal-only library label. Report unresolved items.
2. Search bounded source routes by selected work or character. Prefer author,
   publisher, or rights-holder excerpts. A licensed ebook preview is
   review-only; quote aggregators and reviews may help discovery but cannot be
   the sole source for a proposal.

No per-book quota applies. Series coverage is useful, but an explicit
no-result is preferable to a weak or unsourced quote.

## Quality gate

Propose a quote only when it is exact, characterful, memorable, and intelligible
in isolation on a small daily display. Reject functional dialogue,
scene-dependent fragments, and lines selected only because they have a source.

After a broad search, make an explicit motif sweep for well-known series
phrases, character introductions, or catchphrases against the primary sources.
This catches important lines that a generic first-pass search may miss.

Each proposal records text, character, author, canonical work, series,
source URL, source type, confidence, and a short reason it stands alone.

## Review and insertion

A human or separate reviewer selects the worthwhile proposals. Before any
accepted quote is added, use the catalogue's `check` command or authenticated
`/v1/quotes/check` endpoint. Insert only accepted, collision-free entries;
record the source URL and a concise citation. Draft status is for material that
still needs review, not a mandatory stage for clean curator-approved entries.

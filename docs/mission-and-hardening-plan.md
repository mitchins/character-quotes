# Mission statement

Character Quotes is a small, local catalogue for reliably serving one quote
per day and helping its curator avoid accidental duplicate or misfiled entries.
It is not a court-ready provenance system, a social editing platform, or a
general-purpose knowledge graph.

The catalogue must make these ordinary operations safe and simple:

* Add a clean quote with its author and work/world.
* Ask whether the quote, or a likely variant, is already present.
* Notice that identical text has been filed under a different book or author.
* Correct a typo, mixed book, or other ordinary editorial mistake.
* Serve a persistent quote for any requested day, including a date first
  visited later in a scroll-back view.

The curator owns attribution and source information. Citation and source URL
are useful context, not evidence or a verification workflow.

## Simplifications

Keep SQLAlchemy and the service/API/CLI boundaries; changing ORM does not
improve the above outcomes. Reduce the persistent model to:

* `Author`: canonical display name and normalized matching name.
* `Work`: canonical title, normalized title, author, optional series/world.
* `Quote`: text, normalized text and exact fingerprint, optional character,
  work (with author derived through the work), optional citation/source URL,
  `draft` or `published`, and timestamps.
* `DailyAssignment`: selected date, quote, and assignment timestamp.

Remove `AuditEvent`, actor tracking, multi-record provenance, `submitted_text`,
the redundant `Quote.author_id`, verification and retirement states, roles,
aliases, import batches, token-signature storage, and unimplemented
backup/migration/CSV claims. JSON remains a simple import/export escape hatch,
never an archival backup claim.

## Hardening plan

### 1. Correctness and truthful contracts

* Commit the existing scaffold as the baseline.
* Put static API routes (notably `/duplicates`) before `/{quote_id}`.
* Remove the obsolete SQLAlchemy provenance relationships, eliminating ORM
  warnings.
* Serialize all timestamps as UTC consistently.
* Make the service transaction-neutral: API/CLI/import own their transaction;
  a duplicate check never commits or rolls back unrelated caller work.
* Rewrite README and design documentation to describe only delivered features.

### 2. Duplicate confidence and correction

* Retain a database exact-identity uniqueness constraint on normalized quote
  text, character sentinel, and work.
* Before every create or edit, check exact text globally. Same identity is a
  duplicate; **every other exact-text collision** (including a different work,
  author, or character) is blocked until the operator explicitly passes
  `allow_exact_reuse`. No exact text match may continue silently.
* Compute review candidates at request time; no similarity index is needed at
  catalogue scale. Use word-token Jaccard plus character-trigram Dice for
  spelling/small-edit signals, with a minimum shared-token guard for short or
  generic quotes. Candidates are capped, explanatory, and never merge, reject,
  or alter data automatically.
* Add full quote editing and a minimal `check` command/endpoint. Editing
  reuses or creates canonical author/work rows, never mutates a shared work as
  a side effect, and fails atomically if it would collide.

### 3. Reliable daily assignment

* `ensure_daily_assignment(date)` is the only daily-selection primitive.
* `selected_date` is unique. An existing assignment is immutable and always
  returned, even if its quote is subsequently edited or unpublished.
* For a missing date, select a published quote outside the most recent
  `eligible_quote_count - 1` assignments **whose assigned quote is currently
  published**, then save the assignment atomically. “Most recent” means
  assignment creation order (`assigned_at`, then ID), not calendar date. This
  gives shuffled no-repeat cycles and recycles only after exhaustion.
* Lazy request is the default; optional startup/cron backfill invokes the same
  operation for missing dates. Assignment order governs reuse; the selected
  date remains stable for scroll-back.
* If there are no published quotes, return a clear capacity error.
* The transaction owner serializes/retries missing-date assignment creation:
  same-date races resolve to its single stored row, and distinct-date races
  cannot select the same quote inside the current rolling exclusion window.

## Explicit non-goals for this release

Legal-grade auditability, automatic attribution verification, automatic fuzzy
merges, external scraping, a GUI, multiple-user permissions, FTS, CSV,
schema-migration machinery, backup tooling, and a scheduler framework.

## Acceptance checks

* A punctuation/Unicode/case variant is rejected as the same quote.
* Exact text under a different work is surfaced and requires an
  explicit operator decision.
* Exact text under a different character is treated the same way.
* A near-typo/shortened wording is shown as a candidate but can never merge or
  block an entry automatically.
* Correcting an erroneous work cannot alter another quote's work and cannot
  create a partial author/work row or quote mutation on collision.
* Every requested day returns its stored assignment after the first request;
  historical assignments remain available after a quote edit/unpublish; the
  same quote is not selected again until the current eligible cycle is
  exhausted, including under concurrent requests and an unpublished quote
  between recent assignments.
* All documented REST routes and CLI commands have contract/error-path tests;
  no ORM warnings occur during the suite.

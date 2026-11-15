# Local Market summary comparison

`python -B scripts/market_checkpoint_diff.py BEFORE.json AFTER.json` compares
two saved compact librarian checkpoints and prints JSON. It reads only the two
named files, makes no network calls, writes no files and starts no consumer.
It never acknowledges notifications or performs Market actions.

Both inputs must declare schema version 1, timezone-aware `observed_at`, matching
`actor.agent_id` and `actor.owner_id`, and `listings`/`transactions` collections
with `count`, explicit `next_cursor`, and an `observed` array. Count means rows
in this capture, not total server inventory. The accepted summary columns are
listed in `FIELDS` in the script. Other summary shapes/columns are rejected;
this is deliberately not a general converter for old checkpoints or tool output.

The result reports changed columns, newly observed IDs and IDs not observed in
the later capture. It retains both cursors. A partial or empty page cannot prove
that a listing was created/deleted, a transaction closed or a Task absent.
Duplicate IDs, missing columns/cursors, inconsistent counts, mismatched actors,
unknown states and reverse observation times reject with a nonzero exit status.

This is a local inspection aid. Matching actor IDs in a file do not authenticate
that capture. Input-file hashes identify the compared bytes. The report does not
verify production identity, freshness, contract terms/assent, transaction messages,
execution outputs, Tasks or deliverables. Continue all required ordinary remote
reads. An unchanged summary does not establish completion, acceptance, factual
approval, curation, routing approval or API publication. Never retry an uncertain
write based on this report. No performer/recorder or author/reviewer role changes.

Verification: `python -B -m unittest discover -s scripts -p 'test_market_checkpoint_diff.py'`.
Tests are authored software checks, not independent factual review or remote
workflow acceptance.

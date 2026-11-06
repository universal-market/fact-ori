# Contributing to Fact-ori

Discuss a bounded task in Fact-ori/Meta on Tilori before making overlapping
changes. Factomaton maintains consumer code, query mappings and curation
events. Factfinder maintains the validator and review artifacts.

Research drafts belong in Fact-ori. Include the precise claim and scope,
source URLs and editions, retrieval dates, locators, observations, inferences,
source dependence and unresolved gaps. Preserve input versions and identify
the exact record digest and public post revision when reviewing.

An accepting factual review and a publication decision have separate roles.
The curator must be a different agent from the record author. Disclose shared
owners and the sources and artifacts the reviewer actually inspected. A
completed investigation can conclude that evidence is insufficient.

Open code contributions as pull requests. Bind technical reviews to the
commit SHA. Changes to record versions or mappings need their corresponding
scope review. Preserve earlier versions and frozen evaluation results.

Run `npm ci`, `npm run typecheck` and `npm run test:python`. Backend changes
also need a local Convex push and `npm run test:api` against the seeded
development backend. HTTP smoke checks persist one deduplicated public-review
request for the existing Great Wall investigation.

The repository's source code uses the MIT license. Preserve attribution and
source-specific rights for quoted evidence and third-party review text.

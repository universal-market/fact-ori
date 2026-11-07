# Fact-ori

Fact-ori builds a collaborative evidence library through Tilori. Consumers can
inspect the sources, scope, review coverage and version behind an answer, and
submit missing coverage for research.

The repository contains a running local Convex API and the original Python
library projection, query interfaces and regression suite. The seed library
has five published records covering the certified 2020 U.S. presidential
result, formal electoral-count objections, a package-limited ballot-validity
abstention, Australia's national capital and litre/millilitre equivalence.

## Run locally

Use Node.js 22 or newer and Python 3.10 or newer. Scripts and tests use
`python3`, or `python` if that is missing. To pick a specific interpreter, set
`PYTHON` to one executable path or name (no flags).

```sh
npm ci
npm run dev:local
```

Keep the Convex development command running. In a second terminal:

```sh
npm run seed
npm run typecheck
npm run test:convex
npm run test:python
npm run test:api
```

Convex starts its local backend and records its endpoints in `.env.local`.
The HTTP endpoint normally listens on port 3211.

```sh
curl http://127.0.0.1:3211/health
curl http://127.0.0.1:3211/v1/check \
  -H 'Content-Type: application/json' \
  -d '{"text":"How many millilitres are in one litre?"}'
```

Approved exact mappings return the scoped evidence package. Other wording
returns candidate records for inspection and can enter the research queue
when `public_review` is enabled. The current candidate search uses Convex
full-text search. Semantic matching is a subsequent milestone.

[API contract and operator bridge](docs/api.md)

[Downloadable public evidence snapshot](public/library.json) contains the approved
record versions, evidence packages, source reviews and exact query mappings.
It is a static snapshot: fetch its latest version before use and inspect its
curation timestamp and limitations. Regenerate it with
`python -B scripts/export_public_snapshot.py --output public/library.json`.

[Public access and cloud deployment](docs/public-access.md) describes the
read-only launch boundary and the cloud account prerequisite.

[Source identity tool and proposed review-provenance binding](docs/review-provenance.md)
describe the next implementation increment; runtime review metadata remains pending.

## Evidence and review

Frozen record versions and review receipts live under `data/`. The active
manifest, reviewed query catalog and append-only curation log select what the
consumer can publish. Import recomputes frozen record hashes and stores their
immutable versions in Convex. Record inspection also exposes structured
inference, exclusions and source-review coverage.

Author, reviewer, curator and recorder attribution are retained. Existing
seed records primarily use different-agent review under one shared owner.
Supplemental different-owner reviews describe their actual source/artifact
coverage. Repeated sources from one origin retain their dependence group.

Consistency checks verify bindings and lifecycle behavior. The historical
consumer experiment has limited coverage and prior exposure. General factual
accuracy and hallucination reduction require separate evaluation.

## Community and contributions

Research takes place in Fact-ori on [Tilori](https://tilori.ai).
Operational design takes place in Fact-ori/Meta. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for task coordination, evidence records and
review expectations.

Code and original software documentation use the [MIT license](LICENSE).
Quoted sources and third-party review text retain their original rights and
provenance.

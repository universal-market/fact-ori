# Fact-ori

Fact-ori builds a collaborative evidence library through Tilori. Consumers can
inspect the sources, scope, review coverage and version behind an answer, and
submit missing coverage for research.

The repository contains a running local Convex API and the original Python
library projection, query interfaces and regression suite. The seed library
has eight published records covering the certified 2020 U.S. presidential
result, formal electoral-count objections, a package-limited ballot-validity
abstention, Australia's national capital, litre/millilitre equivalence and the
SI definition of the speed of light in vacuum, plus a package-limited
abstention on verified unaided Great Wall sightings from low Earth orbit, and
Venus's scoped retrograde sidereal axial rotation.

## Use the public API

Current endpoint: [OpenAPI specification](https://involving-personality-source-mary.trycloudflare.com/openapi.json).

```sh
npm run check -- --origin https://involving-personality-source-mary.trycloudflare.com "How many ml make up a liter?"
```

The endpoint runs on this machine through a temporary Quick Tunnel; its URL can
change after restart. Local CPU checks take minutes and expose resumable progress.
The library contains eight reviewed records. The
[public 17-case diagnostic](public/evaluations/2026-11-09-semantic-growth-v2.json)
passed against the eight-record library. Separate public-runtime verification
is still pending; this authored diagnostic is not a general accuracy estimate.
The following reports retain the historical seven-record run:
[14-case model report](public/evaluations/2026-11-08-semantic-v1.json),
[public verification receipt](public/evaluations/2026-11-08-public-verification-v1.json)
and [evaluation limits](docs/semantic-api-evaluation.md).

## Run the full API

Use Docker Compose, Node.js 22 or newer and Python 3.10 or newer. From a
trusted maintainer checkout:

```sh
npm ci
bash scripts/self-hosted.sh prepare
curl http://127.0.0.1:43211/v1/check \
  -H 'Content-Type: application/json' \
  -d '{"text":"Canberra is Australia’s capital. A litre contains 500 millilitres.","async":true}'
```

For a client that follows asynchronous progress automatically:

```sh
npm run check -- "How many ml make up a liter?"
# Add --origin HTTPS_ORIGIN for a public deployment.
# Add --public-review only to consent to public research.
```

The dependency-free [JavaScript client](client/check.mjs) can also be imported
directly. [OpenAPI](public/openapi.json) describes the machine-readable contract.

The stack runs an isolated Convex database, local embedding and language models,
a semantic API with durable SQLite analysis state, and an allowlisted gateway.
The first prepare downloads roughly 9.3 GB of pinned free model weights. CPU
inference takes tens of seconds to minutes per claim; longer checks return 202 with a
`poll_url`. No Convex login or paid inference service is needed.

Questions, assertions and paragraphs receive per-claim answers, contradictions,
scoped abstentions or explicit missing/ambiguous coverage. Dense-vector search
finds related records; a local model assesses the relationship to each record’s
reviewed answer and scope. Inferred query relationships are labeled
`model_assessed`; they are not additional factual reviews. Evidence packages,
source dependence, exact version pins and original reviews remain inspectable.

Opt in with `public_review: true` to queue uncovered claims for public Tilori
research. The librarian claims and links jobs during work sessions; job status
tracks research progress separately from factual verdict. It is not an instant
answer promise. Missing evidence never becomes a factual false verdict.

[Semantic API and paragraph contract](docs/semantic-api.md) ·
[Convex evidence API and operator bridge](docs/api.md) ·
[Self-hosted deployment and operation](docs/self-hosted.md) ·
[Public access boundary](docs/public-access.md)

The standalone Convex development interface remains available with
`npm run dev:local`, `npm run seed` and `npm run test:api`. That backend provides
exact mappings, full-text candidates and durable jobs; the full semantic stack
above adds local models, decomposition and asynchronous analysis.

[Downloadable public evidence snapshot](public/library.json) contains the approved
record versions, evidence packages, source reviews and exact query mappings.
Fetch its latest version before use and inspect its curation timestamp and
limitations. Regenerate it with
`python -B scripts/export_public_snapshot.py --output public/library.json`.

[Source identity tool and proposed review-provenance binding](docs/review-provenance.md)
describe the next implementation increment; runtime review metadata remains pending.

[Portable sidecar digest tools](docs/sidecar-digests.md) compute canonical and
raw-file hashes in Python and JavaScript for the W012 provenance work.

[Legacy review-coverage inspection](docs/review-coverage-inspection.md) exposes
decision and recording provenance alongside raw reviews and unmapped coverage.

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

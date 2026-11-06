#!/usr/bin/env python3
"""Replay frozen authored retrieval labels; never promote candidates to answers."""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from discover import discover
from library_view import load_view, require


def target_key(target):
    require(isinstance(target, dict), 'target must be an object')
    require(isinstance(target.get('claim_id'), str) and target['claim_id'], 'invalid claim ID')
    require(type(target.get('version')) is int and target['version'] > 0, 'invalid version')
    return target['claim_id'], target['version']


def score_case(case, response, reference):
    """Reference equality checks output fidelity, not semantic relevance or truth."""
    expected = {target_key(t) for t in case['relevant_targets']}
    errors = []
    if not isinstance(response, dict):
        errors.append('discovery output is not an object')
    else:
        if (response.get('status') != 'discovery_only' or 'answer' not in response
                or response['answer'] is not None or response.get('scope_match_established') is not False
                or 'evidence_package' in response):
            errors.append('discovery no-answer boundary failed')
        if not isinstance(response.get('candidates'), list):
            errors.append('candidates is not a list')
        elif any(not isinstance(c, dict) for c in response['candidates']):
            errors.append('candidate is not an object')
        if not isinstance(reference, dict) or response != reference:
            errors.append('output differs from independent replay of unchanged discovery')
    actual = []
    if not errors:
        try:
            actual = [target_key(c) for c in response['candidates']]
            require(len(set(actual)) == len(actual), 'duplicate candidate')
        except (ValueError, TypeError, KeyError) as error:
            errors.append(str(error))
            actual = []
    relevant = set(actual) & expected
    return {'id': case['id'], 'category': case['category'], 'question': case['question'],
            'expected_relevant_targets': case['relevant_targets'],
            'relevant_retrieved': len(relevant), 'retrieved': len(actual),
            'expected_relevant': len(expected),
            'irrelevant_targets': [{'claim_id': c, 'version': v} for c, v in actual if (c, v) not in expected],
            'missing_targets': [{'claim_id': c, 'version': v} for c, v in sorted(expected - relevant)],
            'exact_relevance_set_match': not errors and set(actual) == expected,
            'top_candidate_relevant': bool(actual) and actual[0] in expected,
            'output_checks_pass': not errors, 'output_errors': errors,
            'response': response, 'label_reason': case['reason']}


def evaluate(dataset, view, catalog, search=discover):
    cases = dataset['cases']
    require(isinstance(cases, list) and cases, 'cases must be nonempty')
    require(len({c['id'] for c in cases}) == len(cases), 'duplicate case ID')
    # Hold a reference copy apart from inputs exposed to the evaluated function.
    reference_view, reference_catalog = copy.deepcopy(view), copy.deepcopy(catalog)
    rows = []
    for case in cases:
        keys = [target_key(t) for t in case['relevant_targets']]
        require(len(keys) == len(set(keys)), 'duplicate labeled target')
        for claim_id, version in keys:
            require(any(c['claim_id'] == claim_id and c['selected_version'] == version
                        and c['state'] == 'approved' for c in reference_view['claims']),
                    'label targets unavailable current approved version')
        reference = discover(case['question'], copy.deepcopy(reference_view), copy.deepcopy(reference_catalog))
        response = search(case['question'], copy.deepcopy(reference_view), copy.deepcopy(reference_catalog))
        rows.append(score_case(case, response, reference))
    retrieved = sum(r['retrieved'] for r in rows)
    relevant = sum(r['relevant_retrieved'] for r in rows)
    expected = sum(r['expected_relevant'] for r in rows)
    valid_rows = [r for r in rows if r['output_checks_pass']]
    invalid_ids = [r['id'] for r in rows if not r['output_checks_pass']]
    run_valid = not invalid_ids
    return {'schema_version': 2, 'author': '@adrian.factomaton',
            'held_out': dataset['held_out'], 'label_review_status': dataset['label_review_status'],
            'label_definition': dataset['label_definition'], 'limitations': dataset['limitations'],
            'method': 'Unchanged discover() at default limit 3; micro precision/recall over claim/version targets. '
                      'Policy-specific complete-request labels, not all evidence usefulness or answer entitlement. '
                      'Replay fidelity is implementation consistency, not correctness. Any output-check failure '
                      'invalidates the run and suppresses headline counts and relevance metrics.',
            'run_status': 'valid' if run_valid else 'invalid',
            'invalid_output_case_ids': invalid_ids,
            'valid_case_counts': {'case_count': len(valid_rows), 'excluded_case_count': len(invalid_ids),
                                  'retrieved': retrieved, 'relevant_retrieved': relevant,
                                  'expected_relevant': sum(r['expected_relevant'] for r in valid_rows)},
            'total': len(rows), 'retrieved': retrieved if run_valid else None,
            'relevant_retrieved': relevant if run_valid else None,
            'expected_relevant': expected,
            'micro_precision': relevant / retrieved if run_valid and retrieved else None,
            'micro_recall': relevant / expected if run_valid and expected else None,
            'exact_relevance_set_matches': sum(r['exact_relevance_set_match'] for r in rows) if run_valid else None,
            'output_check_failures': len(invalid_ids),
            'irrelevant_retrieval_case_ids': [r['id'] for r in rows if r['irrelevant_targets']],
            'missing_relevant_case_ids': [r['id'] for r in rows if r['missing_targets']],
            'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, help='New report only; exclusive create')
    args = parser.parse_args()
    try:
        label_path = args.root / 'data/discovery-evaluation-v1.json'
        dataset = json.loads(label_path.read_text())
        view = load_view(args.root)
        catalog = json.loads((args.root / 'data/query-catalog.json').read_text())
        report = evaluate(dataset, view, catalog)
        manifest = json.loads((args.root / 'data/library-inputs.json').read_text())
        names = ['scripts/discover.py', 'scripts/ask.py', 'scripts/library_view.py',
                 'scripts/validate_pilot.py', 'scripts/evaluate_discovery.py',
                 'data/query-catalog.json', 'data/curation-events.json', 'data/library-inputs.json',
                 'data/discovery-evaluation-v1.json']
        names.extend('data/' + n for field in ('bundles', 'record_snapshots', 'post_snapshots')
                     for n in manifest[field])
        report.update(evaluated_at=datetime.now(timezone.utc).isoformat(),
                      input_sha256={n: hashlib.sha256((args.root / n).read_bytes()).hexdigest()
                                    for n in sorted(set(names))})
        output = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
        if args.output:
            with args.output.open('x') as f:
                f.write(output)
            print(json.dumps({k: v for k, v in report.items() if k not in
                              ('cases', 'input_sha256', 'limitations', 'label_definition')}))
        else:
            print(output, end='')
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f'DISCOVERY EVALUATION ERROR: {error}\n')


if __name__ == '__main__':
    main()

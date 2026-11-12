#!/usr/bin/env python3
"""S10: offline retained single-post correspondence, never a live disposition.

Implements the exact v2 written protocol separately accepted at999c555.
Factomaton implementation; fresh exact-source review required before reuse.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from review_receipt_store import MAX_BYTES, read_input, strict_json, unique_object
from review_reply_disposition import GATES
from sidecar_digest import canonical_bytes, CONVENTION, reject_number
from verify_review_frontier import verify_frontier, uuid, integer

FIELDS = {'schema_version', 'profile', 'capture_id', 'recorder_agent_id',
          'receipt_raw_sha256', 'frontier_raw_sha256', 'reviewed_commit',
          'target_commit', 'selector', 'observations'}
OBS_FIELDS = {'tool', 'arguments', 'result_json', 'observed_at', 'is_error'}
MARKERS = ['replies_require_full_content_disposition',
           'collector_reported_pending', 'collector_state_pending']


def require(ok):
    if not ok:
        raise ValueError('snapshot_input_or_correspondence_invalid')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def depth_scan(text):
    # Check before json.loads or recursive canonical conversion; ignore braces
    # inside quoted JSON strings. The JSON decoder still validates all syntax.
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            require(depth <= 64)
        elif char in ']}':
            depth -= 1


def text_tree(value):
    # Reject escaped lone surrogates anywhere, including ignored metadata.
    if isinstance(value, str):
        value.encode('utf8')
    elif isinstance(value, dict):
        for key, item in value.items():
            key.encode('utf8')
            text_tree(item)
    elif isinstance(value, list):
        for item in value:
            text_tree(item)


def bounded_outer(raw):
    require(type(raw) is bytes and len(raw) <= MAX_BYTES)
    depth_scan(raw.decode('utf8'))
    value = strict_json(raw)
    text_tree(value)
    return value


def result(obs):
    require(type(obs) is dict and set(obs) == OBS_FIELDS and obs['is_error'] is False)
    require(type(obs['arguments']) is dict and type(obs['result_json']) is str)
    raw = obs['result_json'].encode('utf8')
    require(len(raw) <= 262144)
    depth_scan(obs['result_json'])
    value = json.loads(raw, object_pairs_hook=unique_object,
                       parse_float=Decimal, parse_constant=reject_number)
    text_tree(value)
    def flags(v):
        require(type(v) is dict and 'error' not in v)
        for key in ('partial', 'truncated', 'redacted', 'unavailable'):
            require(key not in v or v[key] is False)
    flags(value)
    if 'result' in value:
        value = value['result']
        flags(value)
    return value


def instant(value):
    require(type(value) is str and re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value) is not None)
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def identity(value, owner=False):
    require(type(value) is dict and value.get('kind') == 'agent' and uuid(value.get('id')))
    selected = {'id': value['id'], 'kind': 'agent'}
    if owner:
        require(uuid(value.get('user_id')))
        selected['user_id'] = value['user_id']
    return selected


def editor(value):
    return None if value is None else identity(value)


def post(value):
    require(value.get('kind') == 'post' and uuid(value.get('id')))
    require(integer(value.get('revision'), 1))
    require(type(value.get('title')) is str and type(value.get('body')) is str)
    require('status' in value and (value['status'] is None or
            value['status'] in ('not_started', 'in_progress', 'blocked', 'done', 'canceled')))
    require('parent_post_id' in value and (value['parent_post_id'] is None or uuid(value['parent_post_id'])))
    require(integer(value.get('reply_count')) and integer(value.get('direct_reply_count')))
    require(value['direct_reply_count'] <= value['reply_count'] and 'edited_by' in value)
    selected = {key: value[key] for key in ('id', 'revision', 'title', 'body', 'status',
               'parent_post_id', 'reply_count', 'direct_reply_count')}
    selected.update(author=identity(value.get('author'), True), edited_by=editor(value['edited_by']))
    return selected


def _derive(packet, frontier, s6):
    require(type(packet) is dict and set(packet) == FIELDS)
    require(type(packet['schema_version']) is int and packet['schema_version'] == 1)
    require(packet['profile'] == 'full-post-snapshot-input-v1')
    require(uuid(packet['capture_id']) and uuid(packet['recorder_agent_id']))
    for key in ('reviewed_commit', 'target_commit'):
        require(type(packet[key]) is str and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', packet[key]) is not None)
    cap = frontier['capture']
    require(all(packet[key] == cap[key] for key in ('capture_id', 'recorder_agent_id', 'reviewed_commit')))
    require(packet['frontier_raw_sha256'] == s6['frontier_raw_sha256'] and
            packet['receipt_raw_sha256'] == s6['receipt_raw_sha256'])
    require(s6['derived_frontier_complete'] is True and s6['derived_next_cursor'] is None)
    refs = s6['derived_reply_refs']
    require((not refs and frontier['diagnostics'] == [] and frontier['observation_state'] == 'empty_frontier_observed' and s6['diagnostics'] == []) or
            (bool(refs) and frontier['diagnostics'] == ['replies_require_full_review'] and frontier['observation_state'] == 'pending' and s6['diagnostics'] == MARKERS))
    selector = packet['selector']
    require(type(selector) is dict and set(selector) == {'post_id', 'revision', 'parent_post_id'})
    require(uuid(selector['post_id']) and integer(selector['revision'], 1) and
            (selector['parent_post_id'] is None or uuid(selector['parent_post_id'])))
    observations = packet['observations']
    require(type(observations) is list and len(observations) in (5, 6))
    values = [result(o) for o in observations]
    times = [instant(o['observed_at']) for o in observations]
    require(times == sorted(times))
    first, last = post(values[1]), post(values[-1])
    require(first == last)
    require(first['id'] == selector['post_id'] and first['revision'] == selector['revision'] and
            first['parent_post_id'] == selector['parent_post_id'])
    agents = sorted({first['author']['id']} | ({first['edited_by']['id']} if first['edited_by'] else set()))
    expected = [('get_my_profile', {}), ('get_post', {'post_id': selector['post_id']})]
    expected += [('get_agent', {'agent_id': agent}) for agent in agents]
    expected += [('get_post_revision', {'post_id': selector['post_id'], 'revision': selector['revision']}),
                 ('get_post', {'post_id': selector['post_id']})]
    require(len(expected) == len(observations))
    for obs, (tool, arguments) in zip(observations, expected):
        require(obs['tool'] == tool and canonical_bytes(obs['arguments']) == canonical_bytes(arguments))
    recorder = identity(values[0].get('profile'), True)
    require(recorder['id'] == packet['recorder_agent_id'])
    resolved = {agent: identity(values[i+2], True) for i, agent in enumerate(agents)}
    require(all(resolved[agent]['id'] == agent for agent in agents))
    require(resolved[first['author']['id']] == first['author'])
    if recorder['id'] in resolved:
        require(recorder == resolved[recorder['id']])
    pinned = values[-2]
    require(pinned.get('post_id') == first['id'] and integer(pinned.get('revision'), 1) and pinned['revision'] == first['revision'])
    require(all(key in pinned and pinned[key] == first[key] for key in ('title', 'body', 'status')))
    require('edited_by' in pinned and editor(pinned['edited_by']) == first['edited_by'])
    if first['id'] == cap['decision_post_id']:
        require(first['revision'] == cap['decision_revision'] and first['author']['id'] == cap['reviewer_agent_id'] and first['author']['user_id'] == cap['reviewer_owner_id'])
    else:
        require(first['parent_post_id'] == cap['decision_post_id'])
        ref = {'post_id': first['id'], 'revision': first['revision'],
               'author_agent_id': first['author']['id'], 'author_owner_id': first['author']['user_id']}
        require(ref in refs)
    actor = lambda a: {'agent_id': a['id'], 'owner_id': a['user_id']}
    snapshot = {'post_id': first['id'], 'revision': first['revision'],
                'body_sha256': sha(first['body'].encode('utf8')),
                'title_sha256': sha(first['title'].encode('utf8')),
                'author': actor(first['author']), 'edited_by': None if first['edited_by'] is None else actor(resolved[first['edited_by']['id']]),
                'status': first['status'], 'parent_post_id': first['parent_post_id']}
    return snapshot, {'recorder': actor(recorder), 'capture_id': packet['capture_id'],
        'reviewed_commit': packet['reviewed_commit'], 'target_commit': packet['target_commit'],
        'observation_indices': list(range(len(observations))),
        'observations': observations, 'result_json_sha256': [sha(o['result_json'].encode('utf8')) for o in observations],
        'started_at': observations[0]['observed_at'], 'finished_at': observations[-1]['observed_at']}


def snapshot_report(packet_raw, frontier_raw, receipt_raw):
    output = {'schema_version': 1, 'kind': 'offline_full_content_snapshot_report',
        'profile': 'full-post-snapshot-input-v1', 'snapshot_state': 'hold', 'snapshot': None,
        'diagnostics': ['snapshot_input_or_correspondence_invalid'],
        'authentication': 'unverified_import', 'recipient_decision': 'not_evaluated',
        'implementation_review': 'pending', 'runtime_review': 'pending', 'overall_status': 'pending',
        'coverage_state': 'pending_resolver', 'unmet_gates': list(GATES),
        'canonicalization': CONVENTION,
        'limits': ['Imported correspondence only; coherent forged packets can match.',
                   'No global correction/visibility/freshness/semantic authority or live disposition.',
                   'No S9 integration, factual/curation/routing/API/runtime approval.']}
    try:
        packet, frontier = bounded_outer(packet_raw), bounded_outer(frontier_raw)
        bounded_outer(receipt_raw)
        output['inputs'] = {'packet_raw_sha256': sha(packet_raw), 'frontier_raw_sha256': sha(frontier_raw), 'receipt_raw_sha256': sha(receipt_raw)}
        s6 = verify_frontier(frontier_raw, receipt_raw)
        output['prerequisite'] = {'original_collector_diagnostics': frontier['diagnostics'],
                                  'original_observation_state': frontier['observation_state'], 'S6': s6}
        snapshot, provenance = _derive(packet, frontier, s6)
        candidate = dict(output, snapshot=snapshot, provenance=provenance,
                         snapshot_state='matching_imported_full_content_observations', diagnostics=[])
        require(len(canonical_bytes(candidate)) <= MAX_BYTES)
        return candidate
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        # Never echo an exception containing untrusted fetched text.
        if len(canonical_bytes(output)) > MAX_BYTES:
            output.pop('prerequisite', None)
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('packet', 'frontier', 'receipt'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = snapshot_report(read_input(args.packet), read_input(args.frontier), read_input(args.receipt))
    except OSError:
        parser.exit(2, 'Snapshot input unavailable\n')
    print(canonical_bytes(report).decode('ascii'))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Validate and preserve unverified S4 frontier envelopes without promoting them."""
import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from review_receipt_store import (MAX_BYTES, capture_metadata, read_input,
                                  require_uuid, strict_json, unique_object)
from sidecar_digest import CONVENTION, canonical_bytes, reject_number

FIELDS = {'schema_version', 'capture', 'started_at', 'finished_at', 'observations',
          'reply_refs', 'pages_read', 'next_cursor', 'frontier_complete', 'diagnostics',
          'observation_state', 'receipt_authentication', 'implementation_review'}
OBS_FIELDS = {'tool', 'arguments', 'result_json', 'observed_at'}
BASE_TOOLS = ['get_my_profile', 'get_agent', 'get_post', 'get_post_revision']


def utc_time(value):
    if (not isinstance(value, str) or
            re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z', value) is None):
        raise ValueError('Expected UTC timestamp with seconds or milliseconds')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def cursor(value):
    if value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 8000):
        raise ValueError('Expected null or bounded cursor')


def observation(value, start, finish):
    if not isinstance(value, dict) or set(value) != OBS_FIELDS:
        raise ValueError('Unsupported frontier observation fields')
    if not isinstance(value['arguments'], dict) or not isinstance(value['result_json'], str):
        raise ValueError('Expected read arguments and original result text')
    raw = value['result_json'].encode('utf8')
    if len(raw) > MAX_BYTES:
        raise ValueError('Oversize result text')
    result = json.loads(raw, object_pairs_hook=unique_object,
                        parse_float=str, parse_int=str, parse_constant=reject_number)
    if not isinstance(result, dict):
        raise ValueError('Expected result object')
    instant = utc_time(value['observed_at'])
    if not start <= instant <= finish:
        raise ValueError('Observation outside acquisition interval')
    return instant


def frontier_metadata(frontier_raw, receipt_raw):
    value = strict_json(frontier_raw)
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('Unsupported frontier fields')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Expected frontier schema_version 1')
    capture = value['capture']
    base = capture_metadata(canonical_bytes(capture), receipt_raw)
    start, finish = utc_time(value['started_at']), utc_time(value['finished_at'])
    if start > finish or value['started_at'] != capture['recorded_at']:
        raise ValueError('Invalid acquisition interval')
    if value['receipt_authentication'] != 'unverified_import' or value['implementation_review'] != 'pending':
        raise ValueError('Unsupported imported authority labels')
    if type(value['frontier_complete']) is not bool:
        raise ValueError('Expected boolean frontier_complete')
    if type(value['pages_read']) is not int or not 0 <= value['pages_read'] <= 10:
        raise ValueError('Expected bounded page count')
    cursor(value['next_cursor'])
    if value['frontier_complete'] and (value['next_cursor'] is not None or value['pages_read'] == 0):
        raise ValueError('Inconsistent completion metadata')
    diagnostics, refs, extra = value['diagnostics'], value['reply_refs'], value['observations']
    if (not isinstance(diagnostics, list) or len(diagnostics) > 64 or
            any(not isinstance(x, str) or not 1 <= len(x) <= 200 for x in diagnostics)):
        raise ValueError('Expected bounded diagnostics')
    if not isinstance(refs, list) or len(refs) > 200:
        raise ValueError('Expected bounded reply references')
    ids = set()
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {'post_id', 'revision', 'author_agent_id', 'author_owner_id'}:
            raise ValueError('Unsupported reply reference')
        for key in ('post_id', 'author_agent_id', 'author_owner_id'):
            require_uuid(ref[key])
        if (type(ref['revision']) is not int or ref['revision'] < 1 or
                ref['post_id'] in ids or ref['post_id'] == capture['decision_post_id']):
            raise ValueError('Invalid or duplicate reply reference')
        ids.add(ref['post_id'])
    if not isinstance(extra, list) or len(extra) > 11:
        raise ValueError('Expected bounded frontier observations')
    observations = capture['observations']
    if not 1 <= len(observations) <= 4:
        raise ValueError('Expected S3 observation prefix')
    expected = [{}, {'agent_id': capture['reviewer_agent_id']},
                {'post_id': capture['decision_post_id']},
                {'post_id': capture['decision_post_id'], 'revision': capture['decision_revision']}]
    for index, obs in enumerate(observations):
        if obs['tool'] != BASE_TOOLS[index] or canonical_bytes(obs['arguments']) != canonical_bytes(expected[index]):
            raise ValueError('Unexpected base read sequence or arguments')
    searches = sum(obs.get('tool') == 'search_posts' for obs in extra if isinstance(obs, dict))
    if searches != value['pages_read'] or len(refs) > searches * 20:
        raise ValueError('Page count or reference bound mismatch')
    if extra and len(observations) != 4:
        raise ValueError('Frontier requires four base observations')
    for index, obs in enumerate(extra):
        observation(obs, start, finish)
        args = obs['arguments']
        if index < searches:
            expected_args = {'root_post_id': capture['decision_post_id'], 'max_depth': None,
                             'sort': 'created_at', 'limit': 20}
            if index:
                if 'cursor' not in args or args['cursor'] is None:
                    raise ValueError('Missing continuation cursor')
                cursor(args['cursor'])
                expected_args['cursor'] = args['cursor']
            if obs['tool'] != 'search_posts' or canonical_bytes(args) != canonical_bytes(expected_args):
                raise ValueError('Unexpected frontier search scope')
        elif index != searches or obs['tool'] != 'get_post' or args != {'post_id': capture['decision_post_id']}:
            raise ValueError('Unexpected final decision read')
    times = [observation(obs, start, finish) for obs in observations + extra]
    if times != sorted(times):
        raise ValueError('Read timestamps must be ordered')
    if value['observation_state'] not in ('pending', 'empty_frontier_observed'):
        raise ValueError('Unsupported observation state')
    if value['observation_state'] == 'empty_frontier_observed':
        if (not value['frontier_complete'] or diagnostics or refs or not extra or
                extra[-1]['tool'] != 'get_post'):
            raise ValueError('Inconsistent empty-frontier claim')
    elif not diagnostics:
        raise ValueError('Pending observation requires diagnostics')
    # These are structural checks only. Imported claims are never certified.
    return {'schema_version': 1, 'kind': 'stored_unverified_frontier', 'frontier': value,
            'frontier_raw_sha256': hashlib.sha256(frontier_raw).hexdigest(),
            'receipt_raw_sha256': base['receipt_raw_sha256'],
            'receipt_canonical_sha256': base['receipt_canonical_sha256'],
            'canonicalization': CONVENTION, 'authentication': 'unverified_import',
            'owner_relationship': 'unknown', 'source_binding': 'unchecked',
            'frontier_verification': 'pending', 'implementation_review': 'pending'}


def store_frontier(database, frontier_raw, receipt_raw):
    metadata = frontier_metadata(frontier_raw, receipt_raw)
    encoded = canonical_bytes(metadata)
    if len(encoded) > MAX_BYTES:
        raise ValueError('Canonical frontier exceeds the 1 MiB limit')
    connection = sqlite3.connect(database, timeout=5)
    try:
        with connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS review_frontiers (
                capture_id TEXT PRIMARY KEY, metadata BLOB NOT NULL,
                frontier_raw BLOB NOT NULL, receipt_raw BLOB NOT NULL)''')
            identity = metadata['frontier']['capture']['capture_id']
            connection.execute('INSERT INTO review_frontiers VALUES (?, ?, ?, ?) ON CONFLICT(capture_id) DO NOTHING',
                               (identity, encoded, frontier_raw, receipt_raw))
            existing = connection.execute('SELECT metadata, frontier_raw, receipt_raw FROM review_frontiers WHERE capture_id = ?', (identity,)).fetchone()
            if existing != (encoded, frontier_raw, receipt_raw):
                raise ValueError('Capture ID already binds different frontier bytes')
    finally:
        connection.close()
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--frontier', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    try:
        metadata = store_frontier(args.database, read_input(args.frontier), read_input(args.receipt))
    except (OSError, ValueError, TypeError, RecursionError, sqlite3.Error) as error:
        parser.exit(2, f'Frontier storage failed: {error}\n')
    print(json.dumps(metadata, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()

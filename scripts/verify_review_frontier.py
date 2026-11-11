#!/usr/bin/env python3
"""Compare imported frontier claims with their retained tool response data."""
import argparse
import json
from decimal import Decimal
from pathlib import Path

from review_frontier_store import frontier_metadata
from review_receipt_store import read_input, require_uuid, unique_object
from sidecar_digest import reject_number


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def uuid(value):
    try:
        require_uuid(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**53 - 1


def response(obs):
    value = json.loads(obs['result_json'], object_pairs_hook=unique_object,
                       parse_float=Decimal, parse_constant=reject_number)
    require(isinstance(value, dict) and 'error' not in value, 'response_error')
    if 'result' in value:
        value = value['result']
    require(isinstance(value, dict) and 'error' not in value, 'response_error')
    return value


def check_post(post, capture, owner):
    require(post.get('kind') == 'post' and post.get('id') == capture['decision_post_id'], 'decision_identity_mismatch')
    author = post.get('author')
    require(isinstance(author, dict) and author.get('id') == capture['reviewer_agent_id'] and
            author.get('user_id') == owner, 'decision_author_mismatch')
    require(integer(post.get('revision'), 1) and post['revision'] == capture['decision_revision'], 'decision_revision_mismatch')
    require(isinstance(post.get('title'), str) and isinstance(post.get('body'), str), 'decision_text_missing')
    require('status' in post and post['status'] is None, 'decision_status_requires_review')
    require(integer(post.get('reply_count')), 'decision_reply_count_invalid')
    check_editor(post, capture['reviewer_agent_id'])


def check_editor(post, reviewer):
    require('edited_by' in post, 'editor_metadata_missing')
    editor = post['edited_by']
    require(editor is None or (isinstance(editor, dict) and editor.get('id') == reviewer), 'unexpected_editor')


def verify_frontier(frontier_raw, receipt_raw):
    # Invalid structural input raises before semantic processing. This never opens SQLite.
    metadata = frontier_metadata(frontier_raw, receipt_raw)
    value, diagnostics, refs = metadata['frontier'], [], []
    capture = value['capture']
    complete, next_cursor = False, None
    try:
        base = capture['observations']
        require(len(base) == 4, 'incomplete_identity_revision_reads')
        profile = response(base[0]).get('profile')
        require(isinstance(profile, dict) and profile.get('kind') == 'agent' and
                profile.get('id') == capture['recorder_agent_id'] and uuid(profile.get('user_id')), 'recorder_identity_mismatch')
        reviewer = response(base[1])
        require(reviewer.get('kind') == 'agent' and reviewer.get('id') == capture['reviewer_agent_id'] and
                uuid(reviewer.get('user_id')) and reviewer['user_id'] == capture['reviewer_owner_id'], 'reviewer_identity_mismatch')
        first = response(base[2])
        check_post(first, capture, reviewer['user_id'])
        pinned = response(base[3])
        require(pinned.get('post_id') == capture['decision_post_id'] and integer(pinned.get('revision'), 1) and
                pinned['revision'] == capture['decision_revision'], 'pinned_revision_mismatch')
        require(pinned.get('title') == first['title'] and pinned.get('body') == first['body'], 'pinned_text_mismatch')
        check_editor(pinned, capture['reviewer_agent_id'])
        extra = value['observations']
        searches = [obs for obs in extra if obs['tool'] == 'search_posts']
        require(bool(searches), 'frontier_reads_missing')
        seen_cursors, seen_ids = set(), set()
        for index, obs in enumerate(searches):
            require(not complete, 'search_after_completion')
            require(obs['arguments'].get('cursor') == next_cursor, 'continuation_cursor_mismatch')
            page = response(obs)
            require(isinstance(page.get('items'), list) and len(page['items']) <= 20, 'malformed_page_items')
            require('next_cursor' in page and (page['next_cursor'] is None or
                    (isinstance(page['next_cursor'], str) and 1 <= len(page['next_cursor']) <= 8000)), 'malformed_page_cursor')
            if 'partial' in page:
                require(type(page['partial']) is bool, 'malformed_partial_flag')
                require(not page['partial'] or page['next_cursor'] is not None, 'partial_without_continuation')
            for item in page['items']:
                post = item.get('post') if isinstance(item, dict) else None
                require(isinstance(post, dict) and post.get('kind') == 'post' and uuid(post.get('id')) and
                        post['id'] != capture['decision_post_id'] and post['id'] not in seen_ids and
                        integer(post.get('revision'), 1), 'invalid_or_duplicate_reply')
                author = post.get('author')
                require(isinstance(author, dict) and uuid(author.get('id')) and uuid(author.get('user_id')), 'reply_author_invalid')
                seen_ids.add(post['id'])
                refs.append({'post_id': post['id'], 'revision': post['revision'],
                             'author_agent_id': author['id'], 'author_owner_id': author['user_id']})
            next_cursor = page['next_cursor']
            complete = next_cursor is None
            require(next_cursor is None or next_cursor not in seen_cursors, 'repeated_response_cursor')
            seen_cursors.add(next_cursor)
        require(value['frontier_complete'] == complete and value['next_cursor'] == next_cursor,
                'claimed_frontier_mismatch')
        require(value['reply_refs'] == refs, 'claimed_reply_refs_mismatch')
        require(len(extra) == len(searches) + 1 and extra[-1]['tool'] == 'get_post', 'final_reread_missing')
        last = response(extra[-1])
        check_post(last, capture, reviewer['user_id'])
        for key in ('title', 'body', 'revision', 'edited_by', 'status', 'reply_count'):
            require(first[key] == last[key], 'decision_changed_during_frontier')
        require(not complete or last['reply_count'] == len(refs), 'response_reply_count_mismatch')
        if not complete:
            diagnostics.append('frontier_incomplete')
        if refs:
            diagnostics.append('replies_require_full_content_disposition')
        if value['diagnostics']:
            diagnostics.append('collector_reported_pending')
        if value['observation_state'] != 'empty_frontier_observed':
            diagnostics.append('collector_state_pending')
    except ValueError as error:
        # Diagnostics are bounded constants from checks, never fetched text.
        diagnostics.append(str(error))
    return {'schema_version': 1, 'kind': 'imported_frontier_semantic_check',
            'frontier_raw_sha256': metadata['frontier_raw_sha256'],
            'receipt_raw_sha256': metadata['receipt_raw_sha256'],
            'capture_id': capture['capture_id'], 'decision_post_id': capture['decision_post_id'],
            'decision_revision': capture['decision_revision'], 'reviewed_commit': capture['reviewed_commit'],
            'response_relationships': 'matching_imported_observations' if not diagnostics else 'pending',
            'diagnostics': diagnostics, 'derived_frontier_complete': complete,
            'derived_next_cursor': next_cursor, 'derived_reply_refs': refs,
            'authentication': 'unverified_import', 'implementation_review': 'pending',
            'source_binding': 'unchecked', 'runtime_review': 'pending'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontier', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_frontier(read_input(args.frontier), read_input(args.receipt))
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f'Frontier verification failed: {error}\n')
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()

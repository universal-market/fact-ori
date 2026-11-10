import {acquireReviewCapture} from './acquire_review_capture.mjs';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const keys = value => Object.keys(value).sort().join();

// A separate, observational envelope. Never mutate the reviewed S3 capture.
export async function acquireReviewFrontier(callRead, request) {
  if (!object(request) || keys(request) !== 'capture_request,max_pages' ||
      !Number.isSafeInteger(request.max_pages) || request.max_pages < 1 || request.max_pages > 10 ||
      !object(request.capture_request)) throw new Error('Expected capture request and 1–10 page budget');
  // Copy primitive request inputs before yielding to the host adapter.
  const captureRequest = {...request.capture_request};
  const maxPages = request.max_pages;
  const base = await acquireReviewCapture(callRead, captureRequest);
  const envelope = {schema_version: 1, capture: base.capture,
    started_at: base.capture.recorded_at, finished_at: null,
    observations: [], reply_refs: [], pages_read: 0, next_cursor: null,
    frontier_complete: false, diagnostics: [...base.diagnostics],
    observation_state: 'pending', receipt_authentication: 'unverified_import',
    implementation_review: 'pending'};
  const finish = () => {
    envelope.finished_at = new Date().toISOString();
    if (envelope.frontier_complete && !envelope.diagnostics.length)
      envelope.observation_state = 'empty_frontier_observed';
    return envelope;
  };
  if (base.acquisition_state !== 'identity_revision_observed') return finish();

  async function read(tool, args) {
    let response;
    try { response = await callRead(tool, args); }
    catch { response = {result_json: '{"error":"TRANSPORT_READ_FAILED"}', is_error: true}; }
    if (typeof response?.result_json !== 'string' || response.result_json.length > 262144)
      response = {result_json: '{"error":"INVALID_OR_OVERSIZE_RESPONSE"}', is_error: true};
    envelope.observations.push({tool, arguments: args, result_json: response.result_json,
      observed_at: new Date().toISOString()});
    let value;
    try { value = JSON.parse(response.result_json); }
    catch { envelope.diagnostics.push(`malformed_response:${tool}`); return null; }
    if (response.is_error || !object(value) || value.error) {
      envelope.diagnostics.push(`read_failed:${tool}`); return null;
    }
    value = Object.hasOwn(value, 'result') ? value.result : value;
    if (!object(value) || value.error) {
      envelope.diagnostics.push(`read_failed:${tool}`); return null;
    }
    return value;
  }

  const cursors = new Set();
  const ids = new Set();
  for (let index = 0; index < maxPages; index++) {
    const args = {root_post_id: captureRequest.decision_post_id, max_depth: null,
      sort: 'created_at', limit: 20};
    if (envelope.next_cursor !== null) args.cursor = envelope.next_cursor;
    const page = await read('search_posts', args);
    envelope.pages_read++;
    if (!page) return finish();
    if (!Array.isArray(page.items) || page.items.length > 20 ||
        !(page.next_cursor === null || (typeof page.next_cursor === 'string' &&
          page.next_cursor.length > 0 && page.next_cursor.length <= 8000))) {
      envelope.diagnostics.push('malformed_frontier_page'); return finish();
    }
    for (const item of page.items) {
      const post = item?.post;
      if (!object(post) || typeof post.id !== 'string' || !UUID.test(post.id) ||
          post.id === captureRequest.decision_post_id || !Number.isSafeInteger(post.revision) ||
          post.revision < 1 || !object(post.author) || typeof post.author.id !== 'string' ||
          !UUID.test(post.author.id) || typeof post.author.user_id !== 'string' ||
          !UUID.test(post.author.user_id) || ids.has(post.id)) {
        envelope.diagnostics.push('malformed_or_duplicate_reply'); return finish();
      }
      ids.add(post.id);
      envelope.reply_refs.push({post_id: post.id, revision: post.revision,
        author_agent_id: post.author.id, author_owner_id: post.author.user_id});
    }
    envelope.next_cursor = page.next_cursor;
    if (page.next_cursor === null) { envelope.frontier_complete = true; break; }
    if (cursors.has(page.next_cursor)) {
      envelope.diagnostics.push('repeated_frontier_cursor'); return finish();
    }
    cursors.add(page.next_cursor);
  }
  if (!envelope.frontier_complete) envelope.diagnostics.push('frontier_page_budget_exhausted');
  // Summaries are discovery data. Every reply, including third-party objections,
  // requires a full-content review by a separate decision actor. No text parsing.
  if (envelope.reply_refs.length) envelope.diagnostics.push('replies_require_full_review');
  const current = await read('get_post', {post_id: captureRequest.decision_post_id});
  if (!current) return finish();
  const firstObservation = base.capture.observations.find(o => o.tool === 'get_post');
  const firstRaw = JSON.parse(firstObservation.result_json);
  const first = firstRaw.result ?? firstRaw;
  if (current.id !== captureRequest.decision_post_id || current.kind !== 'post' ||
      current.revision !== captureRequest.decision_revision ||
      current.author?.id !== captureRequest.reviewer_agent_id ||
      current.author?.user_id !== base.capture.reviewer_owner_id ||
      current.title !== first.title || current.body !== first.body ||
      current.status !== first.status ||
      JSON.stringify(current.edited_by ?? null) !== JSON.stringify(first.edited_by ?? null))
    envelope.diagnostics.push('decision_changed_during_frontier');
  if (first.status !== null || current.status !== null)
    envelope.diagnostics.push('decision_status_requires_review');
  if (!Number.isSafeInteger(first.reply_count) || first.reply_count < 0 ||
      !Number.isSafeInteger(current.reply_count) || current.reply_count < 0 ||
      first.reply_count !== current.reply_count ||
      (envelope.frontier_complete && current.reply_count !== envelope.reply_refs.length))
    envelope.diagnostics.push('reply_count_changed_or_inconsistent');
  return finish();
}

// Explicit caller policy, no default production freshness SLA or authority grant.
export function frontierFreshness(envelope, nowMs, maxAgeMs) {
  if (!Number.isSafeInteger(nowMs) || !Number.isSafeInteger(maxAgeMs) || maxAgeMs < 0)
    throw new Error('Expected integer evaluation time and nonnegative maximum age');
  const times = [envelope?.started_at, envelope?.finished_at,
    ...(envelope?.capture?.observations ?? []).map(o => o.observed_at),
    ...(envelope?.observations ?? []).map(o => o.observed_at)];
  const parsed = times.map(t => typeof t === 'string' ? Date.parse(t) : NaN);
  const valid = parsed.length >= 2 && parsed.every(Number.isSafeInteger) &&
    parsed.every(t => t <= nowMs && nowMs - t <= maxAgeMs) &&
    parsed.every(t => t >= parsed[0] && t <= parsed[1]);
  return {freshness: valid ? 'within_caller_age_bound' : 'pending',
    evaluated_at_ms: nowMs, max_age_ms: maxAgeMs,
    receipt_authentication: 'unverified_import', implementation_review: 'pending'};
}

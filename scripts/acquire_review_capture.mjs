const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const REQUEST_FIELDS = ["capture_id", "recorder_agent_id", "reviewer_agent_id",
  "decision_post_id", "decision_revision", "reviewed_commit", "receipt_raw_sha256"];

// The maintainer host supplies its existing authenticated ordinary-content adapter.
export async function acquireReviewCapture(callRead, request) {
  if (typeof callRead !== "function" || !request ||
      Object.keys(request).sort().join() !== [...REQUEST_FIELDS].sort().join()) {
    throw new Error("Expected read adapter and exact acquisition request fields");
  }
  for (const key of ["capture_id", "recorder_agent_id", "reviewer_agent_id", "decision_post_id"]) {
    if (typeof request[key] !== "string" || !UUID.test(request[key])) {
      throw new Error("Expected canonical UUID request fields");
    }
  }
  if (!Number.isSafeInteger(request.decision_revision) || request.decision_revision < 1 ||
      typeof request.reviewed_commit !== "string" || typeof request.receipt_raw_sha256 !== "string" ||
      !/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(request.reviewed_commit) ||
      !/^[0-9a-f]{64}$/.test(request.receipt_raw_sha256)) {
    throw new Error("Expected exact revision, commit and receipt digest");
  }
  const capture = {schema_version: 1, ...request, recorded_at: new Date().toISOString(),
    reviewer_owner_id: null, observations: []};
  const diagnostics = [];
  let recorderOwner = null;
  const result = () => ({capture, diagnostics,
    acquisition_state: diagnostics.length ? "pending" : "identity_revision_observed",
    recorder_owner_id_observed: recorderOwner,
    receipt_authentication: "unverified_import", implementation_review: "pending"});

  async function read(tool, args) {
    let response;
    try {
      response = await callRead(tool, args);
    } catch {
      // Transport exceptions may contain private connection details.
      response = {result_json: '{"error":"TRANSPORT_READ_FAILED"}', is_error: true};
    }
    if (typeof response?.result_json !== "string" || response.result_json.length > 262144) {
      response = {result_json: '{"error":"INVALID_OR_OVERSIZE_RESPONSE"}', is_error: true};
    }
    capture.observations.push({tool, arguments: args, result_json: response.result_json,
      observed_at: new Date().toISOString()});
    let value;
    try {
      value = JSON.parse(response.result_json);
    } catch {
      diagnostics.push(`malformed_response:${tool}`);
      return null;
    }
    if (response.is_error || !value || typeof value !== "object" || Array.isArray(value) || value.error) {
      diagnostics.push(`read_failed:${tool}`);
      return null;
    }
    return value.result && typeof value.result === "object" ? value.result : value;
  }

  const identity = await read("get_my_profile", {});
  if (!identity) return result();
  const profile = identity.profile;
  if (profile?.kind !== "agent" || profile.id !== request.recorder_agent_id ||
      typeof profile.user_id !== "string" || !UUID.test(profile.user_id)) {
    diagnostics.push("recorder_identity_mismatch");
    return result();
  }
  recorderOwner = profile.user_id;
  const reviewer = await read("get_agent", {agent_id: request.reviewer_agent_id});
  if (!reviewer) return result();
  if (reviewer.kind !== "agent" || reviewer.id !== request.reviewer_agent_id ||
      typeof reviewer.user_id !== "string" || !UUID.test(reviewer.user_id)) {
    diagnostics.push("reviewer_identity_mismatch");
    return result();
  }
  capture.reviewer_owner_id = reviewer.user_id;
  const current = await read("get_post", {post_id: request.decision_post_id});
  if (!current) return result();
  if (current.kind !== "post" || current.id !== request.decision_post_id || current.author?.id !== reviewer.id ||
      current.author?.user_id !== reviewer.user_id) {
    diagnostics.push("decision_author_mismatch");
    return result();
  }
  if (current.revision !== request.decision_revision) diagnostics.push("decision_revision_changed");
  if (current.edited_by && current.edited_by.id !== reviewer.id) diagnostics.push("unexpected_editor");
  const pinned = await read("get_post_revision", {
    post_id: request.decision_post_id, revision: request.decision_revision});
  if (!pinned) return result();
  if (pinned.post_id !== request.decision_post_id || pinned.revision !== request.decision_revision ||
      typeof pinned.body !== "string" || typeof pinned.title !== "string") {
    diagnostics.push("pinned_revision_mismatch");
  }
  if (pinned.edited_by && pinned.edited_by.id !== reviewer.id) diagnostics.push("unexpected_revision_editor");
  if (current.revision === request.decision_revision &&
      (current.body !== pinned.body || current.title !== pinned.title)) diagnostics.push("revision_text_mismatch");
  return result();
}

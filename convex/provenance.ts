/** Missing runtime bindings are disclosed independently of evidence approval. */
export function withImplementationProvenance(value: Record<string, unknown>) {
  return {
    ...value,
    // Keep this compatibility field pending until a separately reviewed runtime
    // build/receipt verifier exists. Neither a DB row nor caller text can set it.
    implementation_review: "pending",
    implementation_provenance: {
      schema_version: 1,
      binding_state: "unconfigured",
      source: null,
      build: null,
      review_receipts: [],
      historical_receipts_loaded: false,
      reason: "Runtime source/build identity and authenticated review receipts are not configured.",
    },
  };
}

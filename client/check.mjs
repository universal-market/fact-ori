/** Public, credential-free client. Analysis progress is distinct from research progress. */
export async function checkText(
  origin,
  text,
  {
    publicReview = false,
    requestKey,
    deadlineMs = 600000,
    intervalMs = 1000,
    onProgress = () => {},
    fetchImpl = fetch,
  } = {},
) {
  const base = new URL(origin);
  if (
    base.username ||
    base.password ||
    base.pathname !== "/" ||
    base.search ||
    base.hash ||
    !(
      base.protocol === "https:" ||
      (base.protocol === "http:" &&
        ["localhost", "127.0.0.1", "[::1]"].includes(base.hostname))
    )
  ) {
    throw new Error(
      "Supply an HTTPS origin or loopback HTTP origin without credentials or paths",
    );
  }
  const started = Date.now();
  async function request(path, init) {
    const response = await fetchImpl(new URL(path, base), {
      ...init,
      redirect: "error",
      signal: AbortSignal.timeout(30000),
    });
    const body = await response.json();
    if (!response.ok)
      throw new Error(
        `Fact-ori HTTP ${response.status}: ${body.error ?? body.reason ?? body.status ?? "request failed"}`,
      );
    return { response, body };
  }
  let { response, body } = await request("/v1/check", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(requestKey ? { "Idempotency-Key": requestKey } : {}),
    },
    body: JSON.stringify({ text, public_review: publicReview, async: true }),
  });
  if (response.status !== 202) return body;
  const path = body.poll_url;
  if (typeof path !== "string" || !/^\/v1\/checks\/[a-f0-9-]{36}$/.test(path))
    throw new Error("Invalid analysis status path");
  while (Date.now() - started < deadlineMs) {
    onProgress(body);
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    ({ body } = await request(path));
    if (body.status === "failed")
      throw new Error(body.error ?? "Analysis failed");
    if (body.status === "complete")
      return { ...body.result, analysis_id: body.id };
  }
  return { ...body, deadline_reached: true, poll_url: path };
}

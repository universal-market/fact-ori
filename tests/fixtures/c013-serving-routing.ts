import { v, type Infer } from "convex/values";

export const generationIdentity = v.object({
  importId: v.string(),
  policyId: v.string(),
  engineId: v.string(),
  indexId: v.string(),
});
export type GenerationIdentity = Infer<typeof generationIdentity>;
export type ServingGeneration = GenerationIdentity & { epoch: number };

export function matchesGeneration(left: GenerationIdentity, right: GenerationIdentity) {
  return left.importId === right.importId && left.policyId === right.policyId &&
    left.engineId === right.engineId && left.indexId === right.indexId;
}

export const protectedLiteral = "Synthetic protected literal?";
export const mappedLiteral = "Synthetic mapped literal?";

export function exactRoute(text: string, preview = false) {
  if (preview) return "preview";
  if (text === protectedLiteral) return "withheld";
  if (text === mappedLiteral) return "mapped";
  return "unmapped";
}

type Effect = { position: number; text: string };
export type RouteProof = {
  originalText: string;
  analysisId: string;
  effect: Effect;
  generation: ServingGeneration;
  route: ReturnType<typeof exactRoute>;
};

type AdmissionRequest = {
  scope: string;
  key: string;
  expectedEpoch: number;
  generation: GenerationIdentity;
  originalText: string;
  effectText: string;
  publicReview?: boolean;
};

type Dependencies<T> = {
  readGeneration: () => Promise<ServingGeneration | null>;
  extract: (text: string) => Effect[];
  classify: (request: Omit<RouteProof, "route">) => RouteProof;
  admit: (request: AdmissionRequest) => Promise<T>;
};

function readPublicInput(input: unknown) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  if (Object.keys(input).some((key) => key !== "text" && key !== "public_review")) {
    return null;
  }
  const { text, public_review: consent } = input as Record<string, unknown>;
  if (typeof text !== "string" || !text.trim() || text.length > 4000 ||
      (Object.hasOwn(input, "public_review") &&
      typeof consent !== "boolean")) return null;
  return { text, ...(typeof consent === "boolean" ? { publicReview: consent } : {}) };
}

// The caller supplies server-owned state and synthetic model stubs in-process.
export async function routeFixtureRequest<T>(
  input: unknown,
  context: { scope: string; analysisId: string; preview: boolean },
  deps: Dependencies<T>,
) {
  const request = readPublicInput(input);
  if (!request) return { status: "invalid" } as const;

  const whole = exactRoute(request.text, context.preview);
  if (whole !== "unmapped") return { status: whole };
  const generation = await deps.readGeneration();
  if (!generation) return { status: "unavailable" } as const;

  const effects = deps.extract(request.text);
  const positions = new Set<number>();
  const eligible: Effect[] = [];
  for (const effect of effects) {
    if (!Number.isSafeInteger(effect.position) || effect.position < 0 ||
        positions.has(effect.position)) return { status: "unavailable" } as const;
    positions.add(effect.position);
    if (exactRoute(effect.text) !== "unmapped") continue;

    const proof = deps.classify({
      originalText: request.text, analysisId: context.analysisId,
      effect: { ...effect }, generation: { ...generation },
    });
    if (proof.originalText !== request.text || proof.analysisId !== context.analysisId ||
        proof.effect.position !== effect.position || proof.effect.text !== effect.text ||
        proof.generation.epoch !== generation.epoch ||
        !matchesGeneration(proof.generation, generation) || proof.route !== "unmapped") {
      return { status: "unavailable" } as const;
    }
    eligible.push(effect);
  }

  const { epoch, ...identity } = generation;
  const results: T[] = [];
  for (const effect of eligible) {
    results.push(await deps.admit({
      scope: context.scope, key: JSON.stringify([context.analysisId, effect.position]),
      expectedEpoch: epoch, generation: identity, originalText: request.text,
      effectText: effect.text, ...(Object.hasOwn(request, "publicReview")
        ? { publicReview: request.publicReview } : {}),
    }));
  }
  return { status: "checked", results } as const;
}

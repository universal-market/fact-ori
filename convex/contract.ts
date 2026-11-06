export function normalize(text: string): string {
  return text.trim().toLowerCase().replace(/\s+/g, " ").replace(/\?+$/, "").trim();
}

export function validateText(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.length > 4000) {
    throw new Error("text must contain 1–4000 characters");
  }
  return value;
}

export function isDigest(value: string): boolean {
  return /^[a-f0-9]{64}$/.test(value);
}

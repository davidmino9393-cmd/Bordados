const BYTES_PER_KB = 1024;
const BYTES_PER_MB = BYTES_PER_KB * 1024;
const MS_PER_SECOND = 1000;
const SHORT_HASH_LENGTH = 8;

export function formatBytes(bytes: number): string {
  if (bytes >= BYTES_PER_MB) return `${(bytes / BYTES_PER_MB).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / BYTES_PER_KB))} KB`;
}

export function formatMegabytes(bytes: number): string {
  return String(Math.round(bytes / BYTES_PER_MB));
}

export function formatSeconds(ms: number): string {
  return (ms / MS_PER_SECOND).toFixed(1).replace('.', ',');
}

export function formatMm(value: number): string {
  return value.toFixed(1).replace('.', ',');
}

export function shortHash(sha: string): string {
  return sha.slice(0, SHORT_HASH_LENGTH);
}

// BORRADOR v0.1 — aprobación física (sección 6). Independiente de ready_for_sewout.

export const SewoutStatus = {
  Untested: 'untested',
  Approved: 'approved',
  NeedsAdjustment: 'needs_adjustment',
} as const;
export type SewoutStatus = (typeof SewoutStatus)[keyof typeof SewoutStatus];

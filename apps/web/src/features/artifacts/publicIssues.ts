import type { Issue } from '../../contracts/validation';

const internal = new Set(['SATIN_RAILS_UNVERIFIED', 'ENGINE_DIAGNOSTIC_UNCLASSIFIED', 'SATIN_RUNG_WARNING', 'SATIN_PAIRED_NODES_VERIFIED']);

export function publicIssues(issues: Issue[]) {
  const seen = new Set<string>();
  return issues.filter((issue) => {
    if (internal.has(issue.code) || seen.has(issue.code)) return false;
    seen.add(issue.code);
    return true;
  });
}

import type { Issue } from '../../contracts/validation';
import { es, issueTitle, severityLabel } from '../../copy/es';
import { Card } from '../../shared/components/Card';

/** Los avisos nunca se ocultan: cada uno indica severidad y objetos afectados. */
export function IssuesList({ issues }: { issues: Issue[] }) {
  return (
    <Card>
      <Card.Header>{es.result.issuesTitle}</Card.Header>
      <Card.Body>
        {issues.length === 0 ? (
          <p>{es.result.noIssues}</p>
        ) : (
          issues.map((issue, index) => (
            <div key={`${issue.code}-${index}`} className="issue">
              <strong>{severityLabel[issue.severity]}: {issueTitle(issue.code, issue.description)}</strong>
              <span className="field__hint">
                {es.review.objects}: {[...issue.object_ids, ...issue.region_ids].join(', ') || '—'}
              </span>
            </div>
          ))
        )}
      </Card.Body>
    </Card>
  );
}

import type { ValidationIssue } from '../../contracts/validation';
import { es, severityLabel } from '../../copy/es';
import { Card } from '../../shared/components/Card';

/** Los avisos nunca se ocultan: cada uno indica severidad y objetos afectados. */
export function IssuesList({ issues }: { issues: ValidationIssue[] }) {
  return (
    <Card>
      <Card.Header>{es.result.issuesTitle}</Card.Header>
      <Card.Body>
        {issues.length === 0 ? (
          <p>{es.result.noIssues}</p>
        ) : (
          issues.map((issue) => (
            <div key={`${issue.code}-${issue.object_ids.join()}`} className="issue">
              <strong>{severityLabel[issue.severity]}</strong>
              <span>{issue.description}</span>
              <span className="field__hint">
                {es.review.objects}: {issue.object_ids.join(', ') || '—'}
              </span>
            </div>
          ))
        )}
      </Card.Body>
    </Card>
  );
}

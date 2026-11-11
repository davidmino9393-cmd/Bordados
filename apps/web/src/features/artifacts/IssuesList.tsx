import { publicIssues } from './publicIssues';
import type { Issue } from '../../contracts/validation';
import { es, issueTitle, severityLabel } from '../../copy/es';
import { Card } from '../../shared/components/Card';

/** El informe de validación conserva los diagnósticos completos. */
export function IssuesList({ issues }: { issues: Issue[] }) {
  const visible = publicIssues(issues);
  return (
    <Card>
      <Card.Header>{es.result.issuesTitle}</Card.Header>
      <Card.Body>
        {issues.length === 0 ? (
          <p>{es.result.noIssues}</p>
        ) : (
          visible.length === 0 ? <p>Revisá el diseño en la vista de puntadas.</p> : visible.map((issue, index) => (
            <div key={`${issue.code}-${index}`} className="issue">
              <strong>{severityLabel[issue.severity]}: {issueTitle(issue.code, 'Revisá el resultado')}</strong>
            </div>
          ))
        )}
      </Card.Body>
    </Card>
  );
}

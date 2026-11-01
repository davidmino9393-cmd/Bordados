import type { ReadbackMetrics } from '../../contracts/artifacts';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { formatMm } from '../../shared/utils/format';

export function MetricsPanel({ metrics }: { metrics: ReadbackMetrics }) {
  const m = es.metrics;
  const rows: [string, string][] = [
    [m.size, `${formatMm(metrics.width_mm)} × ${formatMm(metrics.height_mm)} mm`],
    [m.stitches, metrics.needle_stitches.toLocaleString('es-AR')],
    [m.blocks, String(metrics.thread_blocks)],
    [m.colorChanges, String(metrics.color_changes)],
    [m.jumps, String(metrics.jumps)],
    [m.trims, String(metrics.trims)],
  ];
  return (
    <Card>
      <Card.Header>{es.result.metricsTitle}</Card.Header>
      <Card.Body>
        <dl className="metrics">
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <p className="field__hint">
          {es.result.metricsNote} {m.method}: {metrics.counting_method}.
        </p>
      </Card.Body>
    </Card>
  );
}

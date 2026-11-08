import type { RereadMetrics } from '../../contracts/artifacts';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { formatMm } from '../../shared/utils/format';

export function MetricsPanel({ metrics }: { metrics: RereadMetrics }) {
  const m = es.metrics;
  const { stitch_bounds_mm: b } = metrics;
  const rows: [string, string][] = [
    [m.size, `${formatMm(b.max_x_mm - b.min_x_mm)} × ${formatMm(b.max_y_mm - b.min_y_mm)} mm`],
    [m.stitches, metrics.needle_stitches.toLocaleString('es-AR')],
    [m.colorChanges, String(metrics.color_changes)],
    [m.displacementJumps, String(metrics.displacement_jump_commands)],
    [m.trims, String(metrics.interpreted_trims)],
    [m.maxStitch, `${formatMm(metrics.max_stitch_length_mm)} mm`],
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
          {es.result.metricsNote} {m.method}: {metrics.count_method}.
        </p>
        {!metrics.physical_trim_execution_verified && <p className="field__hint">{es.result.trimsNote}</p>}
      </Card.Body>
    </Card>
  );
}

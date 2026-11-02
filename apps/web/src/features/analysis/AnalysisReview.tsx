import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import type { AnalysisDecision } from '../../contracts/analysis';
import type { JobResponse } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import { AiProvider } from '../../contracts/settings';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage, useAsync } from '../../shared/hooks/useAsync';
import { useIdempotencyKey } from '../../shared/hooks/useIdempotencyKey';
import { formatSeconds } from '../../shared/utils/format';
import { AnalysisOverlay, canvasSize } from './AnalysisOverlay';
import { RegionList } from './RegionList';

const PROVIDER_LABEL: Record<string, string> = {
  [AiProvider.OpenAI]: 'OpenAI (nube)',
  [AiProvider.Ollama]: 'Modelo local (Ollama)',
};

interface AnalysisReviewProps {
  job: JobResponse;
  asset: SourceAsset | undefined;
}

/**
 * H2 — el análisis visual de una imagen terminó con dudas (needs_review). Muestra lo que detectó la
 * IA (cajas ESTIMADAS, no verificadas) y deja aprobar, marcar regiones para revisión manual o
 * regenerar con otro proveedor. Ambas decisiones crean un trabajo nuevo; este no se modifica.
 * Usa operaciones propuestas (getAnalysis / decideAnalysis) que todavía no existen en OpenAPI v0.1.
 */
export function AnalysisReview({ job, asset }: AnalysisReviewProps) {
  const api = useApi();
  const navigate = useNavigate();
  const keyFor = useIdempotencyKey();
  const analysis = useAsync(() => api.getAnalysis(job.job_id), [api, job.job_id]);
  const catalog = useAsync(() => api.getProfiles(), [api]);
  const [flagged, setFlagged] = useState<ReadonlySet<string>>(new Set());
  const [nextProvider, setNextProvider] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const uncertainIds = new Set(job.review?.region_ids ?? []);
  const others = (catalog.data?.providers ?? []).filter(
    (p) => p.available && p.provider_id !== job.settings_snapshot.ai_provider,
  );
  const providerToTry = nextProvider || others[0]?.provider_id || '';

  const toggle = (regionId: string) =>
    setFlagged((current) => {
      const next = new Set(current);
      if (!next.delete(regionId)) next.add(regionId);
      return next;
    });

  const decide = async (decision: AnalysisDecision) => {
    setBusy(true);
    setError(undefined);
    try {
      const next = await api.decideAnalysis(job.job_id, decision, keyFor({ job: job.job_id, decision }));
      navigate(`/trabajos/${next.job_id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  const text = es.analysis;
  const data = analysis.data;
  return (
    <Card>
      <Card.Header>{text.title}</Card.Header>
      <Card.Body>
        <Notice tone={NoticeTone.Warning} title={text.attentionTitle(uncertainIds.size)}>
          <p>{text.estimated}</p>
        </Notice>
        {analysis.error && <Notice tone={NoticeTone.Error}>{analysis.error}</Notice>}
        {analysis.loading && !data && <p role="status">{es.loading}</p>}
        {data && (
          <>
            <p className="field__hint">
              {text.analyzedWith(PROVIDER_LABEL[data.provider] ?? data.provider, data.model, formatSeconds(data.duration_ms))}
            </p>
            <AnalysisOverlay
              imageUrl={asset?.original_download?.url}
              imageAlt={text.originalAlt}
              size={canvasSize({ width: asset?.original_width_px ?? null, height: asset?.original_height_px ?? null }, data.regions)}
              regions={data.regions}
              uncertainIds={uncertainIds}
              flaggedIds={flagged}
            />
            <RegionList regions={data.regions} uncertainIds={uncertainIds} flaggedIds={flagged} onToggle={toggle} />
            <p role="status">{text.flaggedCount(flagged.size)}</p>
          </>
        )}
        {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
        <div className="row">
          <button
            type="button"
            disabled={busy || !data}
            onClick={() => decide({ action: 'approve', flagged_region_ids: [...flagged].sort() })}
          >
            {text.approve}
          </button>
        </div>
        <div className="form-grid">
          <Field label={text.otherProvider} hint={others.length === 0 ? text.noOtherProvider : undefined}>
            <select value={providerToTry} onChange={(e) => setNextProvider(e.target.value)} disabled={others.length === 0}>
              {others.map((p) => (
                <option key={p.provider_id} value={p.provider_id}>{PROVIDER_LABEL[p.provider_id] ?? p.provider_id}</option>
              ))}
            </select>
          </Field>
          <div className="row">
            <button
              type="button"
              className="secondary"
              disabled={busy || others.length === 0}
              onClick={() => decide({ action: 'change_provider', ai_provider: providerToTry as 'openai' | 'ollama' })}
            >
              {text.regenerate}
            </button>
          </div>
        </div>
      </Card.Body>
    </Card>
  );
}

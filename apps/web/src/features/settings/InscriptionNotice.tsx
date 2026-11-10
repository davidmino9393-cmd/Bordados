import { useEffect, useState, type KeyboardEvent } from 'react';
import { useApi } from '../../api/ApiProvider';
import { InscriptionLayout, type Inscription, type InscriptionReport } from '../../contracts/inscriptions';
import { es } from '../../copy/es';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { formatMm } from '../../shared/utils/format';

const DEBOUNCE_MS = 600;
const PERCENT = 100;

const SaveStatus = { Idle: 'idle', Saving: 'saving', Saved: 'saved', Failed: 'failed' } as const;
type SaveStatus = (typeof SaveStatus)[keyof typeof SaveStatus];

type State = { phase: 'loading' } | { phase: 'ready'; report: InscriptionReport } | { phase: 'failed' };

interface InscriptionNoticeProps {
  projectId: string;
  assetId: string;
  widthMm: number;
  heightMm: number;
}

/** Lee las inscripciones al tamaño pedido. La lectura de la imagen la guarda el servidor: cambiar el tamaño no la repite. */
function useInscriptions({ projectId, assetId, widthMm, heightMm }: InscriptionNoticeProps) {
  const api = useApi();
  const [state, setState] = useState<State>({ phase: 'loading' });
  useEffect(() => {
    if (!(widthMm > 0 && heightMm > 0)) return;
    let current = true;
    const timer = setTimeout(() => {
      api
        .getInscriptions(projectId, assetId, { width_mm: widthMm, height_mm: heightMm })
        .then((report) => current && setState({ phase: 'ready', report }))
        .catch(() => current && setState({ phase: 'failed' }));
    }, DEBOUNCE_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [api, projectId, assetId, widthMm, heightMm]);
  return [state, (report: InscriptionReport) => setState({ phase: 'ready', report })] as const;
}

interface InscriptionFieldProps {
  inscription: Inscription;
  value: string;
  smallBelowMm: number;
  useFont: boolean;
  onChange: (value: string) => void;
  onUseFont: (value: boolean) => void;
  onEnter: () => void;
}

function InscriptionField({ inscription, value, smallBelowMm, useFont, onChange, onUseFont, onEnter }: InscriptionFieldProps) {
  const text = es.inscriptions;
  const mm = inscription.letter_height_mm === null ? null : formatMm(inscription.letter_height_mm);
  const confidence = text.confidence(Math.round(inscription.confidence * PERCENT));
  const hint = inscription.small ? `${text.small(formatMm(smallBelowMm))} ${confidence}` : confidence;
  // Enter dentro del formulario de ajustes lo enviaría (y generaría el bordado): acá confirma las frases.
  const handleKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    onEnter();
  };
  const curved = inscription.layout === InscriptionLayout.Curved;
  return (
    <>
      <Field label={text.fieldLabel(curved, mm)} hint={hint}>
        <input type="text" value={value} maxLength={200} onChange={(e) => onChange(e.target.value)} onKeyDown={handleKey} />
      </Field>
      {curved && (
        <>
          <label className="radio">
            <input type="checkbox" checked={useFont} onChange={(e) => onUseFont(e.target.checked)} /> {text.useFont}
          </label>
          <p className="field__hint">{text.useFontHint}</p>
        </>
      )}
    </>
  );
}

/**
 * Guía 1.3: muestra el texto que el servidor leyó en la imagen (recto y en curva) para que la persona confirme o corrija la frase.
 * Nunca bloquea el envío: si la lectura falla o el servidor no tiene el lector, se dice y se sigue.
 */
export function InscriptionNotice(props: InscriptionNoticeProps) {
  const api = useApi();
  const [state, setReport] = useInscriptions(props);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [fonts, setFonts] = useState<Record<string, boolean>>({});
  const [save, setSave] = useState<SaveStatus>(SaveStatus.Idle);
  const text = es.inscriptions;

  if (!(props.widthMm > 0 && props.heightMm > 0)) return null;
  if (state.phase === 'loading') return <p className="field__hint" role="status">{text.searching}</p>;
  if (state.phase === 'failed') return <Notice tone={NoticeTone.Info}>{text.failed}</Notice>;
  const { report } = state;
  if (!report.available) return <p className="field__hint">{text.unavailable}</p>;
  if (report.inscriptions.length === 0) return null;

  const valueOf = (item: Inscription) => drafts[item.inscription_id] ?? item.confirmed_text ?? item.text;
  const fontOf = (item: Inscription) => fonts[item.inscription_id] ?? item.use_font;
  // Una sola frase por arco del sello se borda con letras: el lector puede leer dos veces la misma frase.
  const chooseFont = (chosen: Inscription, value: boolean) => {
    const sameArc = (item: Inscription) => item.inscription_id !== chosen.inscription_id && item.arc === chosen.arc;
    setFonts(Object.fromEntries(report.inscriptions.map((item) => [
      item.inscription_id,
      item.inscription_id === chosen.inscription_id ? value : value && sameArc(item) ? false : fontOf(item),
    ])));
    setSave(SaveStatus.Idle);
  };
  const confirm = () => {
    const confirmed = report.inscriptions
      .map((item) => ({ inscription_id: item.inscription_id, text: valueOf(item).trim(), use_font: fontOf(item) }))
      .filter((item) => item.text !== '');
    setSave(SaveStatus.Saving);
    api
      .confirmInscriptions(props.projectId, props.assetId, confirmed, { width_mm: props.widthMm, height_mm: props.heightMm })
      .then((saved) => {
        setReport(saved);
        setSave(SaveStatus.Saved);
      })
      .catch(() => setSave(SaveStatus.Failed));
  };
  const anySmall = report.inscriptions.some((item) => item.small);
  return (
    <Notice tone={anySmall ? NoticeTone.Warning : NoticeTone.Info} title={text.title}>
      <p>{text.intro}</p>
      {report.inscriptions.map((item) => (
        <InscriptionField
          key={item.inscription_id}
          inscription={item}
          value={valueOf(item)}
          smallBelowMm={report.small_below_mm}
          useFont={fontOf(item)}
          onUseFont={(value) => chooseFont(item, value)}
          onChange={(value) => {
            setDrafts((current) => ({ ...current, [item.inscription_id]: value }));
            setSave(SaveStatus.Idle);
          }}
          onEnter={confirm}
        />
      ))}
      <button type="button" onClick={confirm} disabled={save === SaveStatus.Saving}>
        {save === SaveStatus.Saving ? text.saving : text.confirm}
      </button>
      {save === SaveStatus.Saved && <p role="status">{text.saved}</p>}
      {save === SaveStatus.Failed && <p role="alert">{text.saveFailed}</p>}
    </Notice>
  );
}

import { useState, type FormEvent } from 'react';
import type { SourceAsset } from '../../contracts/project';
import { AiProvider, type JobSettings, type ProfileCatalog } from '../../contracts/settings';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { estimateContain } from '../../shared/utils/fit';
import { formatMm } from '../../shared/utils/format';
import { ProviderPicker } from './ProviderPicker';
import {
  parseMm,
  toJobSettings,
  validateSettings,
  type SettingsErrors,
  type SettingsFormValues,
} from './validateSettings';

const DEFAULT_WIDTH_MM = '130';
const DEFAULT_HEIGHT_MM = '120';
const DEFAULT_COLORS = '3';

interface SettingsFormProps {
  catalog: ProfileCatalog;
  asset: SourceAsset | undefined;
  busy: boolean;
  onSubmit: (settings: JobSettings) => void;
}

function initialValues(catalog: ProfileCatalog): SettingsFormValues {
  const machine = catalog.machines[0];
  return {
    width_mm: DEFAULT_WIDTH_MM,
    height_mm: DEFAULT_HEIGHT_MM,
    machine_profile: machine.id,
    hoop_profile: machine.hoops[0].id,
    fabric_profile: catalog.fabrics[0].id,
    color_limit: DEFAULT_COLORS,
    ai_provider: catalog.providers.find((p) => p.available)?.id ?? AiProvider.OpenAI,
  };
}

export function SettingsForm({ catalog, asset, busy, onSubmit }: SettingsFormProps) {
  const [values, setValues] = useState(() => initialValues(catalog));
  const [errors, setErrors] = useState<SettingsErrors>({});
  const machine = catalog.machines.find((m) => m.id === values.machine_profile) ?? catalog.machines[0];
  const hoop = machine.hoops.find((h) => h.id === values.hoop_profile);
  const set = <K extends keyof SettingsFormValues>(key: K, value: SettingsFormValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  const width = parseMm(values.width_mm);
  const height = parseMm(values.height_mm);
  const estimate = asset
    ? estimateContain(asset.width_px, asset.height_px, { width_mm: width, height_mm: height })
    : null;
  const outsideHoop = hoop && width > 0 && height > 0 && (width > hoop.width_mm || height > hoop.height_mm);

  const changeMachine = (id: string) => {
    const next = catalog.machines.find((m) => m.id === id) ?? machine;
    setValues((v) => ({ ...v, machine_profile: id, hoop_profile: next.hoops[0].id }));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = validateSettings(values, machine);
    setErrors(found);
    if (Object.keys(found).length === 0 && asset) onSubmit(toJobSettings(values));
  };

  const text = es.settings;
  return (
    <Card>
      <Card.Header>{text.title}</Card.Header>
      <Card.Body>
        <form onSubmit={submit} noValidate className="card__body">
          <div className="form-grid">
            <Field label={text.width} error={errors.width_mm && text.positive}>
              <input type="text" inputMode="decimal" value={values.width_mm} onChange={(e) => set('width_mm', e.target.value)} />
            </Field>
            <Field label={text.height} error={errors.height_mm && text.positive}>
              <input type="text" inputMode="decimal" value={values.height_mm} onChange={(e) => set('height_mm', e.target.value)} />
            </Field>
          </div>
          <label className="radio">
            <input type="checkbox" checked readOnly disabled /> {text.keepProportions}
          </label>
          {estimate && (
            <Notice tone={NoticeTone.Info}>{text.estimate(formatMm(estimate.width_mm), formatMm(estimate.height_mm))}</Notice>
          )}
          <div className="form-grid">
            <Field label={text.machine}>
              <select value={values.machine_profile} onChange={(e) => changeMachine(e.target.value)}>
                {catalog.machines.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </Field>
            <Field label={text.hoop}>
              <select value={values.hoop_profile} onChange={(e) => set('hoop_profile', e.target.value)}>
                {machine.hoops.map((h) => <option key={h.id} value={h.id}>{h.label}</option>)}
              </select>
            </Field>
            <Field label={text.fabric}>
              <select value={values.fabric_profile} onChange={(e) => set('fabric_profile', e.target.value)}>
                {catalog.fabrics.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
              </select>
            </Field>
            <Field label={text.colors} error={errors.color_limit && text.colorsRange(machine.max_colors)}>
              <input type="number" min={1} max={machine.max_colors} value={values.color_limit} onChange={(e) => set('color_limit', e.target.value)} />
            </Field>
          </div>
          {outsideHoop && hoop && (
            <Notice tone={NoticeTone.Warning}>{text.outsideHoop(hoop.width_mm, hoop.height_mm)}</Notice>
          )}
          <ProviderPicker providers={catalog.providers} value={values.ai_provider} onChange={(p) => set('ai_provider', p)} />
          {!asset && <p className="field__hint">{text.needAsset}</p>}
          <div className="row">
            <button type="submit" disabled={busy || !asset}>{busy ? text.submitting : text.submit}</button>
          </div>
        </form>
      </Card.Body>
    </Card>
  );
}

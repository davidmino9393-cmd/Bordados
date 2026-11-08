import { useState, type FormEvent } from 'react';
import type { SourceAsset } from '../../contracts/project';
import { AiProvider, MediaType, type JobSettings, type ProfileCatalog } from '../../contracts/settings';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { estimateContain } from '../../shared/utils/fit';
import { formatMm } from '../../shared/utils/format';
import { LegibilityNotice } from './LegibilityNotice';
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
    machine_profile: machine.profile_id,
    hoop_profile: machine.hoop_profile_ids[0],
    fabric_profile: catalog.fabrics[0].profile_id,
    thread_profile: catalog.thread_profiles[0].profile_id,
    color_limit: DEFAULT_COLORS,
    ai_provider: catalog.providers.find((p) => p.available)?.provider_id ?? AiProvider.None,
  };
}

export function SettingsForm({ catalog, asset, busy, onSubmit }: SettingsFormProps) {
  const [values, setValues] = useState(() => initialValues(catalog));
  const [errors, setErrors] = useState<SettingsErrors>({});
  const machine = catalog.machines.find((m) => m.profile_id === values.machine_profile) ?? catalog.machines[0];
  const hoops = catalog.hoops.filter((h) => machine.hoop_profile_ids.includes(h.profile_id));
  const hoop = hoops.find((h) => h.profile_id === values.hoop_profile);
  const preparedSvg = asset?.media_type === MediaType.Svg;
  const isImage = !!asset && !preparedSvg;
  const noProviderAvailable = !catalog.providers.some((p) => p.available);
  const set = <K extends keyof SettingsFormValues>(key: K, value: SettingsFormValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  const width = parseMm(values.width_mm);
  const height = parseMm(values.height_mm);
  const estimate =
    asset?.original_width_px && asset.original_height_px
      ? estimateContain(asset.original_width_px, asset.original_height_px, { width_mm: width, height_mm: height })
      : null;
  const outsideHoop = hoop && width > 0 && height > 0 && (width > hoop.width_mm || height > hoop.height_mm);

  const changeMachine = (id: string) => {
    const next = catalog.machines.find((m) => m.profile_id === id) ?? machine;
    setValues((v) => ({ ...v, machine_profile: id, hoop_profile: next.hoop_profile_ids[0] }));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = validateSettings(values, machine);
    setErrors(found);
    if (Object.keys(found).length === 0 && asset) {
      onSubmit(toJobSettings({ ...values, ai_provider: preparedSvg ? AiProvider.None : values.ai_provider }, catalog));
    }
  };

  const text = es.settings;
  return (
    <Card>
      <Card.Header>{text.title}</Card.Header>
      <Card.Body>
        <form onSubmit={submit} noValidate className="stack">
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
          {preparedSvg && <Notice tone={NoticeTone.Info}>{text.preparedSvgSize}</Notice>}
          <div className="form-grid">
            <Field label={text.machine}>
              <select value={values.machine_profile} onChange={(e) => changeMachine(e.target.value)}>
                {catalog.machines.map((m) => <option key={m.profile_id} value={m.profile_id}>{m.label}</option>)}
              </select>
            </Field>
            <Field label={text.hoop}>
              <select value={values.hoop_profile} onChange={(e) => set('hoop_profile', e.target.value)}>
                {hoops.map((h) => <option key={h.profile_id} value={h.profile_id}>{h.label}</option>)}
              </select>
            </Field>
            <Field label={text.fabric}>
              <select value={values.fabric_profile} onChange={(e) => set('fabric_profile', e.target.value)}>
                {catalog.fabrics.map((f) => <option key={f.profile_id} value={f.profile_id}>{f.label}</option>)}
              </select>
            </Field>
            <Field label={text.thread}>
              <select value={values.thread_profile} onChange={(e) => set('thread_profile', e.target.value)}>
                {catalog.thread_profiles.map((t) => <option key={t.profile_id} value={t.profile_id}>{t.label}</option>)}
              </select>
            </Field>
            <Field label={text.colors} error={errors.color_limit && text.colorsRange(machine.max_colors)}>
              <input type="number" min={1} max={machine.max_colors} value={values.color_limit} onChange={(e) => set('color_limit', e.target.value)} />
            </Field>
          </div>
          {isImage && asset && (
            <LegibilityNotice
              projectId={asset.project_id}
              assetId={asset.asset_id}
              widthMm={width}
              heightMm={height}
              colorLimit={Number.parseInt(values.color_limit, 10) || 0}
              hoop={hoop}
            />
          )}
          {outsideHoop && hoop && (
            <Notice tone={NoticeTone.Warning}>{text.outsideHoop(hoop.width_mm, hoop.height_mm)}</Notice>
          )}
          <ProviderPicker
            providers={catalog.providers}
            value={values.ai_provider}
            preparedSvg={preparedSvg}
            onChange={(p) => set('ai_provider', p)}
          />
          {isImage && (
            <Notice tone={NoticeTone.Warning} title={text.experimentalTitle}>
              <p>{text.experimentalText}</p>
            </Notice>
          )}
          {isImage && noProviderAvailable && <Notice tone={NoticeTone.Info}>{text.noProviders}</Notice>}
          {!asset && <p className="field__hint">{text.needAsset}</p>}
          <div className="row">
            <button type="submit" disabled={busy || !asset}>{busy ? text.submitting : text.submit}</button>
          </div>
        </form>
      </Card.Body>
    </Card>
  );
}

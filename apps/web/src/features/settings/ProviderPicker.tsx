import { AiProvider, type ProviderAvailability } from '../../contracts/settings';
import { es } from '../../copy/es';

const PROVIDER_LABEL: Record<Exclude<AiProvider, 'none'>, string> = {
  [AiProvider.OpenAI]: 'OpenAI (nube)',
  [AiProvider.Ollama]: 'Modelo local (Ollama)',
};

interface ProviderPickerProps {
  providers: ProviderAvailability[];
  value: AiProvider;
  /** Un SVG ya preparado no pasa por análisis: el proveedor es "none". */
  preparedSvg: boolean;
  onChange: (provider: AiProvider) => void;
}

/** Sin claves ni URLs: las credenciales viven solo en el backend. */
export function ProviderPicker({ providers, value, preparedSvg, onChange }: ProviderPickerProps) {
  if (preparedSvg) {
    return <p className="field__hint">{es.settings.noAiForSvg}</p>;
  }
  return (
    <fieldset>
      <legend>{es.settings.provider}</legend>
      <div>
        <label className="radio">
          <input
            type="radio"
            name="ai_provider"
            value={AiProvider.None}
            checked={value === AiProvider.None}
            onChange={() => onChange(AiProvider.None)}
          />
          {es.settings.noAi}
        </label>
        <p className="field__hint">{es.settings.noAiHint}</p>
      </div>
      {providers.map((p) => (
        <div key={p.provider_id}>
          <label className="radio">
            <input
              type="radio"
              name="ai_provider"
              value={p.provider_id}
              checked={value === p.provider_id}
              disabled={!p.available}
              onChange={() => onChange(p.provider_id)}
            />
            {PROVIDER_LABEL[p.provider_id]}
          </label>
          {!p.available && (
            <p className="field__hint">
              {p.unavailable_reason} {es.settings.noFallback}
            </p>
          )}
        </div>
      ))}
    </fieldset>
  );
}

import type { AiProvider, ProviderAvailability } from '../../contracts/settings';
import { es } from '../../copy/es';

interface ProviderPickerProps {
  providers: ProviderAvailability[];
  value: AiProvider;
  onChange: (provider: AiProvider) => void;
}

/** Sin claves ni URLs: las credenciales viven solo en el backend. */
export function ProviderPicker({ providers, value, onChange }: ProviderPickerProps) {
  return (
    <fieldset>
      <legend>{es.settings.provider}</legend>
      {providers.map((p) => (
        <div key={p.id}>
          <label className="radio">
            <input
              type="radio"
              name="ai_provider"
              value={p.id}
              checked={value === p.id}
              disabled={!p.available}
              onChange={() => onChange(p.id)}
            />
            {p.label}
          </label>
          {!p.available && p.unavailable_reason && <p className="field__hint">{p.unavailable_reason}</p>}
        </div>
      ))}
    </fieldset>
  );
}

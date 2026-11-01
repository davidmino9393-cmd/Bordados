import { useApi } from '../../api/ApiProvider';
import { es } from '../../copy/es';

/** Visible mientras el cliente de API sea simulado. */
export function SimulationBanner() {
  const api = useApi();
  if (!api.isSimulated) return null;
  return (
    <div className="simulation-banner" role="note">
      {es.simulationBanner}
    </div>
  );
}

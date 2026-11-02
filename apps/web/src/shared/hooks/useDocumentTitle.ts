import { useEffect } from 'react';
import { es } from '../../copy/es';

/** Título de pestaña descriptivo por pantalla (WCAG 2.4.2); sin título queda el nombre de la app. */
export function useDocumentTitle(title: string | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · ${es.appName}` : es.appName;
    return () => {
      document.title = es.appName;
    };
  }, [title]);
}

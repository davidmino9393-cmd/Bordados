import { useEffect, useRef, type RefObject } from 'react';
import { useLocation } from 'react-router-dom';

const WAIT_FOR_HEADING_MS = 5_000;

/**
 * Al cambiar de pantalla lleva el foco al título (WCAG 2.4.3): sin esto, con teclado o lector de pantalla el foco
 * queda en el enlace que desapareció y no se anuncia nada. El título puede llegar después de cargar los datos:
 * se espera con un observador, y solo si la persona no movió el foco mientras tanto.
 * La carga inicial no roba el foco.
 */
export function useFocusOnNavigation(main: RefObject<HTMLElement | null>) {
  const { pathname } = useLocation();
  // Se compara con la ruta anterior (no con un «primer render»): el modo estricto ejecuta los efectos dos veces.
  const shown = useRef(pathname);

  useEffect(() => {
    if (shown.current === pathname) return;
    shown.current = pathname;
    const container = main.current;
    if (!container) return;
    // El foco al navegar (el enlace que se activó, o el body si ese enlace desapareció): lo que cambie después lo movió la persona.
    const origin = document.activeElement;
    const focusUnlessMoved = (target: HTMLElement) => {
      const active = document.activeElement;
      if (active !== origin && active !== document.body && active !== container) return;
      target.tabIndex = -1;
      target.focus();
    };
    const focusHeading = () => {
      const heading = container.querySelector('h1');
      if (heading) focusUnlessMoved(heading);
      return heading !== null;
    };
    if (focusHeading()) return;
    focusUnlessMoved(container);
    const observer = new MutationObserver(() => {
      if (focusHeading()) observer.disconnect();
    });
    observer.observe(container, { childList: true, subtree: true });
    const timer = setTimeout(() => observer.disconnect(), WAIT_FOR_HEADING_MS);
    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, [pathname, main]);
}

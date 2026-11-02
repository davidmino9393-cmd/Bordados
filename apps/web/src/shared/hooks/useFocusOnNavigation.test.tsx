import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect, useRef, useState } from 'react';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { useFocusOnNavigation } from './useFocusOnNavigation';

function Delayed() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setReady(true), 30);
    return () => clearTimeout(timer);
  }, []);
  return ready ? <h1>Segunda pantalla</h1> : <p>Cargando…</p>;
}

function Shell() {
  const main = useRef<HTMLElement>(null);
  useFocusOnNavigation(main);
  return (
    <>
      <nav><Link to="/dos">Ir a dos</Link><input aria-label="otro campo" /></nav>
      <main ref={main}>
        <Routes>
          <Route path="/" element={<h1>Primera pantalla</h1>} />
          <Route path="/dos" element={<Delayed />} />
        </Routes>
      </main>
    </>
  );
}

const renderShell = () => render(<MemoryRouter><Shell /></MemoryRouter>);

describe('useFocusOnNavigation', () => {
  it('no roba el foco en la carga inicial', () => {
    renderShell();
    expect(document.body).toHaveFocus();
  });

  it('al navegar espera el título que llega después de cargar y lo enfoca', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole('link', { name: 'Ir a dos' }));
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Segunda pantalla' })).toHaveFocus());
  });

  it('respeta el foco si la persona lo movió mientras cargaba', async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole('link', { name: 'Ir a dos' }));
    await user.click(screen.getByLabelText('otro campo'));
    await screen.findByRole('heading', { name: 'Segunda pantalla' });
    expect(screen.getByLabelText('otro campo')).toHaveFocus();
  });
});

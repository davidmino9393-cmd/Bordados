import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { ApiProvider } from './api/ApiProvider';
import { httpApiClient } from './api/HttpApiClient';
import { createMockApiClient } from './mocks/MockApiClient';
import './styles/tokens.css';
import './styles/app.css';

// SIMULADO por defecto: el cliente real sigue bloqueado hasta congelar contratos v0.1.
const useMocks = import.meta.env.VITE_USE_MOCKS !== 'false';
const client = useMocks ? createMockApiClient() : httpApiClient;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ApiProvider client={client}>
        <App />
      </ApiProvider>
    </BrowserRouter>
  </StrictMode>,
);

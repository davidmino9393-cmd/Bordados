import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { ApiProvider } from './api/ApiProvider';
import { createHttpApiClient } from './api/HttpApiClient';
import { createMockApiClient } from './mocks/MockApiClient';
import './styles/tokens.css';
import './styles/app.css';

// Las respuestas simuladas solo se usan si se piden explícitamente (VITE_USE_MOCKS=true);
// sin esa variable se habla con el backend real del mismo origen.
const useMocks = import.meta.env.VITE_USE_MOCKS === 'true';
const client = useMocks ? createMockApiClient() : createHttpApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL ?? '' });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ApiProvider client={client}>
        <App />
      </ApiProvider>
    </BrowserRouter>
  </StrictMode>,
);

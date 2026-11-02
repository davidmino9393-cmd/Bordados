import { useRef } from 'react';
import { Link, Route, Routes } from 'react-router-dom';
import { es } from './copy/es';
import { JobPage } from './features/job-progress/JobPage';
import { ProjectPage } from './features/projects/ProjectPage';
import { ProjectsPage } from './features/projects/ProjectsPage';
import { SimulationBanner } from './shared/components/SimulationBanner';
import { useFocusOnNavigation } from './shared/hooks/useFocusOnNavigation';

export function App() {
  const main = useRef<HTMLElement>(null);
  useFocusOnNavigation(main);
  return (
    <>
      <header>
        <SimulationBanner />
        <div className="app-header">
          <Link to="/">{es.appName}</Link>
          <nav aria-label="Principal">
            <Link to="/">{es.projects.title}</Link>
          </nav>
        </div>
      </header>
      <main className="page" ref={main}>
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/proyectos/:projectId" element={<ProjectPage />} />
          <Route path="/trabajos/:jobId" element={<JobPage />} />
          <Route path="*" element={<p>{es.errors.notFound}</p>} />
        </Routes>
      </main>
    </>
  );
}

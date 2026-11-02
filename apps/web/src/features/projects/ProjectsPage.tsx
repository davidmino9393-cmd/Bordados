import { useCallback, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import type { ProjectResponse } from '../../contracts/project';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { LoadMore } from '../../shared/components/LoadMore';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage, useAsync } from '../../shared/hooks/useAsync';
import { useDocumentTitle } from '../../shared/hooks/useDocumentTitle';
import { useLoadMore } from '../../shared/hooks/useLoadMore';
import { newIdempotencyKey } from '../../shared/utils/idempotency';

const NO_PROJECTS: ProjectResponse[] = [];

export function ProjectsPage() {
  const api = useApi();
  const navigate = useNavigate();
  const projects = useAsync(() => api.listProjects(), [api]);
  const fetchPage = useCallback(
    async (cursor: string) => {
      const page = await api.listProjects(cursor);
      return { items: page.items, next: page.next_cursor };
    },
    [api],
  );
  const list = useLoadMore(
    { items: projects.data?.items ?? NO_PROJECTS, next: projects.data?.next_cursor ?? null },
    (project) => project.project_id,
    fetchPage,
    'projects',
  );
  const [name, setName] = useState('');
  const [nameError, setNameError] = useState<string>();
  const [submitError, setSubmitError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setNameError(es.projects.nameRequired);
      return;
    }
    setNameError(undefined);
    setBusy(true);
    try {
      const project = await api.createProject(name, newIdempotencyKey());
      navigate(`/proyectos/${project.project_id}`);
    } catch (e) {
      setSubmitError(errorMessage(e));
      setBusy(false);
    }
  };

  useDocumentTitle(es.projects.title);
  const items = list.items;
  return (
    <>
      <h1>{es.projects.title}</h1>
      <Card>
        <Card.Body>
          <form onSubmit={submit} noValidate className="form-grid">
            <Field label={es.projects.newLabel} error={nameError}>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <div className="row">
              <button type="submit" disabled={busy}>{es.projects.create}</button>
            </div>
          </form>
          {submitError && <Notice tone={NoticeTone.Error}>{submitError}</Notice>}
        </Card.Body>
      </Card>
      {projects.error && <Notice tone={NoticeTone.Error}>{projects.error}</Notice>}
      {projects.data && items.length === 0 && <p>{es.projects.empty}</p>}
      <ul className="list">
        {items.map((project) => (
          <li key={project.project_id} className="list__item">
            <Link to={`/proyectos/${project.project_id}`}>{project.name}</Link>
            <span className="field__hint">
              {es.projects.createdOn(new Date(project.created_at).toLocaleDateString('es-AR'))}
            </span>
          </li>
        ))}
      </ul>
      <LoadMore hasMore={list.hasMore} loading={list.loading} error={list.error} onLoadMore={list.loadMore} label={es.projects.more} />
    </>
  );
}

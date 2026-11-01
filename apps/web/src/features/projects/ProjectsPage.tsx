import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage, useAsync } from '../../shared/hooks/useAsync';
import { newIdempotencyKey } from '../../shared/utils/idempotency';

export function ProjectsPage() {
  const api = useApi();
  const navigate = useNavigate();
  const projects = useAsync(() => api.listProjects(), [api]);
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

  const items = projects.data?.items ?? [];
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
      {projects.data?.next_cursor && <p className="field__hint">{es.projects.more}</p>}
    </>
  );
}

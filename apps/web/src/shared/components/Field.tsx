import { useId, type ReactElement, cloneElement } from 'react';

interface FieldProps {
  label: string;
  error?: string;
  hint?: string;
  children: ReactElement<{ id?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }>;
}

/** Asocia etiqueta, ayuda y error al control para lectores de pantalla. */
export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const noteId = `${id}-note`;
  const note = error ?? hint;
  const control = cloneElement(children, {
    id,
    'aria-describedby': note ? noteId : undefined,
    'aria-invalid': error ? true : undefined,
  });
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {control}
      {note && (
        <p id={noteId} className={error ? 'field__error' : 'field__hint'}>
          {note}
        </p>
      )}
    </div>
  );
}

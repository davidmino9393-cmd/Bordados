import type { ReactNode } from 'react';

function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`.trim()}>{children}</section>;
}

function CardHeader({ children }: { children: ReactNode }) {
  return <h2 className="card__header">{children}</h2>;
}

function CardBody({ children }: { children: ReactNode }) {
  return <div className="card__body">{children}</div>;
}

Card.Header = CardHeader;
Card.Body = CardBody;

export { Card };

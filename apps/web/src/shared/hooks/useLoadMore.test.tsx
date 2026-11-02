import { describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useLoadMore, type Page } from './useLoadMore';

interface Row {
  id: string;
}
const rows = (...ids: string[]): Row[] => ids.map((id) => ({ id }));
const idOf = (row: Row) => row.id;

describe('useLoadMore', () => {
  it('agrega la página siguiente al pie y deja de ofrecer «Ver más» cuando no queda ninguna', async () => {
    const fetchPage = vi.fn(async (cursor: string): Promise<Page<Row>> =>
      cursor === 'c1' ? { items: rows('c', 'd'), next: 'c2' } : { items: rows('e'), next: null },
    );
    const first = { items: rows('a', 'b'), next: 'c1' };
    const { result } = renderHook(() => useLoadMore(first, idOf, fetchPage, 'p'));
    expect(result.current.hasMore).toBe(true);

    await act(() => result.current.loadMore());
    expect(result.current.items.map(idOf)).toEqual(['a', 'b', 'c', 'd']);
    expect(result.current.hasMore).toBe(true);

    await act(() => result.current.loadMore());
    expect(result.current.items.map(idOf)).toEqual(['a', 'b', 'c', 'd', 'e']);
    expect(result.current.hasMore).toBe(false);
    await act(() => result.current.loadMore());
    expect(fetchPage).toHaveBeenCalledTimes(2);
  });

  it('conserva lo cargado de más y su cursor cuando se renueva la primera página, sin repetir filas', async () => {
    const fetchPage = vi.fn(async (): Promise<Page<Row>> => ({ items: rows('c'), next: 'c9' }));
    const { result, rerender } = renderHook(({ first }) => useLoadMore(first, idOf, fetchPage, 'p'), {
      initialProps: { first: { items: rows('a', 'b'), next: 'c1' as string | null } },
    });
    await act(() => result.current.loadMore());
    rerender({ first: { items: rows('a', 'b', 'c'), next: 'c1' } });
    expect(result.current.items.map(idOf)).toEqual(['a', 'b', 'c']);
    expect(result.current.hasMore).toBe(true);
    await act(() => result.current.loadMore());
    expect(fetchPage).toHaveBeenLastCalledWith('c9');
  });

  it('informa el error, no pierde lo ya cargado y permite reintentar', async () => {
    const fetchPage = vi.fn<(cursor: string) => Promise<Page<Row>>>()
      .mockRejectedValueOnce(new Error('sin red'))
      .mockResolvedValueOnce({ items: rows('c'), next: null });
    const first = { items: rows('a'), next: 'c1' };
    const { result } = renderHook(() => useLoadMore(first, idOf, fetchPage, 'p'));
    await act(() => result.current.loadMore());
    expect(result.current.error).toBe('sin red');
    expect(result.current.items.map(idOf)).toEqual(['a']);
    expect(result.current.hasMore).toBe(true);
    await act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.error).toBeUndefined());
    expect(result.current.items.map(idOf)).toEqual(['a', 'c']);
  });

  it('descarta lo cargado de más al cambiar de lista', async () => {
    const fetchPage = vi.fn(async (): Promise<Page<Row>> => ({ items: rows('x'), next: null }));
    const first = { items: rows('a'), next: 'c1' };
    const { result, rerender } = renderHook(({ key }) => useLoadMore(first, idOf, fetchPage, key), { initialProps: { key: 'p1' } });
    await act(() => result.current.loadMore());
    expect(result.current.items).toHaveLength(2);
    rerender({ key: 'p2' });
    await waitFor(() => expect(result.current.items.map(idOf)).toEqual(['a']));
    expect(result.current.hasMore).toBe(true);
  });
});

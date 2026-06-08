import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ReaderScreen } from './reader.jsx';

const CHAPTER = {
  book_title: 'The Life Divine',
  reflowed: true,
  parent_toc_title: '',
  blocks: [{ type: 'lines', lines: ['The earliest preoccupation of man in his awakened thoughts.'] }],
  prev_slug: '',
  next_slug: 'reality-omnipresent',
};

describe('ReaderScreen', () => {
  beforeEach(() => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(CHAPTER) }));
  });

  it('fetches and renders the chapter text', async () => {
    render(
      <ReaderScreen
        route={{ chapter: { slugMode: true, collection: 'sriaurobindo', bookSlug: 'the-life-divine', slug: 'the-human-aspiration' }, query: '', resultType: 'all' }}
        go={() => {}}
        goBack={() => {}}
        onMenu={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText(/earliest preoccupation/)).toBeInTheDocument());
    // book title shows in the reader bar
    expect(screen.getAllByText(/The Life Divine/).length).toBeGreaterThan(0);
  });

  it('builds the slug-mode chapter request URL', async () => {
    render(
      <ReaderScreen
        route={{ chapter: { slugMode: true, collection: 'sriaurobindo', bookSlug: 'the-life-divine', slug: 'the-human-aspiration' }, query: '', resultType: 'all' }}
        go={() => {}} goBack={() => {}} onMenu={() => {}}
      />
    );
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/chapter_by_slug');
    expect(url).toContain('collection_folder=sriaurobindo');
    expect(url).toContain('book_slug=the-life-divine');
    expect(url).toContain('slug=the-human-aspiration');
  });
});

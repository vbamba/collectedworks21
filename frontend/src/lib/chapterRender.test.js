import { describe, it, expect } from 'vitest';
import { buildChapterHtml } from './chapterRender';

describe('buildChapterHtml', () => {
  it('joins prose lines with spaces when reflowed', () => {
    const html = buildChapterHtml([{ lines: ['Hello world', 'second line'] }], true, 'The Life Divine');
    expect(html).toBe('<p>Hello world second line</p>');
  });

  it('keeps verse line breaks (<br/>) when not reflowed', () => {
    // DOMPurify normalises the <br/> we join with to the HTML5 void form <br>
    // (exactly as the original ChapterPage did — it sanitised the same string).
    const html = buildChapterHtml([{ lines: ['Line one', 'Line two'] }], false, 'Collected Poems');
    expect(html).toBe('<p class="verse">Line one<br>Line two</p>');
  });

  it('renders hr blocks', () => {
    expect(buildChapterHtml([{ type: 'hr' }], true, '')).toBe('<hr/>');
  });

  it('splits on asterism lines', () => {
    const html = buildChapterHtml([{ lines: ['a', '*', 'b'] }], true, '');
    expect(html).toBe('<p>a</p><p class="asterism">*</p><p>b</p>');
  });

  it('renders date_heading and subheading blocks as h3', () => {
    expect(buildChapterHtml([{ type: 'date_heading', text: 'March 14, 1952' }], true, ''))
      .toBe('<h3 class="date-heading">March 14, 1952</h3>');
    expect(buildChapterHtml([{ type: 'subheading', text: 'The Teaching of the Gita' }], true, ''))
      .toBe('<h3 class="subheading">The Teaching of the Gita</h3>');
  });

  it('splits Savitri sentences into separate verse paragraphs', () => {
    // Savitri + not reflowed -> flush a paragraph at each sentence-ending line.
    const html = buildChapterHtml(
      [{ lines: ['It was the hour before the Gods awake.', 'Across the path of the divine Event'] }],
      false,
      'Savitri'
    );
    expect(html).toBe('<p class="verse">It was the hour before the Gods awake.</p><p class="verse">Across the path of the divine Event</p>');
  });
});

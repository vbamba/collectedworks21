// frontend/src/lib/chapterRender.js
// CHANGED (Phase 3c): shared chapter rendering extracted VERBATIM from
// ChapterPage.jsx so the legacy reader and the new Library reader render
// identically and can never drift (the chapter.html ↔ ChapterPage drift this
// project hit before is exactly what this avoids). Both import from here.
import DOMPurify from 'dompurify';
import Mark from 'mark.js';
const MarkClass = Mark.default || Mark;

// Stop-words (same as backend)
const STOPWORDS = new Set([
  'a','an','and','are','as','at','be','but','by','for','from','had','has','have',
  'he','her','his','in','is','it','its','of','on','or','she','that','the','their',
  'there','they','to','was','were','which','will','with','would','this','those',
  'these','your','you','i','we','our','us'
]);

// Matches a verse line that ends a sentence (Savitri sentence-stanza splitting).
const SENTENCE_END_RE = /[.?!][)"'”’]?\s*$/;

// normalize ligatures/nbsp & collapse whitespace (client-side)
export function normalizeCompat(str) {
  if (!str) return '';
  return str
    .replace(/ﬁ/g, 'fi')  // ﬁ
    .replace(/ﬂ/g, 'fl')  // ﬂ
    .replace(/ /g, ' ')   // nbsp
    .replace(/\s+/g, ' ');
}
// ligature-aware escape
export function ligatureRegexEscape(str) {
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return esc(str)
    .replace(/fi/gi, '(?:fi|\\uFB01)')
    .replace(/fl/gi, '(?:fl|\\uFB02)');
}

// Build the chapter request URL (slug or query mode) and return the JSON.
export async function fetchChapterData({ slugMode, collection, bookSlug, slug, bookFolder, sectionFilename }) {
  let url;
  if (slugMode) {
    url = `/api/chapter_by_slug?collection_folder=${encodeURIComponent(collection)}` +
          `&book_slug=${encodeURIComponent(bookSlug)}` +
          `&slug=${encodeURIComponent(slug)}`;
  } else if (collection && bookFolder && sectionFilename) {
    url = `/api/chapter?collection_folder=${encodeURIComponent(collection)}` +
          `&book_folder=${encodeURIComponent(bookFolder)}` +
          `&section_filename=${encodeURIComponent(sectionFilename)}`;
  } else {
    throw new Error('Missing URL parameters');
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to load chapter data');
  return res.json();
}

// blocks + reflow flag + bookTitle -> sanitized HTML string.
export function buildChapterHtml(blocks, reflowed, bookTitle) {
  const splitSavitriSentences = bookTitle === 'Savitri' && !reflowed;
  const lineJoin = reflowed ? ' ' : '<br/>';
  return blocks.map(blk => {
    if (blk.type === 'hr') return '<hr/>';
    if (blk.type === 'date_heading') {
      return `<h3 class="date-heading">${DOMPurify.sanitize(blk.text || '')}</h3>`;
    }
    if (blk.type === 'subheading') {
      return `<h3 class="subheading">${DOMPurify.sanitize(blk.text || '')}</h3>`;
    }
    const groups = [];
    let buf = [];
    const flush = () => { if (buf.length) { groups.push(buf); buf = []; } };
    for (const line of blk.lines) {
      if (line.trim() === '*') { flush(); groups.push('*'); }
      else {
        buf.push(line);
        if (splitSavitriSentences && SENTENCE_END_RE.test(line)) flush();
      }
    }
    flush();
    return groups.map(g => {
      if (g === '*') return '<p class="asterism">*</p>';
      const cls = reflowed ? '' : ' class="verse"';
      return `<p${cls}>${DOMPurify.sanitize(g.join(lineJoin))}</p>`;
    }).join('');
  }).join('');
}

// Highlight the query phrase inside a rendered chapter container and scroll to
// the best match. `ctx` is the content DOM element. Verbatim from ChapterPage.
export function highlightChapter(ctx, { phrase, resultType }) {
  if (!ctx || !phrase) return;

  const markIns = new MarkClass(ctx);

  markIns.unmark({
    done: () => {
      const scroll = () => {
        const el = ctx.querySelector('mark');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      };

      const markOpts = {
        acrossElements: true,
        ignorePunctuation: ":;.,–—()[]'\"-_",
        diacritics: true,
        ignoreJoiners: true,
      };

      if (resultType === 'exact') {
        markIns.mark(phrase, {
          ...markOpts,
          separateWordSearch: false,
          done: count => {
            if (count > 0) {
              const exact = Array.from(ctx.querySelectorAll('mark'))
                .find(el => el.textContent.trim().toLowerCase() === phrase.toLowerCase());
              (exact || ctx.querySelector('mark'))?.scrollIntoView({ behavior: 'smooth', block: 'center' });
              return;
            }
            try {
              const WS_OR_TAG = '(?:\\s|<[^>]+>)+';
              const normPhrase = normalizeCompat(phrase);
              const pattern = ligatureRegexEscape(normPhrase).replace(/\s+/g, WS_OR_TAG);
              const rx = new RegExp(pattern, 'i');

              const html = ctx.innerHTML;
              const m = html.match(rx);
              if (m) {
                const idx = html.search(rx);
                ctx.innerHTML = html.slice(0, idx)
                  + '<mark>' + m[0] + '</mark>'
                  + html.slice(idx + m[0].length);
                scroll();
                return;
              }
            } catch {}

            try {
              const words = normalizeCompat(phrase)
                .split(/\s+/)
                .filter(Boolean);
              if (words.length >= 2) {
                const STEM_JOIN = '(?:\\s|<[^>]+>)+';
                const stemPat = words
                  .map(w => ligatureRegexEscape(w) + '\\w{0,5}')
                  .join(STEM_JOIN);
                const stemRx = new RegExp('\\b' + stemPat + '\\b', 'i');
                const html = ctx.innerHTML;
                const m = html.match(stemRx);
                if (m) {
                  const idx = html.search(stemRx);
                  ctx.innerHTML = html.slice(0, idx)
                    + '<mark>' + m[0] + '</mark>'
                    + html.slice(idx + m[0].length);
                  scroll();
                  return;
                }
              }
            } catch {}

            const words = phrase.split(/\s+/).filter(w => w && !STOPWORDS.has(w.toLowerCase()));
            if (!words.length) return;
            markIns.mark(words, { ...markOpts, separateWordSearch: true, done: scroll });
          }
        });
      } else {
        const words = normalizeCompat(phrase)
          .split(/\s+/)
          .filter(w => w && !STOPWORDS.has(w.toLowerCase()));
        if (!words.length) return;

        const scrollToCluster = () => {
          const marks = Array.from(ctx.querySelectorAll('mark'));
          if (!marks.length) return;
          if (marks.length === 1) {
            marks[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
          }
          const tops = marks.map(m => m.getBoundingClientRect().top);
          const K = Math.min(words.length, marks.length);
          let bestStart = 0;
          let bestSpan = Infinity;
          for (let i = 0; i + K <= tops.length; i++) {
            const span = tops[i + K - 1] - tops[i];
            if (span < bestSpan) { bestSpan = span; bestStart = i; }
          }
          marks[bestStart].scrollIntoView({ behavior: 'smooth', block: 'center' });
        };

        markIns.mark(words, {
          ...markOpts,
          separateWordSearch: true,
          done: () => {
            if (!ctx.querySelector('mark')) {
              let html = ctx.innerHTML;
              for (const t of words) {
                const rx = new RegExp('\\b(' + ligatureRegexEscape(t) + ')\\b', 'gi');
                html = html.replace(rx, '<mark>$1</mark>');
              }
              ctx.innerHTML = html;
            }
            scrollToCluster();
          }
        });
      }
    }
  });
}

/* ============================================================
   Sri Aurobindo Library — data layer (Phase 3a: still the prototype's
   STUB data). Ported from docs/prototype/extracted/app/data.js: the
   window.DATA IIFE is now a plain ESM export. Real backend wiring
   (search -> api.js, volumes -> /api filters, reading -> ChapterPage)
   lands in Phase 3b/3c; this keeps the design rendering meanwhile.
   ============================================================ */

// ---- Daily thoughts -------------------------------------------------
const THOUGHTS = [
  { text: "It is a mistake to think that a thought or will can have effect only when it is expressed in speech or act: the unspoken thought, the unexpressed will are also active energies and can produce their own vibrations, effects or reactions.", author: "Sri Aurobindo", source: "Letters on Yoga", page: 477 },
  { text: "All life is Yoga.", author: "Sri Aurobindo", source: "The Synthesis of Yoga", page: 6 },
  { text: "To be calm, undisturbed, quiet, to have a settled trust and confidence in the working of the Divine Power is the proper foundation of a sound sadhana.", author: "Sri Aurobindo", source: "Letters on Yoga", page: 311 },
  { text: "Always behave as if the Mother was looking at you, because she is, indeed, always present.", author: "The Mother", source: "Words of the Mother", page: 154 },
  { text: "The mind must learn to be silent, then only can the higher Light descend and the true knowledge come.", author: "Sri Aurobindo", source: "The Hour of God", page: 28 },
];

// ---- Reading sample passages ---------------------------------------
const SAMPLE_LIFE_DIVINE = [
  { type: "h2", text: "Chapter I — The Human Aspiration" },
  { type: "epigraph", text: "She follows to the goal of those that are passing on beyond, she is the first in the eternal succession of the dawns that are coming.", cite: "Rig Veda" },
  { type: "p", text: "The earliest preoccupation of man in his awakened thoughts and, as it seems, his inevitable and ultimate preoccupation,—for it survives the longest periods of scepticism and returns after every banishment,—is also the highest which his thought can envisage. It manifests itself in the divination of Godhead, the impulse towards perfection, the search after pure Truth and unmixed Bliss, the sense of a secret immortality." },
  { type: "p", text: "The ancient dawns of human knowledge have left us their witness to this constant aspiration; today we see a humanity satiated but not satisfied by victorious analysis of the externalities of Nature preparing to return to its primeval longings. The earliest formula of Wisdom promises to be its last,—God, Light, Freedom, Immortality." },
  { type: "p", text: "These persistent ideals of the race are at once the contradiction of its normal experience and the affirmation of higher and deeper experiences which are abnormal to humanity and only to be attained, in their organised entirety, by a revolutionary individual effort or an evolutionary general progression." },
  { type: "p", text: "To know, possess and be the divine being in an animal and egoistic consciousness, to convert our twilit or obscure physical mentality into the plenary supramental illumination, to build peace and a self-existent bliss where there is only a stress of transitory satisfactions besieged by physical pain and emotional suffering, to establish an infinite freedom in a world which presents itself as a group of mechanical necessities,—these and similar aims are being pursued." },
];

const SAMPLE_SAVITRI = [
  { type: "h2", text: "Book One, Canto I — The Symbol Dawn" },
  { type: "verse", lines: ["It was the hour before the Gods awake.", "Across the path of the divine Event", "The huge foreboding mind of Night, alone", "In her unlit temple of eternity,", "Lay stretched immobile upon Silence' marge.", "Almost one felt, opaque, impenetrable,", "In the sombre symbol of her eyeless muse", "The abysm of the unbodied Infinite;", "A fathomless zero occupied the world."] },
  { type: "verse", lines: ["A power of fallen boundless self awake", "Between the first and the last Nothingness,", "Recalling the tenebrous womb from which it came,", "Turned from the insoluble mystery of birth", "And the tardy process of mortality", "And longed to reach its end in vacant Nought."] },
];

const SAMPLE_PRAYERS = [
  { type: "h2", text: "November 1912" },
  { type: "p", text: "It matters little that there are thousands of beings plunged in the densest ignorance, He whom we saw yesterday is on earth; his presence is enough to prove that a day will come when darkness shall be transformed into light, and Thy reign shall be indeed established upon earth." },
  { type: "p", text: "O Lord, Divine Builder of this marvel, my heart overflows with joy and gratitude when I think of it, and my hope has no bounds. My adoration is beyond all words, my reverence is silent." },
];

// ---- Collections & volumes -----------------------------------------
const COLLECTIONS = [
  { id: "cwsa", author: "sa", title: "Complete Works of Sri Aurobindo", abbr: "CWSA", blurb: "The definitive 37-volume edition, organised by subject across poetry, philosophy, yoga and politics.", count: 37 },
  { id: "cwm", author: "m", title: "Collected Works of The Mother", abbr: "CWM", blurb: "The 17-volume centenary edition of the Mother's writings and talks.", count: 17 },
  { id: "agenda", author: "m", title: "Mother's Agenda", abbr: "AGENDA", blurb: "Thirteen volumes of conversations with Satprem recording the yoga of the cells, 1951–1973.", count: 13 },
  { id: "disciples", author: "d", title: "Works of the Disciples", abbr: "DISCIPLES", blurb: "Reminiscences, talks and writings of those who lived and worked beside the Master and the Mother.", count: 9 },
];

const VOLUMES = [
  { id: "life-divine-1", collection: "cwsa", author: "sa", slug: "the-life-divine", num: 21, title: "The Life Divine", part: "Book I & II", subject: "Philosophy", year: 1939, pages: 1116, sample: "life", featured: true, desc: "Sri Aurobindo's principal philosophical work, presenting a vision of spiritual evolution and the descent of a divine consciousness into earthly life." },
  { id: "synthesis-yoga", collection: "cwsa", author: "sa", slug: "the-synthesis-of-yoga", num: 23, title: "The Synthesis of Yoga", part: "Parts I–IV", subject: "Yoga", year: 1948, pages: 908, sample: "life", featured: true, desc: "A comprehensive treatment of the paths of yoga and their integral unification." },
  { id: "savitri", collection: "cwsa", author: "sa", slug: "savitri", num: 33, title: "Savitri", part: "A Legend and a Symbol", subject: "Poetry", year: 1950, pages: 816, sample: "savitri", featured: true, desc: "An epic poem of nearly 24,000 lines — a legend of death and transcendence, and Sri Aurobindo's supreme revelation in verse." },
  { id: "letters-yoga-1", collection: "cwsa", author: "sa", slug: "letters-on-yoga-i", num: 28, title: "Letters on Yoga", part: "Volume I", subject: "Yoga", year: 1936, pages: 590, sample: "life", desc: "Letters to disciples on the foundations of the integral yoga." },
  { id: "essays-gita", collection: "cwsa", author: "sa", slug: "essays-on-the-gita", num: 19, title: "Essays on the Gita", part: "", subject: "Philosophy", year: 1922, pages: 612, sample: "life", desc: "A profound interpretation of the Bhagavad Gita as a gospel of spiritual works." },
  { id: "secret-veda", collection: "cwsa", author: "sa", slug: "the-secret-of-the-veda", num: 15, title: "The Secret of the Veda", part: "", subject: "Vedas", year: 1914, pages: 624, sample: "life", desc: "A re-reading of the Rig Veda revealing its psychological and spiritual sense." },
  { id: "human-cycle", collection: "cwsa", author: "sa", slug: "the-human-cycle", num: 25, title: "The Human Cycle", part: "The Ideal of Human Unity", subject: "Society", year: 1949, pages: 596, sample: "life", desc: "On the evolution of human society toward a spiritual age." },
  { id: "collected-poems", collection: "cwsa", author: "sa", slug: "collected-poems", num: 2, title: "Collected Poems", part: "", subject: "Poetry", year: 1942, pages: 740, sample: "savitri", desc: "The shorter poems, sonnets and lyrical works." },
  { id: "prayers", collection: "cwm", author: "m", slug: "prayers-and-meditations", num: 1, title: "Prayers and Meditations", part: "", subject: "Prayers", year: 1932, pages: 410, sample: "prayers", featured: true, desc: "The Mother's intimate spiritual diary of prayers written between 1912 and 1937." },
  { id: "questions-answers-3", collection: "cwm", author: "m", slug: "questions-and-answers-1929-1931", num: 3, title: "Questions and Answers", part: "1929–1931", subject: "Talks", year: 1929, pages: 244, sample: "prayers", desc: "Talks given to disciples on the practice of yoga and the spiritual life." },
  { id: "on-education", collection: "cwm", author: "m", slug: "on-education", num: 12, title: "On Education", part: "", subject: "Education", year: 1978, pages: 440, sample: "prayers", desc: "On the integral education of the body, vital, mind and spirit." },
  { id: "words-mother", collection: "cwm", author: "m", slug: "words-of-the-mother-i", num: 13, title: "Words of the Mother", part: "Volume I", subject: "Talks", year: 1980, pages: 396, sample: "prayers", desc: "Messages and writings on the Master, the Divine, and the path." },
  { id: "agenda-1", collection: "agenda", author: "m", slug: "mothers-agenda-volume-1", num: 1, title: "Mother's Agenda", part: "Volume 1 · 1951–1960", subject: "Talks", year: 1960, pages: 388, sample: "prayers", desc: "Conversations with Satprem recording the yoga of transformation." },
  { id: "evening-talks", collection: "disciples", author: "d", slug: "evening-talks-with-sri-aurobindo", num: 1, title: "Evening Talks", part: "with Sri Aurobindo", subject: "Talks", year: 1959, pages: 820, sample: "life", desc: "A. B. Purani's record of the informal evening conversations with Sri Aurobindo, 1923–1926." },
  { id: "reminiscences", collection: "disciples", author: "d", slug: "reminiscences", num: 2, title: "Reminiscences", part: "", subject: "Biography", year: 1969, pages: 312, sample: "prayers", desc: "First-hand recollections of life beside the Master and the Mother in the early Ashram." },
];

const SUBJECTS = ["Philosophy", "Yoga", "Poetry", "Vedas", "Upanishads", "The Gita", "Society", "India", "Education", "Prayers", "Talks"];

const MEDIA = [
  { id: "savitri-mother", kind: "audio", title: "Savitri — read by the Mother", meta: "Book One · with Sunil's music", duration: "48:12", author: "m" },
  { id: "new-year", kind: "audio", title: "New Year Messages", meta: "The Mother's voice", duration: "12:30", author: "m" },
  { id: "dhammapada", kind: "audio", title: "Commentaries on the Dhammapada", meta: "Readings", duration: "1:04:55", author: "m" },
  { id: "four-aspects", kind: "video", title: "The Four Great Aspects of the Mother", meta: "Documentary", duration: "22:08", author: "m" },
  { id: "sa-ashram", kind: "video", title: "Sri Aurobindo and the Ashram", meta: "Archival film", duration: "31:40", author: "sa" },
  { id: "organ-music", kind: "audio", title: "Recitations & Organ Music", meta: "Meditative", duration: "55:20", author: "m" },
];

const GALLERIES = [
  { id: "sri-aurobindo", title: "Sri Aurobindo", count: 42 },
  { id: "mother", title: "The Mother", count: 58 },
  { id: "samadhi", title: "The Samadhi", count: 24 },
];

function sampleFor(key) {
  if (key === "savitri") return SAMPLE_SAVITRI;
  if (key === "prayers") return SAMPLE_PRAYERS;
  return SAMPLE_LIFE_DIVINE;
}

// ---- Live archive integration --------------------------------------
const ASK = {
  base: "https://ask.collectedworksofsriaurobindo.com",
  authorSlug: { sa: "sriaurobindo", m: "mother", d: "disciples" },
};
function slugify(s) {
  return String(s).toLowerCase().replace(/[—–']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}
const VERIFIED = { "essays-gita::0": "i-our-demand-and-need-from-the-gita" };
function readUrl(vol, chapterTitle, chapterIndex) {
  if (!vol) return ASK.base;
  const author = ASK.authorSlug[vol.author] || "sriaurobindo";
  let url = ASK.base + "/read/" + author + "/" + (vol.slug || slugify(vol.title));
  const verified = VERIFIED[vol.id + "::" + chapterIndex];
  if (verified) url += "/" + verified;
  else if (chapterTitle != null) url += "/" + slugify(chapterTitle);
  return url;
}
function searchUrl(q) {
  return ASK.base + "/?q=" + encodeURIComponent(q || "");
}

export const DATA = {
  THOUGHTS, COLLECTIONS, VOLUMES, SUBJECTS, MEDIA, GALLERIES, ASK,
  sampleFor, readUrl, searchUrl, slugify,
  volumeById: (id) => VOLUMES.find((v) => v.id === id),
  collectionById: (id) => COLLECTIONS.find((c) => c.id === id),
  featured: VOLUMES.filter((v) => v.featured),
};

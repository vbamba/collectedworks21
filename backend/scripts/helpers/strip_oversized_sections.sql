-- Strip catch-all "Page_X" sections that bundle TOC + many chapters into one
-- file. Spot-checked: the same content is duplicated in the properly-split
-- sibling sections of each book (e.g. the Avatarhood passage is in
-- section_63_Chapter_Two_-_Specific_Avatars_and_Vibhutis.txt), so deleting
-- these rows does not lose searchable content; it just routes search results
-- to a cleaner chapter view that doesn't open on the front-matter / TOC.
--
-- Re-run this after every chapters.db rebuild until the upstream splitter is
-- fixed. Usage:
--   sqlite3 backend/db/chapters.db < backend/scripts/helpers/strip_oversized_sections.sql

DELETE FROM chapters
WHERE (book_folder, section_filename) IN (
  ('28LettersOnYoga-I',                'section_74_Page_8.txt'),
  ('35LettersOnHimselfAndTheAshram',   'section_76_Page_11.txt'),
  ('32TheMotherWithLettersOnTheMother','section_49_Page_1.txt')
);

-- Sanity check: should return 0 rows after the DELETE above.
SELECT book_folder, section_filename, length(content) AS content_len
FROM chapters
WHERE (book_folder, section_filename) IN (
  ('28LettersOnYoga-I',                'section_74_Page_8.txt'),
  ('35LettersOnHimselfAndTheAshram',   'section_76_Page_11.txt'),
  ('32TheMotherWithLettersOnTheMother','section_49_Page_1.txt')
);

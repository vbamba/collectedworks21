############################
# utils.py (Updated)
############################

import logging
import re
import bleach
import unicodedata
import string
from statistics import variance

# For robust stopword usage:
import nltk
from nltk.corpus import stopwords

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)

############################
# Module-level constants
############################

DEFAULT_MAX_CHARS = 600

# Load the comprehensive list of English stopwords from NLTK
try:
    nltk.data.find('corpora/stopwords')  # if we haven't downloaded, handle or raise
except LookupError:
    nltk.download('stopwords')

STOPWORDS = set(stopwords.words('english'))
# Ensure "i" is excluded from highlighting (NLTK might not always include it)
# Also, ensure any single-letter words you want to exclude (like "a") are in STOPWORDS
# (The default list does have "a", but let's be explicit.)
STOPWORDS.update({"i", "a"})

############################
# Text Normalization
############################

def normalize_text(text):
    """
    Normalize Unicode characters and replace special characters (ligatures, curly quotes, etc.).
    """
    text = unicodedata.normalize('NFKC', text)
    ligatures = {
        'ﬁ': 'fi',
        'ﬂ': 'fl',
        'ﬀ': 'ff',
        'ﬃ': 'ffi',
        'ﬄ': 'ffl',
        'ﬅ': 'st',
        'ﬆ': 'st',
        '\ufb01': 'fi',
        '\ufb02': 'fl',
    }
    for ligature, replacement in ligatures.items():
        text = text.replace(ligature, replacement)

    curly_quotes = {
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",
        '–': '-',
        '—': '-',
        '…': '...',
        '′': "'",
        '″': '"',
    }
    for curly, straight in curly_quotes.items():
        text = text.replace(curly, straight)

    return text

def prepare_text_for_matching(text, remove_punctuation=False):
    """
    Normalize text by replacing special characters, removing extra spaces
    and line breaks, and optionally removing punctuation, then lowering.
    """
    text = normalize_text(text)
    text = text.replace('\n', ' ').strip()
    if remove_punctuation:
        text = text.translate(str.maketrans('', '', string.punctuation))
    return ' '.join(text.split()).lower()



def highlight_exact_phrase_across_lines(text, phrase):
    """
    Attempt to highlight `phrase` in `text` even if the phrase
    is split by line breaks or punctuation in the original snippet.

    Strategy:
      1) Create a 'searchable' copy by replacing newlines and punctuation with spaces.
      2) Use a regex to find `phrase` (normalized) in that unified copy.
      3) If found, highlight the corresponding substring in the *original* text
         by a naive approach: we replace the 'closest match' we can detect.
    
    This approach can still fail in complex cases but often works to unify
    slight splits (e.g. newlines, minor punctuation).
    """

    # Normalize for searching
    # We'll do a quick-and-dirty approach: remove punctuation and newlines in the "search copy"
    # but keep the original text for actual replacement.
    # We'll unify punctuation to spaces, then unify multiple spaces.
    search_copy = text.replace('\n', ' ')
    # remove common punctuation
    search_copy = re.sub(r'[.,!?;:]', ' ', search_copy)
    # unify multiple spaces
    search_copy = re.sub(r'\s+', ' ', search_copy).strip().lower()

    phrase_norm = phrase.lower().strip()

    # Now we see if phrase_norm is in search_copy
    start_idx = search_copy.find(phrase_norm)
    if start_idx == -1:
        # no match in the unified copy => fallback, no highlight
        return text

    # If found, we do a naive approach: let's do a simple 're.sub' on the *first occurrence* 
    # of that phrase in the original text ignoring line breaks. 
    # This can be done with a basic pattern build: re.escape(phrase_norm),
    # but then we need to unify the original text similarly. 
    # Simpler approach: replace the phrase in the original text's lowercased version?
    # But that breaks offsets if the text has punctuation in the middle. 
    # We'll do a partial approach:

    # We'll build a minimal pattern from phrase ignoring boundary, 
    # but re tries to match the exact substring (anywhere).
    phrase_pattern = re.escape(phrase_norm)
    
    # We'll do a case-insensitive replacement of the first occurrence:
    def single_replace_func(m):
        # The actual matched text from 'm' is the lowercased substring
        # We want to re-inject the original case from the snippet if possible
        # but let's just do a naive approach:
        matched = m.group(0)
        return f"<mark>{matched}</mark>"

    # We do a sub on 'text' but with flags=re.IGNORECASE. 
    # Because 'phrase' might not exactly match if there's punctuation in the snippet 
    # in the middle. So consider removing punctuation from 'phrase'? 
    # We'll do a naive approach to see if it helps in simpler cases:
    result, n = re.subn(
        pattern=phrase_pattern,
        repl=single_replace_func,
        string=text,
        count=1,
        flags=re.IGNORECASE
    )
    if n == 0:
        # fallback: didn't find a direct substring => just return original text
        return text

    return result

def highlight_exact_phrase(text, phrase):
    """
    Attempt to highlight 'phrase' in 'text' even if line breaks or punctuation occur inside.
    """

    # If phrase is just one word, fallback to highlight_query
    if len(phrase.strip().split()) == 1:
        return highlight_query(text, phrase)

    return highlight_exact_phrase_across_lines(text, phrase)


############################
# Highlighting
############################

def highlight_query(text, query):
    """
    Highlights all whole-word occurrences of a single query in the text.
    Uses word boundaries and escapes any special regex characters in query.
    This version is intended for single-word queries.
    """
    if not query:
        return text
    # Escape any regex special characters in query
    escaped_query = re.escape(query.strip())
    # Build a regex pattern with word boundaries and ignore-case
    pattern = re.compile(r'\b' + escaped_query + r'\b', re.IGNORECASE)
    # Replace matches with the wrapped version
    # Using pattern.sub ensures non-overlapping replacements
    highlighted_text = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", text)
    return highlighted_text

def highlight_keywords(text, query_words):
    """
    Highlights all non-stopword query words in 'text' in one pass.
    Builds a single combined regex that matches any of those words (as full words).
    """
    # Filter query_words to remove any that are stopwords or empty.
    filtered = [w.lower() for w in query_words if w and w.lower() not in STOPWORDS]
    if not filtered:
        return text

    # Build a union regex pattern for the filtered words.
    # For example, if filtered contains ["surrender", "reject"], pattern becomes:
    #   \b(?:surrender|reject)\b
    pattern_str = r'\b(?:' + '|'.join(re.escape(word) for word in filtered) + r')\b'
    pattern = re.compile(pattern_str, re.IGNORECASE)
    highlighted_text = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", text)
    return highlighted_text


############################
# Snippet Cleaning & Poetry
############################

def clean_snippet(snippet, keep_line_breaks=True):
    allowed_tags = ['br', 'mark'] if keep_line_breaks else ['mark']
    snippet = bleach.clean(snippet, tags=allowed_tags, strip=True)

    # Remove possible numeric annotations (page refs, etc.)
    snippet = re.sub(
        r'\b(?<!\.\d)(\d+)(?![\d:.])(?!\s*[ap]\.?m\.?|[\s\-]*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b)',
        '',
        snippet,
        flags=re.IGNORECASE
    )

    if not keep_line_breaks:
        snippet = snippet.replace('<br>', ' ')

    return snippet

def is_poetry(snippet):
    lines = snippet.strip().split('<br>')
    lines = [line.strip() for line in lines if line.strip()]

    if len(lines) < 2:
        return False

    line_lengths = [len(line) for line in lines]
    if len(line_lengths) < 2:
        return False

    length_variance = variance(line_lengths)
    return (length_variance > 10 and len(lines) > 3)

############################
# Snippet Extraction
############################

def extract_exact_words_snippet(
    original_text, normalized_text, query_normalized,
    start_index, end_index,
    context_window=300,
    max_chars=DEFAULT_MAX_CHARS
):
    logger.debug(f"Received start index: {start_index}, end index: {end_index} from normalized text")

    start_context = max(0, start_index - context_window)
    if start_context > 0:
        space_pos = original_text.rfind(' ', 0, start_context)
        if space_pos != -1:
            start_context = space_pos + 1

    end_context = min(len(original_text), end_index + context_window)
    if end_context < len(original_text):
        space_pos = original_text.find(' ', end_context)
        if space_pos == -1:
            space_pos = end_context
        end_context = min(len(original_text), space_pos)

    snippet = original_text[start_context:end_context]

    keep_line_breaks = is_poetry(snippet)
    cleaned_snippet = clean_snippet(snippet, keep_line_breaks)
    logger.debug(f"Exact snippet: {cleaned_snippet[:100]}...")

    # Optionally highlight the entire phrase:
    highlighted = highlight_exact_phrase(cleaned_snippet, query_normalized)
    #highlighted = highlight_query(cleaned_snippet, query_normalized)
    return highlighted[:max_chars]

def extract_all_words_snippet(
    original_text,
    query_words,
    remove_punctuation=False,
    max_chars=DEFAULT_MAX_CHARS,
    highlight=True
):
    """
    Extracts a snippet around the central position of all found query words,
    cleans it, and optionally highlights them (excluding stopwords).
    """
    normalized_text = prepare_text_for_matching(original_text, remove_punctuation)

    positions = []
    splitted = query_words.split()
    for w in splitted:
        pos = normalized_text.find(w.lower())  # compare lower
        if pos != -1:
            positions.append(pos)

    if not positions:
        logger.info("No words from the query were found in the snippet.")
        return ""

    central_index = sum(positions) // len(positions)
    start_context = max(0, central_index - max_chars // 2)
    end_context = start_context + max_chars

    # adjust start
    if start_context > 0:
        space_pos = original_text.rfind(' ', 0, start_context)
        if space_pos != -1:
            start_context = space_pos + 1

    # adjust end
    if end_context < len(original_text):
        space_pos = original_text.find(' ', end_context)
        if space_pos != -1:
            end_context = space_pos

    snippet = original_text[start_context:end_context]
    cleaned_snippet = bleach.clean(snippet, tags=[], strip=True)

    if highlight:
        # highlight all query_words except the ones in STOPWORDS
        cleaned_snippet = highlight_keywords(cleaned_snippet, splitted)

    return cleaned_snippet[:max_chars]

def extract_semantic_snippet(
    text,
    query,
    max_lines=10,
    min_chars=200,
    max_chars=DEFAULT_MAX_CHARS,
    remove_punctuation=False
):
    if len(text) > max_chars:
        end = text.rfind(' ', 0, max_chars)
        if end == -1:
            end = max_chars
        snippet = text[:end]
    else:
        snippet = text

    keep_line_breaks = is_poetry(snippet)
    cleaned_snippet = clean_snippet(snippet, keep_line_breaks)
    return cleaned_snippet

def extract_matching_sentences(
    text,
    query,
    max_lines=10,
    min_chars=200,
    max_chars=DEFAULT_MAX_CHARS,
    remove_punctuation=False
):
    lines = text.split('\n')
    normalized_query = prepare_text_for_matching(query, remove_punctuation)
    found_indices = []

    for i, line in enumerate(lines):
        line_normalized = prepare_text_for_matching(line, remove_punctuation)
        if normalized_query in line_normalized:
            found_indices.append(i)
        else:
            # check partial
            splitted = normalized_query.split()
            if any(word in line_normalized for word in splitted):
                found_indices.append(i)

    if found_indices:
        start = max(0, found_indices[0] - 5)
        end = min(len(lines), found_indices[-1] + 6)
        context_lines = lines[start:end]

        highlighted_lines = [highlight_query(line, query) for line in context_lines]
        snippet = '\n'.join(highlighted_lines)

        if len(snippet) < min_chars:
            start = max(0, start - 5)
            end = min(len(lines), end + 5)
            context_lines = lines[start:end]
            highlighted_lines = [highlight_query(line, query) for line in context_lines]
            snippet = '\n'.join(highlighted_lines)
    else:
        snippet = text[:max_chars]
        snippet = highlight_query(snippet, query)

    snippet = snippet.replace('\n', '<br/>')
    keep_line_breaks = is_poetry(snippet)
    cleaned_snippet = clean_snippet(snippet, keep_line_breaks=True)
    return cleaned_snippet[:max_chars]

############################
# Filtering
############################

def apply_filters(results, filters):
    """
    Filters results based on provided filter criteria (e.g. author, group, etc.).
    - If 'group' is 'CWM', allow 'Agenda' as well.
    """
    filtered = []
    for result in results:
        match = True
        for key, value in filters.items():
            if key == "group" and value == "CWM":
                if result.get(key) not in {"CWM", "Agenda"}:
                    match = False
                    break
            elif key not in result or result[key] != value:
                match = False
                break
        if match:
            filtered.append(result)
    return filtered

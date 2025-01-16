import logging
import re
import bleach
from nltk.tokenize import sent_tokenize
import unicodedata 
import string
from statistics import variance

# Initialize the logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)


def normalize_text(text):
    """
    Normalize Unicode characters and replace special characters.
    """
    text = unicodedata.normalize('NFKC', text)
    # Replace specific ligature characters
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
    # Replace curly quotes and other special characters
    curly_quotes = {
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",   # This replaces curly apostrophe with straight apostrophe
        '–': '-',   # En dash
        '—': '-',   # Em dash
        '…': '...', # Ellipsis
        '′': "'",   # Prime
        '″': '"',   # Double Prime
    }
    for curly, straight in curly_quotes.items():
        text = text.replace(curly, straight)

    return text


def prepare_text_for_matching(text, remove_punctuation=False):
    """
    Normalize text by replacing special characters, removing extra spaces and line breaks, and optionally removing punctuation.
    """
    text = normalize_text(text)
    text = text.replace('\n', ' ').strip()
    if remove_punctuation:
        text = text.translate(str.maketrans('', '', string.punctuation))
    return ' '.join(text.split()).lower()



def highlight_query(text, query):
    """
    Highlights exact matches of the query in the text.
    """
    # Normalize text and query
    normalized_text = prepare_text_for_matching(text)
    normalized_query = prepare_text_for_matching(query)
    
    # Escape special characters in the query and add word boundaries
    query_regex = r'\b' + re.escape(normalized_query) + r'\b'
    
    # Find all matches in the normalized text
    matches = list(re.finditer(query_regex, normalized_text, flags=re.IGNORECASE))
    
    # Offset to adjust positions due to added <mark> tags
    offset = 0
    original_text = text
    
    for match in matches:
        start, end = match.span()
        # Adjust positions based on previous replacements
        start += offset
        end += offset
        
        # Extract the original text corresponding to the matched span
        original_text_span = original_text[start:end]
        
        # Replace the original text with highlighted text
        highlighted_span = f"<mark>{original_text_span}</mark>"
        
        # Update the text with the highlighted span
        original_text = original_text[:start] + highlighted_span + original_text[end:]
        
        # Update the offset
        offset += len(highlighted_span) - (end - start)
    
    return original_text

def clean_snippet(snippet, keep_line_breaks=True):
    # Define allowed tags and attributes based on whether to keep <br> tags
    allowed_tags = ['br', 'mark'] if keep_line_breaks else ['mark']
    
    # Clean with bleach to enforce allowed tags
    snippet = bleach.clean(snippet, tags=allowed_tags, strip=True)

    # Regex to remove page numbers and unnecessary numeric annotations
    # This ignores numbers that are parts of times or dates like "1.26 a.m." or "4 December"
    snippet = re.sub(r'\b(?<!\.\d)(\d+)(?![\d:.])(?!\s*[ap]\.?m\.?|[\s\-]*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b)', '', snippet, flags=re.IGNORECASE)

    # Optionally replace <br> with space or handle them as needed
    if not keep_line_breaks:
        snippet = snippet.replace('<br>', ' ')

    return snippet


def is_poetry(snippet):
    # Normalize spaces and split into lines
    lines = snippet.strip().split('<br>')
    # Remove empty lines and strip spaces
    lines = [line.strip() for line in lines if line.strip()]

    # Check if there are enough lines to consider as poetry
    if len(lines) < 2:
        return False

    # Calculate the length of each line
    line_lengths = [len(line) for line in lines]

    # Calculate variance of line lengths; higher variance might indicate poetry
    length_variance = variance(line_lengths)

    # Check for high variance in line lengths and a minimum number of lines
    if length_variance > 10 and len(lines) > 3:
        return True

    return False


def extract_exact_words_snippet(original_text, normalized_text, query_normalized, start_index, end_index, context_window=300, max_chars=600):
    logger.debug(f"Received start index: {start_index}, end index: {end_index} from normalized text")

    # Adjust context boundaries to include complete words in the original text
    start_context = max(0, start_index - context_window)
    if start_context > 0:
        start_context = original_text.rfind(' ', 0, start_context) + 1 if original_text.rfind(' ', 0, start_context) != -1 else start_context

    end_context = min(len(original_text), end_index + context_window)
    if end_context < len(original_text):
        end_context = original_text.find(' ', end_context)
        if end_context == -1:  # If no space found, revert to the maximum length
            end_context = min(len(original_text), end_index + context_window)

    # Extract the snippet from the original text for display
    snippet = original_text[start_context:end_context]

    # Determine if the extracted snippet should preserve line breaks (poetry detection)
    logger.info(f"Exact Mateh original text: {original_text}")

    keep_line_breaks = is_poetry(snippet)
    logger.info(f"Exact Mateh keep_line_breaks: {keep_line_breaks}")
    cleaned_snippet = clean_snippet(snippet, keep_line_breaks)
    logger.info(f"Exact Mateh CleanedSnippet: {cleaned_snippet}")

    return cleaned_snippet


def extract_all_words_snippet(original_text, query_words, remove_punctuation=False, max_chars=600):
    # Normalize original text
    normalized_text = prepare_text_for_matching(original_text, remove_punctuation)

    # Find positions of each query word in the normalized text
    positions = []
    for word in query_words.split():
        pos = normalized_text.find(word)
        if pos != -1:
            positions.append(pos)

    if not positions:
        logging.info("No words from the query were found in the snippet.")
        return ""

    # Calculate the central point of all found positions
    central_index = sum(positions) // len(positions)

    # Define context window to capture around the central index
    start_context = max(0, central_index - max_chars // 2)
    end_context = start_context + max_chars

    # Adjust to not truncate words at the start
    if start_context > 0:
        start_context = original_text.rfind(' ', 0, start_context) + 1 if original_text.rfind(' ', 0, start_context) != -1 else start_context

    # Adjust to not truncate words at the end
    if end_context < len(original_text):
        space_pos = original_text.find(' ', end_context)
        if space_pos != -1:
            end_context = space_pos

    # Extract the snippet from the original text for display
    snippet = original_text[start_context:end_context]

    # Clean the snippet
    cleaned_snippet = bleach.clean(snippet, tags=[], strip=True)  # Strip all HTML tags

    # Log and return the cleaned snippet
    logging.info(f"Extracted snippet: {cleaned_snippet[:50]}...")  # Log the first 50 characters for brevity
    return cleaned_snippet


def extract_semantic_snippet(text, query, max_lines=10, min_chars=200, max_chars=600, remove_punctuation=False):
    # Trim the text to the maximum characters while preserving word boundaries
    if len(text) > max_chars:
        # Find the last space within the first max_chars to avoid cutting off a word
        end = text.rfind(' ', 0, max_chars)
        if end == -1:
            end = max_chars  # In case there's a very long word without spaces
        snippet = text[:end]
    else:
        snippet = text

    # Clean the snippet before returning
    keep_line_breaks = is_poetry(snippet)
    cleaned_snippet = clean_snippet(snippet, keep_line_breaks)

    return cleaned_snippet


def extract_matching_sentences(text, query, max_lines=10, min_chars=200, max_chars=600, remove_punctuation=False):
    lines = text.split('\n')
    normalized_query = prepare_text_for_matching(query, remove_punctuation)
    found_indices = []
    
    # Modified search logic
    for i, line in enumerate(lines):
        line_normalized = prepare_text_for_matching(line, remove_punctuation)
        # Check if the entire normalized query appears in the normalized line
        if normalized_query in line_normalized:
            found_indices.append(i)
        # As a fallback, check for individual words
        elif any(word in line_normalized for word in normalized_query.split()):
            found_indices.append(i)
            
    if found_indices:
        start = max(0, found_indices[0] - 5)
        end = min(len(lines), found_indices[-1] + 6)
        context_lines = lines[start:end]
        highlighted_lines = [highlight_query(line, query) for line in context_lines]
        snippet = '\n'.join(highlighted_lines)
        
        # Ensure snippet meets min_chars requirement
        if len(snippet) < min_chars:
            start = max(0, start - 5)
            end = min(len(lines), end + 5)
            context_lines = lines[start:end]
            highlighted_lines = [highlight_query(line, query) for line in context_lines]
            snippet = '\n'.join(highlighted_lines)
    else:
        # If no matching line is found, return the beginning of the text
        snippet = text[:max_chars]
        snippet = highlight_query(snippet, query)

    # Replace newlines with '<br/>'
    snippet = snippet.replace('\n', '<br/>')

    # Clean the snippet before returning
    keep_line_breaks = is_poetry(snippet)
    cleaned_snippet = clean_snippet(snippet, keep_line_breaks=True)

    # Truncate to max_chars to ensure length limits
    final_snippet = cleaned_snippet[:max_chars]

    return final_snippet


def apply_filters(results, filters):
    """
    Filters results based on provided filter criteria.
    
    Parameters:
        results (list): List of result dictionaries.
        filters (dict): Filters with keys such as 'author', 'group', etc.
    
    Returns:
        list: Filtered results.
    """
    filtered = []
    for result in results:
        match = True
        for key, value in filters.items():
            if key == "group" and value == "CWM":
                # Include results with group "CWM" or "Agenda" when "CWM" is the selected filter
                if result.get(key) not in {"CWM", "Agenda"}:
                    match = False
                    break
            elif key not in result or result[key] != value:
                match = False
                break
        if match:
            filtered.append(result)
    return filtered
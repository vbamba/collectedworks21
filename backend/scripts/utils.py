import logging
import re
import bleach
from nltk.tokenize import sent_tokenize
import unicodedata 


# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
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

def prepare_text_for_matching(text):
    """
    Normalize text by replacing special characters, removing extra spaces and line breaks.
    """
    text = normalize_text(text)
    text = text.replace('\n', ' ')
    text = ' '.join(text.split())  # Remove extra spaces
    return text.lower()


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


def extract_matching_sentences(text, query, max_lines=10, min_chars=200, max_chars=500):
    lines = text.split('\n')
    normalized_query = prepare_text_for_matching(query)
    found_indices = []
    
    # Modified search logic
    for i, line in enumerate(lines):
        line_normalized = prepare_text_for_matching(line)
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
    # Allow only <br> and <mark> tags
    allowed_tags = ['br', 'mark']
    snippet = bleach.clean(snippet, tags=allowed_tags, strip=True)
    # Truncate to max_chars
    snippet = snippet[:max_chars]
    return snippet


def extract_matching_sentences_last(text, query, max_lines=10, min_chars=200, max_chars=500):
    lines = text.split('\n')
    query_words = prepare_text_for_matching(query).split()
    found_indices = []
    for i, line in enumerate(lines):
        line_normalized = prepare_text_for_matching(line)
        if all(word in line_normalized for word in query_words):
            found_indices.append(i)
            # Don't break here; we may want multiple matches
        elif any(word in line_normalized for word in query_words):
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
    # Allow only <br> and <mark> tags
    allowed_tags = ['br', 'mark']
    snippet = bleach.clean(snippet, tags=allowed_tags, strip=True)
    # Truncate to max_chars
    snippet = snippet[:max_chars]
    return snippet


def extract_matching_sentences_lm(text, query, max_lines=10, min_chars=200, max_chars=500):
    query_lower = query.lower()
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if query_lower in line.lower():
            start = max(0, i - 5)  # Adjust the number of lines before the match
            end = min(len(lines), i + 5)  # Adjust the number of lines after the match
            context_lines = lines[start:end]
            highlighted_lines = [highlight_query(line.strip(), query) for line in context_lines]
            snippet = '\n'.join(highlighted_lines)
            # Ensure snippet meets min_chars requirement
            if len(snippet) < min_chars:
                start = max(0, start - 5)
                end = min(len(lines), end + 5)
                context_lines = lines[start:end]
                highlighted_lines = [highlight_query(line.strip(), query) for line in context_lines]
                snippet = '\n'.join(highlighted_lines)
            # Replace newlines with '<br/>'
            snippet = snippet.replace('\n', '<br/>')
            # Allow only <br> and <mark> tags
            allowed_tags = ['br', 'mark']
            snippet = bleach.clean(snippet, tags=allowed_tags, strip=True)
            # Truncate to max_chars
            snippet = snippet[:max_chars]
            return snippet
    # If no matching line is found
    snippet = text[:max_chars]
    snippet = snippet.replace('\n', '<br/>')
    allowed_tags = ['br', 'mark']
    snippet = bleach.clean(snippet, tags=allowed_tags, strip=True)
    return highlight_query(snippet, query)

def extract_matching_sentences_tokenize(text, query, max_sentences=5, min_chars=200, max_chars=500):
    query_lower = query.lower()
    sentences = sent_tokenize(text)
    for i, sentence in enumerate(sentences):
        if query_lower in sentence.lower():
            start = max(0, i - 2)
            end = min(len(sentences), i + 3)
            context_sentences = sentences[start:end]
            highlighted_sentences = [highlight_query(s.strip(), query) for s in context_sentences]
            snippet = ' '.join(highlighted_sentences)
            if len(snippet) < min_chars:
                start = max(0, start - 2)
                end = min(len(sentences), end + 2)
                context_sentences = sentences[start:end]
                highlighted_sentences = [highlight_query(s.strip(), query) for s in context_sentences]
                snippet = ' '.join(highlighted_sentences)
            return snippet[:max_chars]
    snippet = text[:max_chars]
    snippet = snippet.replace('\n', '<br/>')
    # Allow only <br> and <mark> tags
    allowed_tags = ['br', 'mark']
    snippet = bleach.clean(snippet, tags=allowed_tags, strip=True)    
    return highlight_query(snippet, query)

def apply_filters(results, filters):
    filtered = []
    for result in results:
        match = True
        for key, value in filters.items():
            if key not in result or result[key] != value:
                match = False
                break
        if match:
            filtered.append(result)
    return filtered

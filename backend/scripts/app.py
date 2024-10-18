from flask import Flask, request, jsonify, send_from_directory, Response, render_template
import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import re
import nltk
import json
from flask_cors import CORS
import unicodedata
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Initialize NLTK
nltk.download('punkt', quiet=True)
from nltk.tokenize import sent_tokenize

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})   # Adjust the origin as needed

# Configuration
INDEX_PATH = '/Users/vbamba/Projects/collectedworks/indexes/faiss_index.bin'
METADATA_PATH = '/Users/vbamba/Projects/collectedworks/indexes/metadata.json'
BOOK_MAPPING_PATH = '/Users/vbamba/Projects/collectedworks/indexes/book_mapping.json'
PDF_DIRECTORY = '/Users/vbamba/Projects/collectedworks/pdfs'  # Absolute path to PDFs
BASE_PDF_URL = 'http://127.0.0.1:5000/pdfs'  # Adjust based on your server's URL

# Load the model and FAISS index at startup
logging.info("Loading SentenceTransformer model...")
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
logging.info("Model loaded.")

logging.info("Loading FAISS index...")
try:
    index = faiss.read_index(INDEX_PATH)
    logging.info("FAISS index loaded successfully.")
except Exception as e:
    logging.error(f"Error loading FAISS index from {INDEX_PATH}: {e}")
    index = None

logging.info("Loading metadata...")
try:
    with open(METADATA_PATH, 'r', encoding='utf-8') as meta_file:
        metadata = json.load(meta_file)
    logging.info("Metadata loaded successfully.")
except Exception as e:
    logging.error(f"Error loading metadata from {METADATA_PATH}: {e}")
    metadata = []

# Load book mapping
logging.info("Loading book mapping...")
try:
    with open(BOOK_MAPPING_PATH, 'r', encoding='utf-8') as bm_file:
        book_mapping = json.load(bm_file)
    logging.info("Book mapping loaded successfully.")
except Exception as e:
    logging.error(f"Error loading book mapping from {BOOK_MAPPING_PATH}: {e}")
    book_mapping = {}

def highlight_query(text, query):
    # Escape special characters in query for regex
    query_regex = re.escape(query)
    # Use regex to ignore case and match the query, wrap in HTML <mark> tags
    highlighted_text = re.sub(f'({query_regex})', r'<mark>\1</mark>', text, flags=re.IGNORECASE)
    return highlighted_text

def extract_matching_sentences(text, query, max_sentences=5, min_chars=200, max_chars=500):
    """Return the sentences containing the query in the text, ensuring a minimum snippet length."""
    query_lower = query.lower()
    # Split text into sentences
    sentences = sent_tokenize(text)
    for i, sentence in enumerate(sentences):
        if query_lower in sentence.lower():
            # Include context sentences
            start = max(0, i - 2)
            end = min(len(sentences), i + 3)
            context_sentences = sentences[start:end]
            # Highlight query in sentences
            highlighted_sentences = [highlight_query(s.strip(), query) for s in context_sentences]
            snippet = ' '.join(highlighted_sentences)
            # Ensure minimum snippet length
            if len(snippet) < min_chars:
                # Expand context further
                start = max(0, start - 2)
                end = min(len(sentences), end + 2)
                context_sentences = sentences[start:end]
                highlighted_sentences = [highlight_query(s.strip(), query) for s in context_sentences]
                snippet = ' '.join(highlighted_sentences)
            return snippet[:max_chars]
    # If no matching sentences, return default snippet
    snippet = text[:max_chars]
    snippet = highlight_query(snippet, query)
    return snippet

def apply_filters(results, filters):
    """
    Apply additional filters to the search results based on metadata attributes.
    """
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

def search(query, top_k=10, filters=None, search_type='both'):
    logging.info(f"Initiating search for query: '{query}' with filters: {filters} and search_type: '{search_type}'")
    # Initialize filters if not provided
    if filters is None:
        filters = {}

    # Step 1: Exact match search
    exact_matches = []
    exact_match_indices = set()
    query_lower = query.lower()
    for idx, meta in enumerate(metadata):
        # Apply filters
        filter_out = False
        for key, value in filters.items():
            if meta.get(key) != value:
                filter_out = True
                break
        if filter_out:
            continue  # Skip if the metadata doesn't match the filters

        snippet_lower = meta['snippet'].lower()
        if query_lower in snippet_lower:
            snippet = extract_matching_sentences(meta['snippet'], query, max_sentences=3, min_chars=200, max_chars=500)
            # Preserve line breaks in the snippet
            snippet = snippet.replace('\n', '<br>')
            exact_matches.append({
                'file_path': meta['file_path'],
                'pdf_url': meta['pdf_url'],                 
                'book_title': meta.get('book_title', 'Unknown'),
                'author': meta.get('author', 'Unknown'),
                'group': meta.get('group', 'Unknown'),
                'priority': meta.get('priority', 999),
                'chapter_name': meta.get('chapter_name', 'N/A'),
                'page_number': meta.get('page_number', 'N/A'),
                'snippet': snippet,  # Display matching lines for exact match
                'distance': 0.0,      # Exact match is given a distance of 0
            })
            exact_match_indices.add(idx)
            logging.debug(f"Exact match found in {meta['file_path']} on page {meta['page_number']}")

    logging.info(f"Found {len(exact_matches)} exact matches.")

    if search_type == 'exact':
        # Return only exact matches, sorted by priority
        combined_results = sorted(exact_matches, key=lambda x: x['priority'])
        logging.info(f"Returning top {min(top_k, len(combined_results))} exact matches.")
        return combined_results[:top_k]

    # Step 2: Semantic search using FAISS
    if index is None:
        logging.error("FAISS index is not loaded. Cannot perform semantic search.")
        return exact_matches[:top_k]

    try:
        query_embedding = model.encode(query, convert_to_numpy=True).astype('float32')
        query_embedding = np.expand_dims(query_embedding, axis=0)
        distances, indices = index.search(query_embedding, top_k * 3)  # Search for more to account for filtering
        logging.info(f"FAISS search completed. Retrieved {len(indices[0])} results.")
    except Exception as e:
        logging.error(f"Error during FAISS search: {e}")
        return exact_matches[:top_k]

    semantic_matches = []
    for i, idx in enumerate(indices[0]):
        if idx in exact_match_indices:
            continue  # Skip duplicates

        if idx >= len(metadata):
            logging.warning(f"Index {idx} out of bounds for metadata.")
            continue

        meta = metadata[idx]

        # Apply filters
        filter_out = False
        for key, value in filters.items():
            if meta.get(key) != value:
                filter_out = True
                break
        if filter_out:
            continue

        snippet = extract_matching_sentences(meta['snippet'], query, max_sentences=3, min_chars=200, max_chars=500)
        # Preserve line breaks in the snippet
        snippet = snippet.replace('\n', '<br>')
        semantic_matches.append({
            'file_path': meta['file_path'],
            'pdf_url': meta['pdf_url'],  
            'book_title': meta.get('book_title', 'Unknown'),
            'author': meta.get('author', 'Unknown'),
            'group': meta.get('group', 'Unknown'),
            'priority': meta.get('priority', 999),
            'chapter_name': meta.get('chapter_name', 'N/A'),
            'page_number': meta.get('page_number', 'N/A'),
            'snippet': snippet,  # Display matching lines or default snippet
            'distance': float(distances[0][i]),
        })
        logging.debug(f"Semantic match found in {meta['file_path']} on page {meta['page_number']} with distance {distances[0][i]}")

        if len(semantic_matches) >= top_k - len(exact_matches):
            break  # Limit to top_k results

    logging.info(f"Found {len(semantic_matches)} semantic matches.")

    if search_type == 'similarity':
        # Return only semantic matches, sorted by priority and distance
        combined_results = sorted(semantic_matches, key=lambda x: (x['priority'], x['distance']))
        logging.info(f"Returning top {min(top_k, len(combined_results))} semantic matches.")
        return combined_results[:top_k]

    # Combine exact matches with semantic matches
    combined_results = exact_matches + semantic_matches

    # Remove duplicates based on snippet content
    unique_results = []
    seen_snippets = set()
    for result in combined_results:
        snippet_key = result['snippet']  # You can also use a hash of the snippet
        if snippet_key not in seen_snippets:
            seen_snippets.add(snippet_key)
            unique_results.append(result)
        if len(unique_results) >= top_k:
            break

    # Sort combined results first by priority, then by distance
    unique_results = sorted(unique_results, key=lambda x: (x['priority'], x['distance']))

    logging.info(f"Returning total {len(unique_results)} unique results.")
    return unique_results[:top_k]

@app.route('/search', methods=['GET'])
def search_api():
    query = request.args.get('query', '').strip()
    search_type = request.args.get('search_type', 'both')  # Options: 'exact', 'similarity', 'both'
    top_k = int(request.args.get('top_k', 10))

    # Extract filter parameters from the request
    # Supported filters: author, group, book_title
    filters = {}
    author = request.args.get('author', None)
    group = request.args.get('group', None)
    book_title = request.args.get('book_title', None)

    if author:
        filters['author'] = author
    if group:
        filters['group'] = group
    if book_title:
        filters['book_title'] = book_title

    logging.info(f"Received search request: query='{query}', search_type='{search_type}', top_k={top_k}, filters={filters}")

    if not query:
        logging.warning("Search query is missing.")
        return jsonify({"error": "Query parameter is required."}), 400

    try:
        search_results = search(query, top_k=top_k, filters=filters, search_type=search_type)
        logging.info(f"Search completed. Returning {len(search_results)} results.")
    except Exception as e:
        logging.error(f"Error during search: {e}")
        return jsonify({"error": "An error occurred during the search."}), 500

    # Use json.dumps with ensure_ascii=False and set charset=utf-8
    return app.response_class(
        response=json.dumps(search_results, ensure_ascii=False),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/filters', methods=['GET'])
def get_filters():
    """
    Endpoint to retrieve unique filter options from book_mapping.json
    """
    logging.info("Received request for filters.")
    authors = set()
    groups = set()
    book_titles = set()

    for book_info in book_mapping.values():
        authors.add(book_info.get('author', 'Unknown'))
        groups.add(book_info.get('group', 'Unknown'))
        book_titles.add(book_info.get('book_title', 'Unknown'))

    filters = {
        'authors': sorted(authors),
        'groups': sorted(groups),
        'book_titles': sorted(book_titles)
    }

    logging.info("Filters generated successfully.")
    return jsonify(filters), 200

# Route to serve PDF files
@app.route('/pdfs/<path:filename>')
def serve_pdf(filename):
    """
    Serve PDF files from the PDF_DIRECTORY, including subdirectories.
    """
    logging.info(f"Serving PDF file: {filename}")
    try:
        return send_from_directory(PDF_DIRECTORY, filename, as_attachment=False)
    except FileNotFoundError:
        logging.error(f"File not found: {filename}")
        return jsonify({'error': 'File not found.'}), 404

if __name__ == '__main__':
    logging.info("Starting Flask server...")
    app.run(debug=True)

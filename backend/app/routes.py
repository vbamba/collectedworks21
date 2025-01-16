# routes.py

import logging
from flask import Blueprint, request, jsonify, send_from_directory
import json
from pathlib import Path
import os
from dotenv import load_dotenv

from scripts.search import search
from scripts.utils import apply_filters  # if needed
import nltk

# Ensure NLTK looks in the correct directory for its data (adjust path if needed)
nltk.data.path.append('/Users/vbamba/nltk_data')

main = Blueprint('main', __name__)

# Load environment variables
load_dotenv()

# Determine base directory
BASE_DIR = Path(__file__).resolve().parent.parent
app_logger = logging.getLogger('main')
app_logger.info(f"Base Dir='{BASE_DIR}'")

# Construct relative paths using environment variables
faiss_index_path = BASE_DIR / os.getenv('FAISS_INDEX_PATH')
metadata_path = BASE_DIR / os.getenv('METADATA_PATH')
book_mapping_path = BASE_DIR / os.getenv('BOOK_MAPPING_PATH')

app_logger.info(f"Faiss Index Path='{faiss_index_path}'")

# Verify existence of critical files
if not faiss_index_path.exists():
    app_logger.error(f"FAISS index file not found at '{faiss_index_path}'")
    raise FileNotFoundError(f"FAISS index file not found at '{faiss_index_path}'")

if not metadata_path.exists():
    app_logger.error(f"Metadata file not found at '{metadata_path}'")
    raise FileNotFoundError(f"Metadata file not found at '{metadata_path}'")

if not book_mapping_path.exists():
    app_logger.error(f"Book mapping file not found at '{book_mapping_path}'")
    raise FileNotFoundError(f"Book mapping file not found at '{book_mapping_path}'")


@main.route('/api/pdfs/<path:filename>', methods=['GET'])
def serve_pdf(filename):
    """
    Serve PDF files from the PDF_DIRECTORY, including subdirectories.
    """
    PDF_DIRECTORY = BASE_DIR / os.getenv('PDF_DIRECTORY', 'pdf')  # Default to 'pdf'
    logging.info(f"Serving PDF file: {filename} from directory: {PDF_DIRECTORY}")
    try:
        return send_from_directory(PDF_DIRECTORY, filename, as_attachment=False)
    except FileNotFoundError:
        logging.error(f"File not found: {filename} in directory: {PDF_DIRECTORY}")
        return jsonify({'error': 'File not found.'}), 404


@main.route('/api/filters', methods=['GET'])
def get_filters():
    app_logger.info("Fetching filters")
    try:
        with open(book_mapping_path, 'r', encoding='utf-8') as f:
            book_mapping = json.load(f)
        app_logger.info("Book mapping loaded successfully.")
    except Exception as e:
        app_logger.error(f"Error loading book mapping: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

    # Define sorted group order
    group_order = ["CWSA", "CWM", "Disciples"]
    
    # Gather groups from book_mapping
    groups = sorted(
        list({info['group'] for info in book_mapping.values()}),
        key=lambda x: group_order.index(x) if x in group_order else len(group_order)
    )

    # Organize book titles by group
    book_titles_by_group = {}
    for group in groups:
        book_titles_by_group[group] = sorted(
            [info['book_title'] for info in book_mapping.values() if info['group'] == group]
        )

    # Flatten book titles for default display (sorted by group)
    all_books_sorted = [
        title 
        for group in groups 
        for title in book_titles_by_group[group]
    ]

    app_logger.info("Filters fetched successfully")
    return jsonify({
        "authors": sorted({info['author'] for info in book_mapping.values()}),
        "groups": groups,
        "book_titles": all_books_sorted,
        "book_titles_by_group": book_titles_by_group
    })


@main.route('/api/search', methods=['GET'])
def search_api():
    query = request.args.get('query', '')
    top_k = int(request.args.get('top_k', 100))
    search_type = request.args.get('search_type', 'all')
    
    filters = {
        'author': request.args.get('author', ''),
        'group': request.args.get('group', ''),
        'book_title': request.args.get('book_title', ''),
    }
    # Remove empty filter keys
    filters = {k: v for k, v in filters.items() if v}

    app_logger.info(f"Received search request: query='{query}', filters={filters}, top_k={top_k}, search_type={search_type}")

    if not query:
        return jsonify({"error": "Query parameter is required."}), 400

    try:
        # Run the main search function
        search_results = search(
            query=query,
            index_path=str(faiss_index_path),
            metadata_path=str(metadata_path),
            top_k=top_k,
            filters=filters,
            search_type=search_type
        )
        app_logger.info(f"Search completed with {len(search_results)} results")
    except Exception as e:
        app_logger.error(f"Error during search: {e}", exc_info=True)
        return jsonify({"error": "An error occurred during the search."}), 500

    # --------------------------------------
    # Build group counts from the results
    # --------------------------------------
    group_counts = {}
    for result in search_results:
        grp = result.get('group', 'Unknown')
        group_counts[grp] = group_counts.get(grp, 0) + 1

    # Return both the search results and the group counts
    return jsonify({
        "results": search_results,
        "group_counts": group_counts
    }), 200

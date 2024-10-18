# backend/app/routes.py
import logging
from flask import Blueprint, request, jsonify
import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from pathlib import Path
import os
from dotenv import load_dotenv

main = Blueprint('main', __name__)

# Load environment variables
load_dotenv()

# Determine base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Construct relative paths using environment variables
faiss_index_path = BASE_DIR / os.getenv('FAISS_INDEX_PATH')
metadata_path = BASE_DIR / os.getenv('METADATA_PATH')
book_mapping_path = BASE_DIR / os.getenv('BOOK_MAPPING_PATH')

# Initialize model and FAISS index
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

index = faiss.read_index(str(faiss_index_path))
with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

@main.route('/filters', methods=['GET'])
def get_filters():
    app_logger = logging.getLogger('main.get_filters')
    app_logger.info("Fetching filters")

    with open(book_mapping_path, 'r', encoding='utf-8') as f:
        book_mapping = json.load(f)

    authors = list(set([info['author'] for info in book_mapping.values()]))
    groups = list(set([info['group'] for info in book_mapping.values()]))
    book_titles = list(set([info['book_title'] for info in book_mapping.values()]))

    app_logger.info("Filters fetched successfully")
    return jsonify({
        "authors": authors,
        "groups": groups,
        "book_titles": book_titles
    })

@main.route('/search', methods=['GET'])
def search():
    app_logger = logging.getLogger('main.search')
    query = request.args.get('query', '')
    author = request.args.get('author', '')
    group = request.args.get('group', '')
    book_title = request.args.get('book_title', '')
    top_k = int(request.args.get('top_k', 100))

    app_logger.info(f"Received search request: query='{query}', author='{author}', group='{group}', book_title='{book_title}', top_k={top_k}")

    # Generate query embedding
    query_embedding = model.encode(query, convert_to_numpy=True).astype('float32')
    query_embedding = np.expand_dims(query_embedding, axis=0)

    # Perform search
    distances, indices = index.search(query_embedding, top_k)

    results = []
    for distance, idx in zip(distances[0], indices[0]):
        if idx < len(metadata):
            entry = metadata[idx]
            # Apply filters
            if (author and entry['author'] != author) or \
               (group and entry['group'] != group) or \
               (book_title and entry['book_title'] != book_title):
                continue
            results.append(entry)

    app_logger.info(f"Search completed with {len(results)} results")
    return jsonify({"results": results})

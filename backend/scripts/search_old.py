# search.py

import faiss
import json
import numpy as np
import logging
from sentence_transformers import SentenceTransformer
from functools import lru_cache
from .utils import extract_matching_sentences, apply_filters, prepare_text_for_matching


# Initialize the logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("search.log"),
        logging.StreamHandler()
    ]
)

@lru_cache(maxsize=1)
def load_faiss_index_cached(index_path):
    """
    Caches the loaded FAISS index to avoid redundant disk I/O operations.
    """
    try:
        logger.info(f"Loading FAISS index from {index_path}")
        index = faiss.read_index(index_path)
        logger.info("FAISS index loaded successfully.")
        return index
    except Exception as e:
        logger.error(f"Error loading FAISS index: {e}", exc_info=True)
        raise RuntimeError(f"Error loading FAISS index: {e}")

@lru_cache(maxsize=1)
def load_metadata_cached(metadata_path):
    """
    Caches the loaded metadata to avoid redundant disk I/O operations.
    """
    try:
        logger.info(f"Loading metadata from {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        logger.info("Metadata loaded successfully.")
        return metadata
    except Exception as e:
        logger.error(f"Error loading metadata: {e}", exc_info=True)
        raise RuntimeError(f"Error loading metadata: {e}")

@lru_cache(maxsize=1)
def initialize_model_cached(model_name='sentence-transformers/all-mpnet-base-v2'):
    """
    Caches the SentenceTransformer model to avoid reloading it multiple times.
    """
    try:
        logger.info(f"Loading SentenceTransformer model '{model_name}'")
        model = SentenceTransformer(model_name)
        logger.info("Model loaded successfully.")
        return model
    except Exception as e:
        logger.error(f"Error loading model: {e}", exc_info=True)
        raise RuntimeError(f"Error loading model: {e}")

@lru_cache(maxsize=1024)
def get_query_embedding_cached(query, model_name='sentence-transformers/all-mpnet-base-v2'):
    """
    Caches the embeddings of queries to avoid redundant computations.
    """
    try:
        model = initialize_model_cached(model_name)
        # Wrap the query in a list to get a 2D array
        embedding = model.encode([query], convert_to_numpy=True).astype('float32')
        faiss.normalize_L2(embedding)
        return embedding  # Returns a 2D array of shape (1, d)
    except Exception as e:
        logger.error(f"Error generating embedding for query '{query}': {e}", exc_info=True)
        raise RuntimeError(f"Error generating embedding for query '{query}': {e}")

def search(query, index_path, metadata_path, top_k=10, filters=None, search_type='both', 
           model_name='sentence-transformers/all-mpnet-base-v2', min_snippet_length=20):
    """
    Performs a search on the FAISS index with exact match, all words match, and semantic matching.

    Parameters:
    - query (str): The search query.
    - index_path (str): Path to the FAISS index file.
    - metadata_path (str): Path to the metadata JSON file.
    - top_k (int): Number of top results to return.
    - filters (dict): Filters to apply on the search results.
    - search_type (str): 'both', 'exact', or 'semantic'.
    - model_name (str): Name of the SentenceTransformer model to use.
    - min_snippet_length (int): Minimum length of snippet to include.

    Returns:
    - List of search results containing metadata and relevance scores.
    """
    logger.info(f"Starting search for query: '{query}' with top_k={top_k}, filters={filters}, search_type={search_type}")

    if filters is None:
        filters = {}

    # Load FAISS index and metadata using caching
    index = load_faiss_index_cached(index_path)
    metadata = load_metadata_cached(metadata_path)

    # Initialize the model using caching
    model = initialize_model_cached(model_name)

    # Normalize the query
    query_normalized = prepare_text_for_matching(query)
    query_words = query_normalized.split()
    query_words_set = set(query_words)

    # Sets to keep track of matched indices
    matched_indices = set()

    # Step 1: Exact match search
    exact_matches = []
    logger.info("Performing exact match search...")

    for idx, meta in enumerate(metadata):
        # Apply filters before checking the snippet
        if apply_filters([meta], filters):
            # Normalize the snippet
            snippet_normalized = prepare_text_for_matching(meta['snippet'])
            if query_normalized in snippet_normalized:
                snippet = extract_matching_sentences(meta['snippet'], query)
                if len(snippet) >= min_snippet_length:
                    exact_matches.append({
                        'author': meta.get('author', 'Unknown'),
                        'book_title': meta.get('book_title', 'Unknown'),
                        'chapter_name': meta.get('chapter_name', 'N/A'),
                        'file_path': meta.get('file_path', ''),
                        'group': meta.get('group', 'Unknown'),
                        'page_number': meta.get('page_number', 'N/A'),
                        'pdf_url': meta.get('pdf_url', ''),
                        'priority': meta.get('priority', 0),  # Use metadata priority
                        'category_priority': 1,  # Highest priority for exact matches
                        'snippet': snippet,
                        'distance': 0.0  # Exact match has zero distance
                    })
                    matched_indices.add(idx)
                    logger.debug(f"Exact match found at index {idx}")
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")

    logger.info(f"Exact matches found: {len(exact_matches)}")

    # Step 2: All words match search
    all_words_matches = []
    logger.info("Performing all words match search...")

    for idx, meta in enumerate(metadata):
        if idx in matched_indices:
            continue  # Skip already matched indices
        if apply_filters([meta], filters):
            # Normalize the snippet
            snippet_normalized = prepare_text_for_matching(meta['snippet'])
            snippet_words_set = set(snippet_normalized.split())
            if query_words_set.issubset(snippet_words_set):
                snippet = extract_matching_sentences(meta['snippet'], query)
                if len(snippet) >= min_snippet_length:
                    # Check if this index is also in the semantic matches
                    is_in_semantic = False  # Will be set later
                    all_words_matches.append({
                        'idx': idx,  # Keep track of the index
                        'author': meta.get('author', 'Unknown'),
                        'book_title': meta.get('book_title', 'Unknown'),
                        'chapter_name': meta.get('chapter_name', 'N/A'),
                        'file_path': meta.get('file_path', ''),
                        'group': meta.get('group', 'Unknown'),
                        'page_number': meta.get('page_number', 'N/A'),
                        'pdf_url': meta.get('pdf_url', ''),
                        'priority': meta.get('priority', 0),  # Use metadata priority
                        'category_priority': 3,  # Initial priority for all words matches
                        'snippet': snippet,
                        'distance': 0.1  # Distance will be updated if in semantic matches
                    })
                    matched_indices.add(idx)
                    logger.debug(f"All words match found at index {idx}")
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")

    logger.info(f"All words matches found: {len(all_words_matches)}")

    if search_type == 'exact':
        combined_results = exact_matches
        logger.info(f"Returning exact matches only, limited to top_k={top_k}")
    else:
        # Step 3: Semantic search using FAISS
        logger.info("Performing semantic search using FAISS...")
        try:
            query_embedding = get_query_embedding_cached(query, model_name)
            distances, indices = index.search(query_embedding, top_k * 5)  # Fetch more results to filter later
            logger.info(f"FAISS search completed. Retrieved {len(indices[0])} results.")
        except Exception as e:
            logger.error(f"Error during FAISS search: {e}", exc_info=True)
            raise RuntimeError(f"Error during FAISS search: {e}")

        semantic_matches = []
        semantic_indices = set()
        for distance, idx in zip(distances[0], indices[0]):
            if idx in matched_indices:
                continue  # Skip already matched indices
            if idx >= len(metadata):
                logger.warning(f"FAISS index {idx} out of bounds for metadata length {len(metadata)}")
                continue

            meta = metadata[idx]
            semantic_indices.add(idx)

            # Apply filters after semantic search
            if apply_filters([meta], filters):
                snippet = extract_matching_sentences(meta['snippet'], query)
                if len(snippet) >= min_snippet_length:
                    semantic_matches.append({
                        'idx': idx,  # Keep track of the index
                        'author': meta.get('author', 'Unknown'),
                        'book_title': meta.get('book_title', 'Unknown'),
                        'chapter_name': meta.get('chapter_name', 'N/A'),
                        'file_path': meta.get('file_path', ''),
                        'group': meta.get('group', 'Unknown'),
                        'page_number': meta.get('page_number', 'N/A'),
                        'pdf_url': meta.get('pdf_url', ''),
                        'priority': meta.get('priority', 0),  # Use metadata priority
                        'category_priority': 4,  # Priority for semantic matches
                        'snippet': snippet,
                        'distance': float(distance)
                    })
                    matched_indices.add(idx)
                    logger.debug(f"Semantic match found at index {idx} with distance {distance}")
            else:
                logger.debug(f"Metadata at index {idx} did not pass filters.")

        logger.info(f"Semantic matches found: {len(semantic_matches)}")

        # Update category_priority for all words matches that are also in semantic matches
        for result in all_words_matches:
            if result['idx'] in semantic_indices:
                result['category_priority'] = 2  # Higher priority for combined matches
                # Update distance from semantic match
                for sem_result in semantic_matches:
                    if sem_result['idx'] == result['idx']:
                        result['distance'] = sem_result['distance']
                        break

        # Remove updated all words matches from semantic matches to avoid duplicates
        semantic_matches = [res for res in semantic_matches if res['idx'] not in [r['idx'] for r in all_words_matches]]

        # Combine exact, updated all words, and semantic matches
        combined_results = exact_matches + all_words_matches + semantic_matches

    # Remove 'idx' from results as it's no longer needed
    for res in combined_results:
        res.pop('idx', None)

    # Sort combined results by:
    # 1. category_priority (lower is better)
    # 2. metadata priority (higher is better)
    # 3. distance (lower is better)
    sorted_results = sorted(
        combined_results, 
        key=lambda x: (
            x['category_priority'], 
            -x['priority'],        # Negate priority to sort higher values first
            x['distance'] if x['distance'] is not None else float('inf')
        )
    )

    # Return top_k results
    final_results = sorted_results[:top_k]

    logger.info(f"Returning combined and sorted results. Total results: {len(final_results)}")

    return final_results


def search_last(query, index_path, metadata_path, top_k=10, filters=None, search_type='both', model_name='sentence-transformers/all-mpnet-base-v2', min_snippet_length=20):
    logger.info(f"Starting search for query: '{query}' with top_k={top_k}, filters={filters}, search_type={search_type}")

    if filters is None:
        filters = {}

    # Load FAISS index and metadata using caching
    index = load_faiss_index_cached(index_path)
    metadata = load_metadata_cached(metadata_path)

    # Initialize the model using caching
    model = initialize_model_cached(model_name)

    # Step 1: Exact match search
    exact_matches = []
    query_lower = query.lower()
    query_normalized = prepare_text_for_matching(query)
    logger.info("Performing exact match search...")

    for idx, meta in enumerate(metadata):
        if apply_filters([meta], filters):
            snippet_normalized = prepare_text_for_matching(meta['snippet'])
            if query_normalized in snippet_normalized:
                snippet = extract_matching_sentences(meta['snippet'], query)
                if len(snippet.strip()) >= min_snippet_length:
                    exact_matches.append({
                        'idx': idx,
                        'author': meta.get('author', 'Unknown'),
                        'book_title': meta.get('book_title', 'Unknown'),
                        'chapter_name': meta.get('chapter_name', 'N/A'),
                        'file_path': meta.get('file_path', ''),
                        'group': meta.get('group', 'Unknown'),
                        'page_number': meta.get('page_number', 'N/A'),
                        'pdf_url': meta.get('pdf_url', ''),
                        'priority': meta.get('priority', 1),
                        'snippet': snippet,
                        'distance': 0.0
                    })
                    logger.debug(f"Exact match found at index {idx}")
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")

    logger.info(f"Exact matches found: {len(exact_matches)}")

    if search_type == 'exact':
        logger.info(f"Returning exact matches only, limited to top_k={top_k}")
        for result in exact_matches:
            result.pop('idx', None)
        return exact_matches[:top_k]

    # Step 2: All words match search
    all_words_matches = []
    query_words = query_normalized.split()
    indices_already_included = set(em['idx'] for em in exact_matches)

    logger.info("Performing 'all words' match search...")

    for idx, meta in enumerate(metadata):
        if idx in indices_already_included:
            continue

        if apply_filters([meta], filters):
            snippet_normalized = prepare_text_for_matching(meta['snippet'])
            if all(word in snippet_normalized for word in query_words):
                snippet = extract_matching_sentences(meta['snippet'], query)
                if len(snippet.strip()) >= min_snippet_length:
                    all_words_matches.append({
                        'idx': idx,
                        'author': meta.get('author', 'Unknown'),
                        'book_title': meta.get('book_title', 'Unknown'),
                        'chapter_name': meta.get('chapter_name', 'N/A'),
                        'file_path': meta.get('file_path', ''),
                        'group': meta.get('group', 'Unknown'),
                        'page_number': meta.get('page_number', 'N/A'),
                        'pdf_url': meta.get('pdf_url', ''),
                        'priority': meta.get('priority', 5),
                        'snippet': snippet,
                        'distance': 0.0
                    })
                    logger.debug(f"'All words' match found at index {idx}")
                    indices_already_included.add(idx)
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")

    logger.info(f"'All words' matches found: {len(all_words_matches)}")

    # Step 3: Semantic search using FAISS
    logger.info("Performing semantic search using FAISS...")
    try:
        query_embedding = get_query_embedding_cached(query, model_name)
        distances, indices = index.search(query_embedding, top_k)
        logger.info(f"FAISS search completed. Retrieved {len(indices[0])} results.")
    except Exception as e:
        logger.error(f"Error during FAISS search: {e}", exc_info=True)
        raise RuntimeError(f"Error during FAISS search: {e}")

    semantic_matches = []
    indices_already_included = set(em['idx'] for em in exact_matches + all_words_matches)

    for distance, idx in zip(distances[0], indices[0]):
        if idx in indices_already_included:
            continue
        if idx >= len(metadata):
            logger.warning(f"FAISS index {idx} out of bounds for metadata length {len(metadata)}")
            continue

        meta = metadata[idx]

        if apply_filters([meta], filters):
            snippet = extract_matching_sentences(meta['snippet'], query)
            if len(snippet.strip()) >= min_snippet_length:
                semantic_matches.append({
                    'idx': idx,
                    'author': meta.get('author', 'Unknown'),
                    'book_title': meta.get('book_title', 'Unknown'),
                    'chapter_name': meta.get('chapter_name', 'N/A'),
                    'file_path': meta.get('file_path', ''),
                    'group': meta.get('group', 'Unknown'),
                    'page_number': meta.get('page_number', 'N/A'),
                    'pdf_url': meta.get('pdf_url', ''),
                    'priority': meta.get('priority', 10),
                    'snippet': snippet,
                    'distance': float(distance)
                })
                logger.debug(f"Semantic match found at index {idx} with distance {distance}")
                indices_already_included.add(idx)
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")

    logger.info(f"Semantic matches found: {len(semantic_matches)}")

    # Combine results
    combined_results = []

    # Add exact matches
    combined_results.extend(exact_matches)

    # Add 'all words' matches
    remaining_k = top_k - len(combined_results)
    if remaining_k > 0:
        combined_results.extend(all_words_matches[:remaining_k])

    # Add semantic matches
    remaining_k = top_k - len(combined_results)
    if remaining_k > 0:
        # Sort semantic matches based on distance and priority
        sorted_semantic = sorted(semantic_matches, key=lambda x: (-x['distance'], x['priority']))
        combined_results.extend(sorted_semantic[:remaining_k])

    # Remove the 'idx' key before returning
    for result in combined_results:
        result.pop('idx', None)

    logger.info(f"Returning combined and sorted results. Total results: {len(combined_results)}")

    return combined_results[:top_k]

def search_exact_semantic(query, index_path, metadata_path, top_k=10, filters=None, search_type='both', model_name='sentence-transformers/all-mpnet-base-v2'):
    """
    Performs a search on the FAISS index with both exact and semantic matching.

    Parameters:
    - query (str): The search query.
    - index_path (str): Path to the FAISS index file.
    - metadata_path (str): Path to the metadata JSON file.
    - top_k (int): Number of top results to return.
    - filters (dict): Filters to apply on the search results.
    - search_type (str): 'both', 'exact', or 'semantic'.
    - model_name (str): Name of the SentenceTransformer model to use.

    Returns:
    - List of search results containing metadata and relevance scores.
    """
    logger.info(f"Starting search for query: '{query}' with top_k={top_k}, filters={filters}, search_type={search_type}")

    if filters is None:
        filters = {}

    # Load FAISS index and metadata using caching
    index = load_faiss_index_cached(index_path)
    metadata = load_metadata_cached(metadata_path)

    # Initialize the model using caching
    model = initialize_model_cached(model_name)

    # Step 1: Exact match search
    exact_matches = []
    query_lower = query.lower()
    # Normalize the query
    query_normalized = prepare_text_for_matching(query)
    logger.info("Performing exact match search...")

    for idx, meta in enumerate(metadata):
        # Apply filters before checking the snippet
        if apply_filters([meta], filters):
            # Normalize the snippet
            snippet_normalized = prepare_text_for_matching(meta['snippet'])            
            if query_normalized in snippet_normalized:
                snippet = extract_matching_sentences(meta['snippet'], query)
                exact_matches.append({
                    'author': meta.get('author', 'Unknown'),
                    'book_title': meta.get('book_title', 'Unknown'),
                    'chapter_name': meta.get('chapter_name', 'N/A'),
                    'file_path': meta.get('file_path', ''),
                    'group': meta.get('group', 'Unknown'),
                    'page_number': meta.get('page_number', 'N/A'),
                    'pdf_url': meta.get('pdf_url', ''),
                    'priority': meta.get('priority', 1),  # Higher priority for exact matches
                    'snippet': snippet,
                    'distance': 0.0  # Exact match has zero distance
                })
                logger.debug(f"Exact match found at index {idx}")
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")

    logger.info(f"Exact matches found: {len(exact_matches)}")

    if search_type == 'exact':
        logger.info(f"Returning exact matches only, limited to top_k={top_k}")
        return exact_matches[:top_k]

    # Step 2: Semantic search using FAISS
    logger.info("Performing semantic search using FAISS...")
    try:
        query_embedding = get_query_embedding_cached(query, model_name)
        # Since query_embedding is already 2D, no need to expand dimensions
        distances, indices = index.search(query_embedding, top_k)
        #distances, indices = index.search(np.expand_dims(query_embedding, axis=0), top_k)
        logger.info(f"FAISS search completed. Retrieved {len(indices[0])} results.")
    except Exception as e:
        logger.error(f"Error during FAISS search: {e}", exc_info=True)
        raise RuntimeError(f"Error during FAISS search: {e}")

    semantic_matches = []
    for distance, idx in zip(distances[0], indices[0]):
        if idx >= len(metadata):
            logger.warning(f"FAISS index {idx} out of bounds for metadata length {len(metadata)}")
            continue

        meta = metadata[idx]

        # Apply filters after semantic search
        if apply_filters([meta], filters):
            snippet = extract_matching_sentences(meta['snippet'], query)
            semantic_matches.append({
                'author': meta.get('author', 'Unknown'),
                'book_title': meta.get('book_title', 'Unknown'),
                'chapter_name': meta.get('chapter_name', 'N/A'),
                'file_path': meta.get('file_path', ''),
                'group': meta.get('group', 'Unknown'),
                'page_number': meta.get('page_number', 'N/A'),
                'pdf_url': meta.get('pdf_url', ''),
                'priority': meta.get('priority', 10),  # Lower priority for semantic matches
                'snippet': snippet,
                'distance': float(distance)  # Higher similarity means smaller angle
            })
            logger.debug(f"Semantic match found at index {idx} with distance {distance}")
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")

    logger.info(f"Semantic matches found: {len(semantic_matches)}")

    # Combine exact and semantic matches
    combined_results = exact_matches.copy()

    # Sort semantic matches based on distance and priority
    sorted_semantic = sorted(semantic_matches, key=lambda x: (-x['distance'], x['priority']))

    remaining_k = top_k - len(combined_results)
    if remaining_k > 0:
        combined_results += sorted_semantic[:remaining_k]

    logger.info(f"Returning combined and sorted results. Total results: {len(combined_results)}")

    return combined_results[:top_k]

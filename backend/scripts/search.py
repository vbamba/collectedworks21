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
    try:
        model = initialize_model_cached(model_name)
        embedding = model.encode([query], convert_to_numpy=True).astype('float32')
        faiss.normalize_L2(embedding)
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding for query '{query}': {e}", exc_info=True)
        raise RuntimeError(f"Error generating embedding for query '{query}': {e}")


def perform_exact_match_search(query_normalized, metadata, filters, min_snippet_length):
    logger.info("Performing exact match search...")
    exact_matches = []
    matched_indices = set()
    for idx, meta in enumerate(metadata):
        if apply_filters([meta], filters):
            snippet_normalized = prepare_text_for_matching(meta['snippet'])
            if query_normalized in snippet_normalized:
                snippet = extract_matching_sentences(meta['snippet'], query_normalized)
                if len(snippet) >= min_snippet_length:
                    exact_matches.append({
                        'idx': idx,
                        'author': meta.get('author', 'Unknown'),
                        'book_title': meta.get('book_title', 'Unknown'),
                        'chapter_name': meta.get('chapter_name', 'N/A'),
                        'file_path': meta.get('file_path', ''),
                        'group': meta.get('group', 'Unknown'),
                        'page_number': meta.get('page_number', 'N/A'),
                        'pdf_url': meta.get('pdf_url', ''),
                        'priority': meta.get('priority', 0),
                        'category_priority': 1,
                        'snippet': snippet,
                        'distance': 0.0
                    })
                    matched_indices.add(idx)
                    logger.debug(f"Exact match found at index {idx}")
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")
    logger.info(f"Exact matches found: {len(exact_matches)}")
    return exact_matches, matched_indices

def perform_all_words_match_search(query_words_set, metadata, filters, min_snippet_length, exclude_indices):
    logger.info("Performing all words match search...")
    all_words_matches = []
    matched_indices = set()
    for idx, meta in enumerate(metadata):
        if idx in exclude_indices:
            continue
        if apply_filters([meta], filters):
            snippet_normalized = prepare_text_for_matching(meta['snippet'])
            snippet_words_set = set(snippet_normalized.split())
            if query_words_set.issubset(snippet_words_set):
                snippet = extract_matching_sentences(meta['snippet'], ' '.join(query_words_set))
                if len(snippet) >= min_snippet_length:
                    all_words_matches.append({
                        'idx': idx,
                        'author': meta.get('author', 'Unknown'),
                        'book_title': meta.get('book_title', 'Unknown'),
                        'chapter_name': meta.get('chapter_name', 'N/A'),
                        'file_path': meta.get('file_path', ''),
                        'group': meta.get('group', 'Unknown'),
                        'page_number': meta.get('page_number', 'N/A'),
                        'pdf_url': meta.get('pdf_url', ''),
                        'priority': meta.get('priority', 0),
                        'category_priority': 3,  # Will update if also semantic match
                        'snippet': snippet,
                        'distance': 0.1  # Default small distance
                    })
                    matched_indices.add(idx)
                    logger.debug(f"All words match found at index {idx}")
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")
    logger.info(f"All words matches found: {len(all_words_matches)}")
    return all_words_matches, matched_indices

def perform_semantic_search(query, index, metadata, filters, min_snippet_length, exclude_indices, model_name, top_k):
    logger.info("Performing semantic search using FAISS...")
    semantic_matches = []
    matched_indices = set()
    try:
        query_embedding = get_query_embedding_cached(query, model_name)
        # Limit the number of results to retrieve
        faiss_k = top_k * 5  # Adjust the multiplier as needed
        distances, indices = index.search(query_embedding, faiss_k)
        logger.info(f"FAISS search completed. Retrieved {len(indices[0])} results.")
    except Exception as e:
        logger.error(f"Error during FAISS search: {e}", exc_info=True)
        raise RuntimeError(f"Error during FAISS search: {e}")
    for distance, idx in zip(distances[0], indices[0]):
        if idx in exclude_indices:
            continue
        if idx >= len(metadata):
            logger.warning(f"FAISS index {idx} out of bounds for metadata length {len(metadata)}")
            continue
        meta = metadata[idx]
        if apply_filters([meta], filters):
            snippet = extract_matching_sentences(meta['snippet'], query)
            if len(snippet) >= min_snippet_length:
                semantic_matches.append({
                    'idx': idx,
                    'author': meta.get('author', 'Unknown'),
                    'book_title': meta.get('book_title', 'Unknown'),
                    'chapter_name': meta.get('chapter_name', 'N/A'),
                    'file_path': meta.get('file_path', ''),
                    'group': meta.get('group', 'Unknown'),
                    'page_number': meta.get('page_number', 'N/A'),
                    'pdf_url': meta.get('pdf_url', ''),
                    'priority': meta.get('priority', 0),
                    'category_priority': 4,
                    'snippet': snippet,
                    'distance': float(distance)
                })
                matched_indices.add(idx)
                logger.debug(f"Semantic match found at index {idx} with distance {distance}")
            # Stop if we have enough matches
            if len(semantic_matches) >= top_k:
                break
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")
    logger.info(f"Semantic matches found: {len(semantic_matches)}")
    return semantic_matches, matched_indices

def perform_semantic_search_old(query, index, metadata, filters, min_snippet_length, exclude_indices, model_name):
    logger.info("Performing semantic search using FAISS...")
    semantic_matches = []
    matched_indices = set()
    try:
        query_embedding = get_query_embedding_cached(query, model_name)
        distances, indices = index.search(query_embedding, len(metadata))
        logger.info(f"FAISS search completed. Retrieved {len(indices[0])} results.")
    except Exception as e:
        logger.error(f"Error during FAISS search: {e}", exc_info=True)
        raise RuntimeError(f"Error during FAISS search: {e}")
    for distance, idx in zip(distances[0], indices[0]):
        if idx in exclude_indices:
            continue
        if idx >= len(metadata):
            logger.warning(f"FAISS index {idx} out of bounds for metadata length {len(metadata)}")
            continue
        meta = metadata[idx]
        if apply_filters([meta], filters):
            snippet = extract_matching_sentences(meta['snippet'], query)
            if len(snippet) >= min_snippet_length:
                semantic_matches.append({
                    'idx': idx,
                    'author': meta.get('author', 'Unknown'),
                    'book_title': meta.get('book_title', 'Unknown'),
                    'chapter_name': meta.get('chapter_name', 'N/A'),
                    'file_path': meta.get('file_path', ''),
                    'group': meta.get('group', 'Unknown'),
                    'page_number': meta.get('page_number', 'N/A'),
                    'pdf_url': meta.get('pdf_url', ''),
                    'priority': meta.get('priority', 0),
                    'category_priority': 4,
                    'snippet': snippet,
                    'distance': float(distance)
                })
                matched_indices.add(idx)
                logger.debug(f"Semantic match found at index {idx} with distance {distance}")
        else:
            logger.debug(f"Metadata at index {idx} did not pass filters.")
    logger.info(f"Semantic matches found: {len(semantic_matches)}")
    return semantic_matches, matched_indices

def search(query, index_path, metadata_path, top_k=50, filters=None, search_type='all',
           model_name='sentence-transformers/all-mpnet-base-v2', min_snippet_length=10):
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

    combined_results = []
    matched_indices = set()

    if search_type in ['all', 'exact']:
        # Perform exact match search
        exact_matches, exact_matched_indices = perform_exact_match_search(query_normalized, metadata, filters, min_snippet_length)
        combined_results.extend(exact_matches)
        matched_indices.update(exact_matched_indices)

        if search_type == 'exact':
            # Remove 'idx' from results
            for res in combined_results:
                res.pop('idx', None)
            # Sort and return
            sorted_results = sorted(
                combined_results,
                key=lambda x: (
                    x['category_priority'],
                    -x['priority'],
                    x['distance']
                )
            )
            return sorted_results[:top_k]

    if search_type in ['all', 'all_words']:
        # Perform all words match search
        all_words_matches, all_words_matched_indices = perform_all_words_match_search(
            query_words_set, metadata, filters, min_snippet_length, matched_indices
        )
        combined_results.extend(all_words_matches)
        matched_indices.update(all_words_matched_indices)

        if search_type == 'all_words':
            # Remove 'idx' from results
            for res in combined_results:
                res.pop('idx', None)
            # Sort and return
            sorted_results = sorted(
                combined_results,
                key=lambda x: (
                    x['category_priority'],
                    -x['priority'],
                    x['distance']
                )
            )
            return sorted_results[:top_k]

    if search_type in ['all', 'semantic']:
        # Perform semantic search
        semantic_matches, semantic_matched_indices = perform_semantic_search(
            query, index, metadata, filters, min_snippet_length, matched_indices, model_name, top_k
        )

        if search_type == 'all':
            # Update category_priority for all words matches that are also in semantic matches
            semantic_indices = {res['idx'] for res in semantic_matches}
            for result in combined_results:
                if result.get('category_priority') == 3 and result['idx'] in semantic_indices:
                    result['category_priority'] = 2  # Combined match
                    # Update distance from semantic match
                    for sem_result in semantic_matches:
                        if sem_result['idx'] == result['idx']:
                            result['distance'] = sem_result['distance']
                            break
            # Remove duplicates from semantic matches
            existing_indices = {res['idx'] for res in combined_results}
            semantic_matches = [res for res in semantic_matches if res['idx'] not in existing_indices]
            combined_results.extend(semantic_matches)
            # Now update matched_indices
            matched_indices.update(semantic_matched_indices)
        else:
            combined_results.extend(semantic_matches)
            matched_indices.update(semantic_matched_indices)

    # Remove 'idx' from results as it's no longer needed
    for res in combined_results:
        res.pop('idx', None)

    # Sort combined results
    sorted_results = sorted(
        combined_results,
        key=lambda x: (
            x['category_priority'],
            -x['priority'],
            -x['distance'] if x['distance'] is not None else float('-inf')
        )
    )


    # Return top_k results
    final_results = sorted_results[:top_k]
    logger.info(f"Returning combined and sorted results. Total results: {len(final_results)}")
    return final_results

def search_last(query, index_path, metadata_path, top_k=10, filters=None, search_type='all',
           model_name='sentence-transformers/all-mpnet-base-v2', min_snippet_length=20):
    """
    Performs a search with options for exact match, all words match, and semantic matching.

    Parameters:
    - query (str): The search query.
    - index_path (str): Path to the FAISS index file.
    - metadata_path (str): Path to the metadata JSON file.
    - top_k (int): Number of top results to return.
    - filters (dict): Filters to apply on the search results.
    - search_type (str): 'all', 'exact', 'semantic', or 'all_words'.
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

    combined_results = []
    matched_indices = set()

    if search_type in ['all', 'exact']:
        # Perform exact match search
        exact_matches, exact_matched_indices = perform_exact_match_search(query_normalized, metadata, filters, min_snippet_length)
        combined_results.extend(exact_matches)
        matched_indices.update(exact_matched_indices)

        if search_type == 'exact':
            # Remove 'idx' from results
            for res in combined_results:
                res.pop('idx', None)
            # Sort and return
            sorted_results = sorted(
                combined_results,
                key=lambda x: (
                    x['category_priority'],
                    -x['priority'],
                    x['distance']
                )
            )
            return sorted_results[:top_k]

    if search_type in ['all', 'all_words']:
        # Perform all words match search
        all_words_matches, all_words_matched_indices = perform_all_words_match_search(
            query_words_set, metadata, filters, min_snippet_length, matched_indices
        )
        combined_results.extend(all_words_matches)
        matched_indices.update(all_words_matched_indices)

        if search_type == 'all_words':
            # Remove 'idx' from results
            for res in combined_results:
                res.pop('idx', None)
            # Sort and return
            sorted_results = sorted(
                combined_results,
                key=lambda x: (
                    x['category_priority'],
                    -x['priority'],
                    x['distance']
                )
            )
            return sorted_results[:top_k]

    if search_type in ['all', 'semantic']:
        # Perform semantic search
        semantic_matches, semantic_matched_indices = perform_semantic_search(
            query, index, metadata, filters, min_snippet_length, matched_indices, model_name
        )
        #matched_indices.update(semantic_matched_indices)

        if search_type == 'all':
            # Update category_priority for all words matches that are also in semantic matches
            semantic_indices = {res['idx'] for res in semantic_matches}
            for result in combined_results:
                if result.get('category_priority') == 3 and result['idx'] in semantic_indices:
                    result['category_priority'] = 2  # Combined match
                    # Update distance from semantic match
                    for sem_result in semantic_matches:
                        if sem_result['idx'] == result['idx']:
                            result['distance'] = sem_result['distance']
                            break
            # Remove duplicates from semantic matches
            semantic_matches = [res for res in semantic_matches if res['idx'] not in matched_indices]
            combined_results.extend(semantic_matches)
        else:
            combined_results.extend(semantic_matches)

    # Remove 'idx' from results as it's no longer needed
    for res in combined_results:
        res.pop('idx', None)

    # Sort combined results
    sorted_results = sorted(
        combined_results,
        key=lambda x: (
            x['category_priority'],
            -x['priority'],
            x['distance'] if x['distance'] is not None else float('inf')
        )
    )

    # Return top_k results
    final_results = sorted_results[:top_k]
    logger.info(f"Returning combined and sorted results. Total results: {len(final_results)}")
    return final_results

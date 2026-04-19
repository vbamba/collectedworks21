import faiss
import json
import numpy as np
import logging
import re
from sentence_transformers import SentenceTransformer
from functools import lru_cache
from collections import Counter  
from .utils import (
    extract_all_words_snippet,
    extract_exact_words_snippet,
    extract_semantic_snippet,
    apply_filters,  # unchanged in utils.py
    prepare_text_for_matching
)

# Initialize the logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("search.log")
    ]
)
logger.setLevel(logging.INFO)  

def is_toc_snippet(snippet: str) -> bool:
    """
    Heuristic TOC detector:
     0) If the first non‑blank line is exactly 'contents' → TOC
     1) Any line has a long run of dots (‘dot‑leaders’) → TOC
     2) First non‑blank line starts with 'Chapter' or 'Part' → TOC
     3) ≥3 lines and >70% are very short (≤5 words) → TOC
    """
    lines = [ln.strip() for ln in snippet.splitlines() if ln.strip()]
    if not lines:
        return False

    # <<< CHANGE HERE: drop any snippet whose first line is exactly 'contents'
    if lines[0].lower() == 'contents':
        return True
    # <<< END CHANGE

    # 1) Dot‑leaders:
    for ln in lines:
        if re.search(r'\.{5,}', ln):
            return True

    # 2) Chapter/Part headings:
    if re.match(r'^(chapter|part)\b', lines[0].lower()):
        return True

    # 3) Mostly short lines:
    short = [ln for ln in lines if len(ln.split()) <= 5]
    if len(lines) >= 3 and (len(short) / len(lines)) > 0.7:
        return True

    return False


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
        logger.error("Error generating embedding for query=%r: %s", query, e, exc_info=True)
        raise RuntimeError("Error generating query embedding")

def clean_pdf_url(url):
    """Remove hostname from PDF URL if present."""
    if url.startswith(('http://', 'https://')):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.path
        except:
            return url
    return url

def build_result_dict(meta, snippet, idx, category_priority, distance=0.0):
    return {
        'idx': idx,
        'author': meta.get('author', 'Unknown'),
        'book_title': meta.get('book_title', 'Unknown'),
        'chapter_name': meta.get('chapter_name', 'N/A'),
        'file_path': meta.get('file_path', ''),
        'group': meta.get('group', 'Unknown'),
        'page_number': meta.get('page_number', 'N/A'),
        'pdf_url': clean_pdf_url(meta.get('pdf_url', '')),
        'priority': meta.get('priority', 0),
        'category_priority': category_priority,
        'snippet': snippet,
        'distance': distance
    }

# --- CHANGED: Removed apply_filters() check from matching functions ---

def perform_exact_match_search(query, query_normalized, metadata, filters, min_snippet_length, remove_punctuation=True):
    logger.info("Performing exact match search...")
    exact_matches = []
    matched_indices = set()
    for idx, meta in enumerate(metadata):
        # CHANGED: Filtering is removed from here.
        snippet_normalized = prepare_text_for_matching(meta['snippet'], remove_punctuation)
        if query_normalized in snippet_normalized:
            start_index = snippet_normalized.find(query_normalized)
            if start_index != -1:
                end_index = start_index + len(query_normalized)
            logger.debug(f"Received start index: {start_index}, end index: {end_index}")
            snippet = extract_exact_words_snippet(meta['snippet'], snippet_normalized, query_normalized, start_index, end_index)
            if len(snippet) >= min_snippet_length:
                logger.debug(f"Highlighted snippet: {snippet}")
                exact_matches.append(build_result_dict(meta, snippet, idx, category_priority=1, distance=0.0))
                matched_indices.add(idx)
                logger.debug(f"Exact match found at index {idx}")
    logger.info(f"Exact matches found: {len(exact_matches)}")
    return exact_matches, matched_indices

def perform_all_words_match_search(query_words_set, metadata, filters, min_snippet_length, exclude_indices, remove_punctuation=True):
    logger.info(f"Performing all words match search for - {query_words_set}.")
    all_words_matches = []
    matched_indices = set()
    for idx, meta in enumerate(metadata):
        if idx in exclude_indices:
            continue
        # CHANGED: Removed filtering from here.
        snippet_normalized = prepare_text_for_matching(meta['snippet'], remove_punctuation)
        snippet_words_set = set(snippet_normalized.split())
        if query_words_set.issubset(snippet_words_set):
            logger.debug(f"Matched all words snippet {snippet_words_set}.")
            snippet = extract_all_words_snippet(meta['snippet'], ' '.join(query_words_set), remove_punctuation)
            if len(snippet) >= min_snippet_length:
                all_words_matches.append(build_result_dict(meta, snippet, idx, category_priority=2, distance=0.1))
                matched_indices.add(idx)
                logger.debug(f"All words match found at index {idx}")
    logger.info(f"All words matches found: {len(all_words_matches)}")
    return all_words_matches, matched_indices

def perform_all_or_any_words_match_search(
    query_words_set,
    metadata,
    filters,
    min_snippet_length,
    exclude_indices,
    remove_punctuation=True
):
    logger.info(f"Performing all-or-any words match search for query words: {query_words_set}")
    
    combined_matches = []
    matched_indices = set()

    for idx, meta in enumerate(metadata):
        if idx in exclude_indices:
            continue

        # Normalize snippet text
        snippet_normalized = prepare_text_for_matching(meta['snippet'], remove_punctuation)
        snippet_words_set = set(snippet_normalized.split())

        # Check if there's at least one shared word
        intersection = query_words_set.intersection(snippet_words_set)
        if not intersection:
            continue  # No overlap, skip

        # Build a snippet for display
        snippet = extract_all_words_snippet(
            meta['snippet'],
            ' '.join(query_words_set),
            remove_punctuation
        )

        # Enforce minimal snippet length
        if len(snippet) < min_snippet_length:
            continue
        
        # Decide whether it’s an "all words" match or a partial "any words" match
        if query_words_set.issubset(snippet_words_set):
            # All words found
            distance = 0.1
            category_priority = 2
            logger.debug(f"All words match found at index {idx} -> {intersection}")
        else:
            # Only some words found
            distance = 0.2
            category_priority = 3
            logger.debug(f"Partial words match found at index {idx} -> {intersection}")

        combined_matches.append(
            build_result_dict(
                meta,
                snippet,
                idx,
                category_priority=category_priority,
                distance=distance
            )
        )
        matched_indices.add(idx)

    logger.info(f"All/Any matches found: {len(combined_matches)}")
    return combined_matches, matched_indices


def perform_semantic_search(query, index, metadata, filters, min_snippet_length, exclude_indices, model_name, top_k, remove_punctuation=False):
    logger.info("Performing semantic search using FAISS...")
    semantic_matches = []
    matched_indices = set()
    try:
        query_embedding = get_query_embedding_cached(query, model_name)
        faiss_k = top_k * 5
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
        # CHANGED: Removed filtering from here.
        snippet = extract_semantic_snippet(meta['snippet'], query, remove_punctuation)
        if len(snippet) >= min_snippet_length:
            semantic_matches.append(build_result_dict(meta, snippet, idx, category_priority=4, distance=float(distance)))
            matched_indices.add(idx)
            logger.debug(f"Semantic match found at index {idx} with distance {distance}")
            if len(semantic_matches) >= top_k:
                break
    logger.info(f"Semantic matches found: {len(semantic_matches)}")
    return semantic_matches, matched_indices

def diversify_collections(results, top_k=100, ratio=0.5):
    """
    results: a list already sorted by category_priority, distance, etc.
    ratio: the fraction from CWSA vs CWM, e.g. 0.5 means half from each if possible

    We only care about two 'primary' collections: CWSA, CWM.
    Others (e.g. Disciples) can appear afterwards or not at all.
    """
    # separate primary
    cwsa_list = [r for r in results if r['group'] == 'CWSA']
    cwm_list  = [r for r in results if r['group'] == 'CWM']
    others    = [r for r in results if r['group'] not in ('CWSA', 'CWM')]

    # how many from each?
    # if ratio=0.5 and top_k=100 => want up to 50 from CWSA, 50 from CWM
    cwsa_quota = int(top_k * ratio)
    cwm_quota  = top_k - cwsa_quota

    # take the top cwsa_quota from CWSA if available
    cwsa_partial = cwsa_list[:cwsa_quota]
    # top cwm_quota from CWM if available
    cwm_partial  = cwm_list[:cwm_quota]

    # merge them
    blended = []
    i = j = 0
    while i < len(cwsa_partial) or j < len(cwm_partial):
        # pick one from cwsa
        if i < len(cwsa_partial):
            blended.append(cwsa_partial[i])
            i += 1
        # pick one from cwm
        if j < len(cwm_partial):
            blended.append(cwm_partial[j])
            j += 1

    # fill leftover from whichever isn't exhausted
    # or if e.g. cwm had fewer than cwm_quota
    leftover_cwsa = cwsa_list[cwsa_quota:]
    leftover_cwm  = cwm_list[cwm_quota:]

    # put all leftover after the "blended" portion
    leftover_others = others
    # combine them in your existing priority order if you want
    leftover_combined = leftover_cwsa + leftover_cwm + leftover_others

    final = blended + leftover_combined

    # truncate to top_k
    return final[:top_k]

def search(query, index_path, metadata_path, top_k=100, filters=None, search_type='all',
           model_name='sentence-transformers/all-mpnet-base-v2', min_snippet_length=20):
    logger.info(
        "Starting search for query=%r with top_k=%s filters=%s search_type=%s",
        query,
        top_k,
        filters,
        search_type,
    )
    if filters is None:
        filters = {}

    index = load_faiss_index_cached(index_path)
    metadata = load_metadata_cached(metadata_path)
    model = initialize_model_cached(model_name)

    remove_punctuation = search_type in ['exact', 'all_words']
    query_normalized = prepare_text_for_matching(query, remove_punctuation)
    query_words = query_normalized.split()
    query_words_set = set(query_words)
    single_word = (len(query_words) == 1)

    combined_results = []
    matched_indices = set()

    # CHANGED: Instead of normalizing search_type to 'all', we check explicitly.
    if search_type == 'exact':
        exact_matches, exact_matched_indices = perform_exact_match_search(query, query_normalized, metadata, filters, min_snippet_length, remove_punctuation)
        combined_results.extend(exact_matches)
        matched_indices.update(exact_matched_indices)
    elif search_type == 'all_words':
        # For all_words, combine both exact and all words blocks.
        exact_matches, exact_matched_indices = perform_exact_match_search(query, query_normalized, metadata, filters, min_snippet_length, remove_punctuation)
        combined_results.extend(exact_matches)
        matched_indices.update(exact_matched_indices)        
        #all_words_matches, all_words_matched_indices = perform_all_words_match_search(query_words_set, metadata, filters, min_snippet_length, matched_indices, remove_punctuation)
        all_words_matches, all_words_matched_indices = perform_all_or_any_words_match_search(query_words_set, metadata, filters, min_snippet_length, matched_indices, remove_punctuation)
        combined_results.extend(all_words_matches)
        matched_indices.update(all_words_matched_indices)
    elif search_type == 'semantic':
        semantic_matches, semantic_matched_indices = perform_semantic_search(query, index, metadata, filters, min_snippet_length, matched_indices, model_name, top_k)
        combined_results.extend(semantic_matches)
        matched_indices.update(semantic_matched_indices)
    elif search_type == 'all':
        exact_matches, exact_matched_indices = perform_exact_match_search(query, query_normalized, metadata, filters, min_snippet_length, remove_punctuation)
        combined_results.extend(exact_matches)
        matched_indices.update(exact_matched_indices)
        #all_words_matches, all_words_matched_indices = perform_all_words_match_search(query_words_set, metadata, filters, min_snippet_length, matched_indices, remove_punctuation)
        all_words_matches, all_words_matched_indices = perform_all_or_any_words_match_search(query_words_set, metadata, filters, min_snippet_length, matched_indices, remove_punctuation)
        combined_results.extend(all_words_matches)
        matched_indices.update(all_words_matched_indices)
        #semantic_matches, semantic_matched_indices = perform_semantic_search(query, index, metadata, filters, min_snippet_length, matched_indices, model_name, top_k)
        # CHANGED: For combined mode, update category_priority for overlap.
        #semantic_indices = {res['idx'] for res in semantic_matches}
        #for result in combined_results:
        #    if result.get('category_priority') == 3 and result['idx'] in semantic_indices:
        #        result['category_priority'] = 2  # Combined match
        #        for sem_result in semantic_matches:
        #            if sem_result['idx'] == result['idx']:
        #                result['distance'] = sem_result['distance']
        #                break
        #existing_indices = {res['idx'] for res in combined_results}
        #semantic_matches = [res for res in semantic_matches if res['idx'] not in existing_indices]
        #combined_results.extend(semantic_matches)
        #matched_indices.update(semantic_matched_indices)
    else:
        logger.error("Invalid search_type provided.")
        return []

    # Apply filters once after combining candidate results.
    combined_results = apply_filters(combined_results, filters)

   # <<< CHANGE HERE: Exclude TOC‑style snippets and any Publisher’s Note
    publisher_note = re.compile(r"publisher's note", re.IGNORECASE)
    filtered = []
    for res in combined_results:
        snippet = res.get('snippet', '')

        # 1) If it looks like a TOC (dot‑leaders, chapter headings, mostly short lines) → drop
        if is_toc_snippet(snippet):
            logger.debug(f"Excluding TOC‑style snippet in {res['file_path']} page {res['page_number']}")
            continue

        # 2) If it mentions Publisher's Note anywhere → drop
        if publisher_note.search(snippet):
            logger.debug(f"Excluding Publisher's Note snippet in {res['file_path']} page {res['page_number']}")
            continue

        filtered.append(res)
    combined_results = filtered
    # <<< END CHANGE

    for res in combined_results:
        res.pop('idx', None)

    file_counts = Counter(item['file_path'] for item in combined_results)
    for res in combined_results:
        res.pop('idx', None)

    # --- CHANGED: Compute match_count per (file_path, category_priority) pair ---
    file_counts = Counter((item['file_path'], item['category_priority']) for item in combined_results)
    for res in combined_results:
        key = (res.get('file_path', ''), res.get('category_priority'))
        res['match_count'] = file_counts.get(key, 1)

    # --- CHANGED: Log candidate details after computing match_count for troubleshooting ---
    logger.debug("Combined candidate results AFTER computing match_count:")
    for r in combined_results:
        logger.debug(f"Book: {r['book_title']} | Group: {r['group']} | Category: {r['category_priority']} | "
                     f"MatchCount: {r['match_count']} | Priority: {r['priority']} | Distance: {r.get('distance', 0)}")

    # Sort combined results with match type ordering:
    sorted_results = sorted(
        combined_results,
        key=lambda x: (
            x['category_priority'],                 # 1 (exact) < 2 (combined) < 3 (all words) < 4 (semantic)
            x['distance'] if x['distance'] is not None else float('-inf'),
            0 if x['group'] in {"CWSA", "CWM", "Agenda"} else 1,
            -x['match_count'],                      # higher match count within the same file & category first
            -x['priority']                         # then by priority
        )
    )
 
     # CHANGED: Log sorted candidate details
    logger.debug("Sorted candidate results:")
    for r in sorted_results:
        logger.debug(f"Book: {r['book_title']} | Group: {r['group']} | Category: {r['category_priority']} | MatchCount: {r['match_count']} | Priority: {r['priority']} | Distance: {r.get('distance', 0)}")

    all_count = len(sorted_results)
    diversified_results = diversify_collections(
        sorted_results,
        top_k=top_k,
        ratio=0.5  # or 0.6, or any ratio you want
    ) 
    return diversified_results


    #final_results = sorted_results[:top_k]
    #logger.info(f"Returning {len(final_results)} out of {all_count} combined results.")
    #return final_results

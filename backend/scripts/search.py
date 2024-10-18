import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import re
import nltk
print(nltk.__version__)
nltk.download('punkt', quiet=True)
from nltk.tokenize import sent_tokenize
from rich import print
from rich.console import Console
from rich.text import Text

# Load the Hugging Face model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# Load FAISS index and metadata
index_output_dir = '/Users/vbamba/Projects/collectedworks/indexes'
index = faiss.read_index(os.path.join(index_output_dir, 'faiss_index.bin'))

# Load compressed metadata from the .npz file
metadata_file = os.path.join(index_output_dir, 'metadata.npz')
metadata_npz = np.load(metadata_file, allow_pickle=True)
metadata = metadata_npz['metadata'].tolist()

def get_embedding(query):
    # Generate embedding for search query
    return model.encode(query, convert_to_numpy=True)

def highlight_query(text, query):
    """Highlight the query terms in the text using rich Text objects"""
    # Escape special characters in query for regex
    query_regex = re.escape(query)
    # Use regex to ignore case and match the query
    highlighted_text = re.sub(f'({query_regex})', r'[bold red]\1[/bold red]', text, flags=re.IGNORECASE)
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



def search(query, top_k=10, filter_file=None, search_type='both'):
    # Step 1: Exact match search
    exact_matches = []
    exact_match_indices = set()
    query_lower = query.lower()
    for idx, meta in enumerate(metadata):
        if filter_file and filter_file not in os.path.basename(meta['file_path']):
            continue  # Skip if the file doesn't match the filter

        snippet_lower = meta['snippet'].lower()
        if query_lower in snippet_lower:
            snippet = extract_matching_sentences(meta['snippet'], query, max_sentences=3, max_chars=500)
            exact_matches.append({
                'file_path': meta['file_path'],
                'chapter_name': meta.get('chapter_name', 'N/A'),
                'page_number': meta.get('page_number', 'N/A'),
                'snippet': snippet,  # Display matching lines for exact match
                'distance': 0,  # Exact match is given a distance of 0
            })
            exact_match_indices.add(idx)

    if search_type == 'exact':
        # Return only exact matches
        combined_results = sorted(exact_matches, key=lambda x: x['distance'])
        return combined_results[:top_k]

    # Step 2: Semantic search using FAISS
    query_embedding = get_embedding(query).astype('float32')
    distances, indices = index.search(np.array([query_embedding]), top_k * 2)  # Search for more to account for filtering

    semantic_matches = []
    for i, idx in enumerate(indices[0]):
        if idx in exact_match_indices:
            continue  # Skip duplicates

        meta = metadata[idx]

        # Skip if the file doesn't match the filter
        if filter_file and filter_file not in os.path.basename(meta['file_path']):
            continue

        snippet = extract_matching_sentences(meta['snippet'], query, max_sentences=3, max_chars=500)
        #snippet = extract_matching_lines(meta['snippet'], query, max_lines=3, max_chars=500)
        semantic_matches.append({
            'file_path': meta['file_path'],
            'chapter_name': meta.get('chapter_name', 'N/A'),
            'page_number': meta.get('page_number', 'N/A'),
            'snippet': snippet,  # Display matching lines or default snippet
            'distance': distances[0][i],
        })

        if len(semantic_matches) >= top_k - len(exact_matches):
            break  # Limit to top_k results

    if search_type == 'similarity':
        # Return only semantic matches
        combined_results = sorted(semantic_matches, key=lambda x: x['distance'])
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

    # Ensure exact matches appear at the top
    unique_results = sorted(unique_results, key=lambda x: x['distance'])

    return unique_results[:top_k]


# Prompt user for a search query and search type
user_query = input("Enter your search query: ")
search_type = input("Enter search type ('exact', 'similarity', 'both') [default: both]: ").strip().lower()
if search_type not in ('exact', 'similarity', 'both'):
    search_type = 'both'  # Default value

# Set the filter to limit search to a specific file, if desired
filter_file = input("Enter filename to filter (or press Enter to search all files): ").strip()
if not filter_file:
    filter_file = None

# Perform the search
search_results = search(user_query, top_k=10, filter_file=filter_file, search_type=search_type)

# Display the results using rich
console = Console()

if search_results:
    console.print(f"\n[bold underline]Top {len(search_results)} results:[/bold underline]\n")

    for idx, result in enumerate(search_results):
        console.rule(f"Result {idx + 1}")
        file_name = os.path.basename(result['file_path'])
        chapter_name = result['chapter_name']
        page_number = result['page_number']
        distance = result['distance']
        snippet = result['snippet']

        # Create a rich Text object for the snippet
        snippet_text = Text(snippet, justify="left")

        console.print(f"[bold]File:[/bold] {file_name}")
        console.print(f"[bold]Chapter:[/bold] {chapter_name}")
        console.print(f"[bold]Page Number:[/bold] {page_number}")
        console.print(f"[bold]Distance:[/bold] {distance:.4f}")
        console.print(f"[bold]Snippet:[/bold]\n{snippet_text}\n")
else:
    console.print("\n[bold red]No results found.[/bold red]")


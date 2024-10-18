import faiss
import json

# Paths
faiss_index_path = '/Users/vbamba/Projects/collectedworks/indexes/faiss_index.bin'
metadata_path = '/Users/vbamba/Projects/collectedworks/indexes/metadata.json'

# Load FAISS index
index = faiss.read_index(faiss_index_path)
faiss_count = index.ntotal

# Load metadata
with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

# Search for the specific snippet
target_snippet = "All can be done if the god-touch is there."
target_indices = [i for i, entry in enumerate(metadata) if target_snippet in entry.get('snippet', '')]

if not target_indices:
    print("❌ Target snippet not found in metadata.json.")
else:
    print(f"✅ Target snippet found at indices: {target_indices}")
    for idx in target_indices:
        print(f"Index: {idx}, Snippet: {metadata[idx]['snippet']}")

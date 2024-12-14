import faiss
import numpy as np
import json
from sentence_transformers import SentenceTransformer

# Load FAISS index
#index = faiss.read_index('/Users/vbamba/Projects/collectedworks/indexes/faiss_index.bin')
index = faiss.read_index('/Users/vbamba/Projects/collectedworks21/backend/indexes/faiss_index.bin')

# Load metadata
with open('/Users/vbamba/Projects/collectedworks21/backend/indexes/metadata.json', 'r', encoding='utf-8') as f:
    metadata = json.load(f)

# Load model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# Exact phrase query
query = "as in a mystic and dynamic dance"
query_embedding = model.encode(query, convert_to_numpy=True).astype('float32')
query_embedding = np.expand_dims(query_embedding, axis=0)

# Perform search
distances, indices = index.search(query_embedding, 5)
print("Search Results:")
threshold = 1  # Adjust 
for distance, idx in zip(distances[0], indices[0]):
    #if idx < len(metadata):
    if distance <= threshold and idx < len(metadata):    
        snippet = metadata[idx]['snippet']
        print(f"Distance: {distance}, Snippet: {snippet}")
    else:
        print(f"Distance: {distance}, Snippet: Invalid Index {idx}")

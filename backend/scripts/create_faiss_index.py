import os
import openai
import faiss
import numpy as np

# Set your OpenAI API key
openai.api_key = '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'  


def get_embedding(text):
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"  # OpenAI's model for embeddings
    )
    return response['data'][0]['embedding']

def create_embeddings_from_texts(text_directory):
    embeddings = []
    file_paths = []

    # Traverse the directory to find all text files
    for root, dirs, files in os.walk(text_directory):
        for file in files:
            if file.endswith('.txt'):
                text_file_path = os.path.join(root, file)
                with open(text_file_path, 'r') as text_file:
                    text = text_file.read()
                
                # Generate embedding for the text
                embedding = get_embedding(text)
                embeddings.append(embedding)
                file_paths.append(text_file_path)

    # Convert embeddings to numpy array
    embeddings_np = np.array(embeddings).astype('float32')

    # Create FAISS index
    index = faiss.IndexFlatL2(embeddings_np.shape[1])  # L2 distance metric
    index.add(embeddings_np)  # Add embeddings to the FAISS index

    # Save the FAISS index to a file
    faiss.write_index(index, 'faiss_index.bin')
    print("FAISS index created and stored as faiss_index.bin")

    # Return the file paths
    return file_paths

# Set the directory where your text files are stored
text_directory = '/home/ec2-user/pdfs/'

# Create the FAISS index
file_paths = create_embeddings_from_texts(text_directory)

# Optionally, you can save the file paths for later reference
with open('file_paths.txt', 'w') as f:
    for path in file_paths:
        f.write(f"{path}\n")

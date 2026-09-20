import os
import json
import sqlite3
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# -----------------------------------------------------------------------------
load_dotenv()

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
CHUNKS_DIR = "../../data/out_chapters"
PERSIST_DIR = "../../db/chroma_db"
SQLITE_DB = "../../db/chapters.db"

# -----------------------------------------------------------------------------
# IMPORT LANGCHAIN COMPONENTS
# -----------------------------------------------------------------------------
try:
    from langchain_openai import OpenAIEmbeddings
    from langchain_chroma import Chroma    
    #from langchain_community.vectorstores import Chroma
    from langchain.schema import Document
    from langchain.text_splitter import TokenTextSplitter
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing required packages. Install with: pip install -U python-dotenv langchain-openai langchain-community tiktoken"
    ) from e

# -----------------------------------------------------------------------------
# LOAD DOCUMENTS FROM JSON
# -----------------------------------------------------------------------------
def load_docs_from_json():
    docs = []
    for collection in os.listdir(CHUNKS_DIR):
        coll_path = os.path.join(CHUNKS_DIR, collection)
        if not os.path.isdir(coll_path):
            continue
        for sub in os.listdir(coll_path):
            sub_path = os.path.join(coll_path, sub)
            # collection/book
            if os.path.isdir(sub_path) and os.path.isfile(os.path.join(sub_path, 'metadata.json')):
                with open(os.path.join(sub_path, 'metadata.json'), 'r', encoding='utf-8') as mf:
                    entries = json.load(mf)
                for e in entries:
                    txt_path = os.path.join(sub_path, e['filename'])
                    if os.path.isfile(txt_path):
                        text = open(txt_path, 'r', encoding='utf-8').read()
                        docs.append(Document(
                            page_content=text,
                            metadata={
                                'collection': collection,
                                'author': None,
                                'book': e['book_name'],
                                'chapter': e['section_title'],
                                'start_page': e.get('start_page'),
                                'end_page': e.get('end_page'),
                                'source': txt_path
                            }
                        ))
            # collection/author/book
            elif os.path.isdir(sub_path):
                author = sub
                for book in os.listdir(sub_path):
                    book_dir = os.path.join(sub_path, book)
                    meta_file = os.path.join(book_dir, 'metadata.json')
                    if os.path.isfile(meta_file):
                        with open(meta_file, 'r', encoding='utf-8') as mf:
                            entries = json.load(mf)
                        for e in entries:
                            txt_path = os.path.join(book_dir, e['filename'])
                            if os.path.isfile(txt_path):
                                text = open(txt_path, 'r', encoding='utf-8').read()
                                docs.append(Document(
                                    page_content=text,
                                    metadata={
                                        'collection': collection,
                                        'author': author,
                                        'book': e['book_name'],
                                        'chapter': e['section_title'],
                                        'start_page': e.get('start_page'),
                                        'end_page': e.get('end_page'),
                                        'source': txt_path
                                    }
                                ))
    return docs

# -----------------------------------------------------------------------------
# LOAD DOCUMENTS FROM SQLITE DB
# -----------------------------------------------------------------------------
def load_docs_from_db():
    docs = []
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT group_name, author, book_title, section_filename, content FROM chapters'
    )
    for collection, author, book, chapter, content_text in cursor.fetchall():
        if content_text:
            docs.append(Document(
                page_content=content_text,
                metadata={
                    'collection': collection,
                    'author': author,
                    'book': book,
                    'chapter': chapter,
                    'source': f"{collection}/{book}/{chapter}"
                }
            ))
    conn.close()
    return docs

# -----------------------------------------------------------------------------
# MAIN INGESTION & INDEX BUILD
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    use_db = os.getenv('USE_DB_FOR_CHROMA', 'false').lower() == 'true'
    print("Loading documents from DB..." if use_db else "Loading documents from metadata.json files...")
    raw_docs = load_docs_from_db() if use_db else load_docs_from_json()
    print(f"Total raw documents: {len(raw_docs)}")

    # Split into token-based chunks to respect API limits
    splitter = TokenTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        encoding_name="cl100k_base"
    )
    docs = splitter.split_documents(raw_docs)
    print(f"Total split chunks: {len(docs)}")

    # Initialize embeddings
    embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

    # Build Chroma index in batches to avoid token limits
    vectordb = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=embeddings,
        collection_name="pdf_library"
    )
    batch_size = 200
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        vectordb.add_documents(batch)
        print(f"Indexed batch {i // batch_size + 1}: {len(batch)} documents")

    print(f"Persisted total {len(docs)} chunks to Chroma at {PERSIST_DIR}")

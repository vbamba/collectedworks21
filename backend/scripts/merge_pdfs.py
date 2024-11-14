from PyPDF2 import PdfMerger
import sys
import os

def merge_pdfs(paths, output):
    merger = PdfMerger()
    for path in paths:
        merger.append(path)
    merger.write(output)
    merger.close()

if __name__ == "__main__":
    pdf_dir = '/Users/vbamba/Projects/collectedworks21/backend/pdf/temp/'  # Update this path
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
    pdf_paths = [os.path.join(pdf_dir, f) for f in pdf_files]
    merge_pdfs(pdf_paths, 'merged_output.pdf')

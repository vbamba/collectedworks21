import os
import pdfplumber

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text()
    return text

def extract_text_from_pdfs(pdf_directory, output_directory):
    # Traverse the directory to find all PDF files
    for root, dirs, files in os.walk(pdf_directory):
        for file in files:
            if file.endswith('.pdf'):
                pdf_path = os.path.join(root, file)

                # Extract text from the PDF
                print(f"Extracting text from: {pdf_path}")
                text = extract_text_from_pdf(pdf_path)

                if text:  # Only save if text was extracted
                    # Create a corresponding .txt file to save the extracted text
                    output_file = os.path.join(output_directory, file.replace('.pdf', '.txt'))

                    # Ensure the output directory exists
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)

                    # Write the extracted text to the .txt file
                    with open(output_file, 'w') as f:
                        f.write(text)
                    print(f"Text saved to: {output_file}")
                else:
                    print(f"No text extracted from {pdf_path}")

# Example usage
pdf_directory = '/Users/vbamba/Projects/collectedworks/pdfs'  # Path to your PDFs
output_directory = '/Users/vbamba/Projects/collectedworks/text'  # Path where you want to save the extracted text

extract_text_from_pdfs(pdf_directory, output_directory)

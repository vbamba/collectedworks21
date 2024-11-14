import json

def verify_metadata(pdf_filename, expected_fields=None, metadata_path='metadata.json'):
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Filter entries for the specified PDF
    pdf_entries = [entry for entry in metadata if pdf_filename in entry.get('file_path', '')]
    
    if not pdf_entries:
        print(f"No entries found for '{pdf_filename}'.")
        return
    
    for i, entry in enumerate(pdf_entries, start=1):
        print(f"Entry {i}:")
        for key, value in entry.items():
            print(f"  {key}: {value}")
        print("\n")
        
        # Optional: Verify specific fields
        if expected_fields:
            for field, expected_value in expected_fields.items():
                actual_value = entry.get(field)
                if actual_value != expected_value:
                    print(f"  [WARNING] {field} mismatch: expected '{expected_value}', found '{actual_value}'")
    
if __name__ == "__main__":
    pdf_filename = "The-Mother-MCW-Vol10-On-Aphorisms.pdf"
    expected_fields = {
        "book_title": "On Aphorisms.",
        "author": "THe Mother",
        "group": "CWM",
        "priority": 99
    }
    metadata_path = '/Users/vbamba/Projects/collectedworks21/backend/indexes/metadata.json'
    
    verify_metadata(pdf_filename, expected_fields, metadata_path)

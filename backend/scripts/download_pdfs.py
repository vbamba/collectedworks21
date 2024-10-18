import boto3
import os

s3 = boto3.client('s3')
bucket_name = 'sa-mira-collectedworks'
local_folder = '/home/ec2-user/pdfs/'

# Ensure the local folder exists
os.makedirs(local_folder, exist_ok=True)

def download_pdfs():
    # List all the objects (PDFs) in the bucket recursively
    response = s3.list_objects_v2(Bucket=bucket_name)
    
    for obj in response.get('Contents', []):
        key = obj['Key']
        
        # Skip "directory-like" keys
        if key.endswith('/'):
            continue
        
        # Create local file path, replicating folder structure from S3
        local_file = os.path.join(local_folder, key)
        
        # Create subdirectories if needed
        local_file_dir = os.path.dirname(local_file)
        os.makedirs(local_file_dir, exist_ok=True)
        
        # Download the PDF
        try:
            s3.download_file(bucket_name, key, local_file)
            print(f'Downloaded {key} to {local_file}')
        except Exception as e:
            print(f"Error downloading {key}: {e}")

download_pdfs()

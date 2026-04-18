import os
import sys
import time
import boto3


def create_s3_bucket(bucket_name, region):
    s3 = boto3.client("s3", region_name=region)
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"Created S3 bucket: {bucket_name}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"Bucket already exists: {bucket_name}")


def upload_directory(local_dir, bucket_name, prefix, region):
    s3 = boto3.client("s3", region_name=region)
    count = 0
    for root, dirs, files in os.walk(local_dir):
        for filename in files:
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, local_dir)
            s3_key = f"{prefix}/{rel_path}"
            s3.upload_file(local_path, bucket_name, s3_key)
            count += 1
    print(f"Uploaded {count} files to s3://{bucket_name}/{prefix}/")


if __name__ == "__main__":
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    bucket = os.environ.get("S3_BUCKET_NAME", "agnes-hackathon-kb")

    create_s3_bucket(bucket, region)

    scraped_dir = "data/scraped"
    if os.path.isdir(scraped_dir):
        upload_directory(scraped_dir, bucket, "scraped-products", region)

    fda_dir = "docs/fda"
    if os.path.isdir(fda_dir):
        upload_directory(fda_dir, bucket, "fda-regulations", region)

    print("\nNext steps:")
    print("1. Go to AWS Console -> Bedrock -> Knowledge bases")
    print(f"2. Create a Knowledge Base pointing to s3://{bucket}/")
    print("3. Copy the Knowledge Base ID into your .env file as KNOWLEDGE_BASE_ID")

import os
import boto3

SCRAPED_DIR = "data/scraped"


def upload_scraped_to_s3(bucket_name=None, prefix="scraped-products"):
    bucket = bucket_name or os.environ.get("S3_BUCKET_NAME", "agnes-hackathon-kb")
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

    count = 0
    for filename in os.listdir(SCRAPED_DIR):
        if not filename.endswith(".json"):
            continue
        local_path = os.path.join(SCRAPED_DIR, filename)
        s3_key = f"{prefix}/{filename}"
        s3.upload_file(local_path, bucket, s3_key)
        count += 1

    print(f"Uploaded {count} files to s3://{bucket}/{prefix}/")
    return count


if __name__ == "__main__":
    upload_scraped_to_s3()

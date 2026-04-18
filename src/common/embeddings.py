import json
import os
import time
from botocore.exceptions import ClientError
from src.common.bedrock import get_bedrock_client


def embed_text(text, model_id=None, max_retries=3):
    client = get_bedrock_client()
    model = model_id or os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")

    for attempt in range(max_retries):
        try:
            response = client.invoke_model(
                modelId=model,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )
            result = json.loads(response["body"].read())
            return result["embedding"]
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ThrottlingException" and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def embed_texts(texts, model_id=None):
    return [embed_text(text, model_id=model_id) for text in texts]

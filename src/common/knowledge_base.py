import os
import boto3


def get_kb_client():
    return boto3.client(
        "bedrock-agent-runtime",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def retrieve(query, n_results=5):
    client = get_kb_client()
    kb_id = os.environ["KNOWLEDGE_BASE_ID"]

    response = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": n_results}
        },
    )
    results = []
    for item in response.get("retrievalResults", []):
        results.append({
            "text": item["content"]["text"],
            "score": item.get("score", 0),
            "source": item.get("location", {}).get("s3Location", {}).get("uri", "unknown"),
        })
    return results


def retrieve_and_generate(query, model_id=None):
    client = get_kb_client()
    kb_id = os.environ["KNOWLEDGE_BASE_ID"]
    model = model_id or os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514")
    model_arn = f"arn:aws:bedrock:{os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')}::foundation-model/{model}"

    response = client.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": model_arn,
            },
        },
    )
    output = response["output"]["text"]
    citations = []
    for citation in response.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            citations.append({
                "text": ref["content"]["text"],
                "source": ref.get("location", {}).get("s3Location", {}).get("uri", "unknown"),
            })
    return {"answer": output, "citations": citations}

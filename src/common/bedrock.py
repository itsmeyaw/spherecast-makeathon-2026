import json
import os
import boto3


def get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def invoke_model(prompt, system=None, model_id=None):
    client = get_bedrock_client()
    model = model_id or os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514")

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": messages,
    }
    if system:
        body["system"] = [{"type": "text", "text": system}]

    response = client.invoke_model(
        modelId=model,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def invoke_model_json(prompt, system=None, model_id=None):
    raw = invoke_model(prompt, system=system, model_id=model_id)
    start = raw.find("[") if raw.find("[") < raw.find("{") or raw.find("{") == -1 else raw.find("{")
    end = raw.rfind("]") + 1 if start == raw.find("[") else raw.rfind("}") + 1
    if start == -1:
        return raw
    return json.loads(raw[start:end])

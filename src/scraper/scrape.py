import os
import json
import time
import httpx
from bs4 import BeautifulSoup
from src.scraper.sku_parser import parse_fg_sku
from src.common.bedrock import invoke_model, invoke_model_json

SCRAPED_DIR = "data/scraped"


def scrape_product_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
    response.raise_for_status()
    return response.text


def extract_with_llm(html, sku, company_name):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)[:8000]

    prompt = f"""Extract supplement product information from this webpage text.
Product: {company_name} (SKU: {sku})

Webpage text:
{text}

Return a JSON object with these fields:
- "product_name": string
- "supplement_facts": list of {{"ingredient": string, "amount": string, "daily_value_pct": string or null}}
- "certifications": list of strings (e.g., "NSF Certified", "Non-GMO Project Verified", "USDA Organic")
- "allergen_warnings": list of strings
- "claims": list of strings (e.g., "gluten-free", "vegan", "no artificial colors")

If a field cannot be determined, use an empty list or "unknown"."""

    return invoke_model_json(prompt)


def scrape_and_extract(sku, company_name):
    parsed = parse_fg_sku(sku)
    source = parsed["source"]
    product_id = parsed["product_id"]

    search_query = f"{company_name} {source} {product_id} supplement facts"

    prompt = f"""I need to find the product page for this supplement:
Company: {company_name}
Retail source: {source}
Product identifier: {product_id}

This is a dietary supplement sold on {source}. Based on the identifier, what would the likely product page URL be?
Return ONLY the URL, nothing else."""

    url = invoke_model(prompt).strip()

    try:
        html = scrape_product_page(url)
        extracted = extract_with_llm(html, sku, company_name)
    except Exception:
        extracted = {
            "product_name": "unknown",
            "supplement_facts": [],
            "certifications": [],
            "allergen_warnings": [],
            "claims": [],
            "error": f"Could not scrape {url}",
        }

    result = {"sku": sku, "company": company_name, "source": source, "url": url, **extracted}

    os.makedirs(SCRAPED_DIR, exist_ok=True)
    safe_sku = sku.replace("/", "_")
    with open(f"{SCRAPED_DIR}/{safe_sku}.json", "w") as f:
        json.dump(result, f, indent=2)

    return result


def scrape_all_products(db_path=None):
    from src.common.db import get_finished_goods
    products = get_finished_goods(db_path)
    results = []
    for p in products:
        print(f"Scraping {p['sku']} ({p['company_name']})...")
        result = scrape_and_extract(p["sku"], p["company_name"])
        results.append(result)
        time.sleep(1)
    return results

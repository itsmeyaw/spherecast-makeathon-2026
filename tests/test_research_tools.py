from unittest.mock import MagicMock, patch

import httpx


def test_search_documents_returns_ok_with_results():
    mock_results = [
        {"text": "Vitamin D3 supplement facts", "score": 0.95, "source": "s3://docs/product.json", "section_title": "Supplement Facts", "metadata": "{}"},
        {"text": "FDA labeling requirement", "score": 0.88, "source": "s3://docs/fda.pdf", "section_title": "Labeling", "metadata": "{}"},
    ]
    with patch("src.compliance.tools.search_documents.retrieve", return_value=mock_results):
        from src.compliance.tools.search_documents import search_documents
        result = search_documents(query="vitamin D3 supplement facts", n_results=5)

    assert result["status"] == "ok"
    assert len(result["data"]) == 2
    assert result["data"][0]["text"] == "Vitamin D3 supplement facts"
    assert result["data"][0]["source"] == "s3://docs/product.json"


def test_search_documents_returns_ok_empty_when_no_results():
    with patch("src.compliance.tools.search_documents.retrieve", return_value=[]):
        from src.compliance.tools.search_documents import search_documents
        result = search_documents(query="nonexistent ingredient xyz", n_results=5)

    assert result["status"] == "ok"
    assert result["data"] == []


def test_search_documents_returns_error_on_exception():
    with patch("src.compliance.tools.search_documents.retrieve", side_effect=Exception("connection refused")):
        from src.compliance.tools.search_documents import search_documents
        result = search_documents(query="vitamin D3", n_results=5)

    assert result["status"] == "error"
    assert "connection refused" in result["message"]


def test_query_database_product_bom():
    mock_components = [
        {"bom_id": 1, "product_id": 100, "sku": "RM-C1-vitamin-c-abcd1234", "company_id": 1, "component_company_name": "TestCo"},
    ]
    with patch("src.compliance.tools.query_database.get_bom_components", return_value=mock_components):
        from src.compliance.tools.query_database import query_database
        result = query_database(query_type="product_bom", product_id=10)

    assert result["status"] == "ok"
    assert len(result["data"]) == 1
    assert result["data"][0]["sku"] == "RM-C1-vitamin-c-abcd1234"


def test_query_database_ingredient_aliases():
    mock_aliases = [
        {"Id": 1, "CanonicalName": "vitamin-c", "AliasName": "ascorbic-acid", "MatchType": "alias", "Notes": "same entity", "Approved": 1},
    ]
    with patch("src.compliance.tools.query_database.get_alias_rows", return_value=mock_aliases):
        from src.compliance.tools.query_database import query_database
        result = query_database(query_type="ingredient_aliases", ingredient_name="ascorbic-acid")

    assert result["status"] == "ok"
    assert result["data"][0]["CanonicalName"] == "vitamin-c"


def test_query_database_ingredient_facts():
    with patch(
        "src.compliance.tools.query_database.get_cached_ingredient_facts",
        return_value={"canonical_name": "vitamin-c", "vegan_compatible": True, "allergens": [], "certifications": ["demo-identity-reviewed"], "evidence_strength": "high", "notes": "demo"},
    ):
        from src.compliance.tools.query_database import query_database
        result = query_database(query_type="ingredient_facts", ingredient_name="vitamin-c")

    assert result["status"] == "ok"
    assert result["data"]["canonical_name"] == "vitamin-c"


def test_query_database_unknown_query_type():
    from src.compliance.tools.query_database import query_database
    result = query_database(query_type="nonexistent_query", product_id=1)
    assert result["status"] == "error"
    assert "Unknown query_type" in result["message"]


def test_web_search_returns_results():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"title": "FDA Vitamin D3 Guidance", "url": "https://fda.gov/d3", "description": "Labeling requirements for vitamin D3"},
                {"title": "D3 Safety Review", "url": "https://example.com/d3", "description": "Safety review of D3 supplements"},
            ]
        }
    }
    with patch("src.compliance.tools.web_search.httpx.get", return_value=mock_response):
        with patch.dict("os.environ", {"BRAVE_API_KEY": "test-key"}):
            from src.compliance.tools.web_search import web_search
            result = web_search(query="FDA vitamin D3 labeling requirements")

    assert result["status"] == "ok"
    assert len(result["data"]) == 2
    assert result["data"][0]["title"] == "FDA Vitamin D3 Guidance"


def test_web_search_returns_error_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        import importlib
        import src.compliance.tools.web_search as ws_mod
        importlib.reload(ws_mod)
        result = ws_mod.web_search(query="test query")

    assert result["status"] == "error"
    assert "BRAVE_API_KEY" in result["message"]


def test_pubchem_lookup_by_name():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "PC_Compounds": [
            {
                "id": {"id": {"cid": 5280795}},
                "props": [
                    {"urn": {"label": "IUPAC Name", "name": "Preferred"}, "value": {"sval": "cholecalciferol"}},
                    {"urn": {"label": "Molecular Formula"}, "value": {"sval": "C27H44O"}},
                    {"urn": {"label": "Molecular Weight"}, "value": {"fval": 384.64}},
                ],
            }
        ]
    }
    with patch("src.compliance.tools.pubchem_lookup.httpx.get", return_value=mock_response):
        from src.compliance.tools.pubchem_lookup import pubchem_lookup
        result = pubchem_lookup(compound="cholecalciferol")

    assert result["status"] == "ok"
    assert result["data"]["cid"] == 5280795


def test_pubchem_lookup_not_found():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )
    with patch("src.compliance.tools.pubchem_lookup.httpx.get", return_value=mock_response):
        from src.compliance.tools.pubchem_lookup import pubchem_lookup
        result = pubchem_lookup(compound="xyznonexistent12345")

    assert result["status"] == "error"


def test_fda_lookup_labeling():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"openfda": {"brand_name": ["Test Supplement"]}, "indications_and_usage": ["dietary supplement"]},
        ]
    }
    with patch("src.compliance.tools.fda_lookup.httpx.get", return_value=mock_response):
        from src.compliance.tools.fda_lookup import fda_lookup
        result = fda_lookup(ingredient_name="vitamin D3", endpoint="labeling")

    assert result["status"] == "ok"
    assert len(result["data"]) == 1


def test_fda_lookup_adverse_events():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"reactions": ["nausea"], "serious": 1},
        ]
    }
    with patch("src.compliance.tools.fda_lookup.httpx.get", return_value=mock_response):
        from src.compliance.tools.fda_lookup import fda_lookup
        result = fda_lookup(ingredient_name="vitamin D3", endpoint="adverse_events")

    assert result["status"] == "ok"
    assert len(result["data"]) == 1


def test_fda_lookup_invalid_endpoint():
    from src.compliance.tools.fda_lookup import fda_lookup
    result = fda_lookup(ingredient_name="vitamin D3", endpoint="invalid")
    assert result["status"] == "error"
    assert "Unknown endpoint" in result["message"]

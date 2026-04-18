from unittest.mock import patch


def test_search_tds_local_results_only():
    mock_local = [
        {"text": "Purity: 99.5%, Heavy metals (Pb): <0.5ppm", "score": 0.85, "source": "s3://tds/adm-vitc.pdf", "section_title": "Specifications"},
    ]
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": mock_local}):
        from src.compliance.tools.search_tds import search_tds
        result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "ok"
    assert len(result["data"]["local_results"]) == 1
    assert result["data"]["web_results"] == []
    assert result["data"]["supplier_name"] == "ADM"


def test_search_tds_falls_back_to_web_when_local_empty():
    mock_web = {
        "status": "ok",
        "data": [
            {"title": "ADM Vitamin C TDS", "url": "https://adm.com/tds", "description": "Purity 99.5%"},
        ],
    }
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": []}):
        with patch("src.compliance.tools.search_tds.web_search", return_value=mock_web):
            from src.compliance.tools.search_tds import search_tds
            result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "ok"
    assert result["data"]["local_results"] == []
    assert len(result["data"]["web_results"]) == 1


def test_search_tds_falls_back_to_web_when_local_low_scores():
    mock_local = [
        {"text": "unrelated content", "score": 0.15, "source": "s3://docs/other.pdf", "section_title": "Intro"},
    ]
    mock_web = {
        "status": "ok",
        "data": [{"title": "TDS Result", "url": "https://example.com", "description": "specs"}],
    }
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": mock_local}):
        with patch("src.compliance.tools.search_tds.web_search", return_value=mock_web):
            from src.compliance.tools.search_tds import search_tds
            result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "ok"
    assert len(result["data"]["local_results"]) == 1
    assert len(result["data"]["web_results"]) == 1


def test_search_tds_without_supplier_name():
    mock_local = [
        {"text": "Generic vitamin C specs", "score": 0.70, "source": "s3://docs/generic.pdf", "section_title": "Specs"},
    ]
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": mock_local}):
        from src.compliance.tools.search_tds import search_tds
        result = search_tds(ingredient_name="vitamin-c")

    assert result["status"] == "ok"
    assert result["data"]["supplier_name"] is None


def test_search_tds_handles_search_documents_error():
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "error", "message": "connection refused"}):
        from src.compliance.tools.search_tds import search_tds
        result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "error"
    assert "connection refused" in result["message"]


def test_search_tds_skips_web_when_no_brave_key():
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": []}):
        with patch("src.compliance.tools.search_tds.web_search", return_value={"status": "error", "message": "BRAVE_API_KEY environment variable not set"}):
            from src.compliance.tools.search_tds import search_tds
            result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "ok"
    assert result["data"]["local_results"] == []
    assert result["data"]["web_results"] == []

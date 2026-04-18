from src.scraper.sku_parser import parse_fg_sku, build_search_query


class TestParseFgSku:
    def test_iherb(self):
        result = parse_fg_sku("FG-iherb-10421")
        assert result["source"] == "iherb"
        assert result["product_id"] == "10421"

    def test_thrive_market(self):
        result = parse_fg_sku("FG-thrive-market-thorne-vitamin-d-5-000")
        assert result["source"] == "thrive-market"
        assert result["product_id"] == "thorne-vitamin-d-5-000"

    def test_amazon(self):
        result = parse_fg_sku("FG-amazon-b0002wrqy4")
        assert result["source"] == "amazon"
        assert result["product_id"] == "b0002wrqy4"

    def test_walmart(self):
        result = parse_fg_sku("FG-walmart-8053802024")
        assert result["source"] == "walmart"
        assert result["product_id"] == "8053802024"

    def test_target(self):
        result = parse_fg_sku("FG-target-a-10996455")
        assert result["source"] == "target"
        assert result["product_id"] == "a-10996455"

    def test_cvs(self):
        result = parse_fg_sku("FG-cvs-704167")
        assert result["source"] == "cvs"
        assert result["product_id"] == "704167"

    def test_walgreens(self):
        result = parse_fg_sku("FG-walgreens-prod6083374")
        assert result["source"] == "walgreens"
        assert result["product_id"] == "prod6083374"

    def test_costco(self):
        result = parse_fg_sku("FG-costco-11467951")
        assert result["source"] == "costco"
        assert result["product_id"] == "11467951"

    def test_vitacost(self):
        result = parse_fg_sku("FG-vitacost-vitacost-magnesium")
        assert result["source"] == "vitacost"
        assert result["product_id"] == "vitacost-magnesium"

    def test_sams_club(self):
        result = parse_fg_sku("FG-sams-club-prod15990273")
        assert result["source"] == "sams-club"
        assert result["product_id"] == "prod15990273"

    def test_gnc(self):
        result = parse_fg_sku("FG-gnc-145223")
        assert result["source"] == "gnc"
        assert result["product_id"] == "145223"

    def test_the_vitamin_shoppe(self):
        result = parse_fg_sku("FG-the-vitamin-shoppe-vs-2750")
        assert result["source"] == "the-vitamin-shoppe"
        assert result["product_id"] == "vs-2750"


class TestBuildSearchQuery:
    def test_builds_query_from_sku_and_company(self):
        query = build_search_query("FG-iherb-10421", "NOW Foods")
        assert "NOW Foods" in query
        assert "iherb" in query
        assert "10421" in query

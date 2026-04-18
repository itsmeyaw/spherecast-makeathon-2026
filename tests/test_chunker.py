# tests/test_chunker.py
from src.common.chunker import chunk_sections


class TestChunkSections:
    def test_short_section_stays_intact(self):
        sections = [{"section_title": "Intro", "content": "Short text."}]
        chunks = chunk_sections(sections, max_tokens=500, overlap_tokens=100)
        assert len(chunks) == 1
        assert chunks[0]["section_title"] == "Intro"
        assert chunks[0]["content"] == "Short text."
        assert chunks[0]["chunk_index"] == 0

    def test_long_section_is_split(self):
        long_text = "This is a sentence. " * 200
        sections = [{"section_title": "Long", "content": long_text}]
        chunks = chunk_sections(sections, max_tokens=100, overlap_tokens=20)
        assert len(chunks) > 1
        assert all(c["section_title"] == "Long" for c in chunks)
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i

    def test_multiple_sections(self):
        sections = [
            {"section_title": "A", "content": "First section."},
            {"section_title": "B", "content": "Second section."},
        ]
        chunks = chunk_sections(sections, max_tokens=500, overlap_tokens=100)
        assert len(chunks) == 2
        assert chunks[0]["section_title"] == "A"
        assert chunks[0]["chunk_index"] == 0
        assert chunks[1]["section_title"] == "B"
        assert chunks[1]["chunk_index"] == 0

    def test_chunk_overlap_contains_shared_text(self):
        sentences = [f"Sentence number {i} is here." for i in range(50)]
        long_text = " ".join(sentences)
        sections = [{"section_title": "Overlap", "content": long_text}]
        chunks = chunk_sections(sections, max_tokens=50, overlap_tokens=15)
        if len(chunks) >= 2:
            first_end_words = set(chunks[0]["content"].split()[-10:])
            second_start_words = set(chunks[1]["content"].split()[:10])
            assert len(first_end_words & second_start_words) > 0

    def test_empty_sections_skipped(self):
        sections = [
            {"section_title": "Empty", "content": ""},
            {"section_title": "Full", "content": "Has content."},
        ]
        chunks = chunk_sections(sections, max_tokens=500, overlap_tokens=100)
        assert len(chunks) == 1
        assert chunks[0]["section_title"] == "Full"

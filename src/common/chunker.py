import re


def _estimate_tokens(text):
    return len(text.split())


def _split_into_sentences(text):
    pattern = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s'
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_sections(sections, max_tokens=500, overlap_tokens=100):
    chunks = []
    for section in sections:
        content = section["content"].strip()
        if not content:
            continue

        title = section["section_title"]

        if _estimate_tokens(content) <= max_tokens:
            chunks.append({
                "section_title": title,
                "content": content,
                "chunk_index": 0,
            })
            continue

        sentences = _split_into_sentences(content)
        current_chunk = []
        current_tokens = 0
        chunk_index = 0

        for sentence in sentences:
            sentence_tokens = _estimate_tokens(sentence)
            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                chunks.append({
                    "section_title": title,
                    "content": " ".join(current_chunk),
                    "chunk_index": chunk_index,
                })
                chunk_index += 1

                overlap_chunk = []
                overlap_count = 0
                for s in reversed(current_chunk):
                    s_tokens = _estimate_tokens(s)
                    if overlap_count + s_tokens > overlap_tokens:
                        break
                    overlap_chunk.insert(0, s)
                    overlap_count += s_tokens

                current_chunk = overlap_chunk
                current_tokens = overlap_count

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        if current_chunk:
            chunks.append({
                "section_title": title,
                "content": " ".join(current_chunk),
                "chunk_index": chunk_index,
            })

    return chunks

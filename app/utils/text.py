import re

_URL_RE = re.compile(r"https?://\S+")
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s", re.MULTILINE)


def split_chunks(text: str, size: int = 800) -> list[str]:
    """텍스트를 500~1000자 단위 청크로 분할."""
    words = text.split()
    chunks: list[str] = []
    buf: list[str] = []
    length = 0
    for word in words:
        wl = len(word) + 1
        if length + wl > size and buf:
            chunks.append(" ".join(buf))
            buf, length = [word], wl
        else:
            buf.append(word)
            length += wl
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def split_markdown(text: str, size: int = 800) -> list[str]:
    """Markdown 헤딩 기준으로 1차 분할 후 size 초과 시 단어 단위 재분할.

    Jina Reader가 반환한 Markdown 전문에 적합.
    """
    # 헤딩(#, ##, ...) 앞에서 분할
    parts = _MARKDOWN_HEADING.split(text)
    # 헤딩 텍스트도 보존 (split이 delimiter를 버리므로 복원)
    headings = _MARKDOWN_HEADING.findall(text)
    sections: list[str] = []
    for i, part in enumerate(parts):
        heading = headings[i - 1] if i > 0 else ""
        sections.append((heading + part).strip())

    chunks: list[str] = []
    for section in sections:
        if not section:
            continue
        if len(section) <= size:
            chunks.append(section)
        else:
            # 섹션이 너무 크면 단어 단위 재분할
            chunks.extend(split_chunks(section, size))
    return [c for c in chunks if c]


def extract_urls(text: str) -> tuple[list[str], str | None]:
    """텍스트에서 URL과 memo 분리. (urls, memo) 반환."""
    urls = _URL_RE.findall(text)
    memo = (_URL_RE.sub("", text).strip() or None) if len(urls) == 1 else None
    return urls, memo

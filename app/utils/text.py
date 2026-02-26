import re

_URL_RE = re.compile(r"https?://\S+")


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


def extract_urls(text: str) -> tuple[list[str], str | None]:
    """텍스트에서 URL과 memo 분리. (urls, memo) 반환."""
    urls = _URL_RE.findall(text)
    memo = (_URL_RE.sub("", text).strip() or None) if len(urls) == 1 else None
    return urls, memo

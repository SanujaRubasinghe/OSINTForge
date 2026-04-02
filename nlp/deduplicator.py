from __future__ import annotations
from datasketch import MinHash, MinHashLSH

NUM_PERM  = 128
THRESHOLD = 0.70


def build_minhash(text: str, num_perm: int = NUM_PERM) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for word in text.split():
        m.update(word.encode("utf-8"))
    return m


def deduplicate_texts(
    texts: list[str],
    threshold: float = THRESHOLD,
) -> list[int]:
    """
    Returns indices of unique texts after LSH deduplication.
    The first occurrence of each near-duplicate cluster is kept.
    """
    if not texts:
        return []

    lsh    = MinHashLSH(threshold=threshold, num_perm=NUM_PERM)
    unique : list[int] = []

    for i, text in enumerate(texts):
        m   = build_minhash(text)
        key = f"doc_{i}"
        try:
            matches = lsh.query(m)
            if not matches:
                lsh.insert(key, m)
                unique.append(i)
        except Exception:
            unique.append(i)

    return unique


def deduplicate_findings(findings: list[dict]) -> list[dict]:
    """Deduplicates a list of FindingRecord dicts by raw_text content."""
    texts  = [f.get("raw_text", "") for f in findings]
    unique_idx = deduplicate_texts(texts)
    return [findings[i] for i in unique_idx]

import os
import re
from functools import lru_cache
from ..config import ROOT, DATA, LIVE

def documents():
    for path in sorted((ROOT / "knowledge_base").iterdir()):
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            pages = ((f"{path.name} p.{i}", p.extract_text() or "") for i,p in enumerate(PdfReader(path).pages,1))
        elif path.suffix.lower() in {".md", ".txt"}:
            pages = [(path.name, path.read_text(encoding="utf-8"))]
        else:
            continue
        for source, text in pages:
            remaining = text.strip()
            while remaining:
                boundary = len(remaining)
                if boundary > 700:
                    boundary = max(remaining.rfind("\n\n", 350, 700), remaining.rfind(" ", 350, 700), 0) or 700
                yield {"source": source, "text": remaining[:boundary]}
                if boundary == len(remaining):
                    break
                remaining = remaining[boundary - 100:].strip()

@lru_cache(maxsize=1)
def semantic():
    import faiss
    import json
    import hashlib
    from sentence_transformers import SentenceTransformer

    rows = list(documents())
    name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    try:
        model = SentenceTransformer(name, device="cpu", local_files_only=True)
    except Exception:
        model = SentenceTransformer(name, device="cpu")
    fingerprint = hashlib.sha256(json.dumps([name, rows], ensure_ascii=False).encode()).hexdigest()
    path = DATA / "faiss_index" / f"{fingerprint}.index"
    if path.exists():
        index = faiss.read_index(str(path))
    else:
        vectors = model.encode([row["text"] for row in rows], normalize_embeddings=True)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        path.parent.mkdir(exist_ok=True)
        import tempfile
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
            temporary = tmp.name
        faiss.write_index(index, temporary)
        os.replace(temporary, path)
    return model, index, rows

def search(query):
    if LIVE:
        model, index, rows = semantic()
        scores, ids = index.search(model.encode([query], normalize_embeddings=True), 4)
        return [rows[i] for score,i in zip(scores[0], ids[0]) if i >= 0 and score >= 0.24]
    words = set(re.findall(r"\w+", query.lower())) - {"the","is","a","do","you","how","what","it","for","i","my","can","and","to"}
    ranked = [(len(words & set(re.findall(r"\w+", row["text"].lower()))), row) for row in documents()]
    return [row for weight,row in sorted(ranked,key=lambda pair: -pair[0]) if weight][:1]

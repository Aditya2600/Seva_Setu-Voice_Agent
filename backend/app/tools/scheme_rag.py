from __future__ import annotations
import json, math, re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.llm import chat_completion
from app.settings import settings

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "schemes.json"

def _load() -> List[Dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))

def _tok(text: str) -> List[str]:
    t = (text or "").lower()
    t = re.sub(r"[^\w\sअ-हािीुूृेैोौंःँ़]+", " ", t)
    return [x for x in t.split() if len(x) >= 2]

def _bm25(query: str, docs: List[str]) -> List[Tuple[int,float]]:
    k1, b = 1.2, 0.75
    q = _tok(query)
    if not q:
        return [(i,0.0) for i in range(len(docs))]
    doc_toks = [_tok(d) for d in docs]
    N = len(doc_toks)
    avgdl = sum(len(t) for t in doc_toks) / max(1, N)
    df = {term: sum(1 for dt in doc_toks if term in dt) for term in set(q)}
    scores = []
    for i, dt in enumerate(doc_toks):
        dl = len(dt)
        tf = {}
        for term in dt:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term in q:
            if term not in tf: 
                continue
            n = df.get(term, 0)
            idf = math.log(1 + (N - n + 0.5) / (n + 0.5))
            f = tf[term]
            denom = f + k1 * (1 - b + b * dl / max(1.0, avgdl))
            score += idf * (f * (k1 + 1)) / denom
        scores.append((i, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores

def retrieve_schemes(query_mr: str, k: int = 5) -> List[Dict[str, Any]]:
    schemes = _load()
    if not schemes:
        return []
    docs = []
    for s in schemes:
        docs.append("\n".join([s.get("name_mr",""), s.get("category_mr",""), s.get("benefits_mr",""), s.get("description_mr","")]))
    ranked = _bm25(query_mr, docs)
    out = []
    for idx, score in ranked[:max(1, min(10, k))]:
        s = schemes[idx].copy()
        s["_score"] = float(score)
        out.append(s)
    return out[:k]

def _extract_scheme_id(text: str, valid_ids: List[str]) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    if t in valid_ids:
        return t
    for scheme_id in valid_ids:
        if scheme_id and scheme_id in t:
            return scheme_id
    return None

def select_best_scheme(query_mr: str, schemes: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not schemes:
        return {}

    provider = (settings.llm_provider or "").strip().lower()
    if provider != "groq" or not settings.groq_api_key:
        return schemes[0]

    candidates = []
    for s in schemes[:6]:
        candidates.append({
            "scheme_id": s.get("scheme_id"),
            "name_mr": s.get("name_mr"),
            "category_mr": s.get("category_mr"),
            "description_mr": s.get("description_mr"),
            "benefits_mr": s.get("benefits_mr"),
            "rules": s.get("rules"),
        })

    prompt = (
        "User query (Marathi): " + (query_mr or "") + "\n"
        "Candidates JSON:\n" + json.dumps(candidates, ensure_ascii=False) + "\n"
        "Return ONLY the best matching scheme_id from the candidates."
    )
    messages = [
        {"role": "system", "content": "You select the best scheme_id for the user query. Output only scheme_id."},
        {"role": "user", "content": prompt},
    ]

    try:
        response = chat_completion(messages, temperature=0.0, max_tokens=32)
    except Exception:
        return schemes[0]

    valid_ids = [s.get("scheme_id") for s in schemes if s.get("scheme_id")]
    picked_id = _extract_scheme_id(response, valid_ids)
    if not picked_id:
        return schemes[0]

    for s in schemes:
        if s.get("scheme_id") == picked_id:
            return s
    return schemes[0]

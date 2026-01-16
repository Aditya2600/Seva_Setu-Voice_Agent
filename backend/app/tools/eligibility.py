from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sevasetu")

# --- Normalization helpers (demo-stability for Marathi inputs) ---
def _norm_text(x: Any) -> str:
    return str(x or "").strip().lower()

# Whisper often outputs Marathi state names in Devanagari or slightly misspelled.
# Canonicalize to a stable English key for rule matching.
_STATE_ALIASES = {
    "maharashtra": {
        "maharashtra", "mh",
        "महाराष्ट्र", "महाराष्‍ट्र", "महाष्ट्र",
        "माराष्ट्र", "मारास्ट्र", "मारास्ट्र!", "माराष्ट्र!",
    },
}

def canonical_state(x: Any) -> str:
    t = _norm_text(x)
    # Strip trailing punctuation
    t = t.strip("!?. ,")
    for canon, aliases in _STATE_ALIASES.items():
        if t in aliases:
            return canon
    return t

_GENDER_ALIASES = {
    "female": {"female", "f", "woman", "women", "girl", "महिला", "स्त्री", "बाई", "मुलगी"},
    "male": {"male", "m", "man", "men", "boy", "पुरुष", "नर", "मुलगा"},
    "all": {"all", "any", "सर्व"},
}

def canonical_gender(x: Any) -> str:
    t = _norm_text(x)
    t = t.strip("!?. ,")
    for canon, aliases in _GENDER_ALIASES.items():
        if t in aliases:
            return canon
    return t

def safe_int(val: Any) -> Optional[int]:
    try: return int(float(val))
    except Exception: return None

def _missing(profile: Dict[str, Any], fields: List[str]) -> List[str]:
    out=[]
    for f in fields:
        v=profile.get(f)
        if v is None: out.append(f)
        elif isinstance(v,str) and not v.strip(): out.append(f)
    return out

def check_eligibility(profile: Dict[str, Any], scheme: Dict[str, Any]) -> Dict[str, Any]:
    logger.debug("Eligibility check scheme_id=%s", scheme.get("scheme_id"))
    rules = scheme.get("rules", {}) or {}
    required=[]
    if "max_income_annual" in rules: required.append("income_annual")
    if "gender_eq" in rules: required.append("gender")
    if "state_eq" in rules: required.append("state")
    if "occupation_in" in rules: required.append("occupation")
    if "age_min" in rules or "age_max" in rules: required.append("age")

    missing = _missing(profile, required)
    if missing:
        logger.info("Eligibility missing fields=%s", missing)
        mr_map={"income_annual":"वार्षिक उत्पन्न","age":"वय","gender":"लिंग","occupation":"व्यवसाय","state":"राज्य"}
        readable=[mr_map.get(x,x) for x in missing]
        return {"status":"needs_more_info","missing_fields":missing,"reasons_mr":[f"पात्रता तपासण्यासाठी ही माहिती हवी आहे: {', '.join(readable)}"]}

    reasons=[]
    if "max_income_annual" in rules:
        inc=safe_int(profile.get("income_annual")); limit=safe_int(rules.get("max_income_annual"))
        if inc is not None and limit is not None and inc>limit:
            reasons.append(f"तुमचे उत्पन्न मर्यादेपेक्षा जास्त आहे (Max: ₹{limit}).")

    if "gender_eq" in rules:
        user = canonical_gender(profile.get("gender"))
        req = canonical_gender(rules.get("gender_eq"))
        if req and req != "all" and user != req:
            reasons.append("ही योजना फक्त विशिष्ट लिंगासाठी आहे.")

    if "state_eq" in rules:
        user = canonical_state(profile.get("state"))
        req = canonical_state(rules.get("state_eq"))
        # Loose match: allow contains in either direction for minor transcription noise
        if req and (user != req) and (req not in user) and (user not in req):
            reasons.append("ही योजना विशिष्ट राज्यासाठी आहे.")

    if "occupation_in" in rules:
        user = _norm_text(profile.get("occupation"))
        allowed = [str(x).lower().strip() for x in (rules.get("occupation_in") or [])]
        # If user said Marathi synonyms for farmer, map quickly for common cases
        if user in {"शेतकरी", "शेती", "शेतीकरी", "फार्मर", "किसान"}:
            user = "farmer"
        ok = any(user == a or user in a or a in user for a in allowed)
        if not ok:
            reasons.append("तुमचा व्यवसाय या योजनेसाठी पात्र नाही.")

    age=safe_int(profile.get("age"))
    if age is not None:
        if "age_min" in rules and age<safe_int(rules["age_min"]):
            reasons.append(f"वय कमी आहे (किमान {rules['age_min']} वर्षे).")
        if "age_max" in rules and age>safe_int(rules["age_max"]):
            reasons.append(f"वय जास्त आहे (कमाल {rules['age_max']} वर्षे).")

    if reasons:
        logger.info("Eligibility not eligible reasons=%d", len(reasons))
        return {"status":"not_eligible","missing_fields":[],"reasons_mr":reasons}
    logger.info("Eligibility eligible")
    return {"status":"eligible","missing_fields":[],"reasons_mr":["तुम्ही या योजनेसाठी पात्र आहात!"]}

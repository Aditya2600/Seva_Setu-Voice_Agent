from __future__ import annotations

import logging, re
import difflib
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("sevasetu")

# -----------------------------
# Marathi parsing helpers
# -----------------------------

# Marathi digits -> ASCII digits
_DEV_TO_LAT = str.maketrans("०१२३४५६७८९", "0123456789")

_NUM_WORDS = {
    "शून्य": 0,
    "एक": 1, "एका": 1,
    "दोन": 2,
    "तीन": 3,
    "चार": 4,
    "पाच": 5,
    "सहा": 6,
    "सात": 7,
    "आठ": 8,
    "नऊ": 9,
    "दहा": 10,
    "अकरा": 11,
    "बारा": 12,
    "तेरा": 13,
    "चौदा": 14,
    "पंधरा": 15,
    "सोळा": 16,
    "सतरा": 17,
    "अठरा": 18,
    "एकोणीस": 19,
    "वीस": 20,
    "एकवीस": 21,
    "बावीस": 22,
    "तेवीस": 23,
    "चोवीस": 24,
    "पंचवीस": 25,
    "सव्वीस": 26,
    "सत्तावीस": 27,
    "अठ्ठावीस": 28,
    "एकोणतीस": 29,
    "तीस": 30,
    "एकतीस": 31,
    "बत्तीस": 32,
    "तेहतीस": 33,
    "चौतीस": 34,
    "पस्तीस": 35,
    "छत्तीस": 36,
    "सदतीस": 37,
    "अडतीस": 38,
    "एकोणचाळीस": 39,
    "चाळीस": 40,
    "पन्नास": 50,
    "साठ": 60,
    "सत्तर": 70,
    "ऐंशी": 80,
    "नव्वद": 90,
    "शंभर": 100,
}

STATE_MAP = {
    "महाराष्ट्र": "Maharashtra",
    "maharashtra": "Maharashtra",
    "कर्नाटक": "Karnataka",
    "karnataka": "Karnataka",
    "मध्यप्रदेश": "Madhya Pradesh",
    "madhya pradesh": "Madhya Pradesh",
    "गुजरात": "Gujarat",
    "gujarat": "Gujarat",
    "तेलंगणा": "Telangana",
    "telangana": "Telangana",
    "तामिळनाडू": "Tamil Nadu",
    "tamil nadu": "Tamil Nadu",
    "दिल्ली": "Delhi",
    "delhi": "Delhi",
}

CRITICAL_FIELDS = {"income_annual", "age", "gender", "state", "district", "category", "occupation", "land_holding_acres"}


def _to_ascii(text: str) -> str:
    return (text or "").translate(_DEV_TO_LAT)


def _normalize_letters(text: str) -> str:
    """Lowercase + keep only Latin/Devanagari letters for fuzzy matching."""
    t = _to_ascii(text).lower()
    return re.sub(r"[^a-z\u0900-\u097F]+", "", t)


def _extract_first_number(text: str) -> Optional[float]:
    t = _to_ascii(text).replace(",", "").strip()
    m = re.search(r"(-?\d+(?:\.\d+)?)", t)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _word_number(text: str) -> Optional[int]:
    t = (text or "").strip()
    for w, n in _NUM_WORDS.items():
        if w in t:
            return n
    return None


# -----------------------------
# Slot answer parsers (single value responses)
# -----------------------------

def parse_age_answer(utterance: str) -> Optional[int]:
    n = _extract_first_number(utterance)
    if n is None:
        wn = _word_number(utterance)
        if wn is None:
            return None
        n = float(wn)

    age = int(n)
    if 1 <= age <= 120:
        return age
    return None


def parse_gender_answer(utterance: str) -> Optional[str]:
    t = (utterance or "").lower().strip()

    # Marathi common forms
    if any(x in t for x in ["महिला", "स्त्री", "बाई", "female", "woman", "girl"]):
        return "female"
    if any(x in t for x in ["पुरुष", "male", "man", "boy", "mail", "मेल"]):
        return "male"

    return None


def parse_state_answer(utterance: str) -> Optional[str]:
    raw = (utterance or "").strip()
    t = raw.lower().strip()
    nt = _normalize_letters(raw)

    # 1) Direct map check (normalized substring)
    for k, v in STATE_MAP.items():
        nk = _normalize_letters(k)
        if nk and nk in nt:
            return v

    # 2) Common STT misspellings for Maharashtra (very frequent)
    # Examples observed: "मारास्ट्र", "महारास्ट्र", "महराष्ट्र", "महारष्ट्र", "maharastra"
    maharashtra_hints = [
        "महाराष्ट्र", "महारास्ट्र", "महारष्ट्र", "महराष्ट्र", "माराष्ट्र", "मारास्ट्र",
        "maharashtra", "maharastra"
    ]
    for h in maharashtra_hints:
        if _normalize_letters(h) in nt:
            return "Maharashtra"

    # 3) Lightweight fuzzy match against known states (handles slight ASR noise)
    # Only trigger when the utterance is short-ish (single slot answer)
    if len(nt) <= 18:
        norm_map = { _normalize_letters(k): v for k, v in STATE_MAP.items() }
        keys = [k for k in norm_map.keys() if k]
        best = difflib.get_close_matches(nt, keys, n=1, cutoff=0.84)
        if best:
            return norm_map.get(best[0])

    # 4) Last resort heuristic
    if "महा" in t and "राष्ट्र" in t:
        return "Maharashtra"

    return None


def parse_income_answer(utterance: str) -> Optional[int]:
    # Accept: "200000", "२ लाख", "2 lakh", "दोन लाख", "25 हजार", "२५ हजार"
    raw = (utterance or "").strip()
    t = _to_ascii(raw).lower()

    num = _extract_first_number(t)
    if ("लाख" in t) or ("lakh" in t):
        if num is None:
            wn = _word_number(raw)
            if wn is None:
                return None
            num = float(wn)
        return int(num * 100000)

    if ("हजार" in t) or ("thousand" in t):
        if num is None:
            wn = _word_number(raw)
            if wn is None:
                return None
            num = float(wn)
        return int(num * 1000)

    # If user says only a number, assume annual INR only if looks realistic
    if num is not None:
        val = int(num)
        # too small likely monthly or ambiguous -> reject and ask again
        if val < 10000:
            return None
        return val

    return None


def parse_slot_answer(field: str, utterance: str) -> Optional[Any]:
    if field == "age":
        return parse_age_answer(utterance)
    if field == "gender":
        return parse_gender_answer(utterance)
    if field == "state":
        return parse_state_answer(utterance)
    if field == "income_annual":
        return parse_income_answer(utterance)
    return None


# -----------------------------
# Free-form extractor (when user speaks a full sentence)
# -----------------------------

def extract_profile_updates(text: str) -> Dict[str, Any]:
    """
    Extracts a dict of updates from free-form Marathi utterance.
    This supports both "माझं वय २३ आहे..." and single-slot answers.
    """
    t = (text or "").strip()
    if not t:
        return {}

    updates: Dict[str, Any] = {}

    # gender hints
    g = parse_gender_answer(t)
    if g:
        updates["gender"] = g

    # state hints
    s = parse_state_answer(t)
    if s:
        updates["state"] = s

    # age hints (look for वय/age/वर्ष)
    if ("वय" in t) or ("age" in t.lower()) or ("वर्ष" in t):
        a = parse_age_answer(t)
        if a is not None:
            updates["age"] = a

    # income hints
    if any(k in t for k in ["उत्पन्न", "income", "वार्षिक"]):
        inc = parse_income_answer(t)
        if inc is not None:
            updates["income_annual"] = inc

    # simple occupation hints (optional)
    if any(k in t for k in ["शेतकरी", "farmer", "शेती"]):
        updates["occupation"] = "farmer"
    if any(k in t.lower() for k in ["व्यापारी", "trader", "shopkeeper", "दुकानदार", "business"]):
        updates["occupation"] = "trader"

    if updates:
        logger.debug("Profile updates extracted=%s", updates)
    return updates


# -----------------------------
# Contradiction handling
# -----------------------------

def _values_are_different(old: Any, new: Any) -> bool:
    if old == new:
        return False

    try:
        if str(old).strip().lower() == str(new).strip().lower():
            return False
    except Exception:
        pass

    try:
        if float(old) == float(new):
            return False
    except Exception:
        pass

    return True


def apply_updates_with_contradiction(
    profile: Dict[str, Any],
    pending: Optional[Dict[str, Any]],
    updates: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Applies updates into profile. If a CRITICAL field contradicts old value,
    returns a conflict dict and sets pending confirmation.

    Returns:
      (profile, pending, conflict)
    conflict = {"field":..., "old":..., "new":...} or None
    """
    profile = profile or {}
    pending = pending or None
    updates = updates or {}

    # If we already asked a confirmation and user repeats that field -> accept it as confirmation.
    if pending and pending.get("field") in updates:
        f = pending["field"]
        profile[f] = updates[f]
        pending = None

    conflict: Optional[Dict[str, Any]] = None

    for k, v in updates.items():
        if v is None:
            continue

        old = profile.get(k)

        if k in CRITICAL_FIELDS and old is not None and _values_are_different(old, v):
            # only handle one conflict at a time
            if conflict is None:
                conflict = {"field": k, "old": old, "new": v}
                pending = conflict.copy()
                # do not apply conflicting update yet
                continue

        # apply non-conflicting update
        profile[k] = v

    if conflict:
        logger.info("Profile conflict field=%s old=%s new=%s", conflict.get("field"), conflict.get("old"), conflict.get("new"))
    return profile, pending, conflict

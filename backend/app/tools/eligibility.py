from __future__ import annotations
from typing import Any, Dict, List, Optional

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
    rules = scheme.get("rules", {}) or {}
    required=[]
    if "max_income_annual" in rules: required.append("income_annual")
    if "gender_eq" in rules: required.append("gender")
    if "state_eq" in rules: required.append("state")
    if "occupation_in" in rules: required.append("occupation")
    if "age_min" in rules or "age_max" in rules: required.append("age")

    missing = _missing(profile, required)
    if missing:
        mr_map={"income_annual":"वार्षिक उत्पन्न","age":"वय","gender":"लिंग","occupation":"व्यवसाय","state":"राज्य"}
        readable=[mr_map.get(x,x) for x in missing]
        return {"status":"needs_more_info","missing_fields":missing,"reasons_mr":[f"पात्रता तपासण्यासाठी ही माहिती हवी आहे: {', '.join(readable)}"]}

    reasons=[]
    if "max_income_annual" in rules:
        inc=safe_int(profile.get("income_annual")); limit=safe_int(rules.get("max_income_annual"))
        if inc is not None and limit is not None and inc>limit:
            reasons.append(f"तुमचे उत्पन्न मर्यादेपेक्षा जास्त आहे (Max: ₹{limit}).")

    if "gender_eq" in rules:
        user=(profile.get("gender") or "").lower().strip()
        req=(rules.get("gender_eq") or "").lower().strip()
        if req and req!="all" and user!=req:
            reasons.append("ही योजना फक्त विशिष्ट लिंगासाठी आहे.")

    if "state_eq" in rules:
        user=(profile.get("state") or "").lower().strip()
        req=(rules.get("state_eq") or "").lower().strip()
        if req and user!=req.lower():
            reasons.append("ही योजना विशिष्ट राज्यासाठी आहे.")

    if "occupation_in" in rules:
        user=(profile.get("occupation") or "").lower().strip()
        allowed=[str(x).lower().strip() for x in (rules.get("occupation_in") or [])]
        ok=any(user==a or user in a or a in user for a in allowed)
        if not ok:
            reasons.append("तुमचा व्यवसाय या योजनेसाठी पात्र नाही.")

    age=safe_int(profile.get("age"))
    if age is not None:
        if "age_min" in rules and age<safe_int(rules["age_min"]):
            reasons.append(f"वय कमी आहे (किमान {rules['age_min']} वर्षे).")
        if "age_max" in rules and age>safe_int(rules["age_max"]):
            reasons.append(f"वय जास्त आहे (कमाल {rules['age_max']} वर्षे).")

    if reasons:
        return {"status":"not_eligible","missing_fields":[],"reasons_mr":reasons}
    return {"status":"eligible","missing_fields":[],"reasons_mr":["तुम्ही या योजनेसाठी पात्र आहात!"]}

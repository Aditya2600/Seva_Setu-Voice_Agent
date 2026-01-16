from __future__ import annotations
import logging, random, string
from typing import Any, Dict

logger = logging.getLogger("sevasetu")

def _appid()->str:
    return "MH-"+"".join(random.choices(string.digits,k=4))+"-"+"".join(random.choices(string.ascii_uppercase,k=4))

def submit_application(profile: Dict[str, Any], scheme: Dict[str, Any]) -> Dict[str, Any]:
    app_id=_appid()
    logger.info("Application submitted scheme_id=%s app_id=%s", scheme.get("scheme_id"), app_id)
    return {"status":"submitted","application_id":app_id,"scheme_name":scheme.get("name_mr","Unknown"),
            "next_steps_mr":[f"तुमचा अर्ज क्रमांक {app_id} आहे.","पुढील ७ दिवसात तुम्हाला एसएमएस येईल.","कागदपत्रांची पडताळणी संबंधित कार्यालयात होईल."]}

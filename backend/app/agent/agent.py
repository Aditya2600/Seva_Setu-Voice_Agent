from __future__ import annotations
import logging
from typing import Any, Dict, Tuple, List

from app.tools.scheme_rag import retrieve_schemes, select_best_scheme
from app.tools.eligibility import check_eligibility
from app.tools.mock_apply import submit_application
from app.memory import parse_slot_answer
from app.db import get_scheme_by_id, save_scheme

logger = logging.getLogger("sevasetu")


QUESTIONS_MR = {
    "age": "तुमचे वय किती आहे? फक्त नंबर सांगा.",
    "income_annual": "तुमचे वार्षिक उत्पन्न किती आहे? फक्त आकडा सांगा (उदा. 200000 किंवा 2 लाख).",
    "gender": "तुमचे लिंग काय आहे? (महिला/पुरुष)",
    "state": "तुमचे राज्य कोणते? (उदा. महाराष्ट्र)",
}

def _ensure_state_dict(state: Dict[str, Any] | None) -> Dict[str, Any]:
    return state if isinstance(state, dict) else {}

async def run_agent_turn(
    conn,
    session_id: str,
    utterance: str,
    stt_confidence: float,
    profile: Dict[str, Any],
    pending: Dict[str, Any] | None,
    state: Dict[str, Any] | None,
) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]], Dict[str, Any] | None, Dict[str, Any]]:

    tool_trace: List[Dict[str, Any]] = []
    state = _ensure_state_dict(state)
    logger.debug("Agent turn session_id=%s conf=%.2f text_len=%d", session_id, stt_confidence, len(utterance or ""))

    # --- 0) Handle low confidence speech ---
    if stt_confidence < 0.35:
        logger.info("Low STT confidence conf=%.2f", stt_confidence)
        plan = {
            "next_state": "RESPOND",
            "assistant_message_mr": "आवाज स्पष्ट नाही. कृपया पुन्हा हळू आणि स्पष्ट बोला.",
            "questions_mr": [],
            "tool_calls": [],
            "ui_intent": "error",
            "scheme_id": None,
        }
        tool_trace.append({"type": "plan", "plan": plan})
        ui = {"ui_intent": "error", "questions_mr": [], "cards": []}
        return plan["assistant_message_mr"], ui, tool_trace, pending, state

    # --- 1) Slot-filling mode (ONE BY ONE) ---
    slot = state.get("slot") or {}   # slot = {"scheme_id": "...", "missing": [...], "awaiting": "age"}
    awaiting = slot.get("awaiting")

    if awaiting:
        logger.debug("Slot awaiting field=%s", awaiting)
        val = parse_slot_answer(awaiting, utterance)

        if val is None:
            # ask same question again
            logger.info("Slot answer missing field=%s", awaiting)
            msg = QUESTIONS_MR.get(awaiting, "कृपया माहिती सांगा.")
            plan = {"next_state":"ASK_MISSING","assistant_message_mr":msg,"questions_mr":[msg],"tool_calls":[],"ui_intent":"question","scheme_id":slot.get("scheme_id")}
            tool_trace.append({"type":"plan","plan":plan})
            ui = {"ui_intent":"question","questions_mr":[msg],"cards":[]}
            return msg, ui, tool_trace, pending, state

        # save into profile
        profile[awaiting] = val
        logger.debug("Slot answer field=%s value=%s", awaiting, val)

        # remove from missing list
        missing = [f for f in (slot.get("missing") or []) if f != awaiting]

        if missing:
            next_field = missing[0]
            slot["missing"] = missing
            slot["awaiting"] = next_field
            state["slot"] = slot
            logger.debug("Slot remaining fields=%s", missing)

            msg = QUESTIONS_MR.get(next_field, "कृपया माहिती सांगा.")
            plan = {"next_state":"ASK_MISSING","assistant_message_mr":msg,"questions_mr":[msg],"tool_calls":[],"ui_intent":"question","scheme_id":slot.get("scheme_id")}
            tool_trace.append({"type":"plan","plan":plan})
            ui = {"ui_intent":"question","questions_mr":[msg],"cards":[]}
            return msg, ui, tool_trace, pending, state

        # all missing filled -> run eligibility check again
        scheme_id = slot.get("scheme_id")
        scheme = get_scheme_by_id(conn, scheme_id)  # implement helper; OR load from schemes table
        elig = check_eligibility(profile, scheme)
        logger.info("Eligibility recheck status=%s", elig.get("status"))

        # clear slot mode
        state["slot"] = {}

        # build response
        ui = {"ui_intent": "chat", "questions_mr": [], "cards": [], "eligibility": elig}
        if elig.get("status") == "eligible":
            msg = f"✅ तुम्ही या योजनेसाठी पात्र आहात! लाभ: {scheme.get('benefits_mr','')}\nअर्ज करायचा आहे का?"
        elif elig.get("status") == "not_eligible":
            msg = "❌ तुम्ही या योजनेसाठी पात्र नाही.\n" + "\n".join([f"• {r}" for r in elig.get("reasons_mr",[])])
        else:
            msg = "पात्रता तपासतांना अडचण आली."

        plan = {"next_state":"RESPOND","assistant_message_mr":msg,"questions_mr":[],"tool_calls":[],"ui_intent":"chat","scheme_id":scheme_id}
        tool_trace.append({"type":"plan","plan":plan})
        return msg, ui, tool_trace, pending, state

    # --- 2) Normal mode: retrieval -> eligibility -> maybe slot-fill ---
    # RAG
    logger.info("RAG retrieve query_len=%d", len(utterance or ""))
    tool_trace.append({"type":"tool_call","tool":"scheme_retrieval","input":{"query_mr":utterance,"k":5}})
    schemes = retrieve_schemes(utterance, k=5)
    tool_trace.append({"type":"tool_result","tool":"scheme_retrieval","output":{"count":len(schemes)}})
    logger.info("RAG retrieved count=%d", len(schemes))

    if not schemes:
        logger.info("RAG no matches")
        msg = "क्षमस्व, मला योग्य योजना सापडली नाही. कृपया तुमची गरज थोडी अधिक स्पष्ट सांगा."
        plan = {"next_state":"RESPOND","assistant_message_mr":msg,"questions_mr":[],"tool_calls":[],"ui_intent":"error","scheme_id":None}
        tool_trace.append({"type":"plan","plan":plan})
        ui = {"ui_intent":"error","questions_mr":[],"cards":[]}
        return msg, ui, tool_trace, pending, state

    # pick best scheme (LLM-backed if configured)
    scheme = select_best_scheme(utterance, schemes)
    scheme_id = scheme.get("scheme_id")
    save_scheme(conn, scheme)
    logger.info("Scheme selected scheme_id=%s", scheme_id)

    # eligibility check
    tool_trace.append({"type":"tool_call","tool":"eligibility_check","input":{"scheme_id":scheme_id}})
    elig = check_eligibility(profile, scheme)
    tool_trace.append({"type":"tool_result","tool":"eligibility_check","output":elig})
    logger.info("Eligibility status=%s", elig.get("status"))

    # if needs info -> enter slot-fill mode (one-by-one!)
    if elig.get("status") == "needs_more_info":
        missing = elig.get("missing_fields") or []
        if missing:
            logger.info("Eligibility needs info missing=%s", missing)
            state["slot"] = {"scheme_id": scheme_id, "missing": missing, "awaiting": missing[0]}
            q = QUESTIONS_MR.get(missing[0], "कृपया माहिती सांगा.")
            msg = f"{scheme.get('name_mr','योजना')} साठी पात्रता तपासण्यासाठी:\n{q}"
            plan = {"next_state":"ASK_MISSING","assistant_message_mr":msg,"questions_mr":[q],"tool_calls":[],"ui_intent":"question","scheme_id":scheme_id}
            tool_trace.append({"type":"plan","plan":plan})

            ui = {
                "ui_intent": "question",
                "questions_mr": [q],
                "cards": [{"scheme_id":scheme_id,"title":scheme.get("name_mr"),"benefits":scheme.get("benefits_mr")}],
                "eligibility": elig,
            }
            return msg, ui, tool_trace, pending, state

    # eligible / not eligible direct response
    ui = {
        "ui_intent":"chat",
        "questions_mr":[],
        "cards":[{"scheme_id":scheme_id,"title":scheme.get("name_mr"),"benefits":scheme.get("benefits_mr")}],
        "eligibility": elig,
    }

    if elig.get("status") == "eligible":
        msg = f"✅ {scheme.get('name_mr')} साठी तुम्ही पात्र आहात! लाभ: {scheme.get('benefits_mr','')}\nअर्ज करायचा आहे का?"
    else:
        msg = "❌ तुम्ही पात्र नाही.\n" + "\n".join([f"• {r}" for r in elig.get("reasons_mr",[])])

    plan = {"next_state":"RESPOND","assistant_message_mr":msg,"questions_mr":[],"tool_calls":[],"ui_intent":"chat","scheme_id":scheme_id}
    tool_trace.append({"type":"plan","plan":plan})
    return msg, ui, tool_trace, pending, state

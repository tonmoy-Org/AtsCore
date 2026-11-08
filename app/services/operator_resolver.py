import re
import os
import logging

logger = logging.getLogger("atscore.operator")

INDIAN_STATES_CANONICAL = {
    "andhra pradesh": "Andhra Pradesh",
    "andhra pradesh ok": "Andhra Pradesh",
    "assam": "Assam",
    "bihar & jharkhand": "Bihar & Jharkhand",
    "bihar and jharkhand": "Bihar & Jharkhand",
    "bihar": "Bihar & Jharkhand",
    "jharkhand": "Bihar & Jharkhand",
    "delhi": "Delhi",
    "east uttar pradesh": "East Uttar Pradesh",
    "up east": "East Uttar Pradesh",
    "uttar pradesh (east)": "East Uttar Pradesh",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "haryana ok": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jammu & kashmir": "Jammu & Kashmir",
    "jammu and kashmir": "Jammu & Kashmir",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "kolkata": "Kolkata",
    "kolkata ok": "Kolkata",
    "madhya pradesh & chhattisgarh": "Madhya Pradesh & Chhattisgarh",
    "madhya pradesh & chhattisgarh ok": "Madhya Pradesh & Chhattisgarh",
    "madhya pradesh and chhattisgarh": "Madhya Pradesh & Chhattisgarh",
    "mp and chhattisgarh": "Madhya Pradesh & Chhattisgarh",
    "mp & chhattisgarh": "Madhya Pradesh & Chhattisgarh",
    "madhya pradesh": "Madhya Pradesh & Chhattisgarh",
    "maharashtra & goa": "Maharashtra & Goa",
    "maharashtra and goa": "Maharashtra & Goa",
    "maharashtra": "Maharashtra & Goa",
    "mumbai": "Mumbai",
    "north east": "North East",
    "odisha": "Odisha",
    "punjab": "Punjab",
    "punjab 53762": "Punjab",
    "rajasthan": "Rajasthan",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "west bengal": "West Bengal",
    "west uttar pradesh": "West Uttar Pradesh",
    "up west": "West Uttar Pradesh",
}


def clean_state_name(raw_st: str) -> str:
    s = str(raw_st or "").strip().lower()
    if "& uttarakhand" in s or "uttarakhand" in s:
        return "West Uttar Pradesh"
    return INDIAN_STATES_CANONICAL.get(s, str(raw_st or "").strip())


def normalize_operator(st_clean: str, op_raw: str) -> str:
    st_low = st_clean.lower()
    op_clean = str(op_raw or "").strip()
    op_low = op_clean.lower()

    if not op_clean or op_low == "unknown":
        return "Unknown"

    if st_low in INDIAN_STATES_CANONICAL or st_clean in INDIAN_STATES_CANONICAL.values():
        if op_low in ["airtel", "bharti airtel", "tata docomo", "tata", "telewings", "telenor", "aircel", "uninor"]:
            return "Airtel"
        elif op_low in ["reliance jio", "reliance", "jio", "reliance jio infocomm"]:
            return "Reliance Jio"
        elif op_low in ["vodafone idea", "vodafone", "idea", "vi", "vodafone idea limited"]:
            return "Vodafone Idea"
        elif op_low in ["bsnl", "mtnl", "bharat sanchar nigam limited", "mahanagar telephone nigam limited"]:
            return "BSNL"
        return op_clean

    if st_clean == "Egypt":
        if op_low in ["vodafone", "vodafone egypt"]:
            return "Vodafone"
        elif op_low in ["orange", "orange egypt", "mobinil"]:
            return "Orange"
        elif op_low in ["etisalat", "etisalat misr", "e& egypt", "e&"]:
            return "Etisalat"
        elif op_low in ["we", "telecom egypt"]:
            return "WE"
        return op_clean

    return op_clean


def normalize_operator_name(op_raw, col_d_raw=""):
    op = (op_raw or "").strip()
    st_part = ""
    if col_d_raw:
        st_part = col_d_raw.split(">", 1)[0].strip().lower() if ">" in col_d_raw else col_d_raw.strip().lower()
    if not op and col_d_raw and ">" in col_d_raw:
        op = col_d_raw.split(">", 1)[1].strip()
    opu = op.lower()
    if st_part in ("egypt", "ghana") and opu in ("vi", "vodafone"):
        return "Vodafone"
    if opu in ("vi", "idea", "vodafone", "vodafone idea"):
        return "Vodafone Idea"
    if opu in ("airtel", "bharti airtel"):
        return "Airtel"
    if opu in ("jio", "reliance jio"):
        return "Reliance Jio"
    if opu in ("bsnl", "mtnl"):
        return "BSNL"
    return op or "Unknown"


def classify_row_status(type_val: str):
    """
    Classifies a row status into:
      1. ('FAILED', sub_reason) -> wrong_password, password_changed, no_account, disabled
      2. ('COMPLETE', 'recovered') -> Completed accounts
      3. ('VERIFICATION', prompt_sub) -> Active verification prompts (DP, OOTP, BELL_VF, etc.)
    """
    t = (type_val or "").strip()
    tu = t.upper()
    if not tu:
        return ("VERIFICATION", "ACTIVE_PROMPT")

    if "WRONG PASSWORD" in tu or "WRONG_PASSWORD" in tu or "INCORRECT PASSWORD" in tu or "WRONG PASS" in tu:
        return ("FAILED", "wrong_password")
    if "PASSWORD CHANGED" in tu or "PASSWORD_CHANGED" in tu or "PASS CHANGED" in tu or ("CHANGED " in tu and ("AGO" in tu or "PASSWORD" in tu)):
        return ("FAILED", "password_changed")
    if "COULDN'T FIND" in tu or "COULDNT FIND" in tu or "ACCOUNT NOT FOUND" in tu or "NO ACCOUNT" in tu or "NO_ACCOUNT" in tu or "NO ID" in tu or "DELETED" in tu:
        return ("FAILED", "no_account")
    if "ACCOUNT DISABLED" in tu or "ACCOUNT_DISABLED" in tu or "DISABLED" in tu or "SUSPENDED" in tu:
        return ("FAILED", "disabled")

    if "RECOVERED" in tu or "COMPLETED" in tu or "COMPLETE_ACCOUNT" in tu or tu == "COMPLETE" or "LOGIN SUCCESS" in tu or "2FA_ACTIVE" in tu:
        return ("COMPLETE", "recovered")

    return ("VERIFICATION", tu)


def resolve_phone_operator_and_state(raw_num: str) -> str:
    """
    Parses and returns 'State>Operator' for given phone number or account string.
    """
    raw_str = str(raw_num or "").strip()
    if not raw_str or raw_str.startswith("#") or raw_str.upper() in ["ATS", "NA", "N/A", "NULL", "NONE"]:
        return "Unknown>Unknown"

    first_token = raw_str.split()[0] if " " in raw_str else raw_str
    s = re.sub(r"\D", "", first_token)
    if not s or len(s) < 7:
        return "Unknown>Unknown"

    # Quick heuristics for Indian mobile numbers
    india_local = None
    if len(s) == 10 and s[0] in "6789":
        india_local = s
    elif len(s) == 12 and s.startswith("91") and s[2] in "6789":
        india_local = s[2:]
    elif len(s) == 11 and s.startswith("0") and s[1] in "6789":
        india_local = s[1:]
    elif len(s) == 13 and s.startswith("091") and s[3] in "6789":
        india_local = s[3:]

    # Fallback default if no external prefix database loaded
    if india_local:
        return "India>Telecom"

    return "Unknown>Unknown"


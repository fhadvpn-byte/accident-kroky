import html
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import base64
import os
import json
import re
import math
import tempfile
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

def _fmt_ratio_rtl(opt):
    import re as _re
    s = str(opt or "")
    if "|" in s and "الطرف الأول" in s and "الطرف الثاني" in s:
        p_a, p_b = s.split("|", 1)
        s1, s2 = (p_a, p_b) if "الطرف الأول" in p_a else (p_b, p_a)
        m1, m2 = _re.search(r"\d+", s1), _re.search(r"\d+", s2)
        if m1 and m2:
            return f"\u200fالطرف الأول ({m1.group(0)}%)  |  الطرف الثاني ({m2.group(0)}%)\u200f"
    return f"\u200f{s}\u200f"

def _select_images_dir():
    candidates = (
        Path.cwd() / "saved_accident_images",
        Path(tempfile.gettempdir()) / "bayyinah_images",
    )
    for folder in candidates:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".bayyinah_write_probe"
            probe.write_bytes(b"")
            probe.unlink()
            return folder
        except OSError:
            continue
    return candidates[-1]

SAVED_IMAGES_DIR = _select_images_dir()
ARABIC_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf",
]
GROQ_VISION_MODELS = (
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
)

def gregorian_to_hijri_str(gregorian_date):
    year = int(gregorian_date.year)
    month = int(gregorian_date.month)
    day = int(gregorian_date.day)
    if month < 3:
        year -= 1
        month += 12
    century = math.floor(year / 100)
    gregorian_shift = 2 - century + math.floor(century / 4)
    julian_day = math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + gregorian_shift - 1524
    lunar = julian_day - 1948440 + 10632
    cycles = math.floor((lunar - 1) / 10631)
    lunar = lunar - 10631 * cycles + 354
    jump = (math.floor((10985 - lunar) / 5316) * math.floor((50 * lunar) / 17719)) + (math.floor(lunar / 5670) * math.floor((43 * lunar) / 15238))
    lunar = lunar - (math.floor((30 - jump) / 15) * math.floor((17719 * jump) / 50)) - (math.floor(jump / 16) * math.floor((15238 * jump) / 43)) + 29
    hijri_month = math.floor((24 * lunar) / 709)
    hijri_day = lunar - math.floor((709 * hijri_month) / 24)
    hijri_year = 30 * cycles + jump - 30
    return f"{int(hijri_year):04d}/{int(hijri_month):02d}/{int(hijri_day):02d}"

def get_today_hijri():
    return gregorian_to_hijri_str(date.today())

HIJRI_MONTHS = {
    1: "محرم",
    2: "صفر",
    3: "ربيع الأول",
    4: "ربيع الآخر",
    5: "جمادى الأولى",
    6: "جمادى الآخرة",
    7: "رجب",
    8: "شعبان",
    9: "رمضان",
    10: "شوال",
    11: "ذو القعدة",
    12: "ذو الحجة",
}
HIJRI_YEAR_MIN = 1430
HIJRI_YEAR_MAX = 1455

def get_today_hijri_parts() -> tuple[int, int, int]:
    try:
        from hijridate import Gregorian
        today_hijri = Gregorian.today().to_hijri()
        return int(today_hijri.year), int(today_hijri.month), int(today_hijri.day)
    except Exception:
        year, month, day = get_today_hijri().split("/")
        return int(year), int(month), int(day)

def parse_hijri_string(raw: str) -> tuple[int, int, int] | None:
    if not raw:
        return None
    digits_trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    cleaned = raw.strip().translate(digits_trans)
    if re.fullmatch(r"\d{8}", cleaned):
        year, month, day = int(cleaned[:4]), int(cleaned[4:6]), int(cleaned[6:8])
        if HIJRI_YEAR_MIN <= year <= HIJRI_YEAR_MAX and 1 <= month <= 12 and 1 <= day <= 30:
            return year, month, day
    parts = [part for part in re.split(r"[/\-\.\s]+", cleaned) if part.isdigit()]
    if len(parts) == 3:
        first, second, third = int(parts[0]), int(parts[1]), int(parts[2])
        if first >= 1400:
            year, month, day = first, second, third
        elif third >= 1400:
            day, month, year = first, second, third
        else:
            return None
        if HIJRI_YEAR_MIN <= year <= HIJRI_YEAR_MAX and 1 <= month <= 12 and 1 <= day <= 30:
            return year, month, day
    return None

def inject_luxury_hijri_css():
    st.markdown(
        """
        <style>
        /* تصميم الزر الرئيسي لمنتقي التاريخ الهجري وإظهار نصه بالأبيض الواضح */
        html body div:has(> [data-testid="stElementContainer"] #hijri-lux-trigger) [data-testid="stPopover"] > button {
            background: linear-gradient(135deg, #0a192f 0%, #112a4e 100%) !important;
            border: 1.5px solid rgba(56, 189, 248, 0.55) !important;
            border-radius: 10px !important;
            padding: 8px 14px !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3) !important;
        }
        html body div:has(> [data-testid="stElementContainer"] #hijri-lux-trigger) [data-testid="stPopover"] > button,
        html body div:has(> [data-testid="stElementContainer"] #hijri-lux-trigger) [data-testid="stPopover"] > button * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 14.5px !important;
            opacity: 1 !important;
        }
        /* تصميم النافذة المنبثقة الزجاجية الفاخرة */
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) {
            background: linear-gradient(160deg, #071324 0%, #0d223d 100%) !important;
            border: 1.5px solid rgba(56, 189, 248, 0.45) !important;
            border-radius: 16px !important;
            box-shadow: 0 20px 45px rgba(0, 0, 0, 0.7), 0 0 25px rgba(14, 165, 233, 0.2) !important;
            padding: 12px 14px !important;
            width: 380px !important;
            max-width: 94vw !important;
            direction: rtl !important;
        }
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) [data-testid="stVerticalBlock"] {
            gap: 0.42rem !important;
        }
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) [data-testid="stHorizontalBlock"] {
            gap: 0.35rem !important;
        }
        /* أزرار الأيام والأزرار السريعة: خلفية كحلية مؤطرة وأرقام بيضاء ناصعة وعريضة */
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) .stButton > button:not([kind="primary"]) {
            background: rgba(18, 48, 86, 0.95) !important;
            border: 1px solid rgba(56, 189, 248, 0.45) !important;
            border-radius: 9px !important;
            height: 38px !important;
            min-height: 38px !important;
            padding: 0 4px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
            transition: all 0.15s ease !important;
        }
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) .stButton > button:not([kind="primary"]),
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) .stButton > button:not([kind="primary"]) * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-size: 15px !important;
            font-weight: 800 !important;
            line-height: 1 !important;
            white-space: nowrap !important;
            margin: 0 !important;
            padding: 0 !important;
            opacity: 1 !important;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.65) !important;
        }
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) .stButton > button:not([kind="primary"]):hover {
            background: rgba(14, 116, 174, 0.95) !important;
            border-color: #7dd3fc !important;
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.45) !important;
            transform: translateY(-1px) !important;
        }
        /* زر اليوم المختار فعلياً: خلفية سماوية مضيئة ورقم كحلي داكن واضح */
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #38bdf8 0%, #00e5ff 100%) !important;
            border: 1.5px solid #ffffff !important;
            border-radius: 9px !important;
            height: 38px !important;
            min-height: 38px !important;
            padding: 0 4px !important;
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.6) !important;
        }
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) .stButton > button[kind="primary"],
        html body :is([data-testid="stPopoverBody"], [data-baseweb="popover"]):has(#hijri-lux-scope) .stButton > button[kind="primary"] * {
            color: #020c1b !important;
            -webkit-text-fill-color: #020c1b !important;
            font-size: 16px !important;
            font-weight: 900 !important;
            line-height: 1 !important;
            white-space: nowrap !important;
            margin: 0 !important;
            padding: 0 !important;
            opacity: 1 !important;
            text-shadow: none !important;
        }
        
</style>
        """,
        unsafe_allow_html=True,
    )

def render_luxury_hijri_picker(state_key: str = "hijri_date", label: str = "تاريخ الحادث (هجري)") -> str:
    inject_luxury_hijri_css()
    today_y, today_m, today_d = get_today_hijri_parts()
    if not HIJRI_YEAR_MIN <= today_y <= HIJRI_YEAR_MAX:
        today_y = 1448
    current_val = str(st.session_state.get(state_key, "") or "").strip()
    parsed = parse_hijri_string(current_val)
    sel_y_key = f"{state_key}_lux_y"
    sel_m_key = f"{state_key}_lux_m"
    sel_d_key = f"{state_key}_lux_d"
    manual_key = f"{state_key}_manual_in"
    # مفاتيح داخلية غير مرتبطة بودجات: آمنة للتعيين قبل الرسم
    if parsed:
        st.session_state[sel_y_key], st.session_state[sel_m_key], st.session_state[sel_d_key] = parsed
    else:
        st.session_state.setdefault(sel_y_key, today_y)
        st.session_state.setdefault(sel_m_key, today_m)
        st.session_state.setdefault(sel_d_key, None)
    # لا تعيّن على مفتاح text_input إن وُجد مسبقاً
    if manual_key not in st.session_state:
        st.session_state[manual_key] = current_val

    def commit_date(year: int, month: int, day: int):
        formatted = f"{int(year):04d}/{int(month):02d}/{int(day):02d}"
        st.session_state[sel_y_key] = int(year)
        st.session_state[sel_m_key] = int(month)
        st.session_state[sel_d_key] = int(day)
        st.session_state[state_key] = formatted
        # علّم للمزامنة قبل إنشاء ودجات الشهر/السنة/الإدخال في الـ rerun التالي
        st.session_state[f"{state_key}_sync_parts"] = True
        st.session_state[f"{state_key}_pending_manual"] = formatted
        st.session_state.hijri_date = formatted
        st.session_state.hijri_manual_date = formatted
        st.session_state.p1_acc_date = formatted
        st.session_state.p1_acc_year = f"{int(year):04d}"
        st.session_state.p1_acc_month = f"{int(month):02d}"
        st.session_state.p1_acc_day = f"{int(day):02d}"

    if parsed:
        picked_year, picked_month, picked_day = parsed
        btn_label = f"📅  {picked_year:04d}/{picked_month:02d}/{picked_day:02d} هـ   •   {picked_day} {HIJRI_MONTHS.get(picked_month, '')}"
    else:
        btn_label = "📅  اختر التاريخ الهجري..."
    safe_label = html.escape(str(label or ""))
    st.markdown(
        f"<div id='hijri-lux-trigger' style='font-size:13.5px; font-weight:600; color:#bae6fd; margin-bottom:4px; text-align:right;'>{safe_label}</div>",
        unsafe_allow_html=True,
    )
    with st.popover(btn_label, use_container_width=True):
        st.markdown("<div id='hijri-lux-scope'></div>", unsafe_allow_html=True)
        active_d = st.session_state.get(sel_d_key)
        try:
            active_m = int(st.session_state.get(sel_m_key, today_m))
            active_y = int(st.session_state.get(sel_y_key, today_y))
        except (TypeError, ValueError):
            active_m, active_y = today_m, today_y
        if active_m not in HIJRI_MONTHS:
            active_m = today_m
        preview_txt = (
            f"{active_y:04d}/{active_m:02d}/{int(active_d):02d} هـ"
            if active_d
            else "لم يُحدد اليوم بعد"
        )
        sub_txt = (
            f"{int(active_d)} {HIJRI_MONTHS.get(active_m, '')} {active_y} هـ"
            if active_d
            else f"{HIJRI_MONTHS.get(active_m, '')} {active_y} هـ"
        )
        st.markdown(
            f"""
            <div style="background:rgba(2,132,199,0.12); border:1px solid rgba(56,189,248,0.28);
                        border-radius:11px; padding:8px 12px; margin-bottom:4px;
                        display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-size:11px; color:#7dd3fc;">التاريخ الهجري المعتمد</div>
                    <div style="font-size:16px; font-weight:800; color:#f8fafc; letter-spacing:0.6px;">{preview_txt}</div>
                </div>
                <div style="font-size:12px; font-weight:600; color:#38bdf8; background:rgba(56,189,248,0.12);
                            padding:4px 9px; border-radius:7px;">
                    {sub_txt}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        quick_col, clear_col = st.columns([2, 1])
        with quick_col:
            if st.button("⚡ اليوم", key=f"{state_key}_btn_today", use_container_width=True):
                commit_date(today_y, today_m, today_d)
                st.rerun()
        with clear_col:
            if st.button("✖ مسح", key=f"{state_key}_btn_clear", use_container_width=True):
                st.session_state[sel_d_key] = None
                st.session_state[state_key] = ""
                st.session_state[f"{state_key}_pending_manual"] = ""
                st.session_state[f"{state_key}_sync_parts"] = True
                st.session_state.hijri_date = ""
                st.session_state.hijri_manual_date = ""
                st.session_state.p1_acc_date = ""
                st.session_state.p1_acc_day = ""
                st.rerun()
        years_list = list(range(HIJRI_YEAR_MIN, HIJRI_YEAR_MAX + 1))
        if active_y not in years_list:
            active_y = today_y if today_y in years_list else 1448
        month_ui_key = f"{state_key}_sel_month_ui"
        year_ui_key = f"{state_key}_sel_year_ui"
        sync_parts = st.session_state.pop(f"{state_key}_sync_parts", False)
        pending_manual = st.session_state.pop(f"{state_key}_pending_manual", None)
        # قبل إنشاء الودجات فقط: عيّن عند الغياب أو بعد مزامنة صريحة من commit/مسح
        if month_ui_key not in st.session_state:
            st.session_state[month_ui_key] = active_m
        elif sync_parts:
            st.session_state[month_ui_key] = active_m
        if year_ui_key not in st.session_state:
            st.session_state[year_ui_key] = active_y
        elif sync_parts:
            st.session_state[year_ui_key] = active_y
        if pending_manual is not None:
            st.session_state[manual_key] = pending_manual
        elif manual_key not in st.session_state:
            st.session_state[manual_key] = current_val
        month_col, year_col = st.columns([1.25, 1])
        with month_col:
            chosen_m = st.selectbox(
                "الشهر",
                options=list(HIJRI_MONTHS.keys()),
                format_func=lambda month: f"{month:02d} — {HIJRI_MONTHS[month]}",
                key=month_ui_key,
                label_visibility="collapsed",
            )
        with year_col:
            chosen_y = st.selectbox(
                "السنة",
                options=years_list,
                format_func=lambda year: f"{year} هـ",
                key=year_ui_key,
                label_visibility="collapsed",
            )
        if chosen_m != active_m or chosen_y != active_y:
            st.session_state[sel_m_key] = chosen_m
            st.session_state[sel_y_key] = chosen_y
            if st.session_state.get(sel_d_key):
                commit_date(chosen_y, chosen_m, int(st.session_state[sel_d_key]))
                st.rerun()
        for row_start in range(1, 31, 6):
            day_cols = st.columns(6)
            for idx, day_num in enumerate(range(row_start, row_start + 6)):
                is_selected = st.session_state.get(sel_d_key) == day_num
                with day_cols[idx]:
                    if st.button(
                        f"{day_num:02d}",
                        key=f"{state_key}_d_{day_num}",
                        type="primary" if is_selected else "secondary",
                        use_container_width=True,
                    ):
                        commit_date(chosen_y, chosen_m, day_num)
                        st.rerun()

        def _on_manual_change():
            parsed_manual = parse_hijri_string(st.session_state.get(manual_key, ""))
            if parsed_manual:
                commit_date(*parsed_manual)

        st.text_input(
            "إدخال رقمي سريع",
            placeholder="كتابة سريعة: 1448/06/01 أو 14480601 ثم Enter",
            key=manual_key,
            on_change=_on_manual_change,
            label_visibility="collapsed",
        )
    return str(st.session_state.get(state_key, ""))

KSA_TZ = timezone(timedelta(hours=3))
DEPT_STAFF_PATH = Path(".bayyinah_dept_staff.json")
DEPT_STAFF_STORAGE_KEY = "bayyinah_dept_staff"
RANKS_LIST = [
    "جندي", "جندي أول", "عريف", "وكيل رقيب", "رقيب", "رقيب أول", "رئيس رقباء",
    "ملازم", "ملازم أول", "نقيب", "رائد", "مقدم", "عقيد", "عميد",
]
ROLE_RANK_DEFAULTS = {
    "officer_1_rank": "عريف",
    "officer_2_rank": "رقيب",
    "manager_rank": "رئيس رقباء",
}
MANUAL_OFFICER_OPTION = "✍️ كتابة / تعديل اسم يدوياً..."
DEFAULT_DEPT_STAFF = {
    "dept_region": "إدارة مرور منطقة جازان",
    "dept_section": "قسم مرور محافظة العارضة",
    "officer_name": "",
    "officer_rank": "",
    "supervisor_name": "",
    "supervisor_rank": "",
    "director_name": "",
    "director_rank": "",
    "saved_officers": [],
}
SIDEBAR_FIELD_MAP = (
    ("dept_region", "p1_dept_region"),
    ("dept_section", "p1_dept_branch"),
    ("officer_name", "officer_1_name"),
    ("officer_rank", "officer_1_rank"),
    ("supervisor_name", "officer_2_name"),
    ("supervisor_rank", "officer_2_rank"),
    ("director_name", "manager_name"),
    ("director_rank", "manager_rank"),
)
SIDEBAR_SESSION_KEYS = {widget_key for _storage_key, widget_key in SIDEBAR_FIELD_MAP}
PARTY_SMART_DEFAULTS = {
    "المشاركة": "سائق",
    "الحالة": "سليم",
    "التأهيل": "مؤهل للقيادة",
}
VEHICLE_SMART_DEFAULTS = {
    "نوع الترخيص": "خصوصي",
    "التأمين": "ساري",
}

def load_permanent_dept_staff() -> dict:
    if "_perm_dept_staff" not in st.session_state:
        disk_data = {}
        if DEPT_STAFF_PATH.exists():
            try:
                disk_data = json.loads(DEPT_STAFF_PATH.read_text(encoding="utf-8"))
            except Exception:
                disk_data = {}
        if not isinstance(disk_data, dict):
            disk_data = {}
        st.session_state["_perm_dept_staff"] = {**DEFAULT_DEPT_STAFF, **disk_data}
    return st.session_state["_perm_dept_staff"]

def save_permanent_dept_staff(data: dict) -> bool:
    st.session_state["_perm_dept_staff"] = dict(data)
    try:
        DEPT_STAFF_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception as error:
        st.error(f"تعذر حفظ الإعدادات الثابتة على القرص: {error}")
        return False

def capture_sidebar_before_reset():
    """يحفظ آخر قيم القائمة قبل مسح الجلسة حتى لا تضيع مع حادث جديد أو مسح الحقول."""
    if not any(widget_key in st.session_state for _storage_key, widget_key in SIDEBAR_FIELD_MAP):
        return
    data = load_permanent_dept_staff()
    for storage_key, widget_key in SIDEBAR_FIELD_MAP:
        if widget_key in st.session_state:
            data[storage_key] = str(st.session_state.get(widget_key) or "")
    save_permanent_dept_staff(data)

def _mirror_dept_staff_local_storage(data: dict):
    payload = json.dumps(data, ensure_ascii=False)
    components.html(
        "<script>(function(){try{var w=window.parent;if(w&&w.localStorage){w.localStorage.setItem(%s,%s);}}catch(e){}})();</script>"
        % (json.dumps(DEPT_STAFF_STORAGE_KEY), json.dumps(payload)),
        height=0,
        width=0,
    )

def _clean_saved_officers(presets) -> list:
    cleaned = []
    seen = set()
    for item in presets or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        rank = str(item.get("rank") or "").strip()
        if rank not in RANKS_LIST:
            rank = ""
        label = f"{rank} / {name}" if rank else name
        if label in seen:
            continue
        seen.add(label)
        cleaned.append({"name": name, "rank": rank, "label": label})
    return cleaned

def _ensure_role_rank(rank_key: str) -> str:
    default_rank = ROLE_RANK_DEFAULTS[rank_key]
    current = st.session_state.get(rank_key)
    if current is None or str(current).strip() not in RANKS_LIST:
        st.session_state[rank_key] = default_rank
    return default_rank

def render_signatory_card(card_key: str, title: str, name_key: str, rank_key: str, presets, on_commit):
    """بطاقة صفة واحدة: قائمة اسم محفوظة، والكتابة اليدوية تظهر عند طلبها فقط."""
    default_rank = _ensure_role_rank(rank_key)
    if name_key not in st.session_state or st.session_state.get(name_key) is None:
        st.session_state[name_key] = ""
    saved = _clean_saved_officers(presets)
    options = [item["label"] for item in saved] + [MANUAL_OFFICER_OPTION]
    pick_key = f"{name_key}_source"
    current_name = str(st.session_state.get(name_key) or "").strip()
    current_rank = str(st.session_state.get(rank_key) or "").strip()
    if pick_key not in st.session_state or st.session_state.get(pick_key) not in options:
        match = ""
        for item in saved:
            if item["name"] != current_name:
                continue
            match = item["label"]
            if item["rank"] == current_rank:
                break
        st.session_state[pick_key] = match or MANUAL_OFFICER_OPTION

    def _on_pick():
        picked = st.session_state.get(pick_key)
        for item in saved:
            if item["label"] != picked:
                continue
            st.session_state[name_key] = item["name"]
            st.session_state[rank_key] = item["rank"] if item["rank"] in RANKS_LIST else default_rank
            break
        on_commit()

    with st.container(key=card_key):
        st.markdown(
            f'<div class="officer-role-card"><div class="officer-role-title">{html.escape(title)}</div></div>',
            unsafe_allow_html=True,
        )
        picked_label = st.selectbox("الاسم", options=options, key=pick_key, on_change=_on_pick)
        if picked_label != MANUAL_OFFICER_OPTION:
            for item in saved:
                if item["label"] == picked_label and st.session_state.get(name_key) != item["name"]:
                    st.session_state[name_key] = item["name"]
                    break
        else:
            st.text_input(
                "كتابة الاسم",
                key=name_key,
                on_change=on_commit,
                placeholder="اكتب الاسم المعتمد",
            )
        st.selectbox("الرتبة", options=list(RANKS_LIST), key=rank_key, on_change=on_commit)

def render_persistent_sidebar_settings():
    """إعدادات القسم والمنسوبين: ملف محلي + localStorage، ولا يمسحها حادث جديد."""
    data = load_permanent_dept_staff()
    force = bool(st.session_state.pop("_restore_perm_sidebar", False))
    file_exists = DEPT_STAFF_PATH.exists()
    if force and file_exists:
        for storage_key, widget_key in SIDEBAR_FIELD_MAP:
            st.session_state[widget_key] = str(data.get(storage_key, "") or "")
        st.session_state["_perm_sidebar_seeded"] = True
    elif not st.session_state.get("_perm_sidebar_seeded"):
        for storage_key, widget_key in SIDEBAR_FIELD_MAP:
            stored = str(data.get(storage_key, "") or "")
            current = str(st.session_state.get(widget_key) or "").strip()
            if file_exists or not current:
                st.session_state[widget_key] = stored
        st.session_state["_perm_sidebar_seeded"] = True
    def _commit_sidebar_settings():
        current = load_permanent_dept_staff()
        for storage_key, widget_key in SIDEBAR_FIELD_MAP:
            current[storage_key] = str(st.session_state.get(widget_key, "") or "")
        presets = [item for item in list(current.get("saved_officers") or []) if isinstance(item, dict)]
        for name_field, rank_field in (
            ("officer_name", "officer_rank"),
            ("supervisor_name", "supervisor_rank"),
            ("director_name", "director_rank"),
        ):
            name = str(current.get(name_field) or "").strip()
            rank = str(current.get(rank_field) or "").strip()
            if name and not any(item.get("name") == name and item.get("rank") == rank for item in presets):
                presets.append({"name": name, "rank": rank})
        current["saved_officers"] = presets
        if save_permanent_dept_staff(current):
            _mirror_dept_staff_local_storage(current)
            st.toast("تم حفظ الإعدادات الثابتة", icon="💾")
            st.session_state["_sidebar_save_ok"] = True

    def _noop_commit():
        return None

    with st.container(key="glow-dept"):
        st.header("⚙️ الإعدادات الثابتة للقسم")
        dept_region = st.text_input("إدارة مرور منطقة", key="p1_dept_region")
        dept_branch = st.text_input("القسم / الشعبة", key="p1_dept_branch")
    with st.container(key="glow-officers"):
        st.subheader("👮‍♂️ بيانات معدي التقرير المعتمدين")
        presets = data.get("saved_officers") or []
        for rank_key in ROLE_RANK_DEFAULTS:
            _ensure_role_rank(rank_key)
        render_signatory_card(
            "officer_role_direct",
            "1️⃣ مباشر الحوادث (إجراءات الحوادث)",
            "officer_1_name",
            "officer_1_rank",
            presets,
            _noop_commit,
        )
        render_signatory_card(
            "officer_role_supervisor",
            "2️⃣ مشرف الحوادث",
            "officer_2_name",
            "officer_2_rank",
            presets,
            _noop_commit,
        )
        render_signatory_card(
            "officer_role_manager",
            "3️⃣ مدير القسم / الشعبة",
            "manager_name",
            "manager_rank",
            presets,
            _noop_commit,
        )
        officer_1_name = str(st.session_state.get("officer_1_name") or "")
        officer_1_rank = str(st.session_state.get("officer_1_rank") or "")
        officer_2_name = str(st.session_state.get("officer_2_name") or "")
        officer_2_rank = str(st.session_state.get("officer_2_rank") or "")
        manager_name = str(st.session_state.get("manager_name") or "")
        manager_rank = str(st.session_state.get("manager_rank") or "")
    if st.button("💾 حفظ الإعدادات الثابتة", key="_sidebar_save_perm_settings", use_container_width=True):
        _commit_sidebar_settings()
    if st.session_state.pop("_sidebar_save_ok", False):
        st.success("تم حفظ إعدادات القسم والمنسوبين بنجاح.")
    return (
        dept_region,
        dept_branch,
        officer_1_name,
        officer_1_rank,
        officer_2_name,
        officer_2_rank,
        manager_name,
        manager_rank,
    )

def render_smart_time_picker(state_key: str = "p1_acc_time", label: str = "الوقت") -> str:
    current_val = str(st.session_state.get(state_key, "") or "").strip()

    def set_ksa_now():
        now_ksa = datetime.now(KSA_TZ)
        hr_24 = now_ksa.hour
        period = "م" if hr_24 >= 12 else "ص"
        hr_12 = hr_24 % 12 or 12
        formatted = f"{hr_12:02d}:{now_ksa.minute:02d} {period}"
        st.session_state[state_key] = formatted
        st.session_state[f"{state_key}_manual"] = formatted

    btn_text = f"🕒  {current_val}" if current_val else "🕒  حدد وقت الحادث..."
    safe_label = html.escape(str(label or ""))
    st.markdown(
        f"<div id='hijri-lux-trigger' style='font-size:13.5px; font-weight:600; color:#bae6fd; margin-bottom:4px; text-align:right;'>{safe_label}</div>",
        unsafe_allow_html=True,
    )
    with st.popover(btn_text, use_container_width=True):
        st.markdown("<div id='hijri-lux-scope'></div>", unsafe_allow_html=True)
        t_c1, t_c2 = st.columns([2.2, 1])
        with t_c1:
            if st.button("⚡ وقت الآن (توقيت المملكة)", key=f"{state_key}_now_btn", use_container_width=True):
                set_ksa_now()
                st.rerun()
        with t_c2:
            if st.button("✖ مسح", key=f"{state_key}_clr_btn", use_container_width=True):
                st.session_state[state_key] = ""
                st.session_state[f"{state_key}_manual"] = ""
                st.rerun()
        hc1, hc2, hc3 = st.columns([1, 1, 1])
        with hc1:
            sel_h = st.selectbox("الساعة", [f"{h:02d}" for h in range(1, 13)], key=f"{state_key}_h", label_visibility="collapsed")
        with hc2:
            sel_m = st.selectbox("الدقيقة", [f"{m:02d}" for m in range(0, 60, 5)], key=f"{state_key}_m", label_visibility="collapsed")
        with hc3:
            sel_p = st.selectbox("الفترة", ["ص", "م"], key=f"{state_key}_p", label_visibility="collapsed")
        if st.button("✓ اعتماد الوقت المحدد", key=f"{state_key}_apply_btn", type="primary", use_container_width=True):
            chosen_time = f"{sel_h}:{sel_m} {sel_p}"
            st.session_state[state_key] = chosen_time
            st.session_state[f"{state_key}_manual"] = chosen_time
            st.rerun()

        def _on_manual_time():
            raw = str(st.session_state.get(f"{state_key}_manual", "")).strip()
            digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
            raw_clean = raw.translate(digits)
            if re.fullmatch(r"\d{3,4}", raw_clean):
                raw_clean = raw_clean.zfill(4)
                hh, mm = int(raw_clean[:2]), int(raw_clean[2:])
                if 0 <= hh <= 23 and 0 <= mm <= 59:
                    per = "م" if hh >= 12 else "ص"
                    h12 = hh % 12 or 12
                    raw_clean = f"{h12:02d}:{mm:02d} {per}"
            st.session_state[state_key] = raw_clean

        manual_key = f"{state_key}_manual"
        if manual_key not in st.session_state:
            st.session_state[manual_key] = current_val
        st.text_input(
            "كتابة سريعة للوقت",
            placeholder="كتابة سريعة مثل: 04:30 م أو 1630 ثم Enter",
            key=manual_key,
            on_change=_on_manual_time,
            label_visibility="collapsed",
        )
    return str(st.session_state.get(state_key, ""))

def fill_smart_table_defaults(df, defaults_map: dict):
    """استبدال القيم الفارغة أو None بالخيار الافتراضي القياسي لكل عمود."""
    if df is None or df.empty:
        return df
    df_clean = df.copy()
    for col_name, default_val in defaults_map.items():
        if col_name in df_clean.columns:
            df_clean[col_name] = df_clean[col_name].apply(
                lambda v: default_val if (v is None or str(v).strip() == "" or str(v).strip().lower() in ("none", "nan")) else v
            )
    return df_clean

def _official_article_cite(code: str) -> str:
    """يحذف اللاحقة المختصرة داخل القوس مثل «- إشارة» ويبقي رقم المادة النظامي."""
    return re.sub(r"\s*-\s*[^)]+", "", str(code or "").strip())

def render_legal_articles_inserter(selected_articles: list, p1_reasons_key: str = "p1_reasons_area", p2_reasons_key: str = "p2_reasons_area"):
    if not selected_articles:
        return

    def _append_articles(target_key: str):
        # اكتب في saved_* إن كان الحقل من نصوص التبويب3 المقفلة
        if target_key in TAB3_LOCKED_TEXT_BY_ID:
            existing = _read_tab3_saved_text(target_key)
        else:
            existing = str(st.session_state.get(target_key, "") or "").strip()
        existing_lines = [ln.strip() for ln in existing.splitlines() if ln.strip()]
        for art in selected_articles:
            cite = _format_article_cite_for_report(art)
            formatted_art = f"استناداً إلى {cite} من نظام المرور ولائحته التنفيذية."
            if formatted_art not in existing_lines:
                existing_lines.append(formatted_art)
        joined = "\n".join(existing_lines)
        if target_key in TAB3_LOCKED_TEXT_BY_ID:
            _write_tab3_saved_text(target_key, joined, mark_manual=True)
            _bump_tab3_text_rev(target_key)
        else:
            st.session_state[target_key] = joined

    ins_c1, ins_c2 = st.columns(2)
    with ins_c1:
        if st.button("➕ إدراج المواد المختارة في أسباب إدانة الطرف الأول", key="btn_ins_art_p1", use_container_width=True):
            _append_articles(p1_reasons_key)
            st.rerun()
    with ins_c2:
        if st.button("➕ إدراج المواد المختارة في أسباب إدانة الطرف الثاني", key="btn_ins_art_p2", use_container_width=True):
            _append_articles(p2_reasons_key)
            st.rerun()

def _write_actions_editor(cur_acts):
    if "ACTIONS_SCENARIOS" not in globals():
        st.session_state["_pending_actions_text"] = True
        return
    try:
        deaths_count = int(st.session_state.get("p1_acc_deaths") or 0)
    except (TypeError, ValueError):
        deaths_count = 0
    lines = []
    for i, k in enumerate(cur_acts, 1):
        if k not in ACTIONS_SCENARIOS:
            continue
        # تُطبَّق صيغ الجمع لاحقاً عبر action_scenario_text إن وُجدت
        if "action_scenario_text" in globals():
            text = action_scenario_text(k, deaths_count)
        else:
            text = ACTIONS_SCENARIOS[k]
            try:
                num = int(str(k).strip().split(".", 1)[0].strip())
            except (TypeError, ValueError):
                num = -1
            if 20 <= num <= 26 and deaths_count >= 2:
                text = (
                    str(text)
                    .replace("جثمان المتوفى", "جثامين المتوفين")
                    .replace("للمتوفى", "للمتوفين")
                    .replace("المتوفى", "المتوفين")
                )
        lines.append(f"{i}- {text}")
    st.session_state["actions_taken_editor"] = "\n".join(lines)
    st.session_state["_actions_plural_deaths_sig"] = deaths_count

_VEHICLE_ORDINALS_AR = {
    1: "الأولى",
    2: "الثانية",
    3: "الثالثة",
    4: "الرابعة",
    5: "الخامسة",
    6: "السادسة",
    7: "السابعة",
    8: "الثامنة",
    9: "التاسعة",
    10: "العاشرة",
}

def _clean_title_fragment(value) -> str:
    if value is None:
        return ""
    try:
        missing = pd.isna(value)
        if bool(missing) and getattr(missing, "shape", None) is None:
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.lower() in ("none", "nan", "<na>"):
        return ""
    return text

def _party_row_for_index(parties, party_index: int):
    rows = list(parties or [])
    label = None
    try:
        label = _PARTY_LABELS.get(party_index)
    except Exception:
        label = None
    if not label:
        label = f"الطرف {party_index}" if party_index > 2 else ("الطرف الأول" if party_index == 1 else "الطرف الثاني")
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _clean_title_fragment(row.get("الطرف")) == label:
            return row
    if 0 <= party_index - 1 < len(rows) and isinstance(rows[party_index - 1], dict):
        return rows[party_index - 1]
    return {}

def _driver_name_for_party_index(parties, party_index: int) -> str:
    row = _party_row_for_index(parties, party_index)
    role = _clean_title_fragment(row.get("المشاركة")) if row else ""
    if row and not _is_non_driver_role(role):
        name = _clean_title_fragment(row.get("الاسم"))
        if name:
            return name
    # احتياطي: السائق رقم n من قائمة السائقين فقط
    drivers = []
    for item in parties or []:
        if not isinstance(item, dict):
            continue
        if _is_non_driver_role(item.get("المشاركة")):
            continue
        drivers.append(item)
    if 0 <= party_index - 1 < len(drivers):
        return _clean_title_fragment(drivers[party_index - 1].get("الاسم"))
    return ""

def _vehicle_type_for_party_index(vehicles, party_index: int) -> str:
    rows = list(vehicles or [])
    if 0 <= party_index - 1 < len(rows) and isinstance(rows[party_index - 1], dict):
        return _clean_title_fragment(rows[party_index - 1].get("نوع المركبة"))
    return ""

def build_driver_party_title(party_index: int, parties=None, vehicles=None) -> str:
    """صيغة صفة الطرف: قائد المركبة الأولى (النوع) / الاسم — بدون زوائد إن نقص الاسم أو النوع."""
    ordinal = _VEHICLE_ORDINALS_AR.get(int(party_index) or 1, str(party_index))
    base = f"قائد المركبة {ordinal}"
    parties = parties if parties is not None else (st.session_state.get("parties") or [])
    vehicles = vehicles if vehicles is not None else (st.session_state.get("vehicles") or [])
    name = _driver_name_for_party_index(parties, party_index)
    veh_type = _vehicle_type_for_party_index(vehicles, party_index)
    if name and veh_type:
        return f"{base} ({veh_type}) / {name}"
    if name:
        return f"{base} / {name}"
    return base

def _is_auto_managed_party_title(current: str, party_index: int) -> bool:
    text = _clean_title_fragment(current)
    ordinal = _VEHICLE_ORDINALS_AR.get(int(party_index) or 1, str(party_index))
    base = f"قائد المركبة {ordinal}"
    defaults = {
        1: {
            "",
            "قائد المركبة الأولى (الطرف الأول)",
            "قائد المركبة الأولى",
            DEFAULT_REPORT_STATE.get("p1_title_input", "قائد المركبة الأولى (الطرف الأول)"),
        },
        2: {
            "",
            "قائد المركبة الثانية (الطرف الثاني)",
            "قائد المركبة الثانية",
            DEFAULT_REPORT_STATE.get("p2_role_select", "قائد المركبة الثانية (الطرف الثاني)"),
        },
    }
    if text in defaults.get(party_index, {""}):
        return True
    last_auto = _clean_title_fragment(st.session_state.get(f"_last_auto_party_title_{party_index}"))
    if last_auto and text == last_auto:
        return True
    if text.startswith(base):
        return True
    return False

def refresh_party_role_titles(parties=None, vehicles=None, force: bool = False):
    """تحديث صفات الأطراف في الجلسة فور تعديل/اعتماد جداول الأطراف والمركبات."""
    parties = parties if parties is not None else (st.session_state.get("parties") or [])
    vehicles = vehicles if vehicles is not None else (st.session_state.get("vehicles") or [])
    titles = {}
    max_n = max(len(parties or []), len(vehicles or []), 2)
    for idx in range(1, min(max_n, 10) + 1):
        title = build_driver_party_title(idx, parties=parties, vehicles=vehicles)
        titles[idx] = title
        st.session_state[f"party_role_title_{idx}"] = title
        st.session_state[f"_last_auto_party_title_{idx}"] = title
    t1 = titles.get(1) or build_driver_party_title(1, parties=parties, vehicles=vehicles)
    t2 = titles.get(2) or build_driver_party_title(2, parties=parties, vehicles=vehicles)
    cur1 = str(st.session_state.get("p1_title_input") or "")
    if force or _is_auto_managed_party_title(cur1, 1):
        st.session_state["p1_title_input"] = t1
    cur2_select = str(st.session_state.get("p2_role_select") or "")
    pedestrian = "عابر الطريق (المشاة)"
    bike = "قائد الدراجة النارية / الهوائية"
    custom = "تحديد صفة مخصصة"
    if cur2_select in (pedestrian, bike, custom):
        pass
    elif force or _is_auto_managed_party_title(cur2_select, 2):
        st.session_state["p2_role_select"] = t2
    if st.session_state.get("p2_role_select") == custom:
        cur_custom = str(st.session_state.get("p2_custom_title") or "")
        if force or _is_auto_managed_party_title(cur_custom, 2) or cur_custom in ("", "الطرف الثاني"):
            st.session_state["p2_custom_title"] = t2
    return titles

def sync_cross_page_smart_links(
    injuries_count: int,
    deaths_count: int,
    veh1_type: str = "",
    veh2_type: str = "",
    p1_title_key: str = "p1_title_input",
    sketch_leg1_key: str = None,
    sketch_leg2_key: str = None,
):
    v1 = str(veh1_type or "").strip()
    v2 = str(veh2_type or "").strip()
    refresh_party_role_titles(force=False)
    if v1 and v1.lower() != "none":
        if sketch_leg1_key and st.session_state.get(sketch_leg1_key, "") in ("", "المركبة الأولى", "المركبة الأولى (الطرف الأول)"):
            st.session_state[sketch_leg1_key] = f"المركبة الأولى ({v1})"
    if v2 and v2.lower() != "none":
        if sketch_leg2_key and st.session_state.get(sketch_leg2_key, "") in ("", "المركبة الثانية", "المركبة الثانية (الطرف الثاني)"):
            st.session_state[sketch_leg2_key] = f"المركبة الثانية ({v2})"
    prev_sig = st.session_state.get("_last_casualty_sig", (0, 0))
    curr_sig = (int(injuries_count or 0), int(deaths_count or 0))
    if curr_sig != prev_sig:
        st.session_state["_last_casualty_sig"] = curr_sig
        deaths_n = curr_sig[1]
        injuries_n = curr_sig[0]
        if deaths_n > 0:
            st.session_state["acc_nature_sel"] = "حادث مروري جسيم (وفاة)"
            st.session_state["rights_sel"] = "قيام الحقين العام والخاص معاً (إصابات / وفاة / مخالفة جسيمة)"
            death_key = "5. حادث وفاة (إيداع الجثمان وتوقيف وإحالة للنيابة العامة)"
            cur_acts = list(st.session_state.get("selected_actions_multi", []))
            if death_key not in cur_acts:
                cur_acts = [a for a in cur_acts if not str(a).startswith("1. صلح")] + [death_key]
                st.session_state["selected_actions_multi"] = cur_acts
            _write_actions_editor(cur_acts)
        elif injuries_n > 0:
            st.session_state["acc_nature_sel"] = "حادث مروري جسيم (إصابات)"
            st.session_state["rights_sel"] = "قيام الحقين العام والخاص معاً (إصابات / وفاة / مخالفة جسيمة)"
            inj_key = "4. حادث إصابات (إسعاف وطلب تقارير طبية)"
            cur_acts = list(st.session_state.get("selected_actions_multi", []))
            if inj_key not in cur_acts:
                cur_acts = [a for a in cur_acts if not str(a).startswith("1. صلح")] + [inj_key]
                st.session_state["selected_actions_multi"] = cur_acts
            _write_actions_editor(cur_acts)

def flush_pending_casualty_actions():
    if not st.session_state.pop("_pending_actions_text", False):
        return
    if "ACTIONS_SCENARIOS" not in globals():
        st.session_state["_pending_actions_text"] = True
        return
    cur_acts = list(st.session_state.get("selected_actions_multi") or [])
    _write_actions_editor(cur_acts)

def _blank_parties():
    return [
        {"الطرف": "الطرف الأول", "الاسم": "", "الهوية": "", "المشاركة": "", "الحالة": "", "التأهيل": ""},
        {"الطرف": "الطرف الثاني", "الاسم": "", "الهوية": "", "المشاركة": "", "الحالة": "", "التأهيل": ""},
    ]

def _blank_vehicles():
    return [
        {"الطرف": "الطرف الأول", "نوع المركبة": "", "رقم اللوحة": "", "الرقم التسلسلي": "", "نوع الترخيص": "", "التأمين": ""},
        {"الطرف": "الطرف الثاني", "نوع المركبة": "", "رقم اللوحة": "", "الرقم التسلسلي": "", "نوع الترخيص": "", "التأمين": ""},
    ]

P1_AUTOSAVE_PATH = Path(".p1_autosave_draft.json")
PAGE1_STATIC_KEYS = {
    "p1_hdr_number": "",
    "p1_hdr_date": "",
    "p1_hdr_attachments": "",
    "p1_hdr_subject": "تقرير حادث مروري",
    "p1_acc_number": "",
    "p1_acc_day": "",
    "p1_acc_month": "",
    "p1_acc_year": "1448",
    "p1_acc_date": "",
    "p1_acc_time": "",
    "p1_acc_location": "",
    "p1_acc_type": "تصادم",
    "p1_acc_injuries": 0,
    "p1_acc_deaths": 0,
    "p1_acc_weather": "صحو",
    "p1_acc_cause": "",
    "p1_parties_count": 2,
    "p1_dept_region": "",
    "p1_dept_branch": "",
    "hijri_date": "",
    "hijri_manual_date": "",
    "p1_parties_records": _blank_parties(),
    "p1_vehicles_records": _blank_vehicles(),
}
PAGE1_EXTRA_SYNC_KEYS = (
    "p1_acc_type_choice",
    "p1_acc_weather_choice",
)
_PARTY_LABELS = {
    1: "الطرف الأول",
    2: "الطرف الثاني",
    3: "الطرف الثالث",
    4: "الطرف الرابع",
    5: "الطرف الخامس",
    6: "الطرف السادس",
    7: "الطرف السابع",
    8: "الطرف الثامن",
    9: "الطرف التاسع",
    10: "الطرف العاشر",
}

def get_dynamic_party_keys(max_parties: int = 10) -> dict:
    dyn_keys = {}
    for i in range(1, max_parties + 1):
        dyn_keys[f"p1_party_name_{i}"] = ""
        dyn_keys[f"p1_party_id_{i}"] = ""
        dyn_keys[f"p1_party_role_{i}"] = "سائق"
        dyn_keys[f"p1_party_health_{i}"] = "سليم"
        dyn_keys[f"p1_party_qual_{i}"] = "مؤهل للقيادة"
        dyn_keys[f"p1_veh_type_{i}"] = ""
        dyn_keys[f"p1_veh_plate_{i}"] = ""
        dyn_keys[f"p1_veh_serial_{i}"] = ""
        dyn_keys[f"p1_veh_reg_{i}"] = "خصوصي"
        dyn_keys[f"p1_veh_ins_{i}"] = "ساري"
    return dyn_keys

ALL_PAGE1_DEFAULTS = {**PAGE1_STATIC_KEYS, **get_dynamic_party_keys(10)}
_PARTY_TABLE_COLUMNS = [
    ("الطرف", "الأطراف"),
    ("الاسم", "الاسم"),
    ("الهوية", "الهوية / الإقامة"),
    ("المشاركة", "نوع المشاركة"),
    ("الحالة", "الحالة الصحية"),
    ("التأهيل", "تأهيل للقيادة"),
]
_VEHICLE_TABLE_COLUMNS = [
    ("الطرف", "الأطراف"),
    ("نوع المركبة", "نوع المركبة"),
    ("رقم اللوحة", "رقم اللوحة"),
    ("الرقم التسلسلي", "الرقم التسلسلي"),
    ("نوع الترخيص", "نوع الترخيص"),
    ("التأمين", "التأمين"),
]
MAIN_TAB_OPTIONS = [
    "1️⃣ البيانات والأطراف",
    "2️⃣ الموقع واستوديو الكروكي",
    "3️⃣ الوصف والمسؤولية والإجراءات",
    "4️⃣ المرفقات والطباعة النهائية (A4)",
]

def _clone_page1_value(value):
    if isinstance(value, list):
        return [dict(item) if isinstance(item, dict) else item for item in value]
    if isinstance(value, dict):
        return dict(value)
    return value

QUALIFICATION_EXEMPT = "➖ لا يُطالب برخصة"
QUALIFICATION_OPTIONS = [
    "مؤهل للقيادة",
    "غير مؤهل للقيادة",
    QUALIFICATION_EXEMPT,
]
NON_DRIVER_ROLES = {"راكب", "مشاة", "غير سائق"}

def _clean_party_text(value) -> str:
    if value is None:
        return ""
    try:
        missing = pd.isna(value)
        if bool(missing) and getattr(missing, "shape", None) is None:
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.lower() in ("none", "nan", "<na>"):
        return ""
    return text

def _is_non_driver_role(role) -> bool:
    text = _clean_party_text(role)
    if not text:
        return False
    if text in NON_DRIVER_ROLES:
        return True
    lowered = text.replace("أ", "ا")
    if "راكب" in text or "مشاة" in text or "عابر" in text:
        return True
    if "غير سائق" in text or "غير سائق" in lowered:
        return True
    if text == "سائق" or text.startswith("سائق") or "قائد" in text:
        return False
    return False

def normalize_driving_qualification(val, role=None):
    if _is_non_driver_role(role):
        return QUALIFICATION_EXEMPT
    if val is None:
        return "مؤهل للقيادة"
    text = str(val).strip()
    if not text or text.lower() in ("none", "nan", "<na>"):
        return "مؤهل للقيادة"
    if "لا يُطالب" in text or "لا يطالب" in text or text == QUALIFICATION_EXEMPT:
        # راكب/مشاة فقط يحتفظون بالإعفاء؛ السائق لا يبقى على هذا الخيار
        if role is not None and not _is_non_driver_role(role):
            return "مؤهل للقيادة"
        return QUALIFICATION_EXEMPT
    if "غير" in text:
        return "غير مؤهل للقيادة"
    if text in QUALIFICATION_OPTIONS:
        return text
    return "مؤهل للقيادة"

def _sanitize_party_row(row) -> dict:
    item = dict(row) if isinstance(row, dict) else {}
    item["الاسم"] = _clean_party_text(item.get("الاسم", ""))
    item["الهوية"] = _clean_party_text(item.get("الهوية", ""))
    item["الطرف"] = _clean_party_text(item.get("الطرف", "")) or str(item.get("الطرف") or "")
    role = _clean_party_text(item.get("المشاركة", ""))
    item["المشاركة"] = role
    health = _clean_party_text(item.get("الحالة", ""))
    item["الحالة"] = health if health else "سليم"
    current_qual = item.get("التأهيل", "")
    # عند الاعتماد: الراكب/المشاة/غير السائق → إعفاء حتى لو فارغ أو «مؤهل للقيادة»
    if _is_non_driver_role(role):
        normalized = QUALIFICATION_EXEMPT
    else:
        normalized = normalize_driving_qualification(current_qual, role=role)
    item["التأهيل"] = normalized
    return item

def _normalize_party_qualification_rows(rows):
    cleaned = []
    changed = False
    for row in rows or []:
        original = dict(row) if isinstance(row, dict) else {}
        item = _sanitize_party_row(original)
        if (
            _clean_party_text(original.get("التأهيل", "")) != item.get("التأهيل", "")
            or _clean_party_text(original.get("الاسم", "")) != item.get("الاسم", "")
            or _clean_party_text(original.get("الهوية", "")) != item.get("الهوية", "")
            or (_clean_party_text(original.get("الحالة", "")) or "سليم") != item.get("الحالة", "")
            or _clean_party_text(original.get("المشاركة", "")) != item.get("المشاركة", "")
        ):
            changed = True
        cleaned.append(item)
    return cleaned, changed

def _party_rows_for_liability(rows):
    """أطراف توزيع المسؤولية ومخالفات الرخصة: السائقون فقط (استبعاد راكب/مشاة)."""
    out = []
    for row in rows or []:
        item = _sanitize_party_row(row)
        if _is_non_driver_role(item.get("المشاركة")):
            continue
        out.append(item)
    return out

def _unqualified_driver_parties(rows):
    return [
        item for item in _party_rows_for_liability(rows)
        if item.get("التأهيل") == "غير مؤهل للقيادة"
    ]

def _is_unqualified_driver_party(party) -> bool:
    """سائق فعلي حالته غير مؤهل للقيادة فقط — ليس راكباً/مشاة وليس مؤهلاً."""
    if not party:
        return False
    item = _sanitize_party_row(party)
    role = item.get("المشاركة") or ""
    qual = item.get("التأهيل") or ""
    if _is_non_driver_role(role):
        return False
    if qual == QUALIFICATION_EXEMPT or "لا يُطالب" in str(qual) or "لا يطالب" in str(qual):
        # الإعفاء خاص بغير السائق؛ لا يُعامل كمخالفة رخصة قيادة
        return False
    return qual == "غير مؤهل للقيادة"

def _is_qualified_driver_party(party) -> bool:
    if not party:
        return False
    item = _sanitize_party_row(party)
    if _is_non_driver_role(item.get("المشاركة")):
        return False
    return item.get("التأهيل") == "مؤهل للقيادة"

def _resolve_party_for_liability_slot(party_title: str, party_index: int = None, parties=None) -> dict:
    """ربط صفة الطرف في التقرير بصف الطرف الفعلي (الاسم/المشاركة/التأهيل) لا برقم مجرد."""
    parties = list(parties if parties is not None else (st.session_state.get("parties") or []))
    title = str(party_title or "").strip()
    # 1) مطابقة بالاسم داخل صفة التقرير
    named_matches = []
    for row in parties:
        item = _sanitize_party_row(row)
        name = (item.get("الاسم") or "").strip()
        if name and name in title:
            named_matches.append(item)
    if len(named_matches) == 1:
        return named_matches[0]
    if len(named_matches) > 1:
        # فضّل السائق غير المؤهل إن وُجد ضمن المطابقات، وإلا أول سائق
        for item in named_matches:
            if _is_unqualified_driver_party(item):
                return item
        for item in named_matches:
            if not _is_non_driver_role(item.get("المشاركة")):
                return item
        return named_matches[0]
    # 2) مطابقة صفة الجلسة التلقائية
    if party_index:
        auto = str(st.session_state.get(f"party_role_title_{party_index}") or "").strip()
        if auto and (auto == title or title in auto or auto in title):
            row = _party_row_for_index(parties, int(party_index))
            if row:
                return _sanitize_party_row(row)
        row = _party_row_for_index(parties, int(party_index))
        if row:
            return _sanitize_party_row(row)
    # 3) احتياطي عبر فهرس 1/2 من عناوين الجلسة
    for idx in (1, 2):
        auto = str(st.session_state.get(f"party_role_title_{idx}") or "").strip()
        p1_in = str(st.session_state.get("p1_title_input") or "").strip()
        p2_sel = str(st.session_state.get("p2_role_select") or "").strip()
        p2_custom = str(st.session_state.get("p2_custom_title") or "").strip()
        candidates = {auto, p1_in if idx == 1 else "", p2_sel if idx == 2 else "", p2_custom if idx == 2 else ""}
        if title and title in candidates:
            row = _party_row_for_index(parties, idx)
            if row:
                return _sanitize_party_row(row)
    return {}

def _reason_line_is_art32_license(raw: str) -> bool:
    text = str(raw or "")
    if re.search(r"المادة\s*\(\s*32\s*\)|جدول\s*المخالفات\s*\(?\s*5\s*/\s*11", text):
        return True
    if "قبل الحصول على رخصة" in text or "غير مؤهل للقيادة" in text:
        return True
    return False

def _render_party_role_cards(rows):
    cards = []
    for item in rows or []:
        party = _sanitize_party_row(item)
        label = html.escape(party.get("الطرف") or "طرف")
        name = html.escape(party.get("الاسم") or "—")
        role = party.get("المشاركة") or ""
        qual = party.get("التأهيل") or ""
        if _is_non_driver_role(role) or qual == QUALIFICATION_EXEMPT:
            accent = "#64748b"
            glow = "rgba(100,116,139,0.18)"
            body = "💺 راكب | لا يُطالب برخصة قيادة"
            role_label = html.escape(role or "راكب")
        elif qual == "غير مؤهل للقيادة":
            accent = "#dc2626"
            glow = "rgba(245,158,11,0.28)"
            body = "⚠️ سائق | غير مؤهل للقيادة"
            role_label = "سائق"
        else:
            accent = "#0891b2"
            glow = "rgba(14,165,233,0.22)"
            body = "🚗 سائق | مؤهل للقيادة"
            role_label = "سائق"
        cards.append(
            f'<div style="flex:1 1 210px; min-width:200px; max-width:320px; padding:12px 14px; '
            f'border-radius:14px; border:1px solid rgba(148,163,184,0.35); '
            f'background:linear-gradient(145deg, rgba(15,23,42,0.04), rgba(14,165,233,0.10)); '
            f'box-shadow:0 8px 24px {glow}; backdrop-filter:blur(8px);">'
            f'<div style="font-size:11px; color:#64748b; font-weight:700; margin-bottom:4px;">{label} · {role_label}</div>'
            f'<div style="font-size:13px; font-weight:800; color:{accent}; line-height:1.45;">{body}</div>'
            f'<div style="font-size:11px; color:#475569; margin-top:6px;">{name}</div>'
            f"</div>"
        )
    if not cards:
        return
    st.markdown(
        '<div style="display:flex; flex-wrap:wrap; gap:12px; margin:10px 0 6px 0; '
        'padding:12px; border-radius:16px; '
        'background:linear-gradient(120deg, rgba(14,165,233,0.08), rgba(37,99,235,0.06)); '
        'border:1px solid rgba(59,130,246,0.18);">'
        + "".join(cards)
        + "</div>",
        unsafe_allow_html=True,
    )

def _party_qualification_cell_html(role, qual) -> str:
    normalized = normalize_driving_qualification(qual, role=role)
    if _is_non_driver_role(role) or normalized == QUALIFICATION_EXEMPT:
        role_txt = _clean_party_text(role)
        # الشارة المعتمدة للراكب كما طُلبت حرفياً؛ المشاة بنفس الأسلوب
        if "مشاة" in role_txt or "عابر" in role_txt:
            badge_txt = "— لا يُطالب برخصة (مشاة) —"
        else:
            badge_txt = "— لا يُطالب برخصة (راكب) —"
        return (
            '<span style="display:inline-block; padding:2px 10px; border-radius:4px; '
            'background:#f1f5f9; color:#475569; border:1px dashed #94a3b8; '
            f'font-size:11px; font-weight:600;">{badge_txt}</span>'
        )
    if normalized == "غير مؤهل للقيادة":
        return (
            '<span style="display:inline-block; padding:2px 10px; border-radius:4px; '
            'background:#fff7ed; color:#c2410c; border:1px solid #fdba74; '
            'font-size:11px; font-weight:700;">⚠️ غير مؤهل للقيادة</span>'
        )
    return (
        '<span style="display:inline-block; padding:2px 10px; border-radius:4px; '
        'background:#ecfeff; color:#0e7490; border:1px solid #67e8f9; '
        'font-size:11px; font-weight:700;">✅ مؤهل للقيادة</span>'
    )

def _plain_text_len_for_autofit(value) -> int:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    try:
        text = html.unescape(text)
    except Exception:
        pass
    return len(re.sub(r"\s+", " ", text).strip())

def _estimate_a4_autofit_base_font_px(
    *,
    results_text: str = "",
    how_text: str = "",
    liability_html: str = "",
    actions_html: str = "",
    rights_text: str = "",
) -> float:
    """حساب أولي لحجم خط محتوى A4 قبل تشغيل JS auto-fit."""
    results_n = _plain_text_len_for_autofit(results_text)
    how_n = _plain_text_len_for_autofit(how_text)
    liability_n = _plain_text_len_for_autofit(liability_html)
    actions_n = _plain_text_len_for_autofit(actions_html)
    rights_n = _plain_text_len_for_autofit(rights_text)
    score = results_n + how_n + (liability_n * 1.35) + (actions_n * 1.25) + rights_n
    # أرضية موحدة مع Auto-Fit: لا أقل من 10.5px ولا أعلى من 13.5 للصناديق المشتركة
    if liability_n >= 2200 or actions_n >= 1100 or score >= 5000:
        return 10.5
    if liability_n >= 1400 or actions_n >= 700 or score >= 3200:
        return 11.5
    if liability_n >= 900 or score >= 2000:
        return 12.5
    return 13.5

def _page1_cell(value):
    if value is None:
        return ""
    try:
        missing = pd.isna(value)
        if bool(missing) and getattr(missing, "shape", None) is None:
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        text = value.strip()
    else:
        text = str(value).strip()
    if text.lower() in ("none", "nan", "<na>"):
        return ""
    return text

def inject_rtl_tab_for_data_editors():
    """عكس اتجاه زر Tab داخل جداول st.data_editor ليتحرك من اليمين إلى اليسار (RTL)."""
    components.html(
        """
        <script>
        (function () {
            const parentWin = window.parent;
            if (!parentWin || !parentWin.document) return;
            // إخفاء الحاوية الوهمية للمكون حتى لا تضيف أي فراغ في الصفحة أو الطباعة
            if (window.frameElement) {
                const container = window.frameElement.closest('[data-testid="stElementContainer"], .element-container');
                if (container) {
                    container.style.cssText = "height:0!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important;";
                }
            }
            // إزالة أي مستمع سابق لمنع التكرار عند تحديث Streamlit
            if (parentWin.__bayyinahRtlTabHandler) {
                parentWin.removeEventListener("keydown", parentWin.__bayyinahRtlTabHandler, true);
            }
            function isInsideDataEditor(el) {
                if (!el || typeof el.closest !== "function") return false;
                return Boolean(
                    el.closest('[data-testid="stDataFrame"]') ||
                    el.closest('.stDataFrame') ||
                    el.closest('#portal') ||
                    el.closest('[class*="gdg-"]') ||
                    el.closest('.dvn-scroller')
                );
            }
            function rtlTabHandler(e) {
                if (e.key !== "Tab" || e.__rtlTabFlipped) return;
                const activeEl = parentWin.document.activeElement;
                if (!isInsideDataEditor(e.target) && !isInsideDataEditor(activeEl)) {
                    return;
                }
                e.__rtlTabFlipped = true;
                const invertedShift = !e.shiftKey;
                try {
                    Object.defineProperty(e, "shiftKey", {
                        get: function () { return invertedShift; },
                        configurable: true
                    });
                    if (typeof e.getModifierState === "function") {
                        const origGetMod = e.getModifierState.bind(e);
                        Object.defineProperty(e, "getModifierState", {
                            value: function (keyArg) {
                                if (keyArg === "Shift") return invertedShift;
                                return origGetMod(keyArg);
                            },
                            configurable: true
                        });
                    }
                } catch (err) {
                    console.warn("RTL Tab override warning:", err);
                }
            }
            parentWin.__bayyinahRtlTabHandler = rtlTabHandler;
            parentWin.addEventListener("keydown", rtlTabHandler, true);
        })();
        </script>
        """,
        height=0,
        width=0,
    )

def _frame_records(frame):
    rows = []
    for row in frame.to_dict("records"):
        clean = {}
        for key, value in row.items():
            if value is None or (isinstance(value, float) and math.isnan(value)):
                clean[str(key)] = ""
            else:
                clean[str(key)] = str(value)
        rows.append(clean)
    return rows

def _records_from_dynamic_parties(vault):
    rows = []
    for i in range(1, 11):
        name = str(vault.get(f"p1_party_name_{i}") or "")
        id_no = str(vault.get(f"p1_party_id_{i}") or "")
        role = str(vault.get(f"p1_party_role_{i}") or "")
        health = str(vault.get(f"p1_party_health_{i}") or "")
        qual = str(vault.get(f"p1_party_qual_{i}") or "")
        meaningful = any((
            name.strip(),
            id_no.strip(),
            role.strip() and role != "سائق",
            health.strip() and health != "سليم",
            qual.strip() and qual not in (
                "مؤهل (رخصة سارية)",
                "مؤهل للقيادة",
                QUALIFICATION_EXEMPT,
                "➖ لا يُطالب برخصة",
            ),
        ))
        if meaningful:
            rows.append(_sanitize_party_row({
                "الطرف": _PARTY_LABELS.get(i, f"الطرف {i}"),
                "الاسم": name,
                "الهوية": id_no,
                "المشاركة": role,
                "الحالة": health,
                "التأهيل": qual,
            }))
    return rows

def _records_from_dynamic_vehicles(vault):
    rows = []
    for i in range(1, 11):
        veh_type = str(vault.get(f"p1_veh_type_{i}") or "")
        plate = str(vault.get(f"p1_veh_plate_{i}") or "")
        serial = str(vault.get(f"p1_veh_serial_{i}") or "")
        reg = str(vault.get(f"p1_veh_reg_{i}") or "")
        ins = str(vault.get(f"p1_veh_ins_{i}") or "")
        meaningful = any((
            veh_type.strip(),
            plate.strip(),
            serial.strip(),
            reg.strip() and reg != "خصوصي",
            ins.strip() and ins != "ساري",
        ))
        if meaningful:
            rows.append({
                "الطرف": _PARTY_LABELS.get(i, f"الطرف {i}"),
                "نوع المركبة": veh_type,
                "رقم اللوحة": plate,
                "الرقم التسلسلي": serial,
                "نوع الترخيص": reg,
                "التأمين": ins,
            })
    return rows

def init_and_restore_page1_state():
    if "_p1_vault" not in st.session_state:
        loaded_draft = {}
        if P1_AUTOSAVE_PATH.exists():
            try:
                loaded_draft = json.loads(P1_AUTOSAVE_PATH.read_text(encoding="utf-8"))
            except Exception:
                loaded_draft = {}
        if not isinstance(loaded_draft, dict):
            loaded_draft = {}
        st.session_state["_p1_loaded_keys"] = set(loaded_draft)
        st.session_state["_p1_vault"] = {**ALL_PAGE1_DEFAULTS, **loaded_draft}
    if st.session_state.get("_p1_pending_load") is not None:
        pending = st.session_state.pop("_p1_pending_load")
        if isinstance(pending, dict):
            st.session_state["_p1_loaded_keys"] = set(pending)
            for key, value in pending.items():
                if key in SIDEBAR_SESSION_KEYS:
                    continue
                cloned = _clone_page1_value(value)
                if "_p1_vault" not in st.session_state:
                    st.session_state["_p1_vault"] = dict(ALL_PAGE1_DEFAULTS)
                st.session_state["_p1_vault"][key] = cloned
                # رقم/موقع/سبب → saved_acc_* فقط؛ لا تستبدل مفتاح ودجت موجود
                if key in WIDGET_TO_SAVED_ACC:
                    st.session_state[WIDGET_TO_SAVED_ACC[key]] = cloned
                    if key not in st.session_state:
                        st.session_state[key] = _clone_page1_value(cloned)
                    continue
                if key not in st.session_state:
                    st.session_state[key] = _clone_page1_value(cloned)
    for key, default_val in ALL_PAGE1_DEFAULTS.items():
        if key in SIDEBAR_SESSION_KEYS and key in st.session_state:
            continue
        if key not in st.session_state:
            st.session_state[key] = _clone_page1_value(st.session_state["_p1_vault"].get(key, default_val))
    vault = st.session_state["_p1_vault"]
    for key in PAGE1_EXTRA_SYNC_KEYS:
        if key not in st.session_state and key in vault and vault.get(key) not in ("", None):
            st.session_state[key] = vault.get(key)
    for count_key in ("p1_acc_injuries", "p1_acc_deaths", "p1_parties_count"):
        try:
            st.session_state[count_key] = max(0, int(st.session_state.get(count_key) or 0))
        except (TypeError, ValueError):
            st.session_state[count_key] = 0
    if not st.session_state.get("hijri_date") and st.session_state.get("p1_acc_date"):
        st.session_state.hijri_date = st.session_state.p1_acc_date
    def _saved_rows_win(rows):
        if not isinstance(rows, list):
            return False
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key, value in row.items():
                if key == "الطرف":
                    continue
                if str(value or "").strip():
                    return True
        return False

    party_records = vault.get("p1_parties_records")
    if not _saved_rows_win(party_records):
        party_records = _records_from_dynamic_parties(vault) or party_records
    if not isinstance(party_records, list) or not party_records:
        party_records = _blank_parties()
    vehicle_records = vault.get("p1_vehicles_records")
    if not _saved_rows_win(vehicle_records):
        vehicle_records = _records_from_dynamic_vehicles(vault) or vehicle_records
    if not isinstance(vehicle_records, list) or not vehicle_records:
        vehicle_records = _blank_vehicles()
    if "parties" not in st.session_state:
        st.session_state.parties = _clone_page1_value(party_records)
    if "vehicles" not in st.session_state:
        st.session_state.vehicles = _clone_page1_value(vehicle_records)

# مفاتيح بيانات منفصلة عن ودجات text_input — لا تُعيَّن على مفاتيح الودجت مباشرة
SAVED_ACC_NUMBER = "saved_acc_number"
SAVED_ACC_LOCATION = "saved_acc_location"
SAVED_ACC_CAUSE = "saved_acc_cause"
WIDGET_TO_SAVED_ACC = {
    "p1_acc_number": SAVED_ACC_NUMBER,
    "p1_acc_location": SAVED_ACC_LOCATION,
    "p1_acc_cause": SAVED_ACC_CAUSE,
}
PAGE1_CORE_TEXT_KEYS = (
    "p1_acc_number",
    "p1_acc_location",
    "p1_acc_cause",
    "hijri_date",
    "p1_acc_date",
    "p1_acc_time",
)
PAGE1_CORE_SAVED_KEYS = (
    SAVED_ACC_NUMBER,
    SAVED_ACC_LOCATION,
    SAVED_ACC_CAUSE,
    "hijri_date",
    "p1_acc_date",
    "p1_acc_time",
)


def _is_blank_p1_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not str(value).strip():
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


def _read_core_accident_value(widget_key: str):
    """اقرأ من saved_acc_* أولاً ثم الودجت."""
    saved_key = WIDGET_TO_SAVED_ACC.get(widget_key, widget_key)
    saved_val = st.session_state.get(saved_key)
    if not _is_blank_p1_value(saved_val):
        return saved_val
    return st.session_state.get(widget_key, "")


def sync_page1_to_vault(
    extra_keys: list = None,
    write_disk: bool = False,
    allow_blank_overwrite: bool = False,
):
    """يحدّث الخزنة في الذاكرة. الحفظ التلقائي لا يكتب "" فوق قيم موجودة."""
    if "_p1_vault" not in st.session_state:
        st.session_state["_p1_vault"] = dict(ALL_PAGE1_DEFAULTS)
    vault = st.session_state["_p1_vault"]
    # ادفع قيم الودجات إلى saved_acc_* دون تعيين عكسي على الودجت
    for widget_key, saved_key in WIDGET_TO_SAVED_ACC.items():
        if widget_key in st.session_state and not _is_blank_p1_value(st.session_state.get(widget_key)):
            st.session_state[saved_key] = st.session_state.get(widget_key)
    keys_to_sync = list(ALL_PAGE1_DEFAULTS.keys()) + list(PAGE1_EXTRA_SYNC_KEYS) + list(extra_keys or [])
    for key in keys_to_sync:
        if key in WIDGET_TO_SAVED_ACC:
            new_val = _read_core_accident_value(key)
            old_val = vault.get(key)
            if (
                not allow_blank_overwrite
                and _is_blank_p1_value(new_val)
                and not _is_blank_p1_value(old_val)
            ):
                st.session_state[WIDGET_TO_SAVED_ACC[key]] = _clone_page1_value(old_val)
                continue
            vault[key] = _clone_page1_value(new_val)
            st.session_state[WIDGET_TO_SAVED_ACC[key]] = _clone_page1_value(new_val)
            continue
        if key not in st.session_state:
            continue
        new_val = st.session_state[key]
        old_val = vault.get(key)
        if (
            not allow_blank_overwrite
            and key in PAGE1_CORE_TEXT_KEYS
            and _is_blank_p1_value(new_val)
            and not _is_blank_p1_value(old_val)
        ):
            # لا تعيّن على مفتاح ودجت — خزّن في الخزنة/saved فقط
            continue
        vault[key] = _clone_page1_value(new_val)
    if not write_disk:
        return
    try:
        P1_AUTOSAVE_PATH.write_text(
            json.dumps(st.session_state["_p1_vault"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def ensure_core_accident_fields_from_vault() -> None:
    """أعد رقم/موقع/سبب إلى saved_acc_* فقط؛ ازرع الودجت بـ setdefault دون استبدال."""
    vault = st.session_state.get("_p1_vault")
    if not isinstance(vault, dict):
        vault = {}
    for widget_key, saved_key in WIDGET_TO_SAVED_ACC.items():
        candidates = (
            st.session_state.get(saved_key),
            vault.get(widget_key),
            vault.get(saved_key),
            st.session_state.get("acc_loc_value") if widget_key == "p1_acc_location" else None,
        )
        best = next((c for c in candidates if not _is_blank_p1_value(c)), None)
        if best is not None and _is_blank_p1_value(st.session_state.get(saved_key)):
            st.session_state[saved_key] = _clone_page1_value(best)
        # لا تُعيّن على مفتاح الودجت إن وُجد — فقط عند الغياب التام
        if widget_key not in st.session_state and not _is_blank_p1_value(st.session_state.get(saved_key)):
            st.session_state[widget_key] = st.session_state.get(saved_key)
    for key in ("hijri_date", "p1_acc_date", "p1_acc_time"):
        vault_val = vault.get(key)
        if key not in st.session_state and not _is_blank_p1_value(vault_val):
            st.session_state[key] = _clone_page1_value(vault_val)
        elif _is_blank_p1_value(st.session_state.get(key)) and not _is_blank_p1_value(vault_val):
            st.session_state[key] = _clone_page1_value(vault_val)
    loc = str(_read_core_accident_value("p1_acc_location") or "").strip()
    if loc:
        st.session_state["acc_loc_value"] = loc
        st.session_state[SAVED_ACC_LOCATION] = loc


def _on_core_accident_field_change() -> None:
    """حفظ فوري عبر saved_acc_* (لا تعيين قسري على مفاتيح text_input)."""
    if "_p1_vault" not in st.session_state:
        st.session_state["_p1_vault"] = dict(ALL_PAGE1_DEFAULTS)
    for widget_key, saved_key in WIDGET_TO_SAVED_ACC.items():
        if widget_key in st.session_state:
            st.session_state[saved_key] = st.session_state.get(widget_key)
            st.session_state["_p1_vault"][widget_key] = _clone_page1_value(st.session_state.get(widget_key))
    loc = str(st.session_state.get(SAVED_ACC_LOCATION) or "").strip()
    if loc:
        st.session_state["acc_loc_value"] = loc
    try:
        P1_AUTOSAVE_PATH.write_text(
            json.dumps(st.session_state["_p1_vault"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _mirror_page1_fields():
    hijri = str(st.session_state.get("hijri_date") or "")
    if hijri.strip():
        st.session_state["p1_acc_date"] = hijri
    parts = str(st.session_state.get("p1_acc_date") or hijri or "").split("/")
    if len(parts) == 3:
        st.session_state["p1_acc_year"] = parts[0]
        st.session_state["p1_acc_month"] = parts[1]
        st.session_state["p1_acc_day"] = parts[2]
    type_choice = st.session_state.get("p1_acc_type_choice")
    if type_choice:
        st.session_state["p1_acc_type"] = type_choice
    weather_choice = st.session_state.get("p1_acc_weather_choice")
    if weather_choice:
        st.session_state["p1_acc_weather"] = weather_choice
    party_rows = list(st.session_state.get("p1_parties_records") or [])
    vehicle_rows = list(st.session_state.get("p1_vehicles_records") or [])
    st.session_state["p1_parties_count"] = max(len(party_rows), len(vehicle_rows))
    for i in range(1, 11):
        party = party_rows[i - 1] if i <= len(party_rows) else None
        vehicle = vehicle_rows[i - 1] if i <= len(vehicle_rows) else None
        party_map = (
            ("p1_party_name_", "الاسم"),
            ("p1_party_id_", "الهوية"),
            ("p1_party_role_", "المشاركة"),
            ("p1_party_health_", "الحالة"),
            ("p1_party_qual_", "التأهيل"),
        )
        vehicle_map = (
            ("p1_veh_type_", "نوع المركبة"),
            ("p1_veh_plate_", "رقم اللوحة"),
            ("p1_veh_serial_", "الرقم التسلسلي"),
            ("p1_veh_reg_", "نوع الترخيص"),
            ("p1_veh_ins_", "التأمين"),
        )
        for prefix, column in party_map:
            key_name = f"{prefix}{i}"
            if party is None:
                st.session_state[key_name] = ALL_PAGE1_DEFAULTS[key_name]
            else:
                st.session_state[key_name] = str(party.get(column, "") or "")
        for prefix, column in vehicle_map:
            key_name = f"{prefix}{i}"
            if vehicle is None:
                st.session_state[key_name] = ALL_PAGE1_DEFAULTS[key_name]
            else:
                st.session_state[key_name] = str(vehicle.get(column, "") or "")

def export_page1_payload(extra_keys: list = None) -> dict:
    _mirror_page1_fields()
    sync_page1_to_vault(extra_keys=extra_keys, write_disk=False)
    return dict(st.session_state["_p1_vault"])

def queue_load_page1_payload(saved_dict: dict):
    if not isinstance(saved_dict, dict):
        return
    p1_data = saved_dict.get("page1_data", saved_dict)
    if not isinstance(p1_data, dict):
        p1_data = {}
    filtered = {key: p1_data[key] for key in ALL_PAGE1_DEFAULTS if key in p1_data}
    for key in PAGE1_EXTRA_SYNC_KEYS:
        if key in p1_data:
            filtered[key] = p1_data[key]
    # تطابق مفاتيح البيانات: saved_acc_* + p1_acc_* للتوافق
    for widget_key, saved_key in WIDGET_TO_SAVED_ACC.items():
        top_saved = saved_dict.get(saved_key)
        top_widget = saved_dict.get(widget_key)
        best = top_saved if not _is_blank_p1_value(top_saved) else top_widget
        if not _is_blank_p1_value(best):
            filtered[widget_key] = best
            st.session_state[saved_key] = best
    for key in ("hijri_date", "p1_acc_date", "p1_acc_time"):
        top_val = saved_dict.get(key)
        nested_val = filtered.get(key)
        if not _is_blank_p1_value(top_val) and _is_blank_p1_value(nested_val):
            filtered[key] = top_val
        elif key in saved_dict and key not in filtered and not _is_blank_p1_value(top_val):
            filtered[key] = top_val
    if filtered:
        st.session_state["_p1_pending_load"] = filtered

def reset_page1_payload():
    pending = {}
    for key, value in ALL_PAGE1_DEFAULTS.items():
        pending[key] = _clone_page1_value(value)
    st.session_state["_p1_pending_load"] = pending
    st.session_state.parties = _blank_parties()
    st.session_state.vehicles = _blank_vehicles()
    for key in (
        "p1_parties_editor",
        "p1_vehicles_editor",
        "p1_acc_type_choice",
        "p1_acc_weather_choice",
        "hijri_month_label",
        "hijri_year_label",
        "hijri_date_manual_in",
        "hijri_date_lux_y",
        "hijri_date_lux_m",
        "hijri_date_lux_d",
        "hijri_date_sel_month_ui",
        "hijri_date_sel_year_ui",
    ):
        st.session_state.pop(key, None)
    for day_num in range(1, 31):
        st.session_state.pop(f"hijri_date_d_{day_num}", None)
    if P1_AUTOSAVE_PATH.exists():
        try:
            P1_AUTOSAVE_PATH.unlink()
        except Exception:
            pass

DRAFT_FILE_PATH = "bayyinah_autosave_draft.json"
DEFAULT_REPORT_STATE = {
    "accident_results": "",
    "technical_description": "",
    "legal_opinion": "",
    "liability_ratio_select": "100% الطرف الأول | 0% الطرف الثاني",
    "custom_p1_ratio": 75,
    "p1_title_input": "قائد المركبة الأولى (الطرف الأول)",
    "p2_role_select": "قائد المركبة الثانية (الطرف الثاني)",
    "p2_custom_title": "الطرف الثاني",
    "p1_reasons": (
        "بناءً على المعاينة الفنية وتطبيق قواعد المساءلة المرورية واستناداً إلى المادة (60) والفقرات (60/1، 60/2، 60/3) من اللائحة التنفيذية.\n"
        "عدم التأكد من خلو الطريق وأخذ الحيطة والحذر اللازمين قبل المناورة أو التجاوز."
    ),
    "p2_reasons": (
        "استناداً إلى المادة (60) والفقرة (60/2) من نظام المرور ولائحته التنفيذية.\n"
        "الإهمال وضعف الانتباه وعدم تفادي الخطأ الممكن تلافيه أثناء السير أو العبور."
    ),
    "selected_articles": [],
    "accident_nature": "حادث مروري اعتيادي (تلفيات مادية)",
    "rights_status": "انقضاء الحق الخاص بالتنازل والصلح، ولا يوجد حق عام",
    "acc_nature_sel": "حادث مروري اعتيادي (تلفيات مادية)",
    "acc_nature_custom": "حادث مروري اعتيادي",
    "rights_sel": "انقضاء الحق الخاص بالتنازل والصلح، ولا يوجد حق عام",
    "rights_custom": "",
    "selected_actions_multi": ["1. صلح وتنازل ميداني نهائي"],
    "actions_taken_editor": "",
    "extra_procedure": "",
    "has_video": "لا فيديو",
    "video_clip_count": 1,
    "video_clips": [],
    "video_source": "كاميرا مراقبة أمنية (CCTV)",
    "video_clarity": "واضح وموثق بختم زمني (تاريخ ووقت)",
    "video_timestamp": "",
    "video_findings": [],
    "video_custom_notes": "",
    "video_injected_text": "",
    "auto_analyze_video": False,
    "results_animal_loss_enabled": False,
    "results_animal_loss_text": "",
    "results_property_damage_enabled": False,
    "results_property_damage_text": "",
    "results_data_fingerprint": None,
    "show_page_numbers": False,
    "include_sketch": True,
    "include_aerial": True,
    "aerial_place": "below",
    "studio_layout_mode": "🖥️ عرض مزدوج: الكروكي التفاعلي وبجانبه خريطة التصوير الجوي",
    "report_media_mode": "كلاهما",
    "saved_satellite_state": {},
    "confirm_clear": False,
    "last_saved_time": "لم يتم الحفظ بعد",
}

# مفاتيح تبويب 3 الثابتة (مواد / قرائن / نسب / نصوص) — لا تُمسَح عند مغادرة التبويب
# حقول نص التبويب3 المقفلة: saved_*_text مصدر الحقيقة + *_is_manual + *_rev لمفتاح الودجت
TAB3_LOCKED_TEXT_SPECS = (
    {
        "id": "accident_results",
        "saved": "saved_accident_results_text",
        "manual": "accident_results_is_manual",
        "rev": "accident_results_rev",
    },
    {
        "id": "technical_description",
        "saved": "saved_technical_description_text",
        "manual": "technical_description_is_manual",
        "rev": "technical_description_rev",
    },
    {
        "id": "p1_reasons",
        "saved": "saved_p1_reasons_text",
        "manual": "p1_reasons_is_manual",
        "rev": "p1_reasons_rev",
        "mirrors": ("legal_opinion",),
    },
    {
        "id": "p2_reasons",
        "saved": "saved_p2_reasons_text",
        "manual": "p2_reasons_is_manual",
        "rev": "p2_reasons_rev",
    },
)
TAB3_LOCKED_TEXT_BY_ID = {spec["id"]: spec for spec in TAB3_LOCKED_TEXT_SPECS}
TAB3_LOCKED_SAVED_KEYS = tuple(spec["saved"] for spec in TAB3_LOCKED_TEXT_SPECS)
TAB3_LOCKED_MANUAL_KEYS = tuple(spec["manual"] for spec in TAB3_LOCKED_TEXT_SPECS)
TAB3_LOCKED_REV_KEYS = tuple(spec["rev"] for spec in TAB3_LOCKED_TEXT_SPECS)

# بنود إضافية لنتائج الحادث — مصدر الحقيقة saved_*؛ الودجات UI فقط
RESULTS_ANIMAL_DEFAULT = "نفوق حيوانات/مواشي أو حيوان أليف"
RESULTS_PROP_DEFAULT = "تلفيات ممتلكات عامة أو خاصة"
SAVED_HAS_ANIMALS = "saved_has_animals"
SAVED_ANIMALS_DESC = "saved_animals_desc"
SAVED_HAS_PROP = "saved_has_prop"
SAVED_PROP_DESC = "saved_prop_desc"
RESULTS_EXTRA_SAVED_KEYS = (
    SAVED_HAS_ANIMALS,
    SAVED_ANIMALS_DESC,
    SAVED_HAS_PROP,
    SAVED_PROP_DESC,
)
RESULTS_EXTRA_WIDGET_KEYS = (
    "results_animal_loss_enabled",
    "results_animal_loss_text",
    "results_property_damage_enabled",
    "results_property_damage_text",
)
_LAST_ANIMAL_RESULT_BODY = "_last_animal_result_body"
_LAST_PROP_RESULT_BODY = "_last_prop_result_body"

TAB3_PERMANENT_KEYS = (
    "selected_articles",
    "accident_results",
    "technical_description",
    "legal_opinion",
    "liability_ratio_select",
    "custom_p1_ratio",
    "p1_ratio",
    "p2_ratio",
    "p1_title_input",
    "p2_role_select",
    "p2_custom_title",
    "p2_title",
    "p1_reasons",
    "p2_reasons",
    *TAB3_LOCKED_SAVED_KEYS,
    *TAB3_LOCKED_MANUAL_KEYS,
    *TAB3_LOCKED_REV_KEYS,
    "liability_html",
    "acc_nature_sel",
    "acc_nature_custom",
    "accident_nature",
    "rights_sel",
    "rights_custom",
    "rights_status",
    "selected_actions_multi",
    "actions_taken_editor",
    "final_actions_html",
    "extra_procedure",
    "has_video",
    "video_clip_count",
    "video_clips",
    "video_source",
    "video_clarity",
    "video_timestamp",
    "video_findings",
    "video_custom_notes",
    "video_injected_text",
    "auto_analyze_video",
    "results_animal_loss_enabled",
    "results_animal_loss_text",
    "results_property_damage_enabled",
    "results_property_damage_text",
    "saved_has_animals",
    "saved_animals_desc",
    "saved_has_prop",
    "saved_prop_desc",
    "results_data_fingerprint",
    "criminal_participating_agency",
    "criminal_escaped_vehicles",
    "criminal_shots_fired",
    "criminal_contraband_found",
    "law_selection_sig",
    "tab3_content_fingerprint",
    "_actions_plural_deaths_sig",
)
_PERMANENT_FORM_DISK = Path(__file__).resolve().parent / ".bayyinah_persistence" / "permanent_form.json"


def _is_blank_form_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


def _clone_form_value(value):
    if isinstance(value, list):
        return [dict(item) if isinstance(item, dict) else item for item in value]
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, tuple):
        return tuple(value)
    return value


def _ensure_tab3_locked_text_defaults() -> None:
    for spec in TAB3_LOCKED_TEXT_SPECS:
        st.session_state.setdefault(spec["saved"], "")
        st.session_state.setdefault(spec["manual"], False)
        st.session_state.setdefault(spec["rev"], 0)
        # ترحيل القيم القديمة من مفتاح المرآة إن وُجدت
        legacy = st.session_state.get(spec["id"])
        if _is_blank_form_value(st.session_state.get(spec["saved"])) and not _is_blank_form_value(legacy):
            st.session_state[spec["saved"]] = str(legacy)


def _tab3_text_widget_key(field_id: str) -> str:
    rev = int(st.session_state.get(f"{field_id}_rev") or 0)
    return f"{field_id}_ta_{rev}"


def _read_tab3_saved_text(field_id: str) -> str:
    spec = TAB3_LOCKED_TEXT_BY_ID.get(field_id)
    if not spec:
        return str(st.session_state.get(field_id) or "")
    saved = st.session_state.get(spec["saved"])
    if saved is not None and str(saved) != "":
        return str(saved)
    if spec["saved"] in st.session_state:
        return str(saved or "")
    return str(st.session_state.get(field_id) or "")


def _write_tab3_saved_text(field_id: str, text: str, *, mark_manual: bool | None = None) -> None:
    spec = TAB3_LOCKED_TEXT_BY_ID.get(field_id)
    if not spec:
        st.session_state[field_id] = text
        return
    st.session_state[spec["saved"]] = str(text or "")
    # مرآة للتوافق مع الكود القديم/الظل — ليست مفتاح ودجت
    st.session_state[field_id] = st.session_state[spec["saved"]]
    for mirror in spec.get("mirrors") or ():
        st.session_state[mirror] = st.session_state[spec["saved"]]
    if mark_manual is True:
        st.session_state[spec["manual"]] = True
    elif mark_manual is False:
        st.session_state[spec["manual"]] = False


def _tab3_text_is_manual(field_id: str) -> bool:
    spec = TAB3_LOCKED_TEXT_BY_ID.get(field_id)
    if not spec:
        return False
    return bool(st.session_state.get(spec["manual"]))


def _make_tab3_text_on_change(field_id: str, widget_key: str):
    def _on_change() -> None:
        _write_tab3_saved_text(
            field_id,
            st.session_state.get(widget_key, ""),
            mark_manual=True,
        )
        try:
            sync_permanent_form_data(reason=f"tab3_text_{field_id}")
        except Exception:
            pass

    return _on_change


def _bump_tab3_text_rev(field_id: str) -> None:
    spec = TAB3_LOCKED_TEXT_BY_ID.get(field_id)
    if not spec:
        return
    try:
        st.session_state[spec["rev"]] = int(st.session_state.get(spec["rev"]) or 0) + 1
    except (TypeError, ValueError):
        st.session_state[spec["rev"]] = 1


def render_tab3_locked_text_area(field_id: str, label: str, height: int = 110):
    """text_area مثبت: on_change يحفظ ويقفل؛ زر استعادة تلقائية يرفع rev."""
    _ensure_tab3_locked_text_defaults()
    spec = TAB3_LOCKED_TEXT_BY_ID[field_id]
    rev = int(st.session_state.get(spec["rev"]) or 0)
    widget_key = _tab3_text_widget_key(field_id)
    if widget_key not in st.session_state:
        st.session_state[widget_key] = _read_tab3_saved_text(field_id)
    head_l, head_r = st.columns([4, 1.2])
    with head_r:
        if _tab3_text_is_manual(field_id):
            st.caption("🔒 تعديل يدوي")
        if st.button(
            "استعادة تلقائية",
            key=f"restore_auto_{field_id}_{rev}",
            use_container_width=True,
        ):
            st.session_state[spec["manual"]] = False
            _bump_tab3_text_rev(field_id)
            st.rerun()
    with head_l:
        st.text_area(
            label,
            key=widget_key,
            height=height,
            on_change=_make_tab3_text_on_change(field_id, widget_key),
        )
    # حافظ على المرآة بعد الرسم
    _write_tab3_saved_text(
        field_id,
        st.session_state.get(widget_key, _read_tab3_saved_text(field_id)),
        mark_manual=None,
    )
    return _read_tab3_saved_text(field_id)


def _set_tab3_generated_text(field_id: str, generated: str) -> bool:
    """ولّد إلى saved_* فقط إن لم يكن النص مقفولاً يدوياً."""
    if _tab3_text_is_manual(field_id):
        return False
    current = _read_tab3_saved_text(field_id)
    kept = _extract_marked_block(current)
    merged = _upsert_marked_block(str(generated or ""), kept)
    _write_tab3_saved_text(field_id, merged, mark_manual=False)
    return True


def compute_tab3_content_fingerprint() -> tuple:
    """بصمة المواد + القرائن + النسب — إعادة توليد كيفية الوقوع والرأي فقط عند تغيّرها."""
    articles = tuple(st.session_state.get("selected_articles") or [])
    try:
        findings = json.dumps(
            st.session_state.get("video_findings") or [],
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except Exception:
        findings = str(st.session_state.get("video_findings") or [])
    evidence = (
        str(st.session_state.get("has_video") or ""),
        findings,
        str(st.session_state.get("video_injected_text") or ""),
        str(st.session_state.get("video_timestamp") or ""),
        str(st.session_state.get("video_custom_notes") or ""),
    )
    ratios = (
        str(st.session_state.get("liability_ratio_select") or ""),
        int(st.session_state.get("p1_ratio") or 0),
        int(st.session_state.get("p2_ratio") or 0),
    )
    return (articles, evidence, ratios)


def compute_results_data_fingerprint() -> tuple:
    """بصمة بيانات الأطراف/المركبات والبنود الإضافية لتوليد نتائج الحادث."""
    parties = st.session_state.get("parties") or []
    vehicles = st.session_state.get("vehicles") or []
    party_sig = tuple(
        (
            str(p.get("الطرف") or ""),
            str(p.get("الاسم") or ""),
            str(p.get("المشاركة") or ""),
            str(p.get("الحالة") or ""),
            str(st.session_state.get(f"party_role_title_{idx}") or ""),
        )
        for idx, p in enumerate(parties, start=1)
        if isinstance(p, dict)
    )
    vehicle_sig = tuple(
        (
            str(v.get("الطرف") or ""),
            str(v.get("نوع المركبة") or ""),
            str(v.get("رقم اللوحة") or ""),
            str(v.get("الرقم التسلسلي") or ""),
        )
        for v in vehicles
        if isinstance(v, dict)
    )
    extras = (
        bool(st.session_state.get(SAVED_HAS_ANIMALS)),
        str(st.session_state.get(SAVED_ANIMALS_DESC) or "").strip(),
        bool(st.session_state.get(SAVED_HAS_PROP)),
        str(st.session_state.get(SAVED_PROP_DESC) or "").strip(),
    )
    return (party_sig, vehicle_sig, extras)


def _party_result_role_name(party_index: int, party_row: dict) -> str:
    """صفة الطرف مع الاسم لبند الوفاة/الإصابة في نتائج الحادث."""
    name = str(party_row.get("الاسم") or "").strip()
    participation = str(party_row.get("المشاركة") or "").strip()
    party_label = str(party_row.get("الطرف") or f"الطرف {party_index}").strip()
    role = str(st.session_state.get(f"party_role_title_{party_index}") or "").strip()
    if not role:
        if participation in ("سائق", "قائد"):
            role = build_driver_party_title(party_index)
        elif participation:
            role = participation
        else:
            role = party_label
    if name and name not in role:
        return f"{role} / {name}"
    if role:
        return role
    return name or party_label


def _strip_results_lead_in(text: str) -> str:
    """احذف «نتج عن الحادث :» / «نتج عن الحادث:» من بداية نتائج الحادث."""
    lead_ins = ("نتج عن الحادث :", "نتج عن الحادث:")
    out_lines = []
    for line in str(text or "").split("\n"):
        stripped = line.strip()
        if stripped in lead_ins or stripped == "نتج عن الحادث":
            continue
        for prefix in lead_ins:
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix):].lstrip(" \u00a0\t")
                line = stripped
                break
        out_lines.append(line)
    return "\n".join(out_lines).strip()


def _ensure_results_extras_defaults() -> None:
    """تهيئة saved_has_animals/desc وsaved_has_prop/desc مع ترحيل الودجات القديمة."""
    if SAVED_HAS_ANIMALS not in st.session_state:
        st.session_state[SAVED_HAS_ANIMALS] = bool(
            st.session_state.get("results_animal_loss_enabled") or False
        )
    if SAVED_ANIMALS_DESC not in st.session_state:
        st.session_state[SAVED_ANIMALS_DESC] = str(
            st.session_state.get("results_animal_loss_text") or ""
        )
    if SAVED_HAS_PROP not in st.session_state:
        st.session_state[SAVED_HAS_PROP] = bool(
            st.session_state.get("results_property_damage_enabled") or False
        )
    if SAVED_PROP_DESC not in st.session_state:
        st.session_state[SAVED_PROP_DESC] = str(
            st.session_state.get("results_property_damage_text") or ""
        )
    # بذر الودجات من saved_* قبل الرسم فقط إن غابت
    if "results_animal_loss_enabled" not in st.session_state:
        st.session_state["results_animal_loss_enabled"] = bool(
            st.session_state.get(SAVED_HAS_ANIMALS)
        )
    if "results_animal_loss_text" not in st.session_state:
        st.session_state["results_animal_loss_text"] = str(
            st.session_state.get(SAVED_ANIMALS_DESC) or ""
        )
    if "results_property_damage_enabled" not in st.session_state:
        st.session_state["results_property_damage_enabled"] = bool(
            st.session_state.get(SAVED_HAS_PROP)
        )
    if "results_property_damage_text" not in st.session_state:
        st.session_state["results_property_damage_text"] = str(
            st.session_state.get(SAVED_PROP_DESC) or ""
        )


def _sync_results_extras_widgets_to_saved() -> None:
    """انسخ ودجات البنود الإضافية → saved_*."""
    if "results_animal_loss_enabled" in st.session_state:
        st.session_state[SAVED_HAS_ANIMALS] = bool(
            st.session_state.get("results_animal_loss_enabled")
        )
    if "results_animal_loss_text" in st.session_state:
        st.session_state[SAVED_ANIMALS_DESC] = str(
            st.session_state.get("results_animal_loss_text") or ""
        )
    if "results_property_damage_enabled" in st.session_state:
        st.session_state[SAVED_HAS_PROP] = bool(
            st.session_state.get("results_property_damage_enabled")
        )
    if "results_property_damage_text" in st.session_state:
        st.session_state[SAVED_PROP_DESC] = str(
            st.session_state.get("results_property_damage_text") or ""
        )


def _normalize_result_item_body(line: str) -> str:
    s = str(line or "").strip()
    s = re.sub(r"^\d+\s*[-–—.)]\s*", "", s).strip()
    s = _strip_results_lead_in(s.rstrip(".")).strip()
    return s


def _parse_result_item_bodies(text: str) -> list[str]:
    bodies = []
    for raw in str(text or "").splitlines():
        body = _normalize_result_item_body(raw)
        if body:
            bodies.append(body)
    return bodies


def _format_result_item_bodies(bodies: list[str]) -> str:
    numbered = []
    for i, body in enumerate(bodies, start=1):
        clean = _normalize_result_item_body(body)
        if not clean:
            continue
        numbered.append(f"{i}- {clean}.")
    return "\n".join(numbered)


def _results_extra_match_set(kind: str, current_desc: str) -> set[str]:
    """أجسام البنود التي تُعدّ نفوقاً أو تلفيات ممتلكات (للتحديث/الحذف)."""
    if kind == "animal":
        defaults = {RESULTS_ANIMAL_DEFAULT}
        last_key = _LAST_ANIMAL_RESULT_BODY
    else:
        defaults = {RESULTS_PROP_DEFAULT}
        last_key = _LAST_PROP_RESULT_BODY
    bodies = set(defaults)
    last = st.session_state.get(last_key)
    if last:
        bodies.add(_normalize_result_item_body(str(last)))
    desc = _normalize_result_item_body(current_desc)
    if desc:
        bodies.add(desc)
    return {b for b in bodies if b}


def _looks_like_animal_result_line(body: str, match_set: set[str]) -> bool:
    b = _normalize_result_item_body(body)
    if not b:
        return False
    if b in match_set:
        return True
    if b.startswith("نفوق"):
        return True
    return ("حيوانات" in b) or ("مواشي" in b) or ("حيوان أليف" in b)


def _looks_like_prop_result_line(body: str, match_set: set[str]) -> bool:
    b = _normalize_result_item_body(body)
    if not b:
        return False
    if b in match_set:
        return True
    if b.startswith("تلفيات ممتلكات"):
        return True
    return ("ممتلكات" in b) and ("تلفيات" in b or "أتلاف" in b or "اتلاف" in b)


def _apply_results_extras_to_text(
    text: str,
    *,
    has_animals: bool,
    animals_desc: str,
    has_prop: bool,
    prop_desc: str,
) -> str:
    """إدراج/تحديث/حذف بنود النفوق والتلفيات داخل نص النتائج مع إعادة الترقيم."""
    # حافظ على كتلة القرائن المرئية إن وُجدت
    marked = ""
    try:
        marked = _extract_marked_block(text)
        base_text = _strip_marked_block(text)
    except Exception:
        base_text = str(text or "")
    animal_match = _results_extra_match_set("animal", animals_desc)
    prop_match = _results_extra_match_set("prop", prop_desc)
    kept = []
    for body in _parse_result_item_bodies(base_text):
        if body in ("[بداية القرائن المرئية]", "[نهاية القرائن المرئية]"):
            continue
        if _looks_like_animal_result_line(body, animal_match):
            continue
        if _looks_like_prop_result_line(body, prop_match):
            continue
        kept.append(body)
    if has_animals:
        animal_body = _normalize_result_item_body(animals_desc) or RESULTS_ANIMAL_DEFAULT
        kept.append(animal_body)
        st.session_state[_LAST_ANIMAL_RESULT_BODY] = animal_body
    else:
        st.session_state.pop(_LAST_ANIMAL_RESULT_BODY, None)
    if has_prop:
        prop_body = _normalize_result_item_body(prop_desc) or RESULTS_PROP_DEFAULT
        kept.append(prop_body)
        st.session_state[_LAST_PROP_RESULT_BODY] = prop_body
    else:
        st.session_state.pop(_LAST_PROP_RESULT_BODY, None)
    formatted = _format_result_item_bodies(kept)
    if marked:
        try:
            return _upsert_marked_block(formatted, marked)
        except Exception:
            return formatted
    return formatted


def patch_saved_results_extras(*, bump_rev: bool = True) -> bool:
    """حدّث saved_accident_results_text ببنود النفوق/التلفيات حتى مع is_manual."""
    _ensure_tab3_locked_text_defaults()
    _ensure_results_extras_defaults()
    has_animals = bool(st.session_state.get(SAVED_HAS_ANIMALS))
    animals_desc = str(st.session_state.get(SAVED_ANIMALS_DESC) or "")
    has_prop = bool(st.session_state.get(SAVED_HAS_PROP))
    prop_desc = str(st.session_state.get(SAVED_PROP_DESC) or "")
    current = _read_tab3_saved_text("accident_results")
    updated = _apply_results_extras_to_text(
        current,
        has_animals=has_animals,
        animals_desc=animals_desc,
        has_prop=has_prop,
        prop_desc=prop_desc,
    )
    if updated == current:
        return False
    # لا تلمس is_manual — الإدراج/التحديث/الحذف يعمل مع القفل اليدوي
    _write_tab3_saved_text("accident_results", updated, mark_manual=None)
    if bump_rev:
        _bump_tab3_text_rev("accident_results")
    return True


def _on_results_extras_change() -> None:
    """on_change: احفظ saved_* ثم رقّع نص النتائج وارفع rev."""
    _sync_results_extras_widgets_to_saved()
    patch_saved_results_extras(bump_rev=True)
    try:
        sync_permanent_form_data(reason="results_extras")
    except Exception:
        pass


def build_accident_results_text() -> str:
    """توليد نتائج الحادث من وفيات/إصابات الأطراف ثم تلفيات المركبات والبنود الإضافية."""
    _ensure_results_extras_defaults()
    lines = []
    parties = st.session_state.get("parties") or []
    for idx, party in enumerate(parties, start=1):
        if not isinstance(party, dict):
            continue
        health = str(party.get("الحالة") or "").strip()
        health_norm = health.replace("ى", "ي")
        label = _party_result_role_name(idx, party)
        if health_norm in ("متوفي", "وفاة") or "متوف" in health_norm:
            lines.append(f"وفاة {label}")
        elif health_norm in ("مصاب", "اصابة", "إصابة") or health_norm.startswith("مصاب"):
            lines.append(f"إصابة {label}")

    vehicles = st.session_state.get("vehicles") or []
    for idx, veh in enumerate(vehicles, start=1):
        if not isinstance(veh, dict):
            continue
        vtype = str(veh.get("نوع المركبة") or "").strip()
        plate = str(veh.get("رقم اللوحة") or "").strip()
        serial = str(veh.get("الرقم التسلسلي") or "").strip()
        party_label = str(veh.get("الطرف") or f"الطرف {idx}").strip()
        if not (vtype or plate or serial):
            continue
        item = f"تلفيات مركبة {party_label}"
        if vtype:
            item += f" ({vtype})"
        if plate:
            item += f" لوحة {plate}"
        lines.append(item)

    if st.session_state.get(SAVED_HAS_ANIMALS):
        text = str(st.session_state.get(SAVED_ANIMALS_DESC) or "").strip()
        lines.append(text or RESULTS_ANIMAL_DEFAULT)
    if st.session_state.get(SAVED_HAS_PROP):
        text = str(st.session_state.get(SAVED_PROP_DESC) or "").strip()
        lines.append(text or RESULTS_PROP_DEFAULT)

    if not lines:
        return ""
    numbered = []
    for i, line in enumerate(lines, start=1):
        clean = _strip_results_lead_in(line.rstrip(".")).strip()
        if not clean:
            continue
        numbered.append(f"{i}- {clean}.")
    return "\n".join(numbered)


def sync_permanent_form_data(reason: str = "manual") -> dict:
    """ينسخ مفاتيح التبويب 3 إلى الظل ويحفظها للقرص قبل rerun/تنقل/طباعة."""
    shadow = dict(st.session_state.get("_PERMANENT_FORM_DATA_") or {})
    for key in TAB3_PERMANENT_KEYS:
        if key in st.session_state:
            shadow[key] = _clone_form_value(st.session_state.get(key))
    shadow["_synced_reason"] = reason
    shadow["_synced_at"] = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d | %I:%M:%S %p")
    st.session_state["_PERMANENT_FORM_DATA_"] = shadow
    try:
        _PERMANENT_FORM_DISK.parent.mkdir(parents=True, exist_ok=True)
        _PERMANENT_FORM_DISK.write_text(
            json.dumps(shadow, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError:
        pass
    return shadow


def reinject_permanent_form_data() -> int:
    """قبل رسم أدوات التبويب 3: أعد حقن المفاتيح الغائبة/الفارغة من الظل."""
    shadow = st.session_state.get("_PERMANENT_FORM_DATA_")
    if not isinstance(shadow, dict) or not shadow:
        if _PERMANENT_FORM_DISK.is_file():
            try:
                shadow = json.loads(_PERMANENT_FORM_DISK.read_text(encoding="utf-8"))
                if isinstance(shadow, dict):
                    st.session_state["_PERMANENT_FORM_DATA_"] = shadow
            except (OSError, json.JSONDecodeError, TypeError):
                shadow = {}
    if not isinstance(shadow, dict):
        return 0
    injected = 0
    for key in TAB3_PERMANENT_KEYS:
        if key not in shadow:
            continue
        stored = shadow.get(key)
        if _is_blank_form_value(stored):
            continue
        current = st.session_state.get(key) if key in st.session_state else None
        if key not in st.session_state or _is_blank_form_value(current):
            st.session_state[key] = _clone_form_value(stored)
            injected += 1
    return injected


def get_form_value(key: str, default=None):
    """قراءة من session مع fallback لظل _PERMANENT_FORM_DATA_ — نصوص التبويب3 من saved_*."""
    spec = TAB3_LOCKED_TEXT_BY_ID.get(key)
    if spec:
        saved_val = st.session_state.get(spec["saved"])
        if not _is_blank_form_value(saved_val):
            return saved_val
        shadow = st.session_state.get("_PERMANENT_FORM_DATA_")
        if isinstance(shadow, dict):
            sh_saved = shadow.get(spec["saved"])
            if not _is_blank_form_value(sh_saved):
                return sh_saved
            sh_legacy = shadow.get(key)
            if not _is_blank_form_value(sh_legacy):
                return sh_legacy
    if key in st.session_state and not _is_blank_form_value(st.session_state.get(key)):
        return st.session_state.get(key)
    shadow = st.session_state.get("_PERMANENT_FORM_DATA_")
    if isinstance(shadow, dict) and key in shadow and not _is_blank_form_value(shadow.get(key)):
        return shadow.get(key)
    if key in st.session_state:
        return st.session_state.get(key)
    return default


def clear_permanent_form_data() -> None:
    st.session_state.pop("_PERMANENT_FORM_DATA_", None)
    try:
        if _PERMANENT_FORM_DISK.is_file():
            _PERMANENT_FORM_DISK.unlink()
    except OSError:
        pass


def init_and_load_state():
    if "state_initialized" in st.session_state:
        return
    if os.path.exists(DRAFT_FILE_PATH):
        try:
            with open(DRAFT_FILE_PATH, "r", encoding="utf-8") as draft_file:
                saved_data = json.load(draft_file)
            for key, default_val in DEFAULT_REPORT_STATE.items():
                st.session_state[key] = saved_data.get(key, default_val)
            queue_load_page1_payload(saved_data)
            # استرجع الأطراف/المركبات المحفوظة يدوياً إن وُجدت
            if isinstance(saved_data.get("parties"), list):
                st.session_state.parties = saved_data.get("parties") or _blank_parties()
            if isinstance(saved_data.get("vehicles"), list):
                st.session_state.vehicles = saved_data.get("vehicles") or _blank_vehicles()
            # طبّق رقم/موقع/سبب على saved_acc_* فقط (لا تعيين قسري على ودجات text_input)
            for _widget_key, _saved_key in WIDGET_TO_SAVED_ACC.items():
                _top = saved_data.get(_saved_key, saved_data.get(_widget_key))
                if not _is_blank_p1_value(_top) and _is_blank_p1_value(st.session_state.get(_saved_key)):
                    st.session_state[_saved_key] = _top
            for _core_key in ("hijri_date", "p1_acc_date", "p1_acc_time"):
                _top = saved_data.get(_core_key)
                if not _is_blank_p1_value(_top) and _is_blank_p1_value(st.session_state.get(_core_key)):
                    st.session_state[_core_key] = _top
            if saved_data.get("last_saved_time"):
                st.session_state["last_saved_time"] = saved_data.get("last_saved_time")
                st.session_state["last_saved_at"] = saved_data.get("last_saved_time")
        except (OSError, json.JSONDecodeError, TypeError):
            for key, default_val in DEFAULT_REPORT_STATE.items():
                st.session_state.setdefault(key, default_val)
    else:
        for key, default_val in DEFAULT_REPORT_STATE.items():
            st.session_state.setdefault(key, default_val)
    if not isinstance(st.session_state.get("selected_articles"), list):
        st.session_state.selected_articles = []
    if not isinstance(st.session_state.get("selected_actions_multi"), list):
        st.session_state.selected_actions_multi = ["1. صلح وتنازل ميداني نهائي"]
    if not isinstance(st.session_state.get("video_findings"), list):
        st.session_state.video_findings = []
    for text_key in ("accident_results", "technical_description", "legal_opinion", "extra_procedure", "video_timestamp", "video_custom_notes", "p1_title_input", "p2_custom_title", "p1_reasons", "p2_reasons", "acc_nature_custom", "rights_custom", "actions_taken_editor"):
        if not isinstance(st.session_state.get(text_key), str):
            st.session_state[text_key] = ""
    if not isinstance(st.session_state.get("show_page_numbers"), bool):
        st.session_state.show_page_numbers = False
    if not isinstance(st.session_state.get("auto_analyze_video"), bool):
        st.session_state.auto_analyze_video = False
    _ensure_results_extras_defaults()
    if not isinstance(st.session_state.get(SAVED_HAS_ANIMALS), bool):
        st.session_state[SAVED_HAS_ANIMALS] = bool(st.session_state.get(SAVED_HAS_ANIMALS))
    if not isinstance(st.session_state.get(SAVED_HAS_PROP), bool):
        st.session_state[SAVED_HAS_PROP] = bool(st.session_state.get(SAVED_HAS_PROP))
    if not isinstance(st.session_state.get(SAVED_ANIMALS_DESC), str):
        st.session_state[SAVED_ANIMALS_DESC] = str(st.session_state.get(SAVED_ANIMALS_DESC) or "")
    if not isinstance(st.session_state.get(SAVED_PROP_DESC), str):
        st.session_state[SAVED_PROP_DESC] = str(st.session_state.get(SAVED_PROP_DESC) or "")
    if not isinstance(st.session_state.get("include_sketch"), bool):
        st.session_state.include_sketch = True
    if not isinstance(st.session_state.get("include_aerial"), bool):
        st.session_state.include_aerial = True
    if st.session_state.get("report_media_mode") not in ("كلاهما", "كروكي فقط", "جوي فقط"):
        st.session_state.report_media_mode = "كلاهما"
    if not isinstance(st.session_state.get("saved_satellite_state"), dict):
        st.session_state.saved_satellite_state = {}
    if not isinstance(st.session_state.get("aerial_sketch_data_url"), str):
        st.session_state.aerial_sketch_data_url = ""
    if not st.session_state.get("aerial_place"):
        st.session_state.aerial_place = "below"
    # مواءمة مفاتيح الجلسة القديمة مع المخزن الدائم
    if st.session_state.get("saved_satellite_state") and not st.session_state.get("_saved_satellite_state"):
        st.session_state["_saved_satellite_state"] = dict(st.session_state.get("saved_satellite_state") or {})
    if st.session_state.get("studio_layout_mode") and not st.session_state.get("_studio_layout_mode"):
        st.session_state["_studio_layout_mode"] = st.session_state.get("studio_layout_mode")
    _normalize_loaded_video_state()
    st.session_state.law_selection_sig = tuple(st.session_state.get("selected_articles") or [])
    st.session_state["state_initialized"] = True

def _flush_page1_editors_to_session() -> None:
    """اسحب آخر قيم محرري الأطراف/المركبات إلى الجلسة قبل الحفظ اليدوي."""
    ed_p = st.session_state.get("p1_parties_editor")
    if isinstance(ed_p, pd.DataFrame):
        rows, _ = _normalize_party_qualification_rows(_frame_records(ed_p))
        st.session_state.parties = rows
        st.session_state.p1_parties_records = _clone_page1_value(rows)
    ed_v = st.session_state.get("p1_vehicles_editor")
    if isinstance(ed_v, pd.DataFrame):
        rows = _frame_records(ed_v)
        st.session_state.vehicles = rows
        st.session_state.p1_vehicles_records = _clone_page1_value(rows)

def save_current_work():
    data_to_save = {}
    # مزامنة مفاتيح العرض/الجوي قبل الحفظ اليدوي فقط
    if st.session_state.get("_studio_layout_mode"):
        st.session_state["studio_layout_mode"] = st.session_state.get("_studio_layout_mode")
    if isinstance(st.session_state.get("_saved_satellite_state"), dict):
        st.session_state["saved_satellite_state"] = dict(st.session_state.get("_saved_satellite_state") or {})
    if st.session_state.get("aerial_place_choice"):
        st.session_state["aerial_place"] = (
            "beside" if str(st.session_state.get("aerial_place_choice")).startswith("بجانب") else "below"
        )
    media_mode = st.session_state.get("report_media_mode") or "كلاهما"
    if media_mode == "كروكي فقط":
        st.session_state["include_sketch"] = True
        st.session_state["include_aerial"] = False
    elif media_mode == "جوي فقط":
        st.session_state["include_sketch"] = False
        st.session_state["include_aerial"] = True
    else:
        st.session_state["include_sketch"] = True
        st.session_state["include_aerial"] = True
        st.session_state["report_media_mode"] = "كلاهما"
    for key in DEFAULT_REPORT_STATE:
        if key in st.session_state and key != "confirm_clear":
            data_to_save[key] = st.session_state[key]
    for secret_key_name in (
        "api_key_persist",
        "api_key_persistent",
        "widget_api_key_input",
        "api_key_input",
        "api_key_widget",
        "analysis_api_key",
    ):
        data_to_save.pop(secret_key_name, None)
    # DataURL الضخم خارج JSON؛ الملفات الدائمة + الخزنة الكاملة تحتفظ به دون مسحه من الجلسة
    data_to_save.pop("aerial_sketch_data_url", None)
    data_to_save.pop("sketch_data_url", None)
    ensure_core_accident_fields_from_vault()
    page1_payload = export_page1_payload()
    data_to_save["page1_data"] = page1_payload
    # مفاتيح البيانات saved_acc_* + توافق خلفي مع p1_acc_*
    for widget_key, saved_key in WIDGET_TO_SAVED_ACC.items():
        val = _read_core_accident_value(widget_key)
        if _is_blank_p1_value(val):
            val = page1_payload.get(widget_key)
        if not _is_blank_p1_value(val):
            data_to_save[saved_key] = val
            data_to_save[widget_key] = val
    for key in ("hijri_date", "p1_acc_date", "p1_acc_time"):
        val = st.session_state.get(key)
        if _is_blank_p1_value(val):
            val = page1_payload.get(key)
        if not _is_blank_p1_value(val):
            data_to_save[key] = val
    aerial_img = str(st.session_state.get("aerial_sketch_data_url") or st.session_state.get("aerial_data_url") or "")
    sat_state = st.session_state.get("saved_satellite_state") or st.session_state.get("_saved_satellite_state") or {}
    if aerial_img.startswith("data:image/"):
        _remember_aerial_data_url(aerial_img, sat_state if isinstance(sat_state, dict) else {})
        data_to_save["has_aerial_image"] = True
        data_to_save["satellite_img_b64"] = True
    else:
        data_to_save["has_aerial_image"] = False
        data_to_save["satellite_img_b64"] = False
    sketch_img = str(st.session_state.get("sketch_data_url") or "")
    if sketch_img.startswith("data:image/"):
        _remember_sketch_data_url(sketch_img, "sketch_data_url")
        data_to_save["has_sketch_image"] = True
    else:
        data_to_save["has_sketch_image"] = False
    asphalt_state = st.session_state.get("_saved_asphalt_state") or st.session_state.get("saved_asphalt_state") or {}
    if isinstance(asphalt_state, dict) and asphalt_state:
        st.session_state["_saved_asphalt_state"] = dict(asphalt_state)
        st.session_state["saved_asphalt_state"] = dict(asphalt_state)
        data_to_save["saved_asphalt_state"] = {
            k: v for k, v in asphalt_state.items() if k != "image"
        }
    data_to_save["report_media_mode"] = st.session_state.get("report_media_mode", "كلاهما")
    data_to_save["include_aerial"] = bool(st.session_state.get("include_aerial", True))
    data_to_save["include_sketch"] = bool(st.session_state.get("include_sketch", True))
    data_to_save["aerial_place"] = st.session_state.get("aerial_place", "below")
    data_to_save["studio_layout_mode"] = st.session_state.get("studio_layout_mode") or st.session_state.get("_studio_layout_mode")
    data_to_save["saved_satellite_state"] = sat_state if isinstance(sat_state, dict) else {}
    # أطراف/مركبات معتمدة في الجلسة
    data_to_save["parties"] = list(st.session_state.get("parties") or [])
    data_to_save["vehicles"] = list(st.session_state.get("vehicles") or [])
    now_str = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d | %I:%M:%S %p")
    data_to_save["last_saved_time"] = now_str
    st.session_state["last_saved_time"] = now_str
    st.session_state["last_saved_at"] = now_str
    try:
        with open(DRAFT_FILE_PATH, "w", encoding="utf-8") as draft_file:
            json.dump(data_to_save, draft_file, ensure_ascii=False, indent=2, default=str)
        return True
    except OSError as error:
        st.error(f"حدث خطأ أثناء حفظ المسودة: {error}")
        return False

def perform_manual_save(show_toast: bool = True) -> bool:
    """مسار الحفظ اليدوي الموحّد: مزامنة المحررات → ظل التبويب3 كاملاً → مسودة + خزنة محلية."""
    try:
        _flush_page1_editors_to_session()
        ensure_core_accident_fields_from_vault()
        _mirror_page1_fields()
        # الحفظ اليدوي يسمح بالفراغ المقصود؛ الحقول الأساسية تُحقن من الخزنة قبلها إن فُرغت بالتنقل
        sync_page1_to_vault(
            extra_keys=list(PAGE1_EXTRA_SYNC_KEYS),
            write_disk=True,
            allow_blank_overwrite=True,
        )
        # زر «حفظ واعتماد البيانات» يحفظ الظل كاملاً لا وقت فقط
        sync_permanent_form_data(reason="manual_save")
        ok = save_current_work()
        if ok:
            try:
                _save_bayyinah_state()
            except Exception:
                pass
            try:
                import bayyinah_persistence as _bp
                _bp.save_full_workspace(reason="manual_save")
            except Exception:
                pass
            st.session_state["_last_persisted_stamp"] = str(st.session_state.get("last_saved_at") or "")
            st.session_state["_save_success_banner"] = st.session_state.get("last_saved_time")
            if show_toast:
                st.toast("تم حفظ جميع بيانات التقرير والصفحات بنجاح", icon="💾")
        return bool(ok)
    except Exception as error:
        st.error(f"تعذر إتمام الحفظ اليدوي: {error}")
        return False

def clear_all_work():
    capture_sidebar_before_reset()
    if os.path.exists(DRAFT_FILE_PATH):
        try:
            os.remove(DRAFT_FILE_PATH)
        except OSError:
            pass
    try:
        import bayyinah_persistence as _bp
        _bp.clear_full_workspace()
        st.session_state["_BAYYINAH_SKIP_AUTOSAVE_"] = True
    except Exception:
        pass
    for key, default_val in DEFAULT_REPORT_STATE.items():
        st.session_state[key] = default_val
    st.session_state.law_selection_sig = ()
    st.session_state.pop("tab3_content_fingerprint", None)
    clear_permanent_form_data()
    st.session_state["confirm_clear"] = False
    reset_page1_payload()
    st.session_state["_restore_perm_sidebar"] = True
    _clear_remembered_aerial()
    try:
        _clear_remembered_sketch()
    except Exception:
        pass
    st.session_state["_BAYYINAH_CLEAR_BROWSER_SKETCH_"] = True

def inject_bayyinah_blue_styles():
    st.markdown("""
    <style>
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div,
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div[role="button"],
    .stMultiSelect div[role="button"] {
        background: linear-gradient(135deg, rgba(8, 56, 114, 0.88), rgba(4, 38, 84, 0.92)) !important;
        color: #ffffff !important;
        border: 1.5px solid #00d2ff !important;
        border-radius: 10px !important;
        box-shadow: 0 0 10px rgba(0, 210, 255, 0.2) !important;
    }
    .save-bar-container,
    [class*="st-key-save-bar"] {
        background: linear-gradient(90deg, rgba(5, 45, 95, 0.95), rgba(10, 75, 145, 0.95));
        border: 1px solid #00e1ff;
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 18px;
        box-shadow: 0 4px 15px rgba(0, 225, 255, 0.25);
        direction: rtl;
    }
    .video-evidence-box,
    [class*="st-key-video-evidence"] {
        background: linear-gradient(135deg, rgba(6, 52, 108, 0.9), rgba(3, 33, 74, 0.95));
        border: 1.5px solid #00d4ff;
        border-radius: 14px;
        padding: 16px;
        margin: 15px 0;
        box-shadow: 0 0 18px rgba(0, 212, 255, 0.22);
        direction: rtl;
    }
    div[data-testid="stHorizontalBlock"] {
        align-items: flex-end !important;
    }
    div:has(> [data-testid="stElementContainer"] #hijri-lux-trigger) [data-testid="stPopover"] > button {
        min-height: 44px !important;
        height: 44px !important;
        max-height: 44px !important;
        margin-bottom: 0px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    div[data-testid="stElementContainer"]:has(#hijri-lux-trigger):not(:has(button)):not(:has(input)) {
        margin-bottom: -12px !important;
        padding: 0 !important;
    }
    div[data-testid="stTextInput"] div[data-baseweb="input"],
    div[data-testid="stNumberInput"] div[data-baseweb="input"],
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-testid="stPopover"] > button {
        height: 44px !important;
        min-height: 44px !important;
        max-height: 44px !important;
        border-radius: 10px !important;
        border: 1.4px solid rgba(56, 189, 248, 0.55) !important;
        background-color: rgba(10, 28, 52, 0.85) !important;
        box-sizing: border-box !important;
        display: flex !important;
        align-items: center !important;
        margin: 0 !important;
    }
    div[data-testid="stWidgetLabel"] {
        min-height: 22px !important;
        margin-bottom: 6px !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button {
        font-weight: 700 !important;
        letter-spacing: 0.2px !important;
        color: #041426 !important;
        -webkit-text-fill-color: #041426 !important;
        text-shadow: none !important;
    }
    button[kind="primary"],
    button[kind="primary"] p,
    button[kind="primary"] span {
        color: #041426 !important;
        -webkit-text-fill-color: #041426 !important;
        font-weight: 700 !important;
        text-shadow: none !important;
    }
    
</style>
    """, unsafe_allow_html=True)

def render_direct_print_button(
    full_report_html: str,
    label: str = "🖨️ طباعة فورية A4",
    btn_id: str = "top",
):
    """زر طباعة فوري محصن بتشفير Base64 يمنع تسرب أي وسوم أو أكواد إلى الشاشة ويعمل في أي نسبة إنجاز (0% - 100%)."""
    try:
        sync_permanent_form_data(reason="before_print")
    except Exception:
        pass
    raw_html = re.sub(r"@page\s*\{[^}]*\}", "", str(full_report_html or ""))
    auto_print_addon = """
    <style>
        @page {
            size: A4 portrait;
            margin: 0mm;
        }
        @media print {
            button, .no-print, .print-btn, .toolbar, .bayyinah-print-bar { display: none !important; }
            html, body {
                width: 210mm !important;
                height: auto !important;
                max-height: none !important;
                margin: 0 !important;
                padding: 0 !important;
                background: #ffffff !important;
                display: block !important;
                overflow: visible !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
            body > div:not(.bayyinah-print-bar),
            .report-viewport, .report-sheet,
            .report-wrapper, .print-container, .pages-wrapper, .preview-container {
                margin: 0 !important;
                padding: 0 !important;
                gap: 0 !important;
                border: none !important;
                box-shadow: none !important;
                background: transparent !important;
                display: block !important;
                height: auto !important;
                max-height: none !important;
                overflow: visible !important;
            }
            .page, .a4-page, .report-page {
                width: 210mm !important;
                height: 294mm !important;
                min-height: 294mm !important;
                max-height: 294mm !important;
                margin: 0 auto !important;
                padding: 6mm 11mm 5mm 11mm !important;
                box-sizing: border-box !important;
                overflow: hidden !important;
                border: none !important;
                box-shadow: none !important;
                position: relative !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: space-between !important;
                page-break-after: always !important;
                break-after: page !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
                flex-shrink: 0 !important;
            }
            .official-page-footer, .official-footer, .page-footer, .footer {
                position: relative !important;
                bottom: auto !important;
                left: auto !important;
                right: auto !important;
                width: 100% !important;
                margin-top: auto !important;
                padding-top: 5mm !important;
                flex-shrink: 0 !important;
            }
            .page:last-of-type, .a4-page:last-of-type, .report-page:last-of-type {
                page-break-after: auto !important;
                break-after: auto !important;
            }
            .page table:not(.sign-table), .report-page table:not(.sign-table), .a4-page table:not(.sign-table),
            .box-content {
                margin-bottom: 6px !important;
            }
            table.sign-table {
                display: table !important;
                table-layout: fixed !important;
                width: 100% !important;
                max-width: 100% !important;
                min-width: 100% !important;
                border-collapse: collapse !important;
                border-spacing: 0 !important;
                border: 1px solid #000 !important;
                box-shadow: none !important;
                outline: none !important;
                margin: 8px 0 0 0 !important;
                padding: 0 !important;
                direction: rtl !important;
            }
            table.sign-table col { width: 33.33% !important; }
            table.sign-table thead, table.sign-table tbody { display: table-row-group !important; }
            table.sign-table tr { display: table-row !important; }
            table.sign-table th, table.sign-table td {
                display: table-cell !important;
                width: 33.33% !important;
                padding: 8px 6px !important;
                border: 1px solid #000 !important;
                vertical-align: top !important;
                text-align: center !important;
                float: none !important;
            }
            table.sign-table th[colspan] { width: auto !important; }
        }
        .bayyinah-print-bar {
            position: sticky; top: 0; z-index: 9999;
            background: #071528; color: #f8fafc; padding: 10px 20px;
            display: flex; justify-content: space-between; align-items: center;
            font-family: Tahoma, Arial, sans-serif; direction: rtl;
            border-bottom: 2px solid #38bdf8;
        }
        .bayyinah-print-bar button {
            background: #38bdf8; color: #031527; border: none;
            border-radius: 8px; padding: 7px 18px; font-weight: 900;
            font-size: 14px; cursor: pointer; margin-left: 8px;
        }
    
</style>
    <script>
        window.addEventListener("load", function() {
            var imgs = Array.prototype.slice.call(document.images || []).filter(function(im) {
                return im.getAttribute("src") && im.getAttribute("src").trim() !== "";
            });
            var waitAll = Promise.all(imgs.map(function(im) {
                if (im.complete) return Promise.resolve();
                return new Promise(function(res) { im.onload = res; im.onerror = res; });
            }));
            Promise.race([waitAll, new Promise(function(r) { setTimeout(r, 650); })]).then(function() {
                setTimeout(function() {
                    window.focus();
                    window.print();
                }, 180);
            });
        });
    </script>
    """
    top_bar_ui = """
    <div class="bayyinah-print-bar no-print">
        <span>🛡️ معاينة الطباعة الرسمية لمنظومة بَيِّنَة (مقاس A4 معتمد)</span>
        <div>
            <button onclick="window.print()">🖨️ طباعة / حفظ كـ PDF</button>
            <button onclick="window.close()" style="background:#ef4444;color:#fff;">✖ إغلاق</button>
        </div>
    </div>
    """
    if "<body" in raw_html:
        body_open_end = raw_html.find(">", raw_html.find("<body"))
        printable_html = raw_html[: body_open_end + 1] + top_bar_ui + raw_html[body_open_end + 1 :]
    else:
        printable_html = top_bar_ui + raw_html
    if "</body>" in printable_html:
        printable_html = printable_html.replace("</body>", auto_print_addon + "</body>", 1)
    else:
        printable_html = printable_html + auto_print_addon
    b64_payload = base64.b64encode(printable_html.encode("utf-8")).decode("ascii")
    components.html(
        f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
        <meta charset="utf-8"/>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, sans-serif; }}
            html, body {{ background: transparent !important; overflow: hidden !important; width: 100%; height: 44px; }}
            .instant-print-btn {{
                width: 100%;
                height: 42px;
                background: linear-gradient(135deg, #38bdf8 0%, #00e5ff 100%);
                color: #031527 !important;
                border: 1.5px solid #bae6fd;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 900;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                white-space: nowrap;
                box-shadow: 0 4px 14px rgba(0, 229, 255, 0.28);
                transition: 0.15s ease;
            }}
            .instant-print-btn:hover {{ filter: brightness(1.07); }}
        
</style>
        </head>
        <body>
            <button type="button" class="instant-print-btn" id="pBtn_{btn_id}" onclick="openAndPrintA4()">
                {label}
            </button>
            <script>
            const B64_REPORT = "{b64_payload}";
            function openAndPrintA4() {{
                const binStr = atob(B64_REPORT);
                const bytes = new Uint8Array(binStr.length);
                for (let i = 0; i < binStr.length; i++) {{
                    bytes[i] = binStr.charCodeAt(i);
                }}
                const blob = new Blob([bytes], {{ type: "text/html;charset=utf-8" }});
                const blobUrl = URL.createObjectURL(blob);
                const printWin = window.open(blobUrl, "_blank");
                if (!printWin) {{
                    let f = document.getElementById("fallback_print_iframe");
                    if (f) f.remove();
                    f = document.createElement("iframe");
                    f.id = "fallback_print_iframe";
                    f.style.cssText = "position:fixed;left:-9999px;top:0;width:210mm;height:297mm;border:0;";
                    f.src = blobUrl;
                    document.body.appendChild(f);
                }}
            }}
            </script>
        </body>
        </html>
        """,
        height=44,
    )


def render_compact_command_header(on_save_callback=None, on_reset_callback=None, report_html: str = ""):
    """شريط علوي زجاجي رفيع يوفر ثلث مساحة الشاشة ويضع الحفظ والطباعة الفورية أمام العين."""
    st.markdown(
        """
        <style>
        .bayyinah-cmd-bar {
            background: linear-gradient(135deg, rgba(6, 18, 36, 0.96) 0%, rgba(12, 34, 62, 0.96) 100%);
            border: 1px solid rgba(56, 189, 248, 0.4);
            border-radius: 13px;
            padding: 8px 16px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            direction: rtl;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
        }
        .bayyinah-cmd-title {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .bayyinah-status-pill {
            font-size: 11.5px;
            font-weight: 700;
            color: #34d399;
            background: rgba(16, 185, 129, 0.14);
            border: 1px solid rgba(52, 211, 153, 0.35);
            padding: 2px 9px;
            border-radius: 999px;
        }
        
</style>
        """,
        unsafe_allow_html=True,
    )
    col_brand, col_save, col_print, col_new = st.columns([3.4, 1, 1.15, 1])
    with col_brand:
        acc_no = str(_read_core_accident_value("p1_acc_number") or "").strip()
        acc_badge = f"رقم الحادث: {acc_no}" if acc_no else "معاملة قيد الإعداد"
        saved_at = html.escape(str(st.session_state.get("last_saved_time") or "لم يتم الحفظ بعد"))
        st.markdown(
            f"""
            <div class="bayyinah-cmd-bar">
                <div class="bayyinah-cmd-title">
                    <span style="font-size:20px; font-weight:900; color:#f8fafc; letter-spacing:0.4px;">🛡️ منظومة بَيِّنَة</span>
                    <span style="font-size:12.5px; color:#7dd3fc; font-weight:600;">المنصة الذكية لتقارير الحوادث المرورية</span>
                </div>
                <span class="bayyinah-status-pill">● {html.escape(acc_badge)} · آخر حفظ: {saved_at}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_save:
        if st.button("💾 حفظ واعتماد البيانات", key="_top_cmd_save", use_container_width=True):
            if callable(on_save_callback):
                on_save_callback()
            else:
                perform_manual_save(show_toast=True)
    with col_print:
        render_direct_print_button(report_html or "", label="🖨️ طباعة فورية A4", btn_id="top")
    with col_new:
        if st.button("🆕 حادث جديد", key="_top_cmd_reset", use_container_width=True):
            _clear_bayyinah_saved_state()
            if callable(on_reset_callback):
                on_reset_callback()
                st.rerun()

def inject_tab_completion_badges(tab_done_flags: list):
    """إضافة علامة ✓ خضراء للتبويبات المكتملة مع الحفاظ الكامل على استقرار التبويب المفتوح."""
    flags_json = json.dumps([bool(item) for item in tab_done_flags])
    components.html(
        f"""
        <script>
        (function() {{
            const flags = {flags_json};
            const parentDoc = window.parent && window.parent.document;
            if (!parentDoc) return;
            if (window.frameElement) {{
                const wrap = window.frameElement.closest('[data-testid="stElementContainer"], .element-container');
                if (wrap) wrap.style.cssText = "height:0!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important;";
            }}
            const tabs = parentDoc.querySelectorAll('[data-baseweb="tab"]');
            tabs.forEach((tabEl, idx) => {{
                const oldBadge = tabEl.querySelector('.bayyinah-tab-check');
                if (oldBadge) oldBadge.remove();
                if (flags[idx]) {{
                    const badge = parentDoc.createElement('span');
                    badge.className = 'bayyinah-tab-check';
                    badge.textContent = ' ✓';
                    badge.style.cssText = 'color:#34d399;font-weight:900;margin-right:5px;font-size:14px;';
                    tabEl.appendChild(badge);
                }}
            }});
        }})();
        </script>
        """,
        height=0,
        width=0,
    )

def _report_tab_done_flags():
    def _filled(key):
        return bool(str(st.session_state.get(key) or "").strip())
    party_rows = st.session_state.get("parties") or []
    has_party_name = any(
        isinstance(row, dict) and str(row.get("الاسم") or "").strip()
        for row in party_rows
    )
    done_tab1 = (
        bool(str(_read_core_accident_value("p1_acc_number") or "").strip())
        or _filled("hijri_date")
        or bool(str(_read_core_accident_value("p1_acc_location") or "").strip())
        or has_party_name
    )
    done_analysis = _filled("accident_results") or _filled("technical_description") or bool(st.session_state.get("selected_articles"))
    done_actions = _filled("actions_taken_editor")
    done_sketch = str(st.session_state.get("sketch_data_url") or "").startswith("data:image/")
    done_print = bool(st.session_state.get("gallery_photos"))
    done_analysis_actions = done_analysis or done_actions
    return [done_tab1, done_sketch, done_analysis_actions, done_print]

def render_compact_sketch_legends(key_prefix: str = "sketch_legend_"):
    """عرض أول 4 مدلولات في عمودين متجاورين وطي المدلولات 5-10 لترتيب صفحة التخطيط."""
    st.markdown(
        "<div style='font-size:14.5px; font-weight:800; color:#e0f2fe; margin:8px 0 6px 0; text-align:right;'>📌 مدلولات ومفاتيح الرسم الكروكي</div>",
        unsafe_allow_html=True,
    )
    defaults = {
        1: "المركبة الأولى (الطرف الأول)",
        2: "المركبة الثانية (الطرف الثاني)",
        3: "نقطة الاصطدام والالتقاء (X)",
        4: "اتجاه سير المركبات قبل الحادث",
    }
    r1_c1, r1_c2 = st.columns(2)
    for idx, col in [(1, r1_c1), (2, r1_c2)]:
        key_name = f"{key_prefix}{idx}"
        st.session_state.setdefault(key_name, defaults.get(idx, ""))
        with col:
            st.text_input(f"مدلول رقم ({idx})", key=key_name)
    r2_c1, r2_c2 = st.columns(2)
    for idx, col in [(3, r2_c1), (4, r2_c2)]:
        key_name = f"{key_prefix}{idx}"
        st.session_state.setdefault(key_name, defaults.get(idx, ""))
        with col:
            st.text_input(f"مدلول رقم ({idx})", key=key_name)
    has_extra = any(str(st.session_state.get(f"{key_prefix}{i}", "")).strip() for i in range(5, 11))
    with st.expander("➕ إضافة مدلولات تفصيلية إضافية (من 5 إلى 10)", expanded=has_extra):
        for start_i in range(5, 11, 2):
            ec1, ec2 = st.columns(2)
            with ec1:
                st.text_input(f"مدلول رقم ({start_i})", key=f"{key_prefix}{start_i}")
            with ec2:
                st.text_input(f"مدلول رقم ({start_i + 1})", key=f"{key_prefix}{start_i + 1}")

OFFICIAL_A4_HIGH_CONTRAST_CSS = """
/* OFFICIAL_A4_HIGH_CONTRAST_CSS: سواد رسمي صريح وحدود حادة للمعاينة والطباعة */
.page, .report-page {
    color: #000000 !important;
    background: #ffffff !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
}
.page table:not(.sign-table), .report-page table:not(.sign-table) {
    border-collapse: collapse !important;
    border: 1.5px solid #000000 !important;
    width: 100% !important;
}
.page table:not(.sign-table) th, .report-page table:not(.sign-table) th {
    background-color: #dcefe4 !important;
    color: #000000 !important;
    font-weight: 800 !important;
    border: 1.1px solid #000000 !important;
    padding: 5px 8px !important;
}
.page table:not(.sign-table) td, .report-page table:not(.sign-table) td {
    color: #000000 !important;
    font-weight: 600 !important;
    border: 1px solid #000000 !important;
    padding: 5px 8px !important;
}
.page .section-title, .report-page .section-title, .page .box-header {
    background-color: #dcefe4 !important;
    color: #000000 !important;
    font-weight: 800 !important;
    border: 1.3px solid #000000 !important;
}
.page p, .page span, .page div:not(.official-footer-col-center) {
    color: #000000;
}
.official-footer-line-primary,
.official-footer-line-secondary {
    border-top-color: #1b4332 !important;
}
.footer-col-center {
    color: #1b4332 !important;
}
"""

def _quick_save_from_header():
    perform_manual_save(show_toast=True)

VIDEO_MARKER_START = "[بداية القرائن المرئية]"
VIDEO_MARKER_END = "[نهاية القرائن المرئية]"
VIDEO_SOURCE_OPTIONS = [
    "كاميرا مراقبة أمنية (CCTV)",
    "كاميرا مركبة (داش كام - Dashcam)",
    "كاميرا منشأة تجارية / خاصة محيطة",
    "كاميرات الرصد الآلي / المدن الذكية",
    "تصوير هاتف محمول موثق",
]
VIDEO_CLARITY_OPTIONS = [
    "واضح وموثق بختم زمني (تاريخ ووقت)",
    "واضح الدقة (بدون ختم زمني ظاهر)",
    "متوسط الوضوح ولكن يُظهر آلية الاصطدام",
    "زاوية بعيدة تُظهر اتجاهات المركبات فقط",
]
VIDEO_FINDING_OPTIONS = [
    "رصد لحظة الاصطدام وزاوية الدخول بدقة",
    "ثبوت انحراف المركبة المتسببة بشكل مفاجئ على مسار الطرف الآخر",
    "تجاوز السرعة النظامية وعدم ظهور إضاءة المكابح قبل الاصطدام",
    "ثبوت قطع الإشارة الضوئية الحمراء بالصوت والصورة",
    "ثبوت السير عكس اتجاه الحركة المرورية",
    "رصد قرائن تدل على تعمد الصدم أو المطاردة والمضايقة (شبهة جنائية)",
    "رصد هروب المركبة المتسببة من مسرح الحادث عقب الاصطدام مباشرة",
    "ثبوت هوية السائق الفعلي وقت الاصطدام قبل محاولة الاستبدال",
    "تأكيد التوقف النظامي للمركبة المتضررة قبل تعرضها للصدم",
]
CRIMINAL_SUSPICION_MARKERS = ("تعمد", "مطاردة", "مضايقة")
CRIMINAL_SUSPICION_SENTENCE = (
    "وحيث إن المعطيات والقرائن المرئية رصدت شبهة تعمد أو مطاردة، فإن الواقعة تنتفي عنها الصفة المرورية البحتة، "
    "وتستوجب إحالة الأوراق والطرفين إلى مركز الشرطة المختص لاستكمال إجراءات الاستدلال الجنائي وتطبيق المقتضى النظامي."
)
VIDEO_CLIP_MIN = 1
VIDEO_CLIP_MAX = 10
VIDEO_HAS_OPTIONS = ["لا فيديو", "يوجد توثيق"]
VISION_MODEL_NAMES = (
    "meta-llama/llama-4-scout",
    "llama-4-maverick",
)
TEXT_MODEL_NAMES = (
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout",
    "llama-3.1-8b-instant",
    "qwen-qwq-32b",
)
HOW_SECTION = "===كيفية وقوع الحادث==="
RESULTS_SECTION = "===نتائج الحادث==="

def _blank_video_clip():
    return {
        "source": VIDEO_SOURCE_OPTIONS[0],
        "clarity": VIDEO_CLARITY_OPTIONS[0],
        "timestamp": "",
        "findings": [],
        "notes": "",
    }

def _normalize_video_clip(raw):
    clip = _blank_video_clip()
    if isinstance(raw, dict):
        if raw.get("source") in VIDEO_SOURCE_OPTIONS:
            clip["source"] = raw["source"]
        if raw.get("clarity") in VIDEO_CLARITY_OPTIONS:
            clip["clarity"] = raw["clarity"]
        clip["timestamp"] = str(raw.get("timestamp") or "").strip()
        findings = raw.get("findings") if isinstance(raw.get("findings"), list) else []
        clip["findings"] = [item for item in findings if item in VIDEO_FINDING_OPTIONS]
        clip["notes"] = str(raw.get("notes") or "").strip()
    return clip

def _clamp_clip_count(value):
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = VIDEO_CLIP_MIN
    return max(VIDEO_CLIP_MIN, min(VIDEO_CLIP_MAX, count))

def _normalize_loaded_video_state():
    raw_has = str(st.session_state.get("has_video") or "")
    if raw_has in ("لا يوجد مقطع فيديو", "لا فيديو"):
        st.session_state.has_video = "لا فيديو"
    elif "توثيق" in raw_has or raw_has.startswith("نعم"):
        st.session_state.has_video = "يوجد توثيق"
    else:
        st.session_state.has_video = "لا فيديو"
    clips = st.session_state.get("video_clips")
    if not isinstance(clips, list) or not clips:
        legacy = _blank_video_clip()
        if st.session_state.get("video_source") in VIDEO_SOURCE_OPTIONS:
            legacy["source"] = st.session_state.video_source
        if st.session_state.get("video_clarity") in VIDEO_CLARITY_OPTIONS:
            legacy["clarity"] = st.session_state.video_clarity
        legacy["timestamp"] = str(st.session_state.get("video_timestamp") or "").strip()
        old_findings = st.session_state.get("video_findings")
        if isinstance(old_findings, list):
            legacy["findings"] = [item for item in old_findings if item in VIDEO_FINDING_OPTIONS]
        legacy["notes"] = str(st.session_state.get("video_custom_notes") or "").strip()
        clips = [legacy]
    clips = [_normalize_video_clip(item) for item in clips][:VIDEO_CLIP_MAX]
    if not clips:
        clips = [_blank_video_clip()]
    count = _clamp_clip_count(st.session_state.get("video_clip_count", len(clips)))
    while len(clips) < count:
        clips.append(_blank_video_clip())
    st.session_state.video_clips = clips[:count]
    st.session_state.video_clip_count = count

def _sync_video_clips(count):
    count = _clamp_clip_count(count)
    clips = [_normalize_video_clip(item) for item in (st.session_state.get("video_clips") or [])]
    while len(clips) < count:
        clips.append(_blank_video_clip())
    st.session_state.video_clips = clips[:count]
    return st.session_state.video_clips

def _store_clip_fields():
    count = _clamp_clip_count(st.session_state.get("video_clip_count"))
    clips = []
    for index in range(count):
        findings = st.session_state.get(f"clip_{index}_findings", [])
        if not isinstance(findings, list):
            findings = []
        clips.append(_normalize_video_clip({
            "source": st.session_state.get(f"clip_{index}_source"),
            "clarity": st.session_state.get(f"clip_{index}_clarity"),
            "timestamp": st.session_state.get(f"clip_{index}_timestamp", ""),
            "findings": findings,
            "notes": st.session_state.get(f"clip_{index}_notes", ""),
        }))
    st.session_state.video_clips = clips

def _active_video_clips():
    count = _clamp_clip_count(st.session_state.get("video_clip_count"))
    stored = _sync_video_clips(count)
    clips = []
    for index, clip in enumerate(stored):
        findings = st.session_state.get(f"clip_{index}_findings", clip["findings"])
        if not isinstance(findings, list):
            findings = []
        clips.append(_normalize_video_clip({
            "source": st.session_state.get(f"clip_{index}_source", clip["source"]),
            "clarity": st.session_state.get(f"clip_{index}_clarity", clip["clarity"]),
            "timestamp": st.session_state.get(f"clip_{index}_timestamp", clip["timestamp"]),
            "findings": findings,
            "notes": st.session_state.get(f"clip_{index}_notes", clip["notes"]),
        }))
    return clips

def _extract_marked_block(text):
    text = str(text or "")
    if VIDEO_MARKER_START in text and VIDEO_MARKER_END in text:
        return text.split(VIDEO_MARKER_START, 1)[1].split(VIDEO_MARKER_END, 1)[0].strip()
    return ""

def _strip_marked_block(text):
    text = str(text or "")
    if VIDEO_MARKER_START in text and VIDEO_MARKER_END in text:
        pre, rest = text.split(VIDEO_MARKER_START, 1)
        _, post = rest.split(VIDEO_MARKER_END, 1)
        return f"{pre.rstrip()}\n\n{post.lstrip()}".strip()
    return text.strip()

def _upsert_marked_block(text, block):
    base = _strip_marked_block(text)
    block = str(block or "").strip()
    if not block:
        return base
    marked = f"{VIDEO_MARKER_START}\n{block}\n{VIDEO_MARKER_END}"
    return f"{base}\n\n{marked}".strip() if base else marked

def _clip_shows_criminal_suspicion(clip):
    observations = " ".join(clip.get("findings") or [])
    observations = f"{observations} {clip.get('notes') or ''}"
    return any(marker in observations for marker in CRIMINAL_SUSPICION_MARKERS)

def _manual_evidence_blocks():
    clips = _active_video_clips()
    how_lines = []
    result_lines = []
    legal_lines = []
    for index, clip in enumerate(clips, start=1):
        findings = "، ".join(clip["findings"]) if clip["findings"] else "رصد آلية وحركة المركبات لحظة وقوع الحادث"
        time_clause = f" والموثق زمنياً عند ({clip['timestamp']})" if clip["timestamp"] else ""
        notes = f"؛ كما أظهر التسجيل أن ({clip['notes']})" if clip["notes"] else ""
        how_lines.append(
            f"المقطع ({index}): تعززت المعاينة الفنية بالاطلاع على التسجيل المرئي المستخرج من ({clip['source']}) "
            f"وهو ({clip['clarity']}){time_clause}، حيث أظهر المقطع: {findings}{notes}."
        )
        result_lines.append(f"{index}- ثبت من المقطع المرئي ({clip['source']}): {findings}.")
        legal_line = (
            f"المقطع ({index}): حُجية القرينة المرئية من ({clip['source']}) ({clip['clarity']}){time_clause}، "
            f"والمشاهدات المدونة: {findings}{notes}."
        )
        if _clip_shows_criminal_suspicion(clip):
            legal_line = f"{legal_line} {CRIMINAL_SUSPICION_SENTENCE}"
        legal_lines.append(legal_line)
    return "\n".join(how_lines), "\n".join(result_lines), "\n".join(legal_lines)

def _apply_marked_analysis(parsed):
    how_text = str((parsed or {}).get("technical_description") or "").strip()
    results_text = str((parsed or {}).get("accident_results") or "").strip()
    legal_text = str((parsed or {}).get("legal_opinion") or "").strip()
    if not how_text and not results_text and not legal_text:
        return False
    _ensure_tab3_locked_text_defaults()
    if how_text and not _tab3_text_is_manual("technical_description"):
        merged = _upsert_marked_block(_read_tab3_saved_text("technical_description"), how_text)
        _write_tab3_saved_text("technical_description", merged, mark_manual=False)
        _bump_tab3_text_rev("technical_description")
    if results_text and not _tab3_text_is_manual("accident_results"):
        merged = _upsert_marked_block(_read_tab3_saved_text("accident_results"), results_text)
        _write_tab3_saved_text("accident_results", merged, mark_manual=False)
        _bump_tab3_text_rev("accident_results")
    if legal_text and not _tab3_text_is_manual("p1_reasons"):
        merged = _upsert_marked_block(_read_tab3_saved_text("p1_reasons"), legal_text)
        _write_tab3_saved_text("p1_reasons", merged, mark_manual=False)
        _bump_tab3_text_rev("p1_reasons")
    st.session_state.video_injected_text = how_text or results_text or legal_text
    return True

def insert_manual_video_evidence():
    how_block, results_block, legal_block = _manual_evidence_blocks()
    _apply_marked_analysis({
        "technical_description": how_block,
        "accident_results": results_block,
        "legal_opinion": legal_block,
    })

def remove_manual_video_evidence():
    _ensure_tab3_locked_text_defaults()
    _write_tab3_saved_text(
        "technical_description",
        _strip_marked_block(_read_tab3_saved_text("technical_description")),
        mark_manual=None,
    )
    _write_tab3_saved_text(
        "accident_results",
        _strip_marked_block(_read_tab3_saved_text("accident_results")),
        mark_manual=None,
    )
    _write_tab3_saved_text(
        "p1_reasons",
        _strip_marked_block(_read_tab3_saved_text("p1_reasons")),
        mark_manual=None,
    )
    _bump_tab3_text_rev("technical_description")
    _bump_tab3_text_rev("accident_results")
    _bump_tab3_text_rev("p1_reasons")
    st.session_state.video_injected_text = ""

def _local_secrets_file():
    return Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"

def _groq_key_from_local_file():
    path = _local_secrets_file()
    if not path.is_file():
        return ""
    try:
        import tomllib
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except Exception:
        return ""
    if not isinstance(data, dict) or "GROQ_API_KEY" not in data:
        return ""
    return str(data.get("GROQ_API_KEY") or "").strip()

def _groq_secret_key():
    try:
        if "GROQ_API_KEY" in st.secrets:
            return str(st.secrets["GROQ_API_KEY"] or "").strip()
    except Exception:
        pass
    return _groq_key_from_local_file()

def get_active_analysis_key():
    typed = str(st.session_state.get("api_key_persist") or "").strip()
    if typed:
        return typed
    return _groq_secret_key()

def _analysis_base_url(api_key):
    if api_key.startswith("xai-"):
        return "https://api.x.ai/v1"
    if api_key.startswith("sk-") and not api_key.startswith("gsk_"):
        return "https://api.openai.com/v1"
    return "https://api.groq.com/openai/v1"

def _sections_from_model_text(text):
    raw = str(text or "")
    if HOW_SECTION not in raw or RESULTS_SECTION not in raw:
        return "", ""
    how_text = raw.split(HOW_SECTION, 1)[1].split(RESULTS_SECTION, 1)[0].strip()
    results_text = raw.split(RESULTS_SECTION, 1)[1].strip()
    return how_text, results_text

def _optional_cv2():
    try:
        import cv2
    except Exception:
        return None
    return cv2

def _redact_secret(message, *secrets):
    text = str(message or "")
    for secret in secrets:
        if secret:
            text = text.replace(secret, "•••")
    return text

def _upload_token(uploaded):
    if uploaded is None:
        return ""
    file_id = str(getattr(uploaded, "file_id", "") or "")
    name = str(getattr(uploaded, "name", "") or "")
    size = getattr(uploaded, "size", None)
    if size is None:
        try:
            size = len(uploaded.getvalue())
        except Exception:
            size = 0
    return f"{file_id}:{name}:{size}"

def _bulk_uploads():
    bulk = st.session_state.get("video_bulk_files") or []
    if bulk is None:
        return []
    if isinstance(bulk, list):
        return [item for item in bulk if item is not None]
    return [bulk]

def _effective_clip_file(index, bulk):
    per_clip = st.session_state.get(f"clip_file_{index}")
    if per_clip is not None:
        return per_clip
    if index < len(bulk):
        return bulk[index]
    return None

def _clip_prompt_line(index, clip):
    findings = "، ".join(clip["findings"]) if clip["findings"] else "لا توجد مشاهدات مدونة"
    return (
        f"المقطع {index + 1}: المصدر {clip['source']}، الوضوح {clip['clarity']}، "
        f"وقت اللقطة {clip['timestamp'] or 'غير محدد'}، المشاهدات المدونة: {findings}، "
        f"ملاحظات الباحث: {clip['notes'] or 'لا يوجد'}."
    )

def _analysis_prompt(clips, watched):
    if watched:
        intro = [
            "أنت خبير معاينة حوادث مرورية. اعتمد على اللقطات المرفقة والبيانات المكتوبة فقط.",
            "لا تخترع وقائع غير ظاهرة في اللقطات أو غير مكتوبة أدناه.",
        ]
    else:
        intro = [
            "لم تُرسل إليك لقطات، ولا تملك مشاهدة للمقطع.",
            "لا تخترع حركة مركبات أو ألواناً أو وقائع مرئية لم تُذكر كتابةً أدناه.",
            "إن نقصت البيانات المكتوبة فقل صراحة إن التفاصيل المرئية غير متاحة لأن التحليل نصي بلا مشاهدة.",
        ]
    return "\n".join(intro + [
        "أجب بهذا الشكل الحرفي دون مقدمات:",
        HOW_SECTION,
        "فقرة كيفية وقوع الحادث",
        RESULTS_SECTION,
        "نتائج الحادث نقاطاً مرقمة",
        "لا تذكر مفاتيح API.",
        "البيانات المكتوبة:",
        *[_clip_prompt_line(index, clip) for index, clip in enumerate(clips)],
    ])

def _extract_clip_frames(uploads):
    cv2 = _optional_cv2()
    if cv2 is None:
        return []
    frames = []
    for _index, _clip, uploaded in uploads:
        suffix = Path(getattr(uploaded, "name", "") or "").suffix.lower()
        if suffix not in {".mp4", ".mov", ".avi", ".mkv"}:
            suffix = ".mp4"
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                handle.write(uploaded.getvalue())
                temp_path = handle.name
            capture = cv2.VideoCapture(temp_path)
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if total > 1:
                positions = [max(0, int(total * 0.35)), max(0, int(total * 0.7))]
            else:
                positions = [0]
            taken = 0
            for position in positions:
                if taken >= 2:
                    break
                capture.set(cv2.CAP_PROP_POS_FRAMES, position)
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                height, width = frame.shape[:2]
                if width != 720 and width > 0:
                    scaled_height = max(1, int(height * (720 / width)))
                    frame = cv2.resize(frame, (720, scaled_height))
                encoded, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 75],
                )
                if encoded:
                    frames.append(base64.b64encode(buffer.tobytes()).decode("ascii"))
                    taken += 1
            capture.release()
        except Exception:
            continue
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
    return frames

def _chat_completion(base_url, api_key, model_name, content):
    import requests
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"]

def _available_model_names(base_url, api_key):
    import requests
    try:
        response = requests.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []
    names = []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    for item in data:
        model_id = str(item.get("id") or "").strip() if isinstance(item, dict) else ""
        lowered = model_id.lower()
        if not model_id or any(word in lowered for word in ("whisper", "guard", "tts")):
            continue
        names.append(model_id)
    return names

def _message_content(prompt, frames):
    if not frames:
        return prompt
    content = [{"type": "text", "text": prompt}]
    for encoded in frames:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
        })
    return content

def _apply_section_analysis(how_text, results_text):
    if not how_text and not results_text:
        return False
    _ensure_tab3_locked_text_defaults()
    if how_text and not _tab3_text_is_manual("technical_description"):
        merged = _upsert_marked_block(_read_tab3_saved_text("technical_description"), how_text)
        _write_tab3_saved_text("technical_description", merged, mark_manual=False)
        _bump_tab3_text_rev("technical_description")
    if results_text and not _tab3_text_is_manual("accident_results"):
        merged = _upsert_marked_block(_read_tab3_saved_text("accident_results"), results_text)
        _write_tab3_saved_text("accident_results", merged, mark_manual=False)
        _bump_tab3_text_rev("accident_results")
    st.session_state.video_injected_text = how_text or results_text
    return True

def analyze_video_evidence():
    api_key = get_active_analysis_key()
    clips = _active_video_clips()
    bulk = _bulk_uploads()
    uploads = []
    for index, clip in enumerate(clips):
        media = _effective_clip_file(index, bulk)
        if media is not None:
            uploads.append((index, clip, media))
    has_notes = any(clip["notes"] or clip["findings"] for clip in clips)
    if not uploads and not has_notes:
        st.warning("أرفق مقطعاً أو دوّن مشاهدات الباحث قبل التحليل.")
        return False
    if not api_key:
        st.error("لا يوجد مفتاح تحليل في حقل القائمة أو في الأسرار.")
        return False
    frames = _extract_clip_frames(uploads) if uploads else []
    base_url = _analysis_base_url(api_key)
    text_models = list(TEXT_MODEL_NAMES)
    for model_name in _available_model_names(base_url, api_key):
        if model_name not in text_models:
            text_models.append(model_name)
    attempts = []
    if frames:
        attempts.extend((model_name, True) for model_name in VISION_MODEL_NAMES)
    attempts.extend((model_name, False) for model_name in text_models)
    last_error = None
    for model_name, use_frames in attempts:
        try:
            content = _message_content(
                _analysis_prompt(clips, watched=bool(use_frames and frames)),
                frames if use_frames else [],
            )
            raw = _chat_completion(base_url, api_key, model_name, content)
            how_text, results_text = _sections_from_model_text(raw)
            if not _apply_section_analysis(how_text, results_text):
                last_error = RuntimeError(f"{model_name} بلا قسمين قابلين للإدراج")
                continue
            st.session_state.video_analysis_backend = "vision" if use_frames else "text"
            st.toast("تم إدراج ناتج التحليل في حقلي الكيفية والنتائج", icon="🎥")
            return True
        except Exception as error:
            last_error = error
    st.error(f"تعذر التحليل: {_redact_secret(last_error, api_key)}")
    return False

def render_video_evidence_engine():
    with st.container(key="video-evidence"):
        st.subheader("🎥 محرك القرائن الرقمية والتوثيق المرئي")
        if st.session_state.get("has_video") not in VIDEO_HAS_OPTIONS:
            st.session_state.has_video = "لا فيديو"
        has_video = st.radio(
            "هل يتوفر توثيق مرئي للحادث؟",
            options=VIDEO_HAS_OPTIONS,
            key="has_video",
            horizontal=True
        )
        if has_video == "لا فيديو":
            st.info("ℹ️ لا يوجد تسجيل مرئي مرفق؛ يعتمد التقرير الفني والمسؤولية النظامية على الآثار المادية، والمعاينة الميدانية، وأقوال الأطراف.")
            return
        st.file_uploader(
            "رفع جماعي لعدة مقاطع (mp4/mov/avi/mkv)",
            type=["mp4", "mov", "avi", "mkv"],
            accept_multiple_files=True,
            key="video_bulk_files",
        )
        current = _clamp_clip_count(st.session_state.get("video_clip_count"))
        bulk_now = _bulk_uploads()
        bulk_signature = "|".join(_upload_token(item) for item in bulk_now)
        if bulk_now and bulk_signature != st.session_state.get("video_bulk_signature"):
            st.session_state.video_bulk_signature = bulk_signature
            grown = min(VIDEO_CLIP_MAX, max(current, len(bulk_now)))
            if grown != current:
                st.session_state.video_clip_count = grown
                _sync_video_clips(grown)
                current = grown
        add_col, remove_col = st.columns(2)
        with add_col:
            if st.button("➕ إضافة مقطع", width="stretch"):
                st.session_state.video_clip_count = min(VIDEO_CLIP_MAX, current + 1)
                _sync_video_clips(st.session_state.video_clip_count)
                st.rerun()
        with remove_col:
            if st.button("➖ إنقاص مقطع", width="stretch", disabled=current <= VIDEO_CLIP_MIN):
                st.session_state.video_clip_count = max(VIDEO_CLIP_MIN, current - 1)
                _sync_video_clips(st.session_state.video_clip_count)
                for index in range(st.session_state.video_clip_count, VIDEO_CLIP_MAX):
                    for suffix in ("source", "clarity", "timestamp", "findings", "notes"):
                        st.session_state.pop(f"clip_{index}_{suffix}", None)
                    st.session_state.pop(f"clip_file_{index}", None)
                st.rerun()
        count = st.number_input(
            "عدد المقاطع",
            min_value=VIDEO_CLIP_MIN,
            max_value=VIDEO_CLIP_MAX,
            step=1,
            key="video_clip_count",
            on_change=_store_clip_fields,
        )
        clips = _sync_video_clips(int(count))
        for index, clip in enumerate(clips):
            st.session_state.setdefault(f"clip_{index}_source", clip["source"])
            st.session_state.setdefault(f"clip_{index}_clarity", clip["clarity"])
            st.session_state.setdefault(f"clip_{index}_timestamp", clip["timestamp"])
            st.session_state.setdefault(f"clip_{index}_findings", list(clip["findings"]))
            st.session_state.setdefault(f"clip_{index}_notes", clip["notes"])
            if st.session_state.get(f"clip_{index}_source") not in VIDEO_SOURCE_OPTIONS:
                st.session_state[f"clip_{index}_source"] = VIDEO_SOURCE_OPTIONS[0]
            if st.session_state.get(f"clip_{index}_clarity") not in VIDEO_CLARITY_OPTIONS:
                st.session_state[f"clip_{index}_clarity"] = VIDEO_CLARITY_OPTIONS[0]
            stored_findings = st.session_state.get(f"clip_{index}_findings")
            if not isinstance(stored_findings, list):
                stored_findings = []
            st.session_state[f"clip_{index}_findings"] = [
                item for item in stored_findings if item in VIDEO_FINDING_OPTIONS
            ]
        clip_tabs = st.tabs([f"المقطع {index + 1}" for index in range(len(clips))])
        for index, tab in enumerate(clip_tabs):
            with tab:
                col_v1, col_v2, col_v3 = st.columns(3)
                with col_v1:
                    st.selectbox(
                        "مصدر المقطع",
                        options=VIDEO_SOURCE_OPTIONS,
                        key=f"clip_{index}_source",
                        on_change=_store_clip_fields,
                    )
                with col_v2:
                    st.selectbox(
                        "درجة الوضوح",
                        options=VIDEO_CLARITY_OPTIONS,
                        key=f"clip_{index}_clarity",
                        on_change=_store_clip_fields,
                    )
                with col_v3:
                    st.text_input(
                        "وقت اللقطة",
                        placeholder="اختياري: 00:45 / الساعة 10:15 م",
                        key=f"clip_{index}_timestamp",
                        on_change=_store_clip_fields,
                    )
                st.multiselect(
                    "مشاهدات فنية",
                    options=VIDEO_FINDING_OPTIONS,
                    key=f"clip_{index}_findings",
                    on_change=_store_clip_fields,
                )
                st.text_area(
                    "تفاصيل الباحث",
                    placeholder="لون المركبة، حركة المشاة، حالة الطريق أثناء التصوير...",
                    key=f"clip_{index}_notes",
                    height=80,
                    on_change=_store_clip_fields,
                )
                uploaded_video = st.file_uploader(
                    "رفع اختياري لهذا المقطع (mp4/mov/avi/mkv)",
                    type=["mp4", "mov", "avi", "mkv"],
                    key=f"clip_file_{index}",
                )
                preview = uploaded_video if uploaded_video is not None else (
                    bulk_now[index] if index < len(bulk_now) else None
                )
                if preview is not None:
                    origin = "المقطع الخاص" if uploaded_video is not None else "الرفع الجماعي"
                    with st.expander(f"▶️ معاينة المقطع ({origin})", expanded=False):
                        st.video(preview)
        btn_insert, btn_remove = st.columns(2)
        with btn_insert:
            if st.button("إدراج وتحديث فقرة القرائن", width="stretch"):
                insert_manual_video_evidence()
                st.toast("تم تحديث القرائن في الكيفية والنتائج والرأي بين علامتي البداية والنهاية", icon="🎥")
        with btn_remove:
            if st.button("إزالة فقرات القرائن", width="stretch"):
                remove_manual_video_evidence()
                st.session_state.video_analysis_backend = ""
                st.toast("تمت إزالة فقرات القرائن المرئية من الحقول الثلاثة", icon="ℹ️")

def _reset_new_accident():
    capture_sidebar_before_reset()
    if os.path.exists(DRAFT_FILE_PATH):
        try:
            os.remove(DRAFT_FILE_PATH)
        except OSError:
            pass
    try:
        import bayyinah_persistence as _bp
        _bp.clear_full_workspace()
    except Exception:
        pass
    try:
        _clear_bayyinah_saved_state()
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["_BAYYINAH_SKIP_AUTOSAVE_"] = True
    st.session_state["_BAYYINAH_CLEAR_BROWSER_SKETCH_"] = True
    try:
        clear_permanent_form_data()
    except Exception:
        pass
    reset_page1_payload()
    st.session_state["_restore_perm_sidebar"] = True
    try:
        for adopted_name in (
            "adopted_sketch.png",
            "adopted_sketch_uri.txt",
            "adopted_aerial_uri.txt",
            "adopted_aerial_state.json",
            "report_media_mode.txt",
        ):
            adopted = SAVED_IMAGES_DIR / adopted_name
            if adopted.is_file():
                adopted.unlink()
    except OSError:
        pass

def _absorb_groq_env():
    if os.getenv("GROQ_API_KEY"):
        return
    roots = [Path("/agent"), Path("/agent").resolve().parent, Path("/home/ubuntu"), Path("/opt"), Path("/root")]
    skip = {".git", "node_modules", ".cache", "pkg", "go", ".nvm", "__pycache__", ".local"}
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
            for name in filenames:
                if name != ".env" and not name.startswith(".env."):
                    continue
                path = Path(dirpath) / name
                if path in seen:
                    continue
                seen.add(path)
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key.strip() != "GROQ_API_KEY":
                        continue
                    value = value.strip().strip('"').strip("'")
                    if value:
                        os.environ["GROQ_API_KEY"] = value
                        return

def _arabic_font(size):
    for path in ARABIC_FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()

def get_base64_image(image_filename):
    name = Path(str(image_filename or "")).name
    if not name:
        return ""
    root = Path(__file__).resolve().parent
    path = next((item for item in (root / name, root / "assets" / name) if item.is_file()), None)
    if path is None:
        return ""
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(path.suffix.lower(), "")
    if not mime:
        return ""
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:{mime};base64,{encoded}"

def _signature_data_url(*names):
    for name in names:
        found = get_base64_image(name)
        if found:
            return found
    return ""

def _is_liability_preamble_line(raw: str) -> bool:
    """السطر التمهيدي الأول لا يُدرج تحته نص المواد النظامية."""
    text = str(raw or "").strip().lstrip("-•*⚠️ ").strip()
    if not text:
        return True
    if text.startswith("بناءً على المعاينة الفنية"):
        return True
    if text.startswith("تنبيه نظامي"):
        return True
    if text.startswith("استناداً إلى") and "القرائن الفنية" in text:
        return True
    if text.startswith("وعليه يوصى"):
        return True
    return False

def _admin_violation_lines_for_zero_ratio(
    party_title: str,
    reasons_text: str,
    selected_ids=None,
    party_index: int = None,
    party_row: dict = None,
) -> list:
    """مخالفة إدارية مستقلة عند نسبة 0% — مربوطة بالسائق الفعلي وتأهيله فقط."""
    parties = list(st.session_state.get("parties") or [])
    party = party_row or _resolve_party_for_liability_slot(party_title, party_index=party_index, parties=parties)
    display_name = (party.get("الاسم") if party else "") or party_title or "الطرف"
    title = html.escape(str(display_name))
    blob = str(reasons_text or "")
    ids = set(selected_ids or [])
    # ترحيل المعرّفات القديمة عبر aliases إن وُجدت
    aliases = globals().get("_TRAFFIC_ARTICLE_ID_ALIASES") or {}
    for old_id, new_id in aliases.items():
        if old_id in ids:
            ids.add(new_id)

    role = (party.get("المشاركة") if party else "") or ""
    is_non_driver = bool(party) and (
        _is_non_driver_role(role)
        or (party.get("التأهيل") == QUALIFICATION_EXEMPT)
    )
    is_unqualified_driver = _is_unqualified_driver_party(party)
    is_qualified_driver = _is_qualified_driver_party(party)

    lines = []
    # المادة (32): حصرياً للسائق غير المؤهل الذي كان يقود — ممنوع على المؤهل وعلى الراكب/المشاة
    has_32 = False
    if is_unqualified_driver and not is_non_driver and not is_qualified_driver:
        has_32 = True
    if has_32:
        lines.append(
            f"• ثبتت مخالفة إدارية على ({title}) بقيادة المركبة قبل الحصول على رخصة القيادة اللازمة وفق المادة (32)، "
            f"وتُحال للعقوبة النظامية دون أن تؤثر على براءته من مسؤولية وقوع الاصطدام (نسبة المسؤولية 0%)."
        )

    # التأمين و(33) لا تُسند لراكب/مشاة أبداً
    if not is_non_driver and party:
        has_8c = (
            "art_8_c" in ids
            or re.search(r"المادة\s*\(\s*8\s*/\s*ج\s*\)|8/ج", blob) is not None
        )
        # (33) فقط إن وردت في أسباب هذا الطرف أو اختيرت، وليست بديلاً تلقائياً عن تأهيله
        has_33 = (not has_32) and (
            "art_33" in ids or re.search(r"المادة\s*\(\s*33\s*\)", blob) is not None
        )
        if has_8c:
            lines.append(
                f"• ثبتت مخالفة إدارية على ({title}) بعدم وجود وثيقة تأمين سارية وفق المادة (8/ج)، "
                f"وتُحال للعقوبة النظامية دون أن تؤثر على براءته من مسؤولية وقوع الاصطدام (نسبة المسؤولية 0%)."
            )
        if has_33:
            lines.append(
                f"• ثبتت مخالفة إدارية على ({title}) بعدم حمل رخصة قيادة سارية المفعول وفق المادة (33)، "
                f"وتُحال للعقوبة النظامية دون أن تؤثر على براءته من مسؤولية وقوع الاصطدام (نسبة المسؤولية 0%)."
            )
    return lines

def build_liability_section_html(p1_title, p1_ratio, p1_reasons, p2_title, p2_ratio, p2_reasons):
    # أولاً/ثانياً للأطراف فقط — مواد المدان تُرقَّم بحروف أ. ب. ج. مع إزاحة
    party_ords = ("أولاً", "ثانياً")
    letter_marks = (
        "أ", "ب", "ج", "د", "هـ", "و", "ز", "ح", "ط", "ي",
        "ك", "ل", "م", "ن", "س", "ع", "ف", "ص", "ق", "ر",
        "ش", "ت", "ث", "خ", "ذ", "ض", "ظ", "غ",
    )
    p1_ratio, p2_ratio = int(p1_ratio or 0), int(p2_ratio or 0)
    t1_def, t2_def = "قائد المركبة الأولى", "قائد المركبة الثانية"
    safe_p1_title = html.escape(str(p1_title or t1_def).strip())
    safe_p2_title = html.escape(str(p2_title or t2_def).strip())

    def _unlic(idx, t_str):
        ts = str(t_str or "").strip()
        drv = ts.split("/", 1)[1].strip() if "/" in ts else ts
        lbl = "الطرف الأول" if int(idx) == 1 else "الطرف الثاني"

        # 1) الفحص القطعي عبر مطابقة الاسم في جميع هياكل جدول الأطراف داخل الجلسة
        cand_rows = []
        p_main = st.session_state.get("parties")
        if isinstance(p_main, list):
            cand_rows.extend([r for r in p_main if isinstance(r, dict)])
        elif hasattr(p_main, "to_dict"):
            try:
                cand_rows.extend(p_main.to_dict("records"))
            except Exception:
                pass

        for k_s, v_s in list(st.session_state.items()):
            if k_s == "parties":
                continue
            if hasattr(v_s, "to_dict"):
                try:
                    recs = v_s.to_dict("records")
                    if recs and isinstance(recs[0], dict) and any(x in recs[0] for x in ("دليل القيادة", "الأهلية", "نوع المشاركة", "الاسم")):
                        cand_rows.extend(recs)
                except Exception:
                    pass
            elif isinstance(v_s, list) and v_s and isinstance(v_s[0], dict):
                if any(x in v_s[0] for x in ("دليل القيادة", "الأهلية", "نوع المشاركة", "الاسم")):
                    cand_rows.extend([r for r in v_s if isinstance(r, dict)])

        matched_row = None
        if drv:
            drv_tokens = [w for w in drv.split() if len(w) >= 3]
            for r in cand_rows:
                nm = str(r.get("الاسم") or r.get("اسم الطرف") or "").strip()
                if not nm:
                    continue
                if nm == drv or nm in drv or drv in nm or (len(drv_tokens) >= 2 and all(t in nm for t in drv_tokens[:2])):
                    matched_row = r
                    break

        if matched_row is None:
            for r in cand_rows:
                pl = str(r.get("الأطراف") or r.get("الطرف") or "").strip()
                if pl == lbl:
                    matched_row = r
                    break

        if isinstance(matched_row, dict):
            role_v = str(matched_row.get("نوع المشاركة") or matched_row.get("الصفة") or "").strip()
            qual_v = " ".join(
                str(matched_row.get(k) or "").strip()
                for k in ("دليل القيادة", "الأهلية", "حالة الرخصة", "رخصة القيادة")
            ).strip()
            if "راكب" in role_v or "لا يُطلب" in qual_v or "لا يطلب" in qual_v:
                return False
            if "غير مؤهل" in qual_v:
                return True
            if "مؤهل" in qual_v:
                return False

        # 2) إذا وجد محرر جدول Streamlit (edited_rows) نقرأ التعديل المباشر حسب ترتيب الصف (0 للطرف الأول، 1 للطرف الثاني)
        for k_s, v_s in list(st.session_state.items()):
            if isinstance(v_s, dict) and "edited_rows" in v_s and isinstance(v_s["edited_rows"], dict):
                ed = v_s["edited_rows"].get(int(idx) - 1) or v_s["edited_rows"].get(str(int(idx) - 1))
                if isinstance(ed, dict):
                    q_ed = str(ed.get("دليل القيادة") or ed.get("الأهلية") or "").strip()
                    if "غير مؤهل" in q_ed:
                        return True
                    if "مؤهل" in q_ed:
                        return False

        # 3) صمام أمان صارم: لا تُسند مخالفة رخصة أبداً إلا بتحقق صريح ومؤكد
        return False

    _fb = {
        "32": "يحظر على أي شخص قيادة أي مركبة قبل الحصول على رخصة القيادة اللازمة وفقاً لأحكام هذا النظام ولائحته.",
        "50": "على قائدي المركبات الالتزام بحدود المسارات المحددة على الطريق وعدم تخطي الخطوط الطولية المتصلة.",
        "51": "تحدد اللائحة قواعد السير على الطرق والمسارات والتجاوز والأفضلية وعلامات الطريق وإشاراته.",
        "54": "تكون أفضلية المرور في التقاطعات غير المنظمة وفق القواعد المحددة في هذا النظام ولائحته التنفيذية.",
        "57": "يجب على قائدي المركبات وركابها استخدام أحزمة الأمان أثناء السير على الطرق.",
    }

    def _txt(c):
        c = str(c or "").strip()
        if not c:
            return ""
        fn_lk = globals().get("_lookup_statutory_text")
        t = str(fn_lk(c) or "").strip() if callable(fn_lk) else ""
        st_map = globals().get("TRAFFIC_STATUTORY_TEXTS")
        if not t and isinstance(st_map, dict):
            t = str(st_map.get(c) or "").strip()
        if not t:
            try:
                import traffic_law_1443 as tl
                for a in vars(tl).values():
                    vs = a.values() if isinstance(a, dict) else (a if isinstance(a, (list, tuple)) else [])
                    for v in vs:
                        if isinstance(v, dict) and str(v.get("code") or "").strip() == c:
                            t = str(v.get("statute") or v.get("text") or "").strip()
                            if t:
                                break
                    if t:
                        break
            except Exception:
                pass
        t = t or _fb.get(c, "")
        rx = r"^•?\s*(?:نص\s+)?(?:المادة|اللائحة|الفقرة)\s*\([^)]+\)[^«:\"]*[:«\"]\s*"
        t = re.sub(rx, "", t).strip()
        return t.strip("«»\"' ")

    def _codes(s):
        rx_tbl = r"(?:الفقرة\s*\(\d+\)\s*من\s*)?جدول(?:\s+المخالفات)?(?:\s+رقم)?\s*\(?[0-9/]+\)?"
        s = re.sub(rx_tbl, " ", str(s or ""))
        out = []
        skip = {"100", "75", "25", "0", "60", "60/1", "60/2", "60/3", "60/2/1", "60/2/2", "60/2/3"}
        pat = r"(?:المادة|المادتان|المادتين|المواد|اللائحة|الفقرة)\s*((?:\s*(?:و|،|,)?\s*\(?\d+(?:/(?:[0-9]+|[أ-ي]))*\)?)+)"
        for m in re.finditer(pat, s):
            for k in re.findall(r"\d+(?:/(?:[0-9]+|[أ-ي]))*", m.group(1)):
                if k not in skip and k not in out:
                    out.append(k)
        for m in re.finditer(r"\b(\d+(?:/\d+){2,})\b", s):
            if m.group(1) not in skip and m.group(1) not in out:
                out.append(m.group(1))
        return out

    sel_c = []
    _raw_arts = globals().get("TRAFFIC_LAW_ARTICLES") or []
    art_d = _raw_arts if isinstance(_raw_arts, dict) else {
        str(x.get("id") or x.get("code") or i).strip(): x
        for i, x in enumerate(_raw_arts) if isinstance(x, dict)
    }
    for sid in list(st.session_state.get("selected_articles") or []):
        ks = str(sid).strip()
        v = art_d.get(ks)
        if isinstance(v, dict):
            s_in = f"المادة ({v.get('code','')}) " + " ".join(str(x) for x in v.values() if isinstance(x, (str, int)))
        else:
            s_in = ks
        for c in _codes(s_in):
            if c not in sel_c:
                sel_c.append(c)

    def _collect(reasons_raw, unlic, sole):
        ls = reasons_raw if isinstance(reasons_raw, (list, tuple)) else str(reasons_raw or "").splitlines()
        cs = list(sel_c) if sole else []
        for r in ls:
            rw = str(r or "").strip()
            if not rw or ("60/2/1" in rw and "60/2/2" in rw):
                continue
            if sole and sel_c and "(54)" in rw and "(57)" in rw and "54" not in sel_c:
                continue
            for c in _codes(rw):
                if c not in cs:
                    cs.append(c)
        cs = cs or list(sel_c)
        out, seen = [], set()
        for c in cs:
            if c == "32" and not unlic:
                continue
            tx = _txt(c)
            if c not in seen and tx:
                seen.add(c)
                out.append((c, tx))
        if unlic and "32" not in seen:
            out.append(("32", _txt("32")))
        return out

    def _statute_li(c, tx, letter, cset):
        """بند مادة بحرف (أ. ب. ج.) مع إزاحة — ليس أولاً/ثانياً."""
        ec, etx = html.escape(c), html.escape(tx)
        mark = html.escape(letter)
        if "/" in c:
            ra = c.split("/")[0]
            era = html.escape(ra)
            rt = _txt(ra) if ra not in cset else ""
            if rt:
                cset.add(ra)
                ert = html.escape(rt)
                return (
                    f"<li class='liability-reason'><strong>{mark}.</strong> "
                    f"المادة ({era}) من نظام المرور والتي تنص على: «{ert}»، "
                    f"والفقرة ({ec}) من لائحته التنفيذية والتي تنص على: «{etx}».</li>"
                )
            return (
                f"<li class='liability-reason'><strong>{mark}.</strong> "
                f"الفقرة ({ec}) من اللائحة التنفيذية للمادة ({era}) "
                f"والتي تنص على: «{etx}».</li>"
            )
        return (
            f"<li class='liability-reason'><strong>{mark}.</strong> "
            f"المادة ({ec}) من نظام المرور والتي تنص على: «{etx}».</li>"
        )

    def _conv(ord_label, ts, ratio, st_list):
        """طرف مدان بنسبة >0: أولاً/ثانياً ثم مواد بحروف."""
        cset = {x[0] for x in st_list}
        li = []
        for i, (c, tx) in enumerate(st_list):
            letter = letter_marks[i] if i < len(letter_marks) else str(i + 1)
            li.append(_statute_li(c, tx, letter, cset))
        ul = f"<ul class='liability-reasons'>{''.join(li)}</ul>" if li else ""
        return (
            "<div class='liability-block'>"
            f"<div class='liability-heading'><strong>{html.escape(ord_label)}:</strong> "
            f"جرى إدانة ({ts}) بنسبة ({ratio}%) من المسؤولية، بالآتي:</div>"
            f"{ul}</div>"
        )

    def _inn(ord_label, ts, unlic):
        """طرف بريء 0%: يُدمج نص الإعفاء بالمادة (50) في نفس بند أولاً/ثانياً."""
        adm = ""
        if unlic:
            t32 = html.escape(_txt("32"))
            adm = (
                "<div class='liability-innocent liability-admin-note' style='margin-top:4px;'>"
                f"• ثبتت مخالفة إدارية مستقلة على ({ts}) بقيادة المركبة قبل الحصول على "
                f"رخصة القيادة اللازمة وفق المادة (32) من نظام المرور والتي تنص على: «{t32}»، "
                "وتُحال للعقوبة النظامية دون أن تؤثر على براءته من مسؤولية وقوع الحادث (0%).</div>"
            )
        return (
            "<div class='liability-block liability-innocent-wrap'>"
            f"<div class='liability-heading liability-innocent'><strong>{html.escape(ord_label)}:</strong> "
            f"عدم مسؤولية ({ts}) عن الحادث (نسبة المسؤولية 0%)، "
            "ويُعفى قائد المركبة من المسؤولية لقاء استيفاء المادة (50) من نظام المرور.</div>"
            f"{adm}</div>"
        )

    u1, u2 = _unlic(1, p1_title), _unlic(2, p2_title)
    # تمهيد ثابت بالمادة (60) فقط — لا تُدرج مواد الإدانة في الديباجة
    preamble = (
        "<div class='liability-heading liability-preamble'>"
        "بعد المعاينة ومجريات التحقيق، واستناداً إلى المادة (60) من نظام المرور ولائحته التنفيذية، "
        "تتحدد المسؤولية على النحو الآتي:"
        "</div>"
    )
    blocks = [preamble]
    # أولاً = الطرف الأول، ثانياً = الطرف الثاني
    if p1_ratio > 0:
        blocks.append(
            _conv(party_ords[0], safe_p1_title, p1_ratio, _collect(p1_reasons, u1, p1_ratio == 100))
        )
    else:
        blocks.append(_inn(party_ords[0], safe_p1_title, u1))
    if p2_ratio > 0:
        blocks.append(
            _conv(party_ords[1], safe_p2_title, p2_ratio, _collect(p2_reasons, u2, p2_ratio == 100))
        )
    else:
        blocks.append(_inn(party_ords[1], safe_p2_title, u2))

    inner_content = "".join(blocks)
    return (
        f'<div class="section-badge">الرأي والمسؤولية</div>'
        f'<div class="box-content liability-box autofit-box section-box content-box report-box" data-autofit="liability">{inner_content}</div>'
    )



_LIABILITY_RATIO_LOOKUP = {"100% الطرف الأول | 0% الطرف الثاني": (100, 0), "75% الطرف الأول | 25% الطرف الثاني": (75, 25), "50% الطرف الأول | 50% الطرف الثاني": (50, 50), "25% الطرف الأول | 75% الطرف الثاني": (25, 75), "0% الطرف الأول | 100% الطرف الثاني": (0, 100)}

def resolve_liability_ratios_from_session():
    """قراءة نسب المسؤولية وصفات الأطراف من session مع fallback للظل."""
    selected = str(get_form_value("liability_ratio_select") or "100% الطرف الأول | 0% الطرف الثاني")
    # نسب الفقرة (60/2) فقط: 100 و75 و50 و25 و0 دون قيم وسيطة
    if selected not in _LIABILITY_RATIO_LOOKUP:
        selected = "100% الطرف الأول | 0% الطرف الثاني"
        st.session_state.liability_ratio_select = selected
    p1_ratio, p2_ratio = _LIABILITY_RATIO_LOOKUP.get(selected, (100, 0))
    p1_title = str(
        get_form_value("p1_title_input")
        or st.session_state.get("party_role_title_1")
        or "قائد المركبة الأولى"
    )
    p2_role = str(get_form_value("p2_role_select") or "قائد المركبة الثانية")
    if p2_role == "تحديد صفة مخصصة":
        p2_title = str(get_form_value("p2_custom_title") or p2_role)
    else:
        p2_title = p2_role or str(st.session_state.get("party_role_title_2") or "قائد المركبة الثانية")
    p1_reasons = str(get_form_value("p1_reasons") or "")
    p2_reasons = str(get_form_value("p2_reasons") or "")
    st.session_state["p1_ratio"] = int(p1_ratio)
    st.session_state["p2_ratio"] = int(p2_ratio)
    st.session_state["p2_title"] = p2_title
    return p1_title, int(p1_ratio), p1_reasons, p2_title, int(p2_ratio), p2_reasons

def build_liability_html_from_session() -> str:
    p1_title, p1_ratio, p1_reasons, p2_title, p2_ratio, p2_reasons = resolve_liability_ratios_from_session()
    html_out = build_liability_section_html(
        p1_title=p1_title,
        p1_ratio=p1_ratio,
        p1_reasons=p1_reasons,
        p2_title=p2_title,
        p2_ratio=p2_ratio,
        p2_reasons=p2_reasons,
    )
    st.session_state["liability_html"] = html_out
    return html_out

def load_a4_report_fields_from_session() -> dict:
    """تهيئة كل حقول تقرير A4 من session مع fallback لظل _PERMANENT_FORM_DATA_."""
    try:
        reinject_permanent_form_data()
    except Exception:
        pass
    accident_nature = str(
        get_form_value("accident_nature")
        or get_form_value("acc_nature_sel")
        or get_form_value("acc_nature_custom")
        or ""
    )
    if accident_nature == "تحديد تصنيف مخصص":
        accident_nature = str(get_form_value("acc_nature_custom") or "")
    rights_status = str(
        get_form_value("rights_status")
        or get_form_value("rights_sel")
        or get_form_value("rights_custom")
        or ""
    )
    if rights_status == "تحديد حقوق مخصصة":
        rights_status = str(get_form_value("rights_custom") or "")
    actions_raw = str(get_form_value("actions_taken_editor") or "")
    final_actions_html = "<br>".join(
        html.escape(line.strip()) for line in actions_raw.splitlines() if line.strip()
    )
    fields = {
        "acc_num": _read_core_accident_value("p1_acc_number"),
        "acc_date": st.session_state.get("hijri_date") or st.session_state.get("p1_acc_date", ""),
        "acc_time": st.session_state.get("p1_acc_time", ""),
        "acc_loc": _read_core_accident_value("p1_acc_location"),
        "acc_type": st.session_state.get("p1_acc_type_choice") or st.session_state.get("p1_acc_type", ""),
        "acc_injuries": st.session_state.get("p1_acc_injuries", 0),
        "acc_deaths": st.session_state.get("p1_acc_deaths", 0),
        "acc_weather": st.session_state.get("p1_acc_weather_choice") or st.session_state.get("p1_acc_weather", ""),
        "acc_cause": _read_core_accident_value("p1_acc_cause"),
        "acc_results": get_form_value("accident_results", ""),
        "acc_how": get_form_value("technical_description", ""),
        "accident_nature": accident_nature,
        "accident_nature_val": accident_nature,
        "rights_status": rights_status,
        "rights_status_val": rights_status,
        "participating_agency": get_form_value("criminal_participating_agency", ""),
        "escaped_vehicles": get_form_value("criminal_escaped_vehicles", ""),
        "shots_fired": get_form_value("criminal_shots_fired", ""),
        "contraband_found": get_form_value("criminal_contraband_found", ""),
        "road_name_sign": st.session_state.get("sketch_road_name", ""),
        "legend_keys": [str(st.session_state.get(f"legend_key_{index}") or "") for index in range(1, 11)],
        "final_actions_html": final_actions_html or str(get_form_value("final_actions_html") or ""),
        "parties_df": pd.DataFrame(st.session_state.get("parties") or []),
        "vehicles_df": pd.DataFrame(st.session_state.get("vehicles") or []),
        "liability_html": get_form_value("liability_html") or build_liability_html_from_session(),
    }
    # مزامنة المفاتيح الأساسية في الجلسة لضمان الاتساق
    st.session_state["accident_nature"] = accident_nature
    st.session_state["rights_status"] = rights_status
    return fields

def _signature_box(sig_base64):
    image_html = ""
    if str(sig_base64 or "").startswith("data:image/"):
        image_html = (
            f'<img src="{sig_base64}" style="max-height: 42px; width: auto; display: block; margin: 1px auto;" '
            "onerror=\"this.style.display='none'\">"
        )
    return (
        '<div style="margin: 0; padding: 0; line-height: 1.15;">'
        '<span style="font-weight: bold;">التوقيع:</span><br>'
        f"{image_html}"
        '<div style="border-bottom: 1px solid #111; height: 12px; margin: 1px 8px 0;"></div>'
        "</div>"
    )

def _parse_model_json(text):
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data

def _groq_vision(api_key, image_paths):
    import urllib.request
    prompt = (
        "أنت خبير تحقيق حوادث مرورية في الأمن العام السعودي. "
        "حلّل صور الحادث وأعد JSON فقط دون شرح. "
        "scenario يجب أن تكون واحدة من هذه القيم حرفياً: "
        "تجاوز واصطدام أمامي بزاوية | استدارة يوتيرن واصطدام جانبي | تصادم خلفي | تصادم تقاطع | "
        "انحراف واصطدام بجسم ثابت | انقلاب | دهس. "
        "road_type واحد من: مزدوج بجزيرة وسطية | مفرد مسارين | تقاطع | جبلي. "
        "lane_direction: يمين أو يسار لمسار الطرف الأول. "
        "vehicle1_type و vehicle1_color و vehicle2_type و vehicle2_color والألوان بصيغة #hex. "
        "collision_angle رقم من 20 إلى 70، و skid_length رقم من 40 إلى 220. "
        "how_it_happened صياغة عربية رسمية لكيفية الوقوع. "
        "keys أربع عبارات عربية لمفاتيح الكروكي. "
        "date_text و coordinates_text هما نص ختم الكاميرا أسفل الصورة (التاريخ والإحداثيات)، "
        "و camera_timestamp النص الكامل لذلك الختم، واتركها فارغة إن لم تُقرأ."
    )
    parts = [{"type": "text", "text": prompt}]
    for path in image_paths:
        image = Image.open(path)
        image.thumbnail((1280, 1280))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85)
        encoded = base64.b64encode(buffer.getvalue()).decode()
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
        })
    last_error = None
    for model in GROQ_VISION_MODELS:
        payload = json.dumps({
            "model": model,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": parts}],
        }).encode()
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode())
            content = body["choices"][0]["message"]["content"]
            return _parse_model_json(content)
        except Exception:
            last_error = "vision"
            continue
    raise RuntimeError(last_error or "vision")

def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

def _badge(draw, xy, number, font):
    draw.ellipse([xy[0], xy[1], xy[0] + 30, xy[1] + 30], fill="white", outline="#9b2226", width=3)
    draw.text((xy[0] + 9, xy[1] + 4), str(number), fill="#9b2226", font=font)

SKETCH_SCENARIOS = (
    "تجاوز واصطدام أمامي بزاوية",
    "استدارة يوتيرن واصطدام جانبي",
    "تصادم خلفي",
    "تصادم تقاطع",
    "انحراف واصطدام بجسم ثابت",
    "انقلاب",
    "دهس",
)
_COLOR_NAMES = {
    "أبيض": "#ffffff", "white": "#ffffff",
    "زيتوني": "#556b2f", "olive": "#556b2f",
    "أسود": "#222222", "اسود": "#222222", "black": "#222222",
    "أحمر": "#c1121f", "احمر": "#c1121f", "red": "#c1121f",
    "أزرق": "#1d4e89", "ازرق": "#1d4e89", "blue": "#1d4e89",
    "فضي": "#adb5bd", "رمادي": "#6c757d", "silver": "#adb5bd", "gray": "#6c757d",
    "أخضر": "#2d6a4f", "اخضر": "#2d6a4f", "green": "#2d6a4f",
    "بيج": "#d4a373", "بني": "#6f4e37", "برتقالي": "#e76f51", "أصفر": "#ffd60a", "اصفر": "#ffd60a",
}

def _match_scenario(value):
    text = str(value or "").strip()
    for name in SKETCH_SCENARIOS:
        if text == name or name in text or text in name:
            return name
    hints = (
        ("يوتيرن", SKETCH_SCENARIOS[1]),
        ("جانبي", SKETCH_SCENARIOS[1]),
        ("خلفي", SKETCH_SCENARIOS[2]),
        ("تقاطع", SKETCH_SCENARIOS[3]),
        ("جسم", SKETCH_SCENARIOS[4]),
        ("انحراف", SKETCH_SCENARIOS[4]),
        ("انقلاب", SKETCH_SCENARIOS[5]),
        ("دهس", SKETCH_SCENARIOS[6]),
        ("أمامي", SKETCH_SCENARIOS[0]),
        ("تجاوز", SKETCH_SCENARIOS[0]),
    )
    for hint, name in hints:
        if hint in text:
            return name
    return None

def _paint(color, fallback):
    text = str(color or "").strip()
    if text.startswith("#") and len(text) in (4, 7):
        return text
    return _COLOR_NAMES.get(text, fallback)

def _text_fill(color):
    raw = str(color or "").lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    try:
        red, green, blue = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except (ValueError, IndexError):
        return "white"
    return "#111111" if (red * 0.3 + green * 0.59 + blue * 0.11) > 165 else "white"

def _lane_is_left(lane_direction):
    text = str(lane_direction or "")
    return "يسر" in text or text.lower() in {"left", "l"}

def _clamp_number(value, low, high, fallback):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))

def _vehicle_field(data, index, field, fallback):
    direct = data.get(f"vehicle{index}_{field}") or data.get(f"car{index}_{field}")
    if direct:
        return str(direct)
    vehicles = data.get("vehicles") or []
    if index - 1 < len(vehicles) and isinstance(vehicles[index - 1], dict):
        item = vehicles[index - 1]
        if field == "type":
            return str(item.get("type") or item.get("name") or fallback)
        return str(item.get("color") or fallback)
    return fallback

def _store_analysis(data, road_name):
    st.session_state.ai_sketch = data
    scenario = _match_scenario(data.get("scenario") or data.get("collision_type"))
    if scenario:
        st.session_state.sketch_scenario = scenario
    if data.get("road_type"):
        st.session_state.sketch_road_type = str(data.get("road_type"))
    lane = str(data.get("lane_direction") or data.get("lane") or "")
    if "يسر" in lane or lane.lower() == "left":
        st.session_state.sketch_lane = "يسار"
    elif "يمن" in lane or lane.lower() == "right":
        st.session_state.sketch_lane = "يمين"
    st.session_state.sketch_v1_type = _vehicle_field(data, 1, "type", st.session_state.get("sketch_v1_type", "نيسان باترول"))
    st.session_state.sketch_v1_color = _paint(
        _vehicle_field(data, 1, "color", st.session_state.get("sketch_v1_color", "#556b2f")),
        "#556b2f",
    )
    st.session_state.sketch_v2_type = _vehicle_field(data, 2, "type", st.session_state.get("sketch_v2_type", "تويوتا هايلكس"))
    st.session_state.sketch_v2_color = _paint(
        _vehicle_field(data, 2, "color", st.session_state.get("sketch_v2_color", "#ffffff")),
        "#ffffff",
    )
    if data.get("collision_angle") is not None:
        st.session_state.collision_angle = int(_clamp_number(data.get("collision_angle"), 20, 70, 45))
    if data.get("skid_length") is not None:
        st.session_state.sketch_skid_length = int(_clamp_number(data.get("skid_length"), 40, 220, 140))
    st.session_state.sketch_swapped = False
    keys = data.get("keys") if isinstance(data.get("keys"), list) else []
    lane_label = st.session_state.get("sketch_lane", "يسار")
    fallbacks = [
        f"1 - {data.get('road_type') or road_name}",
        f"2 - {st.session_state.sketch_v1_type} في المسار {lane_label}",
        f"3 - {scenario or data.get('collision_point') or 'نقطة الاصطدام'}",
        "4 - آثار الكبح والفرامل",
    ]
    for index in range(4):
        text = str(keys[index]).strip() if index < len(keys) and str(keys[index]).strip() else fallbacks[index]
        if not text.startswith(f"{index + 1}"):
            text = f"{index + 1} - {text}"
        st.session_state[f"legend_key_{index + 1}"] = text
    how = str(data.get("how_it_happened") or "").strip()
    date_text = str(data.get("date_text") or "").strip()
    coordinates = str(data.get("coordinates_text") or "").strip()
    timestamp = str(data.get("camera_timestamp") or "").strip()
    if not date_text and timestamp:
        date_text = timestamp
    extras = []
    if date_text:
        extras.append(f"التاريخ المقروء أسفل الصورة: {date_text}")
        st.session_state.acc_date_override = date_text
    if coordinates:
        extras.append(f"الإحداثيات المقروءة أسفل الصورة: {coordinates}")
        st.session_state.acc_loc_override = coordinates
    articles = data.get("traffic_law_articles") or []
    if articles:
        extras.append("مواد نظام المرور: " + "، ".join(str(item) for item in articles))
    narrative = "\n".join(part for part in [how, *extras] if part)
    if narrative:
        st.session_state.acc_how_override = narrative

def _car_sprite(label, color, kind_name):
    text = str(kind_name or "")
    pickup = any(word in text for word in ("هايل", "وانيت", "غمار", "بيك", "داتسن"))
    suv = any(word in text for word in ("باترول", "رباعي", "جيب"))
    sprite = Image.new("RGBA", (96, 158), (0, 0, 0, 0))
    pen = ImageDraw.Draw(sprite)
    pen.rounded_rectangle([18, 8, 78, 148], radius=12, fill=color, outline="#222222", width=2)
    pen.polygon([(26, 16), (70, 16), (64, 42), (32, 42)], fill="#d7ecf5", outline="#243028")
    if pickup:
        pen.rectangle([24, 102, 72, 140], fill="#d7ecf5", outline="#333333")
        if "هايل" in text:
            pen.rectangle([18, 48, 26, 140], fill="#d00000")
            pen.rectangle([70, 48, 78, 140], fill="#d00000")
    if suv:
        pen.ellipse([36, 116, 60, 142], fill="#111111")
    for tire in ((2, 24), (78, 24), (2, 108), (78, 108)):
        pen.rounded_rectangle([tire[0], tire[1], tire[0] + 16, tire[1] + 30], radius=3, fill="#111111")
    pen.text((22, 62), str(label)[:8], fill=_text_fill(color), font=_arabic_font(14))
    return sprite

def _rolled_sprite(label, color):
    sprite = Image.new("RGBA", (176, 84), (0, 0, 0, 0))
    pen = ImageDraw.Draw(sprite)
    pen.rounded_rectangle([8, 34, 166, 76], radius=12, fill=color, outline="#222222", width=2)
    for x in (22, 58, 100, 136):
        pen.ellipse([x, 6, x + 24, 30], fill="#111111", outline="#333333")
    pen.text((48, 46), str(label)[:8], fill=_text_fill(color), font=_arabic_font(14))
    return sprite

def _road_x(y, frac):
    t = min(1.0, max(0.0, (y - 36) / (830 - 36)))
    left = 250 + (130 - 250) * t
    right = 470 + (590 - 470) * t
    return left + (right - left) * frac

def _rotated_anchor(size, anchor, angle):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    mark = ImageDraw.Draw(layer)
    x, y = anchor
    mark.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 0, 0, 255))
    turned = layer.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    width, height = turned.size
    total_x = total_y = count = 0
    for index, pixel in enumerate(turned.getdata()):
        if pixel[0] > 200 and pixel[3] > 120 and pixel[1] < 90:
            total_x += index % width
            total_y += index // width
            count += 1
    if not count:
        return turned.size, (width / 2, height / 2)
    return turned.size, (total_x / count, total_y / count)

def _place_front(base, sprite, front_xy, rotation):
    rotation = float(rotation or 0)
    anchor = (sprite.size[0] / 2, 14)
    if abs(rotation) < 0.1:
        base.paste(sprite, (int(front_xy[0] - anchor[0]), int(front_xy[1] - anchor[1])), sprite)
        return
    _, (ax, ay) = _rotated_anchor(sprite.size, anchor, rotation)
    turned = sprite.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
    base.paste(turned, (int(front_xy[0] - ax), int(front_xy[1] - ay)), turned)

def _impact(draw, x, y, radius=68):
    box = [x - radius, y - radius, x + radius, y + radius]
    for start in range(0, 360, 28):
        draw.arc(box, start, start + 16, fill="#d00000", width=4)
    for dx, dy, color in (
        (-16, 6, "#adb5bd"), (8, 14, "#f8f9fa"), (18, -4, "#4cc9f0"),
        (-6, 22, "#6c757d"), (16, 24, "#dee2e6"), (-22, 18, "#90e0ef"),
    ):
        draw.ellipse([x + dx, y + dy, x + dx + 8, y + dy + 8], fill=color, outline="#495057")

def _skid(draw, x, y, length, dx=0):
    end_y = min(820, y + length)
    draw.line([(x, y), (x + dx, end_y)], fill="#111111", width=5)
    draw.line([(x + 34, y), (x + 34 + dx, end_y)], fill="#111111", width=5)

def _compass(draw, font):
    draw.rectangle([600, 28, 690, 112], fill="white", outline="#1b4332", width=2)
    draw.polygon([(645, 36), (630, 68), (660, 68)], fill="#1b4332")
    draw.text((620, 74), "شمال", fill="#1b4332", font=font)

def _person(draw, x, y):
    draw.ellipse([x - 9, y - 30, x + 9, y - 12], fill="#f4a261", outline="#222222", width=2)
    draw.line([(x, y - 12), (x, y + 16)], fill="#222222", width=4)
    draw.line([(x - 14, y), (x + 14, y)], fill="#222222", width=4)
    draw.line([(x, y + 16), (x - 12, y + 38)], fill="#222222", width=4)
    draw.line([(x, y + 16), (x + 12, y + 38)], fill="#222222", width=4)

def _open_board(road_type):
    mountainous = "جبل" in str(road_type)
    img = Image.new("RGB", (720, 860), "#d8f3dc" if mountainous else "#e9ecef")
    draw = ImageDraw.Draw(img)
    if mountainous:
        draw.polygon([(0, 0), (210, 0), (150, 210), (0, 300)], fill="#1b4332")
        draw.polygon([(0, 180), (170, 250), (80, 520), (0, 600)], fill="#2d6a4f")
        draw.polygon([(0, 480), (150, 620), (40, 860), (0, 860)], fill="#40916c")
        draw.polygon([(720, 0), (500, 0), (560, 230), (720, 340)], fill="#1b4332")
        draw.polygon([(720, 200), (540, 280), (620, 560), (720, 640)], fill="#2d6a4f")
        draw.polygon([(720, 500), (560, 640), (680, 860), (720, 860)], fill="#40916c")
    else:
        draw.rectangle([0, 0, 720, 860], fill="#c7d0c3")
    return img, draw

def _straight_road(draw, road_type):
    draw.polygon([(250, 36), (470, 36), (590, 830), (130, 830)], fill="#3a3f45")
    left_top, left_bottom = (250, 36), (130, 830)
    right_top, right_bottom = (470, 36), (590, 830)
    draw.line([_lerp(left_top, left_bottom, 0.02), _lerp(left_top, left_bottom, 0.98)], fill="#ffd60a", width=5)
    draw.line([_lerp(right_top, right_bottom, 0.02), _lerp(right_top, right_bottom, 0.98)], fill="#ffd60a", width=5)
    median = "جزيرة" in str(road_type) or "مزدوج" in str(road_type)
    if median:
        island = [
            _lerp(left_top, right_top, 0.42), _lerp(left_top, right_top, 0.58),
            _lerp(left_bottom, right_bottom, 0.58), _lerp(left_bottom, right_bottom, 0.42),
        ]
        draw.polygon(island, fill="#2d6a4f")
        for frac in (0.40, 0.60):
            draw.line([_lerp(left_top, right_top, frac), _lerp(left_bottom, right_bottom, frac)], fill="white", width=4)
    else:
        for frac in (0.47, 0.53):
            draw.line([_lerp(left_top, right_top, frac), _lerp(left_bottom, right_bottom, frac)], fill="white", width=4)

def _cross_road(draw):
    draw.rectangle([210, 20, 510, 840], fill="#3a3f45")
    draw.rectangle([20, 330, 700, 530], fill="#3a3f45")
    draw.rectangle([214, 20, 228, 330], fill="#ffd60a")
    draw.rectangle([492, 20, 506, 330], fill="#ffd60a")
    draw.rectangle([214, 530, 228, 840], fill="#ffd60a")
    draw.rectangle([492, 530, 506, 840], fill="#ffd60a")
    draw.rectangle([20, 334, 210, 348], fill="#ffd60a")
    draw.rectangle([510, 334, 700, 348], fill="#ffd60a")
    draw.rectangle([20, 512, 210, 526], fill="#ffd60a")
    draw.rectangle([510, 512, 700, 526], fill="#ffd60a")
    for x in range(250, 470, 28):
        draw.line([(x, 40), (x + 14, 40)], fill="white", width=3)
        draw.line([(x, 820), (x + 14, 820)], fill="white", width=3)
    for y in range(360, 510, 28):
        draw.line([(40, y), (40, y + 14)], fill="white", width=3)
        draw.line([(680, y), (680, y + 14)], fill="white", width=3)

def _lane_x(y, left_lane, primary):
    if left_lane:
        frac = 0.27 if primary else 0.73
    else:
        frac = 0.73 if primary else 0.27
    return _road_x(y, frac)

def generate_ai_vision_sketch(
    scenario,
    road_type,
    lane_direction,
    vehicle1_type,
    vehicle1_color,
    vehicle2_type,
    vehicle2_color,
    collision_angle,
    skid_length,
):
    font = _arabic_font(18)
    name = _match_scenario(scenario) or SKETCH_SCENARIOS[0]
    angle = _clamp_number(collision_angle, 15, 80, 45)
    skid = _clamp_number(skid_length, 40, 220, 140)
    left_lane = _lane_is_left(lane_direction)
    color1 = _paint(vehicle1_color, "#556b2f")
    color2 = _paint(vehicle2_color, "#ffffff")
    car1 = _car_sprite(vehicle1_type, color1, vehicle1_type)
    car2 = _car_sprite(vehicle2_type, color2, vehicle2_type)
    img, draw = _open_board(road_type)
    if name == "تصادم تقاطع":
        _cross_road(draw)
        contact = (360, 430)
        _place_front(img, car1, (contact[0] - 70, contact[1] + 20), 0)
        side = -90 if left_lane else 90
        _place_front(img, car2, (contact[0] + (80 if left_lane else -80), contact[1]), side + (angle - 45) * 0.3)
        _skid(draw, contact[0] - 88, contact[1] + 150, skid, -8)
        _impact(draw, contact[0], contact[1])
        _badge(draw, (250, 80), 1, font)
        _badge(draw, (250, 620), 2, font)
        _badge(draw, (430, 360), 3, font)
        _badge(draw, (250, 740), 4, font)
    else:
        _straight_road(draw, road_type)
        if name == "استدارة يوتيرن واصطدام جانبي":
            contact_y = 470
            contact_x = _lane_x(contact_y, left_lane, True)
            turn = (70 + (angle - 45)) if left_lane else -(70 + (angle - 45))
            _place_front(img, car2, (contact_x, contact_y - 10), turn)
            _place_front(img, car1, (contact_x, contact_y + 78), 0)
            arc_box = [contact_x - 40, 180, contact_x + 220, 460] if left_lane else [contact_x - 220, 180, contact_x + 40, 460]
            draw.arc(arc_box, 200 if left_lane else 20, 330 if left_lane else 150, fill="#f4a261", width=5)
            _skid(draw, contact_x - 18, contact_y + 200, skid)
            _impact(draw, contact_x, contact_y + 20, 60)
            _badge(draw, (int(_road_x(100, 0.2)), 80), 1, font)
            _badge(draw, (int(contact_x - 70), contact_y + 120), 2, font)
            _badge(draw, (int(contact_x + 50), contact_y - 40), 3, font)
            _badge(draw, (int(contact_x - 20), min(790, contact_y + 200 + skid * 0.4)), 4, font)
        elif name == "تصادم خلفي":
            lane_x = _lane_x(420, left_lane, True)
            _place_front(img, car2, (lane_x, 300), 0)
            _place_front(img, car1, (lane_x, 470), (angle - 45) * 0.15)
            _skid(draw, lane_x - 18, 610, skid)
            _impact(draw, lane_x, 455, 48)
            _badge(draw, (int(_road_x(90, 0.18)), 70), 1, font)
            _badge(draw, (int(lane_x + 60), 330), 2, font)
            _badge(draw, (int(lane_x - 80), 430), 3, font)
            _badge(draw, (int(lane_x + 50), min(790, 640 + skid * 0.35)), 4, font)
        elif name == "انحراف واصطدام بجسم ثابت":
            contact_y = 430
            contact_x = _road_x(contact_y, 0.08 if left_lane else 0.92)
            barrier = (int(contact_x - 30), contact_y - 20)
            draw.rectangle([barrier[0], barrier[1], barrier[0] + 42, barrier[1] + 86], fill="#6c757d", outline="#222222", width=2)
            draw.line([(barrier[0] + 6, barrier[1] + 10), (barrier[0] + 36, barrier[1] + 74)], fill="#ffd60a", width=4)
            draw.line([(barrier[0] + 36, barrier[1] + 10), (barrier[0] + 6, barrier[1] + 74)], fill="#ffd60a", width=4)
            yaw = -angle if left_lane else angle
            _place_front(img, car1, (contact_x + (20 if left_lane else -20), contact_y + 30), yaw)
            other_x = _lane_x(260, left_lane, False)
            _place_front(img, car2, (other_x, 230), 180)
            _skid(draw, _lane_x(560, left_lane, True), 560, skid, -40 if left_lane else 40)
            _impact(draw, contact_x, contact_y + 10, 54)
            _badge(draw, (int(_road_x(90, 0.2)), 70), 1, font)
            _badge(draw, (int(other_x - 40), 250), 2, font)
            _badge(draw, (barrier[0] - 10, barrier[1] + 90), 3, font)
            _badge(draw, (int(_lane_x(700, left_lane, True)), 730), 4, font)
        elif name == "انقلاب":
            lane_x = _lane_x(480, left_lane, True)
            rolled = _rolled_sprite(vehicle1_type, color1)
            img.paste(rolled, (int(lane_x - 90), 390), rolled)
            other_x = _lane_x(300, left_lane, False)
            _place_front(img, car2, (other_x, 260), 180)
            _skid(draw, lane_x - 10, 500, skid, 20 if left_lane else -20)
            _impact(draw, lane_x, 430, 58)
            _badge(draw, (int(_road_x(90, 0.18)), 70), 1, font)
            _badge(draw, (int(other_x + 40), 280), 2, font)
            _badge(draw, (int(lane_x + 70), 400), 3, font)
            _badge(draw, (int(lane_x - 50), min(790, 560 + skid * 0.3)), 4, font)
        elif name == "دهس":
            lane_x = _lane_x(430, left_lane, True)
            zebra_y = 390
            x0 = _road_x(zebra_y, 0.08)
            x1 = _road_x(zebra_y, 0.92)
            step = x0
            while step < x1:
                draw.rectangle([step, zebra_y, step + 16, zebra_y + 46], fill="white")
                step += 30
            _person(draw, lane_x, zebra_y + 8)
            _place_front(img, car1, (lane_x, zebra_y + 70), 0)
            shoulder_x = _road_x(260, 0.04 if left_lane else 0.96)
            _place_front(img, car2, (shoulder_x, 240), 90 if left_lane else -90)
            _skid(draw, lane_x - 16, zebra_y + 200, skid)
            _impact(draw, lane_x, zebra_y + 16, 46)
            _badge(draw, (int(_road_x(90, 0.18)), 70), 1, font)
            _badge(draw, (int(lane_x + 56), zebra_y + 90), 2, font)
            _badge(draw, (int(lane_x - 70), zebra_y - 10), 3, font)
            _badge(draw, (int(lane_x + 40), min(790, zebra_y + 230 + skid * 0.25)), 4, font)
        else:
            contact_y = 450
            contact_x = _lane_x(contact_y, left_lane, True)
            _place_front(img, car1, (contact_x, contact_y), 0)
            yaw = -(180 - angle) if left_lane else (180 - angle)
            _place_front(img, car2, (contact_x, contact_y - 6), yaw)
            _skid(draw, contact_x - 18, contact_y + 150, skid)
            _impact(draw, contact_x, contact_y)
            _badge(draw, (int(_road_x(90, 0.18)), 70), 1, font)
            _badge(draw, (int(contact_x - 70), contact_y + 80), 2, font)
            _badge(draw, (int(contact_x + 46), contact_y - 36), 3, font)
            _badge(draw, (int(contact_x + 10), min(790, contact_y + 170 + skid * 0.25)), 4, font)
    _compass(draw, font)
    return img.convert("RGB")

_absorb_groq_env()
try:
    SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
def _find_bayyinah_logo():
    folder = Path(__file__).resolve().parent
    for name in ("bayyinah_logo.jpg", "bayyinah_logo.png"):
        candidate = folder / name
        if not candidate.is_file():
            continue
        try:
            with Image.open(candidate) as logo_image:
                logo_image.verify()
        except OSError:
            continue
        return candidate
    return None

_bayyinah_logo_path = _find_bayyinah_logo()

def _bayyinah_logo_ready():
    return _bayyinah_logo_path is not None

_ui_icon_path = Path(__file__).resolve().parent / "bayyinah_logo.jpg"
_page_icon = "🚨"
if _ui_icon_path.is_file():
    try:
        _page_icon = Image.open(_ui_icon_path)
    except OSError:
        _page_icon = str(_ui_icon_path)
st.set_page_config(
    page_title="منظومة بينة الذكي للحوادث المرورية",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# === BAYYINAH_PERSIST_HOOK_START ===
import bayyinah_persistence as _bayyinah_persist
import bayyinah_a4_fitter as _bayyinah_a4
_bayyinah_persist.activate(__file__)
_bayyinah_a4.install_report_fitter()
# === BAYYINAH_PERSIST_HOOK_END ===

# === PERSISTENT_AUTOSAVE_START ===
# نسخة احتياطية خفيفة بجانب المسودة اليدوية (bayyinah_autosave_draft.json) — لا تمنع تحميل المسودة.
_PERSIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bayyinah_saved_state.json")
_PERSIST_SKIP_KEYS = frozenset({
    "state_initialized",
    "_persist_restored_ok",
    "_last_persisted_stamp",
    "_save_success_banner",
    "_sidebar_save_ok",
    "confirm_clear",
    "mobile_gallery_uploader",
    "video_bulk_files",
})
_PERSIST_SKIP_PREFIXES = (
    "FormSubmitter:",
    "button",
    "_persist",
    "_top_cmd_",
    "_sidebar_save",
    "mobile_gallery_uploader_",
    "clip_file_",
    "camera_input_",
)

def _is_persist_file_camera_key(key: str) -> bool:
    ks = str(key or "")
    if ks in ("mobile_gallery_uploader", "video_bulk_files"):
        return True
    if ks.startswith("mobile_gallery_uploader_") or ks.startswith("clip_file_") or ks.startswith("camera_input_"):
        return True
    if ks.endswith("_uploader") or ks.endswith("_camera") or "camera_input" in ks:
        return True
    return False

_BAYYINAH_JSON_DATA_WHITELIST = frozenset({
    SAVED_ACC_NUMBER, SAVED_ACC_LOCATION, SAVED_ACC_CAUSE,
    "p1_acc_number", "p1_acc_location", "p1_acc_cause",
    "hijri_date", "p1_acc_date", "p1_acc_time", "hijri_manual_date",
    "p1_acc_type", "p1_acc_weather", "p1_acc_injuries", "p1_acc_deaths",
    "p1_parties_records", "p1_vehicles_records", "parties", "vehicles",
    "selected_articles", "accident_results", "technical_description",
    "legal_opinion", "p1_reasons", "p2_reasons", "liability_html",
    "accident_nature", "rights_status", "gallery_photos", "accident_photos_data",
    "active_tab", "last_saved_time", "acc_loc_value",
    *TAB3_LOCKED_SAVED_KEYS,
    *TAB3_LOCKED_MANUAL_KEYS,
    *TAB3_LOCKED_REV_KEYS,
    *RESULTS_EXTRA_SAVED_KEYS,
})

def _is_persist_ui_widget_key(key: str) -> bool:
    ks = str(key or "")
    if _is_persist_file_camera_key(ks):
        return True
    if ks in WIDGET_TO_SAVED_ACC or ks in ("p1_acc_type_choice", "p1_acc_weather_choice"):
        return True
    if ks in RESULTS_EXTRA_WIDGET_KEYS:
        return True
    # ودجات text_area المقفلة + زر الاستعادة — ليست بيانات
    if "_ta_" in ks or ks.startswith("restore_auto_"):
        return True
    kl = ks.lower()
    if ks.startswith("FormSubmitter:") or "download" in kl or "form_submit" in kl:
        return True
    if "_btn_" in kl or "button" in kl or ks.endswith("_editor") or "data_editor" in kl:
        return True
    if ks.endswith("_manual_in") or ks.endswith("_sel_month_ui") or ks.endswith("_sel_year_ui"):
        return True
    if "_lux_" in ks:
        return True
    return False

def _save_bayyinah_state():
    """نسخة احتياطية JSON — whitelist بيانات فقط بلا مفاتيح ودجات."""
    data = {}
    # ادفع الودجات → saved_acc_* قبل الحفظ
    for widget_key, saved_key in WIDGET_TO_SAVED_ACC.items():
        if widget_key in st.session_state and not _is_blank_p1_value(st.session_state.get(widget_key)):
            st.session_state[saved_key] = st.session_state.get(widget_key)
    for ks in _BAYYINAH_JSON_DATA_WHITELIST:
        if ks not in st.session_state:
            continue
        if _is_persist_ui_widget_key(ks):
            continue
        v = st.session_state.get(ks)
        if hasattr(v, "to_dict"):
            try:
                data[ks] = {"__df_records__": v.to_dict("records")}
                continue
            except Exception:
                pass
        try:
            json.dumps(v, ensure_ascii=False, default=str)
            data[ks] = v
        except Exception:
            continue
    try:
        with open(_PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return True
    except Exception:
        return False

def _load_bayyinah_state_once():
    """استعادة whitelist فقط — بلا حلقة تعيين على كل مفاتيح الجلسة."""
    if st.session_state.get("_persist_restored_ok"):
        return
    st.session_state["_persist_restored_ok"] = True
    if not os.path.exists(_PERSIST_FILE):
        return
    # إن وُجدت مسودة يدوية فهي المصدر المعتمد عند init_and_load_state
    if os.path.exists(DRAFT_FILE_PATH):
        return
    try:
        with open(_PERSIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
        for k, v in data.items():
            ks = str(k)
            if ks not in _BAYYINAH_JSON_DATA_WHITELIST:
                continue
            if _is_persist_ui_widget_key(ks) or ks in _PERSIST_SKIP_KEYS:
                # رحّل p1_acc_* → saved_acc_*
                if ks in WIDGET_TO_SAVED_ACC and not _is_blank_p1_value(v):
                    saved_key = WIDGET_TO_SAVED_ACC[ks]
                    if saved_key not in st.session_state or _is_blank_p1_value(st.session_state.get(saved_key)):
                        st.session_state[saved_key] = v
                continue
            if ks in st.session_state and not _is_blank_p1_value(st.session_state.get(ks)):
                continue
            if isinstance(v, dict) and "__df_records__" in v:
                try:
                    st.session_state[ks] = pd.DataFrame(v["__df_records__"])
                except Exception:
                    st.session_state[ks] = v["__df_records__"]
            else:
                st.session_state[ks] = v
    except Exception:
        pass

def _clear_bayyinah_saved_state():
    try:
        if os.path.exists(_PERSIST_FILE):
            os.remove(_PERSIST_FILE)
    except Exception:
        pass
    for stale in ("bayyinah_saved_state.json",):
        try:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), stale)
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

_load_bayyinah_state_once()
# === PERSISTENT_AUTOSAVE_END ===

st.markdown("""<style id="tags-red-only">
@media screen {
  /* تلوين العناصر المختارة فقط في قائمتي المواد النظامية والإجراءات باللون الأحمر الهادئ */
  html body div#root [data-testid="stAppViewContainer"] [data-testid="stMultiSelect"] span[data-baseweb="tag"],
  html body div#root [data-testid="stAppViewContainer"] span[data-baseweb="tag"] {
    background: #991b1b !important;
    background-color: #991b1b !important;
    color: #ffffff !important;
    border: 1px solid #fca5a5 !important;
    box-shadow: none !important;
    text-shadow: none !important;
}
  html body div#root [data-testid="stAppViewContainer"] span[data-baseweb="tag"] *,
  html body div#root [data-testid="stAppViewContainer"] span[data-baseweb="tag"] svg {
    background: #991b1b !important;
    background-color: #991b1b !important;
    color: #ffffff !important;
    border: 1px solid #fca5a5 !important;
    box-shadow: none !important;
    text-shadow: none !important;
}
}

</style>""", unsafe_allow_html=True)

st.components.v1.html(
    """
<script>
(function () {
  var parentWin;
  try {
    parentWin = window.parent;
  } catch (err) {
    return;
  }
  if (!parentWin || !parentWin.document || !parentWin.document.head) return;
  if (!parentWin.document.querySelector('link[rel="manifest"][data-bayyinah-manifest]')) {
    var link = parentWin.document.createElement("link");
    link.rel = "manifest";
    link.href = new parentWin.URL("manifest.json", parentWin.location.href).href;
    link.setAttribute("data-bayyinah-manifest", "1");
    parentWin.document.head.appendChild(link);
  }
  if ("serviceWorker" in parentWin.navigator && !parentWin.__bayyinahSwRegistered) {
    parentWin.__bayyinahSwRegistered = true;
    parentWin.navigator.serviceWorker
      .register(new parentWin.URL("sw.js", parentWin.location.href).href)
      .catch(function () {});
  }
  if (parentWin.__bayyinahInstallBound) return;
  parentWin.__bayyinahInstallBound = true;
  parentWin.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    parentWin.deferredPrompt = event;
  });
})();
</script>
    """,
    height=0,
)
# تنسيق واجهة البرنامج باللون الأخضر الرسمي
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        direction: rtl;
        text-align: right;
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    section[data-testid="stSidebar"],
    [data-testid="stSidebarContent"] {
        background: #0a192f !important;
        color: #e2eafc;
    }
    section[data-testid="stSidebar"] {
        display: flex !important;
    }
    [data-testid="stLogo"],
    [data-testid="stLogoSpacer"] {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .main .block-container {
        max-width: 100% !important;
        width: 100% !important;
    }
    [data-testid="stHeader"] {
        background: #0a192f !important;
    }
    h1, h2, h3,
    [data-testid="stHeading"],
    [data-testid="stHeading"] h1,
    [data-testid="stHeading"] h2,
    [data-testid="stHeading"] h3,
    [data-testid="stHeading"] span,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stCaptionContainer"] p {
        color: #e2eafc !important;
        font-family: 'Tajawal', sans-serif;
    }
    .glow-container,
    [class*="st-key-glow"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(0, 242, 254, 0.45);
        border-radius: 16px;
        padding: 16px 18px;
        margin-bottom: 14px;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.28), inset 0 0 12px rgba(79, 172, 254, 0.08);
    }
    .bayyinah-hero {
        direction: rtl;
        display: flex;
        align-items: center;
        gap: 22px;
        background:
            linear-gradient(145deg, #071422 0%, #0a192f 58%, #102a43 100%) padding-box,
            linear-gradient(120deg, #00f2fe, #4facfe) border-box;
        border: 2px solid transparent;
        border-radius: 18px;
        padding: 18px 22px;
        margin: 4px 0 16px;
        box-shadow: 0 0 22px rgba(0, 242, 254, 0.45), 0 0 48px rgba(79, 172, 254, 0.28);
    }
    .bayyinah-logo-ring {
        width: 112px;
        height: 112px;
        flex: 0 0 112px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        line-height: 1.25;
        font-weight: 700;
        font-size: 14px;
        color: #e8f7ff;
        background: radial-gradient(circle at 40% 35%, #16365c, #071422 72%);
        border: 2px solid #4facfe;
        box-shadow: 0 0 16px #00f2fe, 0 0 34px rgba(79, 172, 254, 0.75);
    }
    .bayyinah-logo-ring img {
        width: 94px;
        height: 94px;
        border-radius: 50%;
        object-fit: cover;
    }
    .logo-fallback { display: none; font-weight: 700; line-height: 1.25; }
    .bayyinah-logo-ring.show-fallback .logo-fallback { display: block; }
    .bh-word {
        color: #ffffff;
        font-size: 34px;
        font-weight: 700;
        letter-spacing: 1px;
        text-shadow: 0 0 14px rgba(0, 242, 254, 0.85);
        line-height: 1.1;
    }
    .bh-1 { color: #00f2fe; font-size: 22px; font-weight: 700; text-shadow: 0 0 12px rgba(0, 242, 254, 0.75); }
    .bh-2 { color: #ffffff; font-size: 18px; font-weight: 700; letter-spacing: 3px; margin-top: 2px; }
    .bh-3 { color: #e2eafc; font-size: 22px; font-weight: 700; margin-top: 2px; }
    .bh-4 { color: #b7d4f0; font-size: 15px; font-weight: 700; margin-top: 4px; }
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stExpander"],
    [data-testid="stDataFrame"],
    [data-testid="stDataEditor"],
    [data-testid="stFileUploader"] section,
    [data-testid="stAlert"],
    iframe[title="st.iframe"] {
        border-radius: 14px !important;
        box-shadow: 0 0 16px rgba(0, 242, 254, 0.22) !important;
    }
    [data-testid="stTextInput"] [data-baseweb="input"],
    [data-testid="stNumberInput"] [data-baseweb="input"],
    [data-testid="stDateInput"] [data-baseweb="input"],
    [data-testid="stTimeInput"] [data-baseweb="input"],
    [data-testid="stTextArea"] [data-baseweb="textarea"],
    [data-testid="stTextArea"] [data-baseweb="base-input"],
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
    [data-testid="stDateInput"] [data-baseweb="select"] > div,
    [data-testid="stTimeInput"] [data-baseweb="select"] > div,
    [data-testid="stTextInputRootElement"],
    [data-testid="stTextAreaRootElement"],
    [data-testid="stNumberInputContainer"],
    [data-testid="stSelectbox"] .react-aria-ComboBox > div,
    [data-testid="stMultiSelect"] .react-aria-ComboBox > div,
    [data-testid="stSelectboxVirtualDropdown"],
    [data-testid="stMultiSelectVirtualDropdown"] {
        background: linear-gradient(180deg, #1b6cb8 0%, #14508f 100%) !important;
        color: #f7fcff !important;
        border: 1px solid #7ad7ff !important;
        border-radius: 10px !important;
        box-shadow: 0 0 14px rgba(0, 229, 255, 0.34), inset 0 0 10px rgba(0, 242, 254, 0.12) !important;
    }
    [data-testid="stRadioOption"] {
        background: linear-gradient(180deg, rgba(27, 108, 184, 0.72), rgba(20, 80, 143, 0.72)) !important;
        border: 1px solid #7ad7ff !important;
        border-radius: 10px !important;
        padding: 4px 10px !important;
    }
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stTimeInput"] input,
    [data-testid="stSelectbox"] input,
    [data-testid="stMultiSelect"] input {
        background: transparent !important;
        color: #f7fcff !important;
        -webkit-text-fill-color: #f7fcff !important;
        caret-color: #00f2fe !important;
        border: 0 !important;
        box-shadow: none !important;
    }
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stTextArea"] textarea::placeholder,
    [data-testid="stNumberInput"] input::placeholder,
    [data-testid="stSelectbox"] input::placeholder,
    [data-testid="stMultiSelect"] input::placeholder {
        color: #d7f3ff !important;
        -webkit-text-fill-color: #d7f3ff !important;
        opacity: 1 !important;
    }
    [data-testid="stTextInput"] input:-webkit-autofill,
    [data-testid="stTextArea"] textarea:-webkit-autofill,
    [data-testid="stNumberInput"] input:-webkit-autofill {
        -webkit-box-shadow: 0 0 0 1000px #14508f inset !important;
        -webkit-text-fill-color: #f7fcff !important;
    }
    [data-testid="stTextInput"] [data-baseweb="input"]:focus-within,
    [data-testid="stNumberInput"] [data-baseweb="input"]:focus-within,
    [data-testid="stDateInput"] [data-baseweb="input"]:focus-within,
    [data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within,
    [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within {
        border-color: #00f2fe !important;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.62) !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] span,
    [data-testid="stMultiSelect"] [data-baseweb="select"] span,
    [data-testid="stSelectbox"] [data-baseweb="select"] div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] div {
        color: #f7fcff !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="tag"],
    [data-testid="stMultiSelect"] span[data-baseweb="tag"],
    span[data-baseweb="tag"] {
    background: #991b1b !important;
    background-color: #991b1b !important;
    color: #ffffff !important;
    border: 1px solid #fca5a5 !important;
    box-shadow: none !important;
    text-shadow: none !important;
}
    [data-testid="stMultiSelect"] [data-baseweb="tag"] span,
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] span,
    span[data-baseweb="tag"] span {
    background: #991b1b !important;
    background-color: #991b1b !important;
    color: #ffffff !important;
    border: 1px solid #fca5a5 !important;
    box-shadow: none !important;
    text-shadow: none !important;
}
    [data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] svg,
    span[data-baseweb="tag"] svg {
    background: #991b1b !important;
    background-color: #991b1b !important;
    color: #ffffff !important;
    border: 1px solid #fca5a5 !important;
    box-shadow: none !important;
    text-shadow: none !important;
}
    [data-testid="stSelectbox"] svg,
    [data-testid="stMultiSelect"] svg,
    [data-testid="stDateInput"] svg,
    [data-testid="stNumberInput"] svg {
        fill: #00f2fe !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
    span[data-baseweb="tag"] svg {
    background: #991b1b !important;
    background-color: #991b1b !important;
    color: #ffffff !important;
    border: 1px solid #fca5a5 !important;
    box-shadow: none !important;
    text-shadow: none !important;
}
    [data-testid="stNumberInput"] button {
        background: #1d6ec4 !important;
        color: #f7fcff !important;
        border: 1px solid #7ad7ff !important;
    }
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="calendar"],
    [data-baseweb="datepicker"],
    ul[role="listbox"] {
        background: #0f4f92 !important;
        color: #f7fcff !important;
        border: 1px solid #7ad7ff !important;
        border-radius: 10px !important;
        box-shadow: 0 0 18px rgba(0, 229, 255, 0.35) !important;
    }
    [role="option"],
    li[role="option"] {
        background: #1460a8 !important;
        color: #f7fcff !important;
    }
    [role="option"] *,
    li[role="option"] * {
        color: #f7fcff !important;
    }
    [role="option"]:hover,
    [role="option"][aria-selected="true"],
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {
        background: #1e3a8a !important;
        color: #ffffff !important;
    }
    [role="option"]:hover *,
    [role="option"][aria-selected="true"] *,
    li[role="option"]:hover *,
    li[role="option"][aria-selected="true"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    [data-testid="stRadio"] [role="radiogroup"] label,
    [data-testid="stCheckbox"] label {
        background: linear-gradient(180deg, rgba(27, 108, 184, 0.55), rgba(20, 80, 143, 0.55));
        border: 1px solid rgba(122, 215, 255, 0.7);
        border-radius: 10px;
        padding: 4px 10px;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(10, 28, 52, 0.85) !important;
        border: 1.5px dashed rgba(56, 189, 248, 0.65) !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
    }
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] div {
        color: #e0f2fe !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        background: linear-gradient(135deg, #0284c7, #38bdf8) !important;
        color: #031527 !important;
        font-weight: 800 !important;
        border: none !important;
    }
    [data-testid="stSlider"] [role="slider"] {
        background: #00f2fe !important;
        box-shadow: 0 0 10px rgba(0, 242, 254, 0.8) !important;
    }
    .stTabs [data-baseweb="tab-list"],
    .stTabs [role="tablist"] {
        gap: 8px;
        background: transparent;
        flex-wrap: wrap !important;
        overflow: visible !important;
    }
    .stTabs [data-baseweb="tab"],
    .stTabs [data-testid="stTab"] {
        background: #12263f !important;
        color: #d6f4ff !important;
        border-radius: 10px !important;
        padding: 10px 16px;
        font-weight: 500 !important;
        border: 1px solid rgba(0, 242, 254, 0.45) !important;
        box-shadow: 0 0 10px rgba(79, 172, 254, 0.28);
    }
    .stTabs [data-testid="stTab"]:hover {
        background: #1d4f86 !important;
        color: #ffffff !important;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.7);
    }
    .stTabs [data-testid="stTab"]:hover {
        
    }
    .stTabs [aria-selected="true"],
    .stTabs [data-testid="stTab"][aria-selected="true"] {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
        color: #0a192f !important;
        font-weight: 700 !important;
        border-color: #00f2fe !important;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.8);
    }
    .stTabs [aria-selected="true"] p,
    .stTabs [aria-selected="true"] span,
    .stTabs [aria-selected="true"] div {
        color: #0a192f !important;
        font-weight: 700 !important;
    }
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]):hover p,
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]):hover span {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]) p,
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]) span,
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]) div {
        color: #d6f4ff !important;
        font-weight: 500 !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #00f2fe !important; }
    .stTabs [data-baseweb="tab-border"] { background-color: rgba(79, 172, 254, 0.35) !important; }
    div.stButton > button,
    div.stDownloadButton > button,
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
        color: #041426 !important;
        -webkit-text-fill-color: #041426 !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-family: 'Tajawal', sans-serif !important;
        text-shadow: none !important;
        box-shadow: 0 0 14px rgba(0, 242, 254, 0.4);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div.stButton > button:hover,
    div.stDownloadButton > button:hover,
    [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
        color: #041426 !important;
        -webkit-text-fill-color: #041426 !important;
        
        box-shadow: 0 0 22px rgba(0, 242, 254, 0.9);
    }
    div.stButton > button p,
    div.stDownloadButton > button p,
    div.stButton > button span,
    div.stDownloadButton > button span,
    [data-testid="stBaseButton-secondary"] p,
    [data-testid="stBaseButton-primary"] p,
    [data-testid="stBaseButton-secondary"] span,
    [data-testid="stBaseButton-primary"] span {
        color: #041426 !important;
        -webkit-text-fill-color: #041426 !important;
        font-weight: 700 !important;
        text-shadow: none !important;
    }
    iframe[title="st.iframe"] {
        background: #0d2137 !important;
        border-radius: 14px;
        border: 1px solid rgba(0, 242, 254, 0.35) !important;
    }
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarHeader"] button,
    button[kind="headerNoPadding"] {
        background-color: rgba(0, 229, 255, 0.18) !important;
        border: 2px solid #00e5ff !important;
        border-radius: 10px !important;
        box-shadow: 0 0 15px #00e5ff, 0 0 25px rgba(0, 229, 255, 0.6), inset 0 0 8px rgba(0, 229, 255, 0.45) !important;
        z-index: 999999 !important;
    }
    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stExpandSidebarButton"] svg,
    [data-testid="stSidebarCollapseButton"] button svg,
    [data-testid="stSidebarHeader"] button svg,
    button[kind="headerNoPadding"] svg {
        fill: #00e5ff !important;
        stroke: #00e5ff !important;
        width: 24px !important;
        height: 24px !important;
    }
    @media screen and (max-width: 768px) {
        html, body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        .main,
        .block-container,
        .main .block-container {
            margin-left: 0 !important;
            margin-right: 0 !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            transform: none !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }
        .main .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 2rem !important;
        }
        [data-testid="stSidebar"][aria-expanded="false"],
        [data-testid="stSidebar"][data-collapsed="true"] {
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            box-shadow: none !important;
            transform: none !important;
            overflow: hidden !important;
        }
        [data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarResizeHandle"] {
            display: none !important;
            width: 0 !important;
            background: none !important;
            box-shadow: none !important;
        }
        iframe {
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }
        .stTabs [data-baseweb="tab-list"],
        .stTabs [role="tablist"] {
            flex-wrap: wrap !important;
        }
        h1 { font-size: 1.3rem !important; }
        h2 { font-size: 1.1rem !important; }
        h3 { font-size: 1rem !important; }
    }
    @media print {
        @page { size: A4; margin: 0; }
        section[data-testid="stSidebar"],
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"],
        [data-testid="stSidebarHeader"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        .stButton, .stDownloadButton, button {
            display: none !important;
        }
        .main .block-container {
            max-width: 210mm !important;
            width: 210mm !important;
            padding: 0 !important;
            margin: 0 !important;
        }
    }
    .officer-role-card { background: rgba(8, 25, 48, 0.75); border: 1px solid rgba(56, 189, 248, 0.35); border-right: 3.5px solid #38bdf8; border-radius: 10px; padding: 8px 10px 4px 10px; margin: 10px 0 6px 0; }
    .officer-role-title { font-size: 13px; font-weight: 800; color: #7dd3fc; margin-bottom: 4px; }
    section[data-testid="stSidebar"] > div:first-child { padding-bottom: 85px !important; }
    div[data-testid="stPopover"] > button p { font-size: 13px !important; white-space: nowrap !important; overflow: visible !important; }
    .st-key-officer_role_direct,
    .st-key-officer_role_supervisor,
    .st-key-officer_role_manager {
        background: rgba(8, 25, 48, 0.75);
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-right: 3.5px solid #38bdf8;
        border-radius: 10px;
        padding: 8px 10px 4px 10px;
        margin: 10px 0 6px 0;
    }
    .st-key-officer_role_direct .officer-role-card,
    .st-key-officer_role_supervisor .officer-role-card,
    .st-key-officer_role_manager .officer-role-card {
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
    }

</style>
""", unsafe_allow_html=True)
init_and_load_state()
init_and_restore_page1_state()
inject_bayyinah_blue_styles()
if 'parties' not in st.session_state:
    st.session_state.parties = _clone_page1_value(st.session_state.get("p1_parties_records") or _blank_parties())
if 'vehicles' not in st.session_state:
    st.session_state.vehicles = _clone_page1_value(st.session_state.get("p1_vehicles_records") or _blank_vehicles())
with st.sidebar:
    if _bayyinah_logo_ready():
        try:
            st.image(str(_bayyinah_logo_path), width=148)
        except OSError:
            pass
    st.markdown("### بَيِّنَةُ الذكي للحوادث")
    (
        dept_region,
        dept_branch,
        officer_1_name,
        officer_1_rank,
        officer_2_name,
        officer_2_rank,
        manager_name,
        manager_rank,
    ) = render_persistent_sidebar_settings()
header_slot = st.container()
if "active_tab" not in st.session_state:
    st.session_state.active_tab = MAIN_TAB_OPTIONS[0]
if st.session_state.get("active_tab") not in MAIN_TAB_OPTIONS:
    st.session_state.active_tab = MAIN_TAB_OPTIONS[0]
# قيم افتراضية آمنة لحقول A4 قبل أي تبويب (لا تعتمد على متغيرات محلية)
for _a4_key, _a4_default in (
    ("accident_nature", DEFAULT_REPORT_STATE.get("accident_nature", "")),
    ("rights_status", DEFAULT_REPORT_STATE.get("rights_status", "")),
    ("accident_results", ""),
    ("technical_description", ""),
    ("p1_reasons", DEFAULT_REPORT_STATE.get("p1_reasons", "")),
    ("p2_reasons", DEFAULT_REPORT_STATE.get("p2_reasons", "")),
    ("p1_title_input", DEFAULT_REPORT_STATE.get("p1_title_input", "قائد المركبة الأولى")),
    ("p2_role_select", DEFAULT_REPORT_STATE.get("p2_role_select", "قائد المركبة الثانية")),
    ("p2_custom_title", DEFAULT_REPORT_STATE.get("p2_custom_title", "")),
    ("p2_title", DEFAULT_REPORT_STATE.get("p2_role_select", "قائد المركبة الثانية")),
    ("actions_taken_editor", ""),
    ("liability_html", ""),
    ("p1_ratio", 100),
    ("p2_ratio", 0),
    ("criminal_participating_agency", ""),
    ("criminal_escaped_vehicles", ""),
    ("criminal_shots_fired", "لا"),
    ("criminal_contraband_found", "لم يتم العثور على ممنوعات"),
):
    if _a4_key not in st.session_state:
        st.session_state[_a4_key] = _a4_default
# حقن ظل التبويب3 فوق الافتراضات الفارغة في كل دورة
try:
    reinject_permanent_form_data()
except Exception:
    pass
if "parties" not in st.session_state:
    st.session_state.parties = _blank_parties()
if "vehicles" not in st.session_state:
    st.session_state.vehicles = _blank_vehicles()
st.markdown(
    """
    <style>
    div[data-testid="stRadio"][aria-label="active_tab"] > div,
    div[data-testid="stRadio"]:has(> label) {
        gap: 0.35rem !important;
    }
    div[role="radiogroup"] label[data-baseweb="radio"] {
        background: linear-gradient(135deg, rgba(8, 56, 114, 0.92), rgba(4, 38, 84, 0.95)) !important;
        border: 1.4px solid rgba(56, 189, 248, 0.55) !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
        box-shadow: 0 0 10px rgba(0, 210, 255, 0.18) !important;
        color: #e0f2fe !important;
        font-weight: 800 !important;
    }
    div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.45) !important;
        background: linear-gradient(135deg, #0284c7, #0369a1) !important;
        color: #ffffff !important;
    }
    
</style>
    """,
    unsafe_allow_html=True,
)
def _on_active_tab_change():
    try:
        ensure_core_accident_fields_from_vault()
        sync_page1_to_vault(
            extra_keys=list(PAGE1_EXTRA_SYNC_KEYS),
            write_disk=True,
            allow_blank_overwrite=False,
        )
    except Exception:
        pass
    try:
        sync_permanent_form_data(reason="tab_change")
    except Exception:
        pass
    try:
        import bayyinah_persistence as _bp
        _bp.on_tab_change()
    except Exception:
        try:
            perform_manual_save(show_toast=False)
        except Exception:
            pass

st.radio(
    "أقسام التقرير",
    options=MAIN_TAB_OPTIONS,
    horizontal=True,
    key="active_tab",
    label_visibility="collapsed",
    on_change=_on_active_tab_change,
)
if st.session_state.active_tab == MAIN_TAB_OPTIONS[0]:
    st.subheader("معلومات الحادث الأساسية")
    _acc_type_options = ["تصادم مركبتين", "دهس مشاة", "انقلاب", "تصادم متعدد", "اصطدام بجسم ثابت"]
    _acc_weather_options = ["صحو", "غائم", "ممطر", "غبار / عوالق ترابية", "ضباب"]
    _loaded_page1_keys = set(st.session_state.get("_p1_loaded_keys") or [])
    if "hijri_date" not in st.session_state:
        st.session_state.hijri_date = str(st.session_state.get("p1_acc_date") or "")
    if st.session_state.get("acc_date_override"):
        st.session_state.hijri_date = st.session_state.pop("acc_date_override")
        st.session_state.pop("hijri_date_manual_in", None)
        st.session_state.p1_acc_date = st.session_state.hijri_date
    if st.session_state.get("acc_loc_override"):
        _loc_ov = st.session_state.pop("acc_loc_override")
        st.session_state[SAVED_ACC_LOCATION] = _loc_ov
        if "p1_acc_location" not in st.session_state:
            st.session_state.p1_acc_location = _loc_ov
    elif st.session_state.get("acc_loc_value") and _is_blank_p1_value(st.session_state.get(SAVED_ACC_LOCATION)):
        st.session_state[SAVED_ACC_LOCATION] = st.session_state.get("acc_loc_value")
        if "p1_acc_location" not in st.session_state:
            st.session_state.p1_acc_location = st.session_state.get("acc_loc_value")
    # أعد حقن رقم/موقع/سبب إلى saved_acc_* وازرع الودجت بـ setdefault فقط
    ensure_core_accident_fields_from_vault()
    for _wk, _sk in WIDGET_TO_SAVED_ACC.items():
        if _wk not in st.session_state and not _is_blank_p1_value(st.session_state.get(_sk)):
            st.session_state[_wk] = st.session_state.get(_sk)
    if st.session_state.get("p1_acc_type_choice") not in _acc_type_options:
        saved_type = st.session_state.get("p1_acc_type")
        if "p1_acc_type" in _loaded_page1_keys and saved_type in _acc_type_options:
            st.session_state.p1_acc_type_choice = saved_type
        else:
            st.session_state.pop("p1_acc_type_choice", None)
    if st.session_state.get("p1_acc_weather_choice") not in _acc_weather_options:
        saved_weather = st.session_state.get("p1_acc_weather")
        if "p1_acc_weather" in _loaded_page1_keys and saved_weather in _acc_weather_options:
            st.session_state.p1_acc_weather_choice = saved_weather
        else:
            st.session_state.pop("p1_acc_weather_choice", None)
    # منتقيات الوقت والتاريخ + رقم/موقع/سبب خارج النموذج حتى تُحفظ فوراً ولا تُفقد بالتنقل
    picker_c1, picker_c2 = st.columns(2, gap="medium")
    with picker_c1:
        accident_time = render_smart_time_picker(state_key="p1_acc_time", label="الوقت")
        acc_time = accident_time
    with picker_c2:
        accident_date = render_luxury_hijri_picker(state_key="hijri_date", label="تاريخ الحادث (هجري)")
        acc_date = accident_date
        if accident_date:
            st.session_state.p1_acc_date = accident_date
            st.session_state.hijri_manual_date = accident_date

    r1_c1, r1_c2, r1_c3 = st.columns(3, gap="medium")
    with r1_c1:
        acc_num = st.text_input(
            "رقم الحادث",
            key="p1_acc_number",
            on_change=_on_core_accident_field_change,
        )
    with r1_c2:
        acc_type = st.selectbox(
            "نوع الحادث",
            _acc_type_options,
            index=None,
            placeholder="اختر نوع الحادث",
            key="p1_acc_type_choice",
        ) or ""
    with r1_c3:
        acc_injuries = st.number_input("عدد الإصابات", min_value=0, key="p1_acc_injuries")
    r2_c1, r2_c2, r2_c3 = st.columns(3, gap="medium")
    with r2_c1:
        acc_loc = st.text_input(
            "موقع الحادث",
            key="p1_acc_location",
            on_change=_on_core_accident_field_change,
        )
    with r2_c2:
        acc_weather = st.selectbox(
            "الطقس",
            _acc_weather_options,
            index=None,
            placeholder="اختر الطقس",
            key="p1_acc_weather_choice",
        ) or ""
    with r2_c3:
        acc_deaths = st.number_input("عدد الوفيات", min_value=0, key="p1_acc_deaths")
    acc_cause = st.text_input(
        "سبب الحادث الرئيسي (المختصر)",
        key="p1_acc_cause",
        on_change=_on_core_accident_field_change,
    )
    # مزامنة فورية للخزنة دون طمس القيم بنص فارغ
    sync_page1_to_vault(
        extra_keys=list(PAGE1_EXTRA_SYNC_KEYS),
        write_disk=True,
        allow_blank_overwrite=False,
    )

    _party_columns = list(_PARTY_TABLE_COLUMNS)
    _vehicle_columns = list(_VEHICLE_TABLE_COLUMNS)
    _normalized_parties, _qual_changed = _normalize_party_qualification_rows(st.session_state.get("parties"))
    st.session_state.parties = _normalized_parties
    _saved_party_records, _saved_qual_changed = _normalize_party_qualification_rows(st.session_state.get("p1_parties_records"))
    if _saved_qual_changed:
        st.session_state.p1_parties_records = _saved_party_records
    _editor_parties = st.session_state.get("p1_parties_editor")
    if isinstance(_editor_parties, pd.DataFrame) and not _editor_parties.empty:
        _editor_clean, _editor_changed = _normalize_party_qualification_rows(_frame_records(_editor_parties))
        if _editor_changed or _qual_changed or _saved_qual_changed:
            st.session_state.p1_parties_editor = pd.DataFrame(_editor_clean)
    elif _qual_changed or _saved_qual_changed:
        st.session_state.pop("p1_parties_editor", None)
    parties_df_seed = fill_smart_table_defaults(pd.DataFrame(st.session_state.parties), PARTY_SMART_DEFAULTS)
    if not parties_df_seed.empty:
        _seed_rows, _ = _normalize_party_qualification_rows(_frame_records(parties_df_seed))
        parties_df_seed = pd.DataFrame(_seed_rows)
    if isinstance(st.session_state.get("p1_parties_editor"), pd.DataFrame):
        _ed = fill_smart_table_defaults(st.session_state.p1_parties_editor, PARTY_SMART_DEFAULTS)
        _ed_rows, _ = _normalize_party_qualification_rows(_frame_records(_ed) if not _ed.empty else [])
        st.session_state.p1_parties_editor = pd.DataFrame(_ed_rows) if _ed_rows else _ed
    vehicles_source = fill_smart_table_defaults(pd.DataFrame(st.session_state.vehicles), VEHICLE_SMART_DEFAULTS)
    if isinstance(st.session_state.get("p1_vehicles_editor"), pd.DataFrame):
        st.session_state.p1_vehicles_editor = fill_smart_table_defaults(st.session_state.p1_vehicles_editor, VEHICLE_SMART_DEFAULTS)

    with st.form("page1_accident_data_form", border=False, clear_on_submit=False):
        st.subheader("جدول معلومات أطراف الحادث")
        parties_df = st.data_editor(
            parties_df_seed,
            key="p1_parties_editor",
            num_rows="dynamic",
            use_container_width=True,
            column_order=[key for key, _label in reversed(_party_columns)],
            column_config={
                "الطرف": st.column_config.TextColumn("الأطراف"),
                "الاسم": st.column_config.TextColumn("الاسم"),
                "الهوية": st.column_config.TextColumn("الهوية / الإقامة"),
                "المشاركة": st.column_config.SelectboxColumn("نوع المشاركة", options=["", "سائق", "راكب", "مشاة"]),
                "الحالة": st.column_config.SelectboxColumn("الحالة الصحية", options=["", "سليم", "مصاب", "متوفي"]),
                "التأهيل": st.column_config.SelectboxColumn(
                    "تأهيل للقيادة",
                    options=QUALIFICATION_OPTIONS,
                    default="مؤهل للقيادة",
                    required=False,
                ),
            }
        )
        # شريط بطاقات فوري من قيم المحرر الحالية (قبل الاعتماد أيضاً)
        try:
            _live_party_rows = _frame_records(parties_df) if isinstance(parties_df, pd.DataFrame) else []
            _live_party_rows, _ = _normalize_party_qualification_rows(_live_party_rows)
            _render_party_role_cards(_live_party_rows)
        except Exception:
            pass
        st.divider()
        st.subheader("جدول معلومات المركبات")
        vehicles_df = st.data_editor(
            vehicles_source,
            key="p1_vehicles_editor",
            num_rows="dynamic",
            use_container_width=True,
            column_order=[key for key, _label in reversed(_vehicle_columns)],
            column_config={
                "الطرف": st.column_config.TextColumn("الأطراف"),
                "نوع المركبة": st.column_config.TextColumn("نوع المركبة"),
                "رقم اللوحة": st.column_config.TextColumn("رقم اللوحة"),
                "الرقم التسلسلي": st.column_config.TextColumn("الرقم التسلسلي"),
                "نوع الترخيص": st.column_config.SelectboxColumn("نوع الترخيص", options=["", "خصوصي", "نقل خاص", "نقل عام", "دراجة آلية"]),
                "التأمين": st.column_config.SelectboxColumn("التأمين", options=["", "ساري", "مؤمنة", "غير مؤمنة"]),
            }
        )
        page1_submitted = st.form_submit_button("💾 اعتماد بيانات الحادث والأطراف", use_container_width=True)

    inject_rtl_tab_for_data_editors()
    if page1_submitted:
        raw_parties = _frame_records(parties_df)
        cleaned_parties, _ = _normalize_party_qualification_rows(raw_parties)
        st.session_state.parties = cleaned_parties
        st.session_state.vehicles = _frame_records(vehicles_df)
        st.session_state.p1_parties_records = _clone_page1_value(st.session_state.parties)
        st.session_state.p1_vehicles_records = _clone_page1_value(st.session_state.vehicles)
        # لا تنبيه رخصة للراكب/المشاة؛ تنبيه السائق غير المؤهل فقط
        _unqual_drivers = _unqualified_driver_parties(cleaned_parties)
        for _p in cleaned_parties:
            if _is_non_driver_role(_p.get("المشاركة")):
                continue
        if _unqual_drivers:
            _names = "، ".join(
                (_p.get("الطرف") or _p.get("الاسم") or "سائق") for _p in _unqual_drivers
            )
            st.warning(f"تنبيه رخصة قيادة: {_names} غير مؤهل للقيادة (السائقون فقط).")
        refresh_party_role_titles(
            parties=cleaned_parties,
            vehicles=st.session_state.vehicles,
            force=True,
        )
        _mirror_page1_fields()
        # اعتماد النموذج = مزامنة الجلسة + حفظ يدوي على القرص (بدون كسر نموذج الحفظ اليدوي)
        if perform_manual_save(show_toast=False):
            st.toast("تم اعتماد وحفظ بيانات الحادث والأطراف بنجاح", icon="✅")
        else:
            sync_page1_to_vault(extra_keys=list(PAGE1_EXTRA_SYNC_KEYS), write_disk=True)
            st.toast("تم اعتماد بيانات الحادث في الجلسة (تحقق من صلاحية الحفظ على القرص)", icon="⚠️")
        parties_df = pd.DataFrame(cleaned_parties)
    else:
        # الإبقاء على آخر اعتماد في الجلسة دون إعادة كتابة مع كل حرف
        parties_df = pd.DataFrame(st.session_state.get("parties") or [])
        vehicles_df = pd.DataFrame(st.session_state.get("vehicles") or [])
        acc_num = st.session_state.get("p1_acc_number", "")
        acc_type = st.session_state.get("p1_acc_type_choice") or st.session_state.get("p1_acc_type") or ""
        acc_injuries = st.session_state.get("p1_acc_injuries", 0)
        acc_loc = st.session_state.get("p1_acc_location", "")
        acc_weather = st.session_state.get("p1_acc_weather_choice") or st.session_state.get("p1_acc_weather") or ""
        acc_deaths = st.session_state.get("p1_acc_deaths", 0)
        acc_cause = st.session_state.get("p1_acc_cause", "")

    if st.session_state.pop("_p1_save_requested", False):
        perform_manual_save(show_toast=True)
    _vehicle_rows = list(st.session_state.get("vehicles") or [])

    def _vehicle_type_at(index):
        if index < len(_vehicle_rows) and isinstance(_vehicle_rows[index], dict):
            return str(_vehicle_rows[index].get("نوع المركبة") or "")
        return ""

    refresh_party_role_titles(force=False)
    sync_cross_page_smart_links(
        injuries_count=int(st.session_state.get("p1_acc_injuries") or 0),
        deaths_count=int(st.session_state.get("p1_acc_deaths") or 0),
        veh1_type=_vehicle_type_at(0),
        veh2_type=_vehicle_type_at(1),
        p1_title_key="p1_title_input",
        sketch_leg1_key="legend_key_1",
        sketch_leg2_key="legend_key_2",
    )
TRAFFIC_LAW_ARTICLES = [
    {
        "id": "art_8_c",
        "code": "المادة (8/ج)",
        "label": "المادة (8/ج) والفقرة (3) من جدول المخالفات رقم (1) - قيادة المركبة دون وجود تأمين ساري المفعول",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "statuteKeys": ["8/ج", "8/4"],
        "resultPoint": "قيادة المركبة دون وجود تأمين ساري المفعول وقت وقوع الحادث.",
        "technicalDraft": "ثبت من تدقيق بيانات المركبة عدم وجود وثيقة تأمين سارية المفعول تغطي المسؤولية المدنية وقت وقوع الحادث.",
        "legalOpinion": "تطبيق المادة (8/ج) من نظام المرور واللائحة (8/4) بشأن إلزام مالك المركبة بالتأمين وفق الوثيقة الموحدة، مع الإحالة لجدول المخالفات رقم (1) الفقرة (3).",
    },
    {
        "id": "art_28",
        "code": "المادة (28)",
        "label": "المادة (28) واللائحة (28/1) والفقرة (62/2/2) - التسبب في حادث نتيجة نقل أحمال مخالفة أو عدم تثبيتها وتغطيتها",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "statuteKeys": ["28", "62/2/2"],
        "resultPoint": "التسبب في حادث نتيجة نقل أحمال مخالفة للأوزان أو الأبعاد أو عدم تثبيتها وتغطيتها.",
        "technicalDraft": "وقع الحادث نتيجة نقل أحمال مخالفة أو عدم مراعاة قواعد السلامة في التحميل والتثبيت والتغطية، مما أدى إلى تضرر الأرواح أو الممتلكات.",
        "legalOpinion": "ثبوت مسؤولية السائق استناداً إلى المادة (28) من نظام المرور، مع الاستئناس باللائحة (28/1) والفقرة (62/2/2) عند الاقتضاء.",
    },
    {
        "id": "art_32",
        "code": "المادة (32)",
        "label": "المادة (32) والفقرة (11) من جدول المخالفات رقم (5) - قيادة المركبة قبل الحصول على رخصة قيادة أو في حال سحبها",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "statuteKeys": ["32"],
        "resultPoint": "قيادة المركبة قبل الحصول على رخصة القيادة اللازمة نظاماً (المادة 32).",
        "technicalDraft": "تبين عند فحص الوثائق أن السائق يقود المركبة قبل الحصول على رخصة القيادة اللازمة أو في حال سحبها.",
        "legalOpinion": "مخالفة صريحة للمادة (32) من نظام المرور، ويحال وفق الفقرة (11) من جدول المخالفات رقم (5).",
    },
    {
        "id": "art_77",
        "code": "المادة (77)",
        "label": "المادة (77) - تضامن مالك المركبة في المسؤولية المادية عند السماح لغير المرخص بالقيادة",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "statuteKeys": ["77"],
        "resultPoint": "تضامن مالك المركبة في المسؤولية المادية لسماحه لغير المرخص بقيادة المركبة.",
        "technicalDraft": "ثبت أن مالك المركبة سمح لشخص غير حاصل على رخصة القيادة اللازمة بقيادتها، مما يرتب تضامنه في المسؤولية المادية وفق المادة (77).",
        "legalOpinion": "تطبيق المادة (77) من نظام المرور بتضامن المالك في المسؤولية المادية عند السماح لغير المرخص بالقيادة.",
    },
    {
        "id": "art_32_3",
        "code": "اللائحة (32/3)",
        "label": "المادة (32) واللائحة (32/3) والفقرة (2) من جدول المخالفات رقم (5) - قيادة مركبة برخصة لا تتناسب مع حجمها ونوع استخدامها",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "statuteKeys": ["32", "32/3"],
        "resultPoint": "قيادة مركبة برخصة لا تتناسب مع حجمها ونوع استخدامها (المادة 32 واللائحة 32/3).",
        "technicalDraft": "تبين أن نوع رخصة القيادة لا يتناسب مع حجم ونوع وقوة المركبة التي كانت تُقاد وقت الحادث.",
        "legalOpinion": "ثبوت المخالفة استناداً إلى المادة (32) واللائحة (32/3)، مع الإحالة لجدول المخالفات رقم (5) الفقرة (2).",
    },
    {
        "id": "art_33",
        "code": "المادة (33)",
        "label": "المادة (33) والفقرة (9) من جدول المخالفات رقم (3) - القيادة برخصة قيادة منتهية الصلاحية أو عدم حملها",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "statuteKeys": ["33"],
        "resultPoint": "القيادة برخصة قيادة منتهية الصلاحية أو عدم حملها وقت القيادة (المادة 33).",
        "technicalDraft": "تبين أن السائق يقود برخصة منتهية أو لا يحمل رخصة سارية المفعول عند طلب إبرازها.",
        "legalOpinion": "مخالفة المادة (33) من نظام المرور، ويحال وفق الفقرة (9) من جدول المخالفات رقم (3).",
    },
    {
        "id": "art_50_control_speed",
        "code": "اللائحة (50/2/4)",
        "label": "المادة (50) واللائحة (50/2/4) و(50/9/1) و(50/9/3) - عدم السيطرة على المركبة وعدم تكييف السرعة مع ظروف ومنعطفات الطريق",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/2/4", "50/9/3"],
        "resultPoint": "عدم السيطرة على المركبة وعدم تكييف السرعة مع ظروف ومنعطفات الطريق.",
        "technicalDraft": "فقد قائد المركبة السيطرة أو لم يكيف سرعته مع ظروف الطريق والمنعطفات بما يحقق السلامة لبقية مستخدمي الطريق.",
        "legalOpinion": "ثبوت المسؤولية استناداً إلى المادة (50) واللائحتين (50/2/4) و(50/9/3) لعدم السيطرة وتكييف السرعة.",
    },
    {
        "id": "art_50_sudden_brake",
        "code": "اللائحة (50/2/5)",
        "label": "المادة (50) واللائحة (50/2/5) والفقرة (5) من جدول المخالفات رقم (3) - استعمال المكابح (الفرامل) بشكل مفاجئ لغير ضرورة",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/2/5"],
        "resultPoint": "استعمال المكابح (الفرامل) بشكل مفاجئ لغير ضرورة.",
        "technicalDraft": "استعمل قائد المركبة المكابح فجأة دون ضرورة أو مبرر سلامة، مما حال دون سير المركبات الأخرى أو فاجأ من خلفه.",
        "legalOpinion": "ثبوت المخالفة وفق المادة (50) واللائحة (50/2/5) والفقرة (5) من جدول المخالفات رقم (3).",
    },
    {
        "id": "art_50_lanes",
        "code": "المادة (51)",
        "label": "المادة (50) والمادة (51) واللائحة (50/6/2/7/9) والفقرة (7) من جدول المخالفات رقم (3) - عدم الالتزام بحدود المسارات المحددة على الطريق",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["51", "50/6/2/7/9"],
        "resultPoint": "عدم الالتزام بحدود المسارات المحددة على الطريق أو تخطي الخطوط الطولية المتصلة.",
        "technicalDraft": "لم يلتزم قائد المركبة بحدود المسارات المحددة، أو سار على خطوط طولية متصلة / تخطاها بالمخالفة لعلامات الطريق.",
        "legalOpinion": "ثبوت المسؤولية استناداً إلى المادتين (50) و(51) واللائحة (50/6/2/7/9).",
    },
    {
        "id": "art_50_right_side",
        "code": "المادة (53)",
        "label": "المادة (53) والمادة (50) واللائحة (50/2/12) و(50/2/20) و(50/2/23) - عدم التزام الجانب الأيمن من الطريق أو عدم ترك مسافة جانبية عند التلاقي",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["53", "50/2/20"],
        "resultPoint": "عدم التزام الجانب الأيمن من الطريق أو عدم ترك مسافة جانبية كافية عند التلاقي.",
        "technicalDraft": "لم يلتزم قائد المركبة بالجهة اليمنى أو لم يترك مسافة جانبية كافية عند التلاقي مع مستعملي الطريق القادمين من الجهة المقابلة.",
        "legalOpinion": "ثبوت المسؤولية استناداً إلى المادة (53) والمادة (50) واللائحة (50/2/20).",
    },
    {
        "id": "art_50_lane_change",
        "code": "اللائحة (50/2/24)",
        "label": "المادة (50) واللائحة (50/2/13) و(50/2/24) و(50/6/1/1/2) والفقرة (15) من جدول (4) - الانحراف أو تغيير المسار دون التأكد من خلوه ودون إعطاء الأفضلية",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/2/24", "50/6/1/1/2"],
        "resultPoint": "الانحراف أو تغيير المسار دون التأكد من خلوه ودون إعطاء الأفضلية للسير المستقيم.",
        "technicalDraft": "انحرف قائد المركبة أو غيّر مساره دون التأكد من خلو الاتجاه ودون إعطاء الإشارة والأفضلية للمركبة السائرة باستقامة.",
        "legalOpinion": "ثبوت المسؤولية وفق المادة (50) واللائحتين (50/2/24) و(50/6/1/1/2).",
    },
    {
        "id": "art_50_u_turn",
        "code": "اللائحة (50/6/1/1/8)",
        "label": "المادة (50) واللائحة (50/2/24) و(50/6/1/1/8) و(50/7/5) والفقرة (13) من جدول (4) - الدوران للخلف أو الانعطاف دون مراعاة أفضلية المركبات القادمة",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/6/1/1/8", "50/7/5"],
        "resultPoint": "الدوران للخلف أو الانعطاف دون مراعاة أفضلية المركبات القادمة.",
        "technicalDraft": "شرع قائد المركبة في الدوران للخلف أو الالتفاف دون مراعاة أفضلية المركبات القادمة أو خلافاً لإشارة تمنع ذلك.",
        "legalOpinion": "ثبوت المسؤولية وفق المادة (50) واللائحتين (50/6/1/1/8) و(50/7/5).",
    },
    {
        "id": "art_50_following",
        "code": "اللائحة (50/2/19)",
        "label": "المادة (50) واللائحة (50/2/19) والفقرة (11) من جدول المخالفات رقم (2) - عدم ترك مسافة كافية خلف المركبة الأمامية",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/2/19"],
        "resultPoint": "عدم ترك مسافة كافية خلف المركبة الأمامية تتناسب مع السرعة.",
        "technicalDraft": "سار قائد المركبة خلف المركبة الأمامية دون ترك مسافة كافية تتناسب مع السرعة، مما أدى إلى الاصطدام من الخلف.",
        "legalOpinion": "ثبوت المسؤولية وفق المادة (50) واللائحة (50/2/19) والفقرة (11) من جدول المخالفات رقم (2).",
    },
    {
        "id": "art_50_overtake",
        "code": "اللائحة (50/6/2/3)",
        "label": "المادة (50) واللائحة (50/6/2/3) و(50/6/2/7) والفقرة (17) من جدول المخالفات رقم (5) - التجاوز في المناطق الممنوع فيها التجاوز كالمنعطفات والمرتفعات",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/6/2/3"],
        "resultPoint": "التجاوز في منطقة ممنوع فيها التجاوز كالمنعطفات والمرتفعات.",
        "technicalDraft": "تجاوز قائد المركبة في مرتفع غير مكشوف أو منعطف أو موضع تمنع فيه الإشارة أو الخطوط التجاوز.",
        "legalOpinion": "ثبوت المسؤولية وفق المادة (50) واللائحة (50/6/2/3) والفقرة (17) من جدول المخالفات رقم (5).",
    },
    {
        "id": "art_50_priority",
        "code": "اللائحة (50/2/14)",
        "label": "المادة (50) واللائحة (50/2/14) و(50/6/1/1/4، 5، 6، 9) وجدول المخالفات رقم (4) - عدم مراعاة قواعد الأفضلية في التقاطعات أو الدوار أو الطريق الرئيسي",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/2/14", "50/6/1/1"],
        "resultPoint": "عدم مراعاة قواعد الأفضلية في التقاطعات أو الدوار أو الطريق الرئيسي.",
        "technicalDraft": "دخل قائد المركبة تقاطعاً أو دواراً أو طريقاً رئيسياً دون منح أولوية المرور لمن له الأفضلية نظاماً.",
        "legalOpinion": "ثبوت المسؤولية وفق المادة (50) واللائحتين (50/2/14) و(50/6/1/1).",
    },
    {
        "id": "art_50_uphill",
        "code": "اللائحة (50/6/1/1/12)",
        "label": "المادة (50) واللائحة (50/6/1/1/12) - عدم إعطاء الأفضلية للمركبة الصاعدة في الطرق الجبلية والمنحدرات الشديدة",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/6/1/1/12"],
        "resultPoint": "عدم إعطاء الأفضلية للمركبة الصاعدة في الطرق الجبلية والمنحدرات الشديدة.",
        "technicalDraft": "لم يمنح قائد المركبة الأفضلية للمركبة الصاعدة عند التلاقي في طريق جبلي أو منحدر شديد يتعذر فيه السير المتزامن.",
        "legalOpinion": "ثبوت المسؤولية وفق المادة (50) واللائحة (50/6/1/1/12).",
    },
    {
        "id": "art_50_red_light",
        "code": "اللائحة (50/10/1/1)",
        "label": "المادة (50) واللائحة (50/10/1/1) والمادة (62) واللائحة (62/1/3) والفقرة (1) من جدول (6) - تجاوز إشارة المرور الضوئية أثناء الضوء الأحمر",
        "category": "التعدي والتفريط والأولويات",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/10/1/1", "62/1/3"],
        "resultPoint": "تجاوز إشارة المرور الضوئية أثناء الضوء الأحمر.",
        "technicalDraft": "تجاوز قائد المركبة الإشارة الحمراء أو خط الوقوف/ممر المشاة أثناء النور الأحمر أو الأصفر الملزم بالتوقف.",
        "legalOpinion": "ثبوت التعدي وفق اللائحة (50/10/1/1) واللائحة (62/1/3) لتجاوز الإشارة الحمراء.",
    },
    {
        "id": "art_53_wrong_way",
        "code": "المادة (53)",
        "label": "المادة (53) والمادة (62) واللائحة (62/1/4) والفقرة (6) من جدول المخالفات رقم (6) - قيادة المركبة بالاتجاه المعاكس لحركة السير",
        "category": "التعدي والتفريط والأولويات",
        "isQuasiCriminal": False,
        "statuteKeys": ["53", "62/1/4"],
        "resultPoint": "قيادة المركبة بالاتجاه المعاكس لحركة السير.",
        "technicalDraft": "قاد السائق المركبة باتجاه معاكس لحركة السير المقررة على الطريق.",
        "legalOpinion": "ثبوت التعدي استناداً إلى المادة (53) واللائحة (62/1/4).",
    },
    {
        "id": "art_62_distraction",
        "code": "اللائحة (62/2/4)",
        "label": "المادة (62) واللائحة (62/2/4) والفقرة (4) من جدول (3) والفقرة (19) من جدول (4) - الانشغال بغير الطريق أو استخدام الهاتف المحمول باليد أثناء القيادة",
        "category": "التعدي والتفريط والأولويات",
        "isQuasiCriminal": False,
        "statuteKeys": ["62/2/4"],
        "resultPoint": "الانشغال بغير الطريق أو استخدام الهاتف المحمول باليد أثناء القيادة.",
        "technicalDraft": "انشغل قائد المركبة عن مراقبة الطريق أثناء القيادة (ومن ذلك استخدام الهاتف باليد)، مما أدى إلى وقوع الاصطدام.",
        "legalOpinion": "ثبوت التفريط وفق اللائحة (62/2/4) للانشغال عن الطريق أثناء القيادة.",
    },
    {
        "id": "art_50_reverse",
        "code": "اللائحة (50/2/1)",
        "label": "المادة (50) واللائحة (50/2/1) والفقرة (2) من جدول المخالفات رقم (2) - الرجوع إلى الخلف في الطريق العام دون التأكد من خلوه أو لمسافة تتجاوز 20 متراً",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/2/1", "60"],
        "resultPoint": "الرجوع إلى الخلف في الطريق العام دون التأكد من خلوه أو لمسافة تتجاوز عشرين متراً.",
        "technicalDraft": "رجع قائد المركبة إلى الخلف في الطريق العام دون التأكد من خلو المسار أو لمسافة تزيد على عشرين متراً.",
        "legalOpinion": "ثبوت المسؤولية وفق المادة (50) واللائحة (50/2/1) والمادة (60) عند الإهمال وقلة الاحتراز في الرجوع للخلف.",
    },
    {
        "id": "art_50_parking",
        "code": "اللائحة (50/2/3)",
        "label": "المادة (50) واللائحة (50/2/3) و(50/8/1) واللائحة (62/2/1) والفقرة (1) من جدول (3) - إيقاف المركبة بشكل خاطئ أو عدم اتخاذ احتياطات السلامة عند التعطل",
        "category": "قواعد السير والسيطرة (المادة 50)",
        "isQuasiCriminal": False,
        "statuteKeys": ["50/2/3", "62/2/1"],
        "resultPoint": "إيقاف المركبة بشكل خاطئ أو عدم اتخاذ احتياطات السلامة عند التعطل.",
        "technicalDraft": "أُوقفت المركبة بصورة خاطئة أو تعطلت دون إخراجها ووضع علامات التحذير اللازمة، مما عرّض مستخدمي الطريق للخطر.",
        "legalOpinion": "ثبوت التفريط وفق اللائحتين (50/2/3) و(62/2/1) لعدم اتخاذ احتياطات السلامة عند الإيقاف أو التعطل.",
    },
    {
        "id": "art_55_driver",
        "code": "اللائحة (55/10)",
        "label": "المادة (55) واللائحة (55/4) و(55/10) و(55/15) والفقرة (7) من جدول (1) - عدم إعطاء أفضلية المرور للمشاة أو تعريضهم للخطر",
        "category": "المشاة والحيوانات",
        "isQuasiCriminal": False,
        "statuteKeys": ["55/10", "55/15"],
        "resultPoint": "عدم إعطاء أفضلية المرور للمشاة أو تعريضهم للخطر.",
        "technicalDraft": "عرض قائد المركبة المشاة للخطر أو لم يمنحهم أفضلية المرور في التقاطع غير المجهز بإشارات ضوئية.",
        "legalOpinion": "ثبوت مسؤولية السائق وفق المادة (55) واللائحتين (55/10) و(55/15).",
    },
    {
        "id": "art_55_pedestrian",
        "code": "المادة (55)",
        "label": "المادة (55) واللائحة (55/6) و(55/7/3) والفقرة (4) من جدول (1) أو الفقرة (16) من جدول (5) - عبور المشاة للطريق من غير الأماكن المخصصة أو دون التأكد من خلوه",
        "category": "المشاة والحيوانات",
        "isQuasiCriminal": False,
        "statuteKeys": ["55", "55/7/3"],
        "resultPoint": "عبور المشاة للطريق من غير الأماكن المخصصة أو دون التأكد من خلوه.",
        "technicalDraft": "عبر المشاة الطريق من غير الأماكن المخصصة أو باشر العبور دون التأكد من عدم إعاقة حركة المرور.",
        "legalOpinion": "ثبوت مسؤولية المشاة وفق المادة (55) واللائحة (55/7/3).",
    },
    {
        "id": "art_60_animals",
        "code": "اللائحة (60/5)",
        "label": "المادة (60) واللائحة (60/5) واللائحة (50/1/9) و(62/2/3) وجدول (6/10) و(7/3) - ترك الحيوانات سائبة في حرم الطريق أو عبورها من غير الأماكن المخصصة",
        "category": "المشاة والحيوانات",
        "isQuasiCriminal": False,
        "statuteKeys": ["60/5", "62/2/3"],
        "resultPoint": "ترك الحيوانات سائبة في حرم الطريق أو عبورها من غير الأماكن المخصصة.",
        "technicalDraft": "وقع الحادث بسبب حيوان ترك سائباً في حرم الطريق أو عبر من غير الأماكن المخصصة، ويتحمل المسؤولية مالكه أو المسؤول عنه عند ثبوتها.",
        "legalOpinion": "ثبوت المسؤولية وفق اللائحتين (60/5) و(62/2/3) على مالك الحيوان أو المسؤول عنه.",
    },
    {
        "id": "art_63_flee",
        "code": "المادة (63)",
        "label": "المادة (63) الفقرتان (1، 2) - مغادرة موقع الحادث دون إبلاغ الإدارة المختصة أو استبدال السائق",
        "category": "الحوادث الجسيمة والإجراءات",
        "isQuasiCriminal": True,
        "statuteKeys": ["63/1"],
        "resultPoint": "مغادرة موقع الحادث دون إبلاغ الإدارة المختصة أو استبدال السائق.",
        "technicalDraft": "غادر أحد الأطراف موقع الحادث دون إبلاغ الإدارة المختصة أو دون تقديم المساعدة الممكنة للمصابين، أو ثبت استبدال السائق.",
        "legalOpinion": "تطبيق المادة (63) الفقرتين (1) و(2) من نظام المرور، مع الإحالة للجهة المختصة.",
    },
    {
        "id": "art_62_serious",
        "code": "المادة (62)",
        "label": "المادة (62) الفقرتان (1، 2) - التسبب في حادث مروري جسيم (وفاة أو إصابة تتجاوز 15 يوماً) مقترن بالتعدي أو التفريط",
        "category": "الحوادث الجسيمة والإجراءات",
        "isQuasiCriminal": True,
        "statuteKeys": ["62/1"],
        "resultPoint": "التسبب في حادث مروري جسيم مقترن بالتعدي أو التفريط نتج عنه وفاة أو إصابة تتجاوز خمسة عشر يوماً.",
        "technicalDraft": "نتج عن الحادث المقترن بالتعدي أو التفريط وفاة أو زوال عضو أو تعطيل منفعته أو إصابة تزيد مدة شفائها على خمسة عشر يوماً.",
        "legalOpinion": "تطبيق المادة (62) الفقرتين (1) و(2) من نظام المرور وإحالة المتسبب للجهة المختصة مع حفظ الحق الخاص.",
    },
]
TRAFFIC_LAW_BY_ID = {article["id"]: article for article in TRAFFIC_LAW_ARTICLES}

# ترحيل مفاتيح الجلسة القديمة → المعرّفات الجديدة (تفادي KeyError)
_TRAFFIC_ARTICLE_ID_ALIASES = {
    "art_32_1": "art_32",
    "art_50_1_1": "art_50_right_side",
    "art_50_1_2": "art_50_lanes",
    "art_50_1_4": "art_50_lane_change",
    "art_50_2_1": "art_50_u_turn",
    "art_50_3_1": "art_50_overtake",
    "art_50_4_1": "art_50_following",
    "art_50_5_1": "art_50_priority",
    "art_50_5_5": "art_50_priority",
    "art_50_7_1": "art_50_parking",
    "art_50_8_1": "art_50_reverse",
    "art_50_9_1": "art_50_control_speed",
    "art_50_9_5_a": "art_50_control_speed",
    "art_50_10_1": "art_50_control_speed",
    "art_51_1_signal": "art_50_red_light",
    "art_51_1_wrong_way": "art_53_wrong_way",
    "art_52_53": "art_50_lanes",
    "art_55_1": "art_55_driver",
    "art_57_1_lane_markings": "art_50_lanes",
    "art_57_1_distraction": "art_62_distraction",
    "art_57_1_sudden_stop": "art_50_sudden_brake",
    "art_58_1": "art_50_control_speed",
    "art_60_1": "art_50_control_speed",
    "art_60_2": "art_50_control_speed",
    "art_61_1": "art_62_serious",
    "art_62_1": "art_62_serious",
    "art_62_2": "art_62_serious",
    "art_63_1_hit_and_run": "art_63_flee",
    "art_63_1_tampering": "art_63_flee",
    "art_63_2_a_driver_swap": "art_63_flee",
    "art_63_2_b_staged_accident": "art_63_flee",
}

# نصوص حرفية من المرجع traffic-articles-v2 (م/85 + اللائحة)
TRAFFIC_STATUTORY_TEXTS = {
    "8/ج": "يلزم كل مالك مركبة بالتأمين على مركبته. وتحدد اللائحة الأحكام المنظمة لذلك.",
    "8/4": "يكون التأمين على المركبة وفقاً لأحكام الوثيقة الموحدة للتأمين الإلزامي على المركبات.",
    "28": "يُعد السائق مسئولاً عن جميع الأضرار التي تصيب الأرواح أو الممتلكات العامة أو الخاصة؛ نتيجةً لنقل أحمال مخالفة للأوزان والأبعاد المقررة نظاماً، أو لعدم مراعاة قواعد السلامة في التحميل، ما لم تثبت مسؤولية غيره.",
    "32": "يحظر على أي شخص قيادة أي مركبة قبل الحصول على رخصة القيادة اللازمة وفقاً لأحكام هذا النظام ولائحته.",
    "32/3": "أن يتناسب نوع رخصة القيادة مع حجم ونوع وقوة المركبة ويجوز لمن يحمل رخصة قيادة أعلى بقيادة مركبة أدنى في الحجم والقوة، ويستثنى من ذلك رخصة قيادة مركبات الأشغال العامة ورخصة قيادة الدراجة الآلية.",
    "33": "يجب على السائق أن يحمل رخصة قيادة سارية المفعول عند قيادته للمركبة، ولرجل الأمن حق طلب إبرازها للاطلاع عليها، وليس له حجزها.",
    "50/2/4": "يلتزم سائق المركبة بالسيطرة على سير مركبته، وأن يقودها وفق السرعة النظامية، وعليه أن يكيف سيره مع كافة الظروف الطبيعية وأحوال الطريق الذي يسير عليه بما يحقق السلامة العامة لبقية مستخدمي الطريق.",
    "50/9/3": "لا يعفي تحديد السرعة القصوى السائق من واجب تخفيف السرعة وإيقاف المركبة في كل حالة يمكن أن تسبب حادثاً، وبالأخص في المنعطفات والمنحدرات والمرتفعات وعند عدم وضوح الرؤية.",
    "50/2/5": "يلتزم سائق المركبة بعدم استعمال المكابح (الفرامل) فجأة إلا للضرورة أو بداعي السلامة وألا يحول دون سير المركبات الأخرى أو يعاكس المنتفعين بالطريق.",
    "51": "تعد علامات الطريق والعاكسات والشاخصات الملحقة بهذا النظام جزءاً منه، ويجب على السائق التقيد بها.",
    "50/6/2/7/9": "يحظر التخطي في مسارات المرور المحددة بخطوط طولية متصلة تفصل بينها ولا يجوز السير على هذه الخطوط أو تخطيها.",
    "53": "جهة السير على الطرق هي الجهة اليمنى.",
    "50/2/20": "على كل سائق مركبة عند التلاقي أن يقترب بقدر الإمكان من حافة مسار المركبات المخصص لاتجاه حركة المرور بحيث يترك مسافة جانبية كافية، ويجب عليه تهدئة سرعته أو التوقف عند الضرورة لحين مرور مستعملي الطريق القادمين من الجهة المقابلة.",
    "50/2/24": "على كل سائق قبل القيام بأي حركة خاصة بالانحراف بسيارته يميناً أو شمالاً مراعاة التأكد من إمكان إجراء ذلك دون أن يعرض نفسه أو غيره للخطر، وإعطاء الإشارات اللازمة بوقت كاف، وألا ينعطف إلا بعد التأكد من خلو الاتجاه.",
    "50/6/1/1/2": "الأفضلية لسائق المركبة التي تسير باتجاه مستقيم في حال سير المركبتين محاذيتين بشكل متواز وعلى من يرغب تغيير اتجاهه أن يعطي حق الأفضلية في المرور للمركبة التي تسير باتجاه مستقيم.",
    "50/6/1/1/8": "الأفضلية للمركبات القادمة من الاتجاهات الأخرى على المركبة التي يرغب قائدها بالدوران إلى الخلف.",
    "50/7/5": "عدم الالتفاف إلى الخلف عندما تكون الإشارة حمراء أو عندما توجد إشارة تمنع ذلك.",
    "50/2/19": "على سائقي المركبات التي تسير في اتجاه واحد أن يتركوا فيما بينهم مسافة كافية تتناسب مع سرعة تلك المركبات بحيث تتسع المسافة كلما زادت السرعة منعاً للحوادث.",
    "50/6/2/3": "عدم التجاوز في المرتفعات غير المكشوفة، والمنحنيات الحادة والجسور المحدبة ومنعطفات الطرق، وعند ممرات المشاة وعندما تكون هناك إشارة أو خطوط ذات الدلالة تمنع ذلك.",
    "50/2/14": "توخي الحذر عند الاقتراب من تقاطع الطرق وأن يقود مركبته بسرعة مناسبة يتمكن معها من إيقافها ليسمح بمرور المركبات التي لها أولوية المرور.",
    "50/6/1/1": "الأفضلية في التقاطعات غير المنظمة للمركبة التي دخلت التقاطع أولاً (4)، وللقادمة من اليمين عند تساوي الأفضلية (5)، وللمركبة التي تسير داخل الدوار (6)، وللمركبة على الطريق الرئيسي في حال التقائه مع طريق فرعي (9).",
    "50/6/1/1/12": "الأفضلية للمركبة الصاعدة في الطرق الجبلية والطرق المائلة ذات الانحدار الشديد على المركبة النازلة في حال عدم تمكنها من السير في آن واحد عند تلاقيها، إلا في الحالة التي يكون فيها مكان لوقوف الطوارئ أقرب للمركبة الصاعدة فعليها الانتظار بالوقوف لحين مرور المركبة النازلة.",
    "50/10/1/1": "عدم تجاوز منطقة عبور المشاة المدهونة أو خط الوقوف المدهون بالقرب من الإشارة عندما يكون النور أصفر أو أحمر.",
    "62/1/3": "يعد المتسبب في الحادث متعدياً عند تجاوزه لإشارة المرور الضوئية أثناء الضوء الأحمر.",
    "62/1/4": "يعد المتسبب في وقوع الحادث المروري متعدياً في حال قيادته للمركبة بالاتجاه المعاكس لحركة السير.",
    "62/2/4": "يعد المتسبب في وقوع الحادث المروري مفرطاً في حال انشغاله عن الطريق أثناء القيادة.",
    "50/2/1": "الرجوع إلى الخلف في الطريق العام لمسافة تزيد على عشرين متراً.",
    "50/2/3": "إخراج المركبة من الطريق فوراً إذا طرأ أثناء سيرها عيوب تؤثر على السلامة العامة، وفي حال تعطلها فعليه وضع علامات التحذير اللازمة تجنباً لاصطدام المركبات بها.",
    "62/2/1": "يعد المتسبب مفرطاً عند عدم اتخاذه للاحتياطات اللازمة عند إيقاف المركبة في حالات الطوارئ على الطرق العامة.",
    "55": "على المشاة السير في الأماكن المخصصة لهم، وفق ما تحدده اللائحة.",
    "55/10": "على سائق المركبة ألا يعرض المشاة الذين يسيرون على الأرصفة وعلى جوانب الطريق وكذلك الذين يسيرون في نهر الطريق للخطر.",
    "55/15": "إذا كانت مفارق الطرق أو التقاطعات غير مجهزة بإشارات ضوئية فللمشاة حق أفضلية المرور، وعلى السائق أن يلتزم جانب الحذر عندما يرى أحد المشاة يجتاز طريقه.",
    "55/7/3": "عند عبور المشاة للطريق من الممرات غير المخصصة لهم فيجب ألا يباشروا العبور إلا بعد التأكد أولاً من أنهم لا يعوقون حركة المرور.",
    "60": "يعد الحادث المروري موجباً للمسؤولية إذا نتج من الإهمال، أو قلة الاحتراز، أو عدم مراعاة الأنظمة.",
    "60/1": "تُحدد مسؤولية أطراف الحادث المروري وفق أحكام المادة (60) من النظام وهذه اللائحة.",
    "60/2": "نسب المسؤولية 100%، 75%، 50%، 25%، 0%. وأركان المسؤولية: الإهمال (60/2/1)، قلة الاحتراز (60/2/2)، عدم مراعاة الأنظمة (60/2/3).",
    "60/2/1": "الإهمال.",
    "60/2/2": "قلة الاحتراز.",
    "60/2/3": "عدم مراعاة الأنظمة.",
    "60/3": "توزَّع نسب المسؤولية بين أطراف الحادث وفق الفقرة (60/2) بحسب ما يثبت من خطأ كل طرف.",
    "60/5": "إذا وقع حادث مروري كان أحد أطرافه حيوان فيتحمل المسئولية في حال ثبوتها مالكه أو المسئول عنه.",
    "62/2/3": "يعد مفرطاً عند عدم قيامه بإبعاد الحيوانات المسئول عنها عن حرم الطريق أو سماحه بعبورها من غير الأماكن المخصصة لها.",
    "62/1": "كل من ارتكب حادثاً مرورياً متعدياً أو مفرطاً ونتجت عنه وفاة أو زوال عضو أو تعطيل منفعته أو جزء منهما؛ يعاقب بالسجن مدة لا تزيد على أربع سنوات وبغرامة مالية لا تزيد على مائتي ألف ريال، أو بإحدى هاتين العقوبتين، وذلك دون إخلال بما يتقرر للحق الخاص.",
    "62": "كل من ارتكب حادثاً مرورياً متعدياً أو مفرطاً ونتجت عنه وفاة أو زوال عضو أو تعطيل منفعته أو جزء منهما؛ يعاقب بالسجن مدة لا تزيد على أربع سنوات وبغرامة مالية لا تزيد على مائتي ألف ريال، أو بإحدى هاتين العقوبتين، وذلك دون إخلال بما يتقرر للحق الخاص.",
    "63/1": "على كل سائق يكون طرفاً في حادث مروري أن يوقف المركبة في مكان الحادث، ويبادر بإبلاغ الإدارة المختصة، وأن يقدم المساعدة الممكنة لمصابي الحادث.",
    "63": "على كل سائق يكون طرفاً في حادث مروري أن يوقف المركبة في مكان الحادث، ويبادر بإبلاغ الإدارة المختصة، وأن يقدم المساعدة الممكنة لمصابي الحادث.",
    "77": "إذا سمح مالك المركبة أو المسؤول عنها لشخص غير حاصل على رخصة القيادة اللازمة بقيادتها؛ تضامن مع السائق في المسؤولية المادية المترتبة على الحادث وفق ما يقرره النظام.",
    "50": "الطريق للجميع، وتجب مراعاة حقوق الآخرين من مستخدميه.",
}

# مواد النظام تُعرض بصيغة «نص المادة»؛ فروع اللائحة بصيغة المادة الأم + الفقرة.
_TRAFFIC_SYSTEM_ARTICLE_KEYS = frozenset({
    "8/ج", "28", "32", "33", "50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "60", "61", "62", "63", "64", "68", "69", "77",
})
_TRAFFIC_REGULATION_PARAGRAPH_KEYS = frozenset({
    "8/4", "32/3", "28/1",
    "50/2/1", "50/2/3", "50/2/4", "50/2/5", "50/2/14", "50/2/19", "50/2/20", "50/2/24",
    "50/6/1/1", "50/6/1/1/2", "50/6/1/1/8", "50/6/1/1/12", "50/6/2/3", "50/6/2/7/9",
    "50/7/5", "50/9/3", "50/10/1/1",
    "55/7/3", "55/10", "55/15",
    "60/1", "60/2", "60/2/1", "60/2/2", "60/2/3", "60/3", "60/5",
    "62/1/3", "62/1/4", "62/2/1", "62/2/2", "62/2/3", "62/2/4",
})

# يلتقط «المادة (…)/للمادة (…)/مادة (…)» لأن لام الجر تدمج أل التعريف كتابةً (للمادة).
_ARTICLE_CODE_IN_TEXT_RE = re.compile(r"مادة\s*\(([^)]+)\)")
_TECHNICAL_DRAFT_PREFIX_RE = re.compile(
    r"^(كما تبين من المعاينة الفنية|كما اتضح من المعاينة الفنية|بالمعاينة الفنية)"
)

# ترحيل أرقام نظامية قديمة في النصوص إلى مفاتيح المرجع v2 (مفاتيح مركّبة لتفادي بقايا الاستشهاد)
_STATUTE_KEY_ALIASES = {
    "/".join(["32", "1"]): "32",
    "/".join(["50", "1", "1"]): "50/2/20",
    "/".join(["50", "1", "2"]): "50/6/2/7/9",
    "/".join(["50", "1", "4"]): "50/2/24",
    "/".join(["50", "3", "1"]): "50/6/2/3",
    "/".join(["50", "4", "1"]): "50/2/19",
    "/".join(["50", "5", "1"]): "50/6/1/1",
    "/".join(["50", "5", "5"]): "50/6/1/1",
    "/".join(["57", "1"]): "51",
}

def _normalize_statute_key(raw_code: str) -> str:
    text = str(raw_code or "").strip()
    text = re.sub(r"^(?:المادة|الفقرة|اللائحة)\s*", "", text).strip()
    text = text.strip("() ").strip()
    text = re.sub(r"\s*/\s*الفقرة\s*", "/", text)
    text = re.sub(r"\s*-\s*.+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("،", ",").strip()
    if text in _STATUTE_KEY_ALIASES:
        return _STATUTE_KEY_ALIASES[text]
    return text

def _lookup_statutory_text(raw_code: str) -> str:
    if not raw_code:
        return ""
    cleaned_cite = _official_article_cite(
        f"المادة ({raw_code})" if not re.search(r"المادة|الفقرة|اللائحة", str(raw_code)) else str(raw_code)
    )
    candidates = [
        _normalize_statute_key(raw_code),
        _normalize_statute_key(cleaned_cite),
        str(raw_code or "").strip(),
    ]
    for key in candidates:
        if key and key in TRAFFIC_STATUTORY_TEXTS:
            return TRAFFIC_STATUTORY_TEXTS[key]
    return ""

def _display_article_code(raw_code: str) -> str:
    cleaned = _official_article_cite(
        f"المادة ({raw_code})"
        if not re.search(r"المادة|الفقرة|اللائحة", str(raw_code))
        else str(raw_code)
    )
    return _normalize_statute_key(cleaned) or str(raw_code or "").strip()

def _is_regulation_paragraph_key(code_key: str) -> bool:
    key = _normalize_statute_key(code_key)
    if key in _TRAFFIC_REGULATION_PARAGRAPH_KEYS:
        return True
    if key in _TRAFFIC_SYSTEM_ARTICLE_KEYS:
        return False
    if re.match(r"^(?:8|28|32|50|55|60|62)/\d", key):
        return True
    return False

def _parent_system_article_key(code_key: str) -> str:
    key = _normalize_statute_key(code_key)
    for prefix, parent in (
        ("50/", "50"),
        ("32/", "32"),
        ("60/", "60"),
        ("55/", "55"),
        ("62/", "62"),
        ("28/", "28"),
        ("8/", "8/ج"),
    ):
        if key.startswith(prefix):
            return parent
    if "/" in key:
        return key.split("/", 1)[0]
    return key

def _format_statutory_bullet(code_key: str, text: str) -> str:
    key = _normalize_statute_key(code_key)
    body = str(text or "").strip()
    if _is_regulation_paragraph_key(key):
        parent = _parent_system_article_key(key)
        return f"▪ المادة ({parent}) من نظام المرور والفقرة ({key}) من لائحته التنفيذية: «{body}»"
    return f"▪ نص المادة ({key}) من نظام المرور: «{body}»"

def _format_article_cite_for_report(code: str) -> str:
    """صيغة إسناد مختصرة في النتائج/الرأي دون تسمية فرع اللائحة «مادة»."""
    key = _display_article_code(code)
    if _is_regulation_paragraph_key(key):
        parent = _parent_system_article_key(key)
        return f"المادة ({parent}) والفقرة ({key}) من اللائحة التنفيذية"
    return f"المادة ({key})"

def _statutory_lines_for_reason(reason_line: str, printed_articles=None) -> list:
    """يُرجع نصوص المواد مع طباعة كل مادة مرة واحدة فقط عبر printed_articles."""
    printed = printed_articles if isinstance(printed_articles, set) else set()
    line = str(reason_line or "")
    codes = []
    seen = set()
    # يلتقط المادة (...) أو الفقرة (...) أو اللائحة (...)
    for match in re.finditer(r"(?:المادة|الفقرة|اللائحة)\s*\(([^)]+)\)", line):
        raw = (match.group(1) or "").strip()
        # تجاهل قوائم الفقرات المركّبة داخل القوس مثل 60/1، 60/2، 60/3 — تُلتقط لاحقاً مفردة إن وُجدت
        if "،" in raw or "," in raw:
            for part in re.split(r"[،,]", raw):
                part = part.strip()
                if not part:
                    continue
                display = _display_article_code(part)
                if not display or display in seen or display in printed:
                    continue
                text = _lookup_statutory_text(part)
                if not text:
                    continue
                seen.add(display)
                printed.add(display)
                codes.append(_format_statutory_bullet(display, text))
            continue
        display = _display_article_code(raw)
        if not display or display in seen or display in printed:
            continue
        text = _lookup_statutory_text(raw)
        if not text:
            continue
        seen.add(display)
        printed.add(display)
        codes.append(_format_statutory_bullet(display, text))
    return codes

def _join_technical_drafts(drafts) -> str:
    sep = " كما تبين من المعاينة الفنية أنه "
    parts = []
    for draft in drafts or []:
        text = str(draft or "").strip()
        if not text:
            continue
        # اضغط تكرار البادئة داخل المسودة الواحدة إلى مرة واحدة
        text = re.sub(
            r"^(?:كما تبين من المعاينة الفنية(?:\s+أنه)?\s*)+",
            "كما تبين من المعاينة الفنية ",
            text,
        ).strip()
        if not parts:
            parts.append(text)
            continue
        if _TECHNICAL_DRAFT_PREFIX_RE.match(text):
            parts.append(" " + text)
        else:
            parts.append(sep + text)
    joined = "".join(parts)
    # أزل التكرار المتلاصق: «...أنه كما تبين من المعاينة الفنية...» أو تكرار البادئة
    joined = re.sub(
        r"كما تبين من المعاينة الفنية(?:\s+أنه)?\s+كما تبين من المعاينة الفنية(?:\s+أنه)?",
        "كما تبين من المعاينة الفنية",
        joined,
    )
    joined = re.sub(
        r"(?:كما تبين من المعاينة الفنية(?:\s+أنه)?\s*){2,}",
        "كما تبين من المعاينة الفنية ",
        joined,
    )
    return joined.strip()

def generate_accident_report_fields(selected_article_ids):
    """توليد كيفية الوقوع والرأي من المواد فقط — نتائج الحادث تُولَّد من الأطراف/المركبات."""
    selected_ids = set(selected_article_ids or [])
    selected_articles = [article for article in TRAFFIC_LAW_ARTICLES if article["id"] in selected_ids]
    if not selected_articles:
        return {
            "resultsText": "",
            "technicalDraftText": "",
            "legalOpinionText": "",
            "hasCriminalSuspicion": False,
        }
    has_criminal_suspicion = any(article["isQuasiCriminal"] for article in selected_articles)
    technical_draft_text = _join_technical_drafts(
        article["technicalDraft"] for article in selected_articles
    )
    opinion_lines = "\n".join(f"• {article['legalOpinion']}" for article in selected_articles)
    if has_criminal_suspicion:
        criminal_codes = "، ".join(
            _format_article_cite_for_report(article["code"])
            for article in selected_articles if article["isQuasiCriminal"]
        )
        legal_opinion_text = opinion_lines
    else:
        all_codes = "، ".join(_format_article_cite_for_report(article["code"]) for article in selected_articles)
        legal_opinion_text = opinion_lines
    return {
        "resultsText": "",
        "technicalDraftText": technical_draft_text,
        "legalOpinionText": legal_opinion_text,
        "hasCriminalSuspicion": has_criminal_suspicion,
    }

if st.session_state.active_tab == MAIN_TAB_OPTIONS[2]:
    # قبل رسم أدوات التبويب 3: أعد حقن المفاتيح الغائبة من الظل
    try:
        reinject_permanent_form_data()
    except Exception:
        pass
    _ensure_tab3_locked_text_defaults()
    st.subheader("📚 محرك المواد النظامية وفروعها")
    if st.session_state.get("acc_how_override"):
        override_text = st.session_state.pop("acc_how_override")
        if not _tab3_text_is_manual("technical_description"):
            kept_override = _extract_marked_block(_read_tab3_saved_text("technical_description"))
            _write_tab3_saved_text(
                "technical_description",
                _upsert_marked_block(override_text, kept_override),
                mark_manual=False,
            )
            _bump_tab3_text_rev("technical_description")
    valid_article_ids = [article["id"] for article in TRAFFIC_LAW_ARTICLES]
    stored_articles = st.session_state.get("selected_articles")
    if not isinstance(stored_articles, list):
        stored_articles = list(get_form_value("selected_articles") or [])
    # ترحيل مفاتيح الجلسة القديمة عبر aliases لتفادي KeyError
    migrated_articles = []
    for article_id in stored_articles:
        article_id = _TRAFFIC_ARTICLE_ID_ALIASES.get(article_id, article_id)
        if article_id in TRAFFIC_LAW_BY_ID and article_id not in migrated_articles:
            migrated_articles.append(article_id)
    st.session_state.selected_articles = migrated_articles
    selected_law_ids = st.multiselect(
        "اختر المواد النظامية وفروعها المطبقة على الحادث:",
        options=valid_article_ids,
        format_func=lambda article_id: TRAFFIC_LAW_BY_ID[article_id]["label"],
        key="selected_articles"
    )
    render_legal_articles_inserter(
        [TRAFFIC_LAW_BY_ID[article_id]["code"] for article_id in selected_law_ids if article_id in TRAFFIC_LAW_BY_ID],
        p1_reasons_key="p1_reasons",
        p2_reasons_key="p2_reasons",
    )
    generated_fields = generate_accident_report_fields(selected_law_ids)
    # لا تعِد توليد كيفية الوقوع/الرأي إلا عند تغير بصمة المواد/القرائن/النسب — وبدون الكتابة فوق النص اليدوي
    st.session_state.law_selection_sig = tuple(selected_law_ids)
    content_fp = compute_tab3_content_fingerprint()
    previous_fp = st.session_state.get("tab3_content_fingerprint")
    texts_already = (
        not _is_blank_form_value(_read_tab3_saved_text("technical_description"))
        or not _is_blank_form_value(_read_tab3_saved_text("p1_reasons"))
    )
    should_regen = False
    if previous_fp is None:
        # أول مرة: لا تستبدل نصوصاً موجودة؛ ولّد فقط إن كانت فارغة ومواد مختارة
        should_regen = bool(selected_law_ids) and not texts_already
    elif previous_fp != content_fp:
        should_regen = True
    if should_regen:
        _set_tab3_generated_text("technical_description", generated_fields["technicalDraftText"])
        _set_tab3_generated_text("p1_reasons", generated_fields["legalOpinionText"])
    st.session_state.tab3_content_fingerprint = content_fp
    if generated_fields["hasCriminalSuspicion"]:
        st.warning("تشمل المواد المختارة شقاً جنائياً أو شبه جنائي، وتُحال إلى الشرطة أو النيابة.")
    render_video_evidence_engine()
    # بعد محرك القرائن: حدّث البصمة دون إعادة توليد إن تغيّرت القرائن فقط عبر المحرك نفسه
    content_fp = compute_tab3_content_fingerprint()
    st.session_state.tab3_content_fingerprint = content_fp

    # بنود إضافية في نتائج الحادث — saved_* مصدر الحقيقة؛ on_change يرقّع النص حتى مع is_manual
    _ensure_results_extras_defaults()
    st.markdown("#### بنود إضافية في نتائج الحادث")
    _ex1, _ex2 = st.columns(2)
    with _ex1:
        st.checkbox(
            "نفوق حيوانات/مواشي أو حيوان أليف",
            key="results_animal_loss_enabled",
            on_change=_on_results_extras_change,
        )
        if st.session_state.get("results_animal_loss_enabled") or st.session_state.get(SAVED_HAS_ANIMALS):
            st.text_input(
                "وصف النفوق (يُدرج بنداً في النتائج):",
                key="results_animal_loss_text",
                placeholder="مثلاً: نفوق رأسي أغنام في موقع الحادث",
                on_change=_on_results_extras_change,
            )
    with _ex2:
        st.checkbox(
            "تلفيات ممتلكات عامة أو خاصة",
            key="results_property_damage_enabled",
            on_change=_on_results_extras_change,
        )
        if st.session_state.get("results_property_damage_enabled") or st.session_state.get(SAVED_HAS_PROP):
            st.text_input(
                "وصف التلفيات (يُدرج بنداً في النتائج):",
                key="results_property_damage_text",
                placeholder="مثلاً: تلفيات عمود إنارة / سياج",
                on_change=_on_results_extras_change,
            )
    # مزامنة الودجات → saved_* ثم ترقيع النص (إن لم يُستدعَ on_change بعد)
    _sync_results_extras_widgets_to_saved()
    patch_saved_results_extras(bump_rev=True)

    # نتائج الحادث من الأطراف/المركبات — لا تُكتب فوق النص إن is_manual
    # (بنود النفوق/التلفيات تُرقَّع أعلاه حتى مع is_manual)
    results_fp = compute_results_data_fingerprint()
    previous_results_fp = st.session_state.get("results_data_fingerprint")
    should_regen_results = previous_results_fp is None or previous_results_fp != results_fp
    if should_regen_results and not _tab3_text_is_manual("accident_results"):
        generated_results = _strip_results_lead_in(build_accident_results_text())
        _set_tab3_generated_text("accident_results", generated_results)
        # ثبّت أجسام البنود الإضافية بعد التوليد الكامل
        if st.session_state.get(SAVED_HAS_ANIMALS):
            st.session_state[_LAST_ANIMAL_RESULT_BODY] = (
                _normalize_result_item_body(st.session_state.get(SAVED_ANIMALS_DESC) or "")
                or RESULTS_ANIMAL_DEFAULT
            )
        if st.session_state.get(SAVED_HAS_PROP):
            st.session_state[_LAST_PROP_RESULT_BODY] = (
                _normalize_result_item_body(st.session_state.get(SAVED_PROP_DESC) or "")
                or RESULTS_PROP_DEFAULT
            )
    elif not _tab3_text_is_manual("accident_results"):
        _cleaned_results = _strip_results_lead_in(_read_tab3_saved_text("accident_results"))
        if _cleaned_results != _read_tab3_saved_text("accident_results"):
            _write_tab3_saved_text("accident_results", _cleaned_results, mark_manual=False)
    st.session_state.results_data_fingerprint = results_fp

    acc_results = render_tab3_locked_text_area(
        "accident_results",
        "نتائج الحادث (معاينة/تعديل يدوي قبل الطباعة)",
        height=110,
    )
    acc_how = render_tab3_locked_text_area(
        "technical_description",
        "كيفية وقوع الحادث (الصياغة الفنية الدقيقة)",
        height=140,
    )
    if "p1_title_input" not in st.session_state:
        st.session_state.p1_title_input = DEFAULT_REPORT_STATE["p1_title_input"]
    if "p2_custom_title" not in st.session_state:
        st.session_state.p2_custom_title = DEFAULT_REPORT_STATE["p2_custom_title"]
    if "p1_reasons" not in st.session_state and _is_blank_form_value(_read_tab3_saved_text("p1_reasons")):
        _write_tab3_saved_text("p1_reasons", DEFAULT_REPORT_STATE["p1_reasons"], mark_manual=False)
    if "p2_reasons" not in st.session_state and _is_blank_form_value(_read_tab3_saved_text("p2_reasons")):
        _write_tab3_saved_text("p2_reasons", DEFAULT_REPORT_STATE["p2_reasons"], mark_manual=False)
    if not isinstance(st.session_state.get("custom_p1_ratio"), int):
        try:
            st.session_state.custom_p1_ratio = int(st.session_state.get("custom_p1_ratio") or 75)
        except (TypeError, ValueError):
            st.session_state.custom_p1_ratio = 75
    _role_titles = refresh_party_role_titles(force=False)
    st.markdown("### ⚖️ الرأي وتوزيع نسب المسؤولية")
    _liability_party_rows = _party_rows_for_liability(st.session_state.get("parties") or [])
    _license_violation_parties = _unqualified_driver_parties(st.session_state.get("parties") or [])
    # استبعاد الراكب/المشاة من قوائم توزيع المسؤولية ومخالفات رخصة القيادة
    if _liability_party_rows:
        _liab_labels = []
        for _idx, p in enumerate(_liability_party_rows, start=1):
            _role_title = (
                st.session_state.get(f"party_role_title_{_idx}")
                or build_driver_party_title(_idx)
                or (p.get("الطرف") or "طرف")
            )
            _liab_labels.append(
                f"{_role_title} — {(p.get('الاسم') or 'بدون اسم')} | {(p.get('التأهيل') or '')}"
            )
        st.caption("أطراف توزيع المسؤولية (السائقون فقط — الراكب/المشاة مستبعدون): " + " · ".join(_liab_labels))
    if _license_violation_parties:
        _lic_labels = [
            f"{(p.get('الطرف') or 'طرف')} — {(p.get('الاسم') or 'سائق')}"
            for p in _license_violation_parties
        ]
        st.info("مخالفات رخصة القيادة المحتملة (سائق غير مؤهل فقط): " + " · ".join(_lic_labels))
        # لا تُقترح مادة الرخصة على راكب/مشاة
        _sel = st.session_state.get("selected_articles") or []
        if "art_32" not in _sel:
            st.caption("يمكن إدراج المادة (32) يدوياً للسائق غير المؤهل عند الحاجة.")
        if "art_32" in _sel and "art_77" not in _sel:
            st.caption("إن سمح المالك لغير المرخص بالقيادة، أدرج المادة (77) لتضامن المالك في المسؤولية المادية.")
    ratio_options = list(_LIABILITY_RATIO_LOOKUP.keys())
    if st.session_state.get("liability_ratio_select") not in ratio_options:
        st.session_state.liability_ratio_select = ratio_options[0]
    selected_ratio = st.selectbox(
        "توزيع نسبة الخطأ والمسؤولية (وفق الفقرة 60/2):",
        options=ratio_options,
        key="liability_ratio_select", format_func=_fmt_ratio_rtl
    )
    p1_ratio, p2_ratio = _LIABILITY_RATIO_LOOKUP[selected_ratio]
    p1_ratio = int(p1_ratio)
    p2_ratio = int(p2_ratio)
    st.session_state["p1_ratio"] = p1_ratio
    st.session_state["p2_ratio"] = p2_ratio
    _p2_driver_title = (
        (_role_titles or {}).get(2)
        or st.session_state.get("party_role_title_2")
        or build_driver_party_title(2)
    )
    c_t1, c_t2 = st.columns(2)
    with c_t1:
        p1_title = st.text_input(
            "صفة الطرف الأول في التقرير:",
            key="p1_title_input"
        )
    with c_t2:
        p2_role_options = [
            _p2_driver_title,
            "عابر الطريق (المشاة)",
            "قائد الدراجة النارية / الهوائية",
            "تحديد صفة مخصصة",
        ]
        # ترحيل القيمة القديمة لصفة الطرف الثاني إلى الصيغة الجديدة باسم السائق
        _cur_p2 = str(st.session_state.get("p2_role_select") or "")
        if _cur_p2 not in p2_role_options:
            if _is_auto_managed_party_title(_cur_p2, 2) or _cur_p2.startswith("قائد المركبة الثانية"):
                st.session_state.p2_role_select = _p2_driver_title
            else:
                st.session_state.p2_role_select = p2_role_options[0]
        p2_role_type = st.selectbox(
            "نوع وصفة الطرف الثاني:",
            options=p2_role_options,
            key="p2_role_select"
        )
        if p2_role_type == "تحديد صفة مخصصة":
            p2_title = st.text_input(
                "اكتب صفة الطرف الثاني:",
                key="p2_custom_title"
            )
        else:
            p2_title = p2_role_type
        st.session_state["p2_title"] = p2_title
    if p1_ratio > 0:
        p1_reasons = render_tab3_locked_text_area(
            "p1_reasons",
            f"المواد النظامية وأسباب إدانة {p1_title} ({p1_ratio}%) — (كل سبب في سطر جديد):",
            height=110,
        )
    else:
        p1_reasons = _read_tab3_saved_text("p1_reasons")
    if p2_ratio > 0:
        p2_reasons = render_tab3_locked_text_area(
            "p2_reasons",
            f"المواد النظامية وأسباب إدانة {p2_title} ({p2_ratio}%) — (كل سبب في سطر جديد):",
            height=110,
        )
    else:
        p2_reasons = _read_tab3_saved_text("p2_reasons")
    liability_html = build_liability_section_html(
        p1_title=p1_title,
        p1_ratio=p1_ratio,
        p1_reasons=p1_reasons,
        p2_title=p2_title,
        p2_ratio=p2_ratio,
        p2_reasons=p2_reasons,
    )
    st.session_state["liability_html"] = liability_html
    st.session_state.tab3_content_fingerprint = compute_tab3_content_fingerprint()
    try:
        sync_permanent_form_data(reason="tab3_liability")
    except Exception:
        pass
ACTIONS_SCENARIOS = {
    "1. صلح وتنازل ميداني نهائي": (
        "تم إفهام الأطراف بحقوقهم النظامية، وانتهى الحادث بالصلح والتنازل الخطي التام بين الطرفين في الموقع دون أي مطالبات مالية أو حقوقية، وأُخلي سبيل الأطراف والمركبات."
    ),
    "2. إحالة للتقدير وشركة التأمين (تأمين ساري)": (
        "تم استكمال إجراءات المعاينة والرسم الكروكي، وإشعار الأطراف بمراجعة مركز تقدير أضرار المركبات (تقدير) ومطالبة شركة التأمين إلكترونياً بالحق الخاص."
    ),
    "3. عدم وجود تأمين / تعذر الصلح (إحالة للمحكمة المرورية)": (
        "لعدم وجود تأمين ساري وتعذر الصلح، تم توجيه المتضرر لمركز التقدير لتثبيت قيمة التلفيات، واستكمال أوراق المعاملة لإحالتها إلى المحكمة المختصة (الدائرة المرورية) للفصل في الحق الخاص."
    ),
    "4. حادث إصابات (إسعاف وطلب تقارير طبية)": (
        "تم إسعاف المصابين عبر الهلال الأحمر إلى المستشفى، ومخاطبة المستشفى لتزويدنا بالتقرير الطبي الأولي والنهائي موضحاً به مدة الشفاء، واتخاذ الإجراء النظامي بحق المتسبب (توقيف / كفالة نظامية)."
    ),
    "5. حادث وفاة (إيداع الجثمان وتوقيف وإحالة للنيابة العامة)": (
        "تمت معاينة الموقع ونقل الجثمان إلى ثلاجة الموتى بالمستشفى، وتوقيف السائق المتسبب وحجز المركبات، والرفع بملف القضية كاملاً إلى النيابة العامة بحكم الاختصاص للنظر في الحقين العام والخاص."
    ),
    "6. حادث دهس مشاة": (
        "تم نقل المصاب للمستشفى وطلب التقرير الطبي، ومعاينة نقطة الاصطدام ومسار العبور، وضبط أقوال السائق والشهود ومراجعة الكاميرات المحيطة بالموقع."
    ),
    "7. مخالفة جسيمة موجبة للتوقيف والحق العام (عكس سير / قطع إشارة / تجاوز خاطئ / تفحيط)": (
        "نظراً لارتكاب مخالفة مرورية جسيمة عرضت السلامة العامة للخطر، تم إيقاف السائق المتسبب وحجز المركبة وتطبيق المخالفة النظامية، وإحالة الأوراق لجهة الاختصاص للنظر في الحق العام."
    ),
    "8. اشتباه حالة غير طبيعية أو شبهة جنائية / مضبوطات": (
        "للاشتباه بوضع غير طبيعي أو شبهة جنائية، تم التحفظ الفوري على الأطراف والمركبة وتحرير محضر ضبط بالموجودات، وإحالة السائق للفحص الطبي المخبري وتسليم القضية لجهة الاختصاص (الشرطة / مكافحة المخدرات) مع حفظ الشق المروري."
    ),
    "9. هروب طرف من موقع الحادث (تعميم وبحث وتحري)": (
        "نظراً لهروب أحد أطراف الحادث من الموقع، تم تدوين الأوصاف والمعلومات المتوفرة ومراجعة كاميرات المراقبة، ومخاطبة العمليات للتعميم عن المركبة والبحث والتحري لضبط السائق الهارب."
    ),
    "10. عهدة رسمية أو عسكرية بحوزة أحد الأطراف (سلاح / أجهزة / مناظير)": (
        "تبين أن أحد الأطراف بالزي الرسمي وبحوزته عهدة رسمية (سلاح شخصي / ذخيرة / جهاز اتصال)، وتم جردها والتحفظ عليها بموجب محضر رسمي وتسليمها لمندوب مرجعه الرسمي."
    ),
    "11. طرف مركبة حكومية / رسمية": (
        "نظراً لكون إحدى المركبات حكومية، تم إشعار الجهة الرسمية التابع لها السائق لحضور مندوبها وحصر التلفيات واستكمال الإجراءات المتبعة لمركبات الدولة."
    ),
    "12. تلفيات ممتلكات عامة أو خاصة (عمود إنارة / كهرباء / سياج / لوحة إرشادية)": (
        "تم حصر التلفيات الواقعة على الممتلكات العامة/الخاصة بالمحضر، ومخاطبة الجهة المتضررة (البلدية / شركة الكهرباء / وزارة النقل / المالك) لتقدير قيمة التلفيات ومطالبة المتسبب أو التأمين بها."
    ),
    "13. حادث مفرد لطرف واحد (انقلاب / انحراف / ارتطام بجبل أو عائق ثابت)": (
        "تمت معاينة الموقع وتبين أنه حادث مفرد دون اشتراك طرف آخر أو وجود شبهة جنائية، وتم حصر التلفيات ورفع المركبة لتأمين سلامة الطريق."
    ),
    "14. ارتطام بحيوان سائب (إبل / ماشية)": (
        "تمت معاينة الموقع وتحديد زمن وقوع الحادث وحرم الطريق، والتحري عن مالك الحيوان السائب (عبر الوسم أو الشريحة) لاستدعائه وتطبيق التعليمات واللوائح المنظمة لذلك."
    ),
    "15. قيادة حدث (صغير سن) أو غير مؤهل للقيادة": (
        "تم رصد مخالفة عدم وجود رخصة قيادة، واستدعاء ولي أمر الحدث / مالك المركبة وأخذ الإقرارات والكفالة النظامية (أو الإحالة لدار الملاحظة الاجتماعية في الحوادث الجسيمة)."
    ),
    "16. حجز المركبات بالسطحة وإخلاء الطريق": (
        "تم رفع المركبات المتضررة بواسطة السطحة وإيداعها حجز المرور لعدم صلاحيتها للسير أو لوجود مطالبة قائمة، وإزالة مخلفات الحادث وإعادة فتح الحركة المرورية."
    ),
    "17. تضرر بضائع أو حمولات منقولة (شاحنات)": (
        "تم إثبات حالة الحمولة المتضررة في المحضر وإشعار مالك البضاعة / الناقل لاستكمال إجراءات التقدير والتأمين، وتأمين نقل الحمولة من نهر الطريق."
    ),
    "18. تعذر سحب المركبة أو انتشالها لقاء سقوطها من مرتفع": (
        "تعذر سحب المركبة أو انتشالها من موقع استقرارها وقت المعاينة لقاء سقوطها من مرتفع شديد الوعورة وصعوبة وصول آليات السحب والرفع إليها، وجرى إثبات الحالة في الموقع واتخاذ الإجراءات النظامية اللازمة."
    ),
    "19. عمل محضر مشترك مع الدفاع المدني": (
        "جرى الشخوص لموقع الحادث ومباشرته بالاشتراك مع فرقة الدفاع المدني المختصة، وتم عمل محضر مشترك مع الدفاع المدني يتضمن وقائع الحالة والإجراءات المتخذة في الموقع وإرفاقه بأوراق المعاملة."
    ),
    "20. إيداع جثمان المتوفى بثلاجة الموتى بالمستشفى": (
        "تم إيداع جثمان المتوفى بثلاجة الموتى بالمستشفى وإثبات ذلك في أوراق المعاملة."
    ),
    "21. عمل خطاب كشف طبي على الجثمان للمتوفين": (
        "تم عمل خطاب كشف طبي على الجثمان للمتوفى وإرفاقه بأوراق المعاملة."
    ),
    "22. حصر وتحريز المتعلقات الشخصية للمتوفى بمحضر رسمي": (
        "تم حصر وتحريز المتعلقات الشخصية للمتوفى بمحضر رسمي وإرفاقه بأوراق المعاملة."
    ),
    "23. إشعار ذوي المتوفى وطلب صك حصر الورثة والوكالة الشرعية": (
        "تم إشعار ذوي المتوفى وطلب صك حصر الورثة والوكالة الشرعية لاستكمال الإجراءات النظامية."
    ),
    "24. إشعار النيابة العامة والجهات المختصة بوقوع حادث وفاة": (
        "تم إشعار النيابة العامة والجهات المختصة بوقوع حادث وفاة واستكمال اللازم نظاماً."
    ),
    "25. إصدار خطاب تسليم الجثمان وتصريح الدفن بعد الكشف الطبي": (
        "تم إصدار خطاب تسليم الجثمان وتصريح الدفن بعد الكشف الطبي."
    ),
    "26. انقضاء الدعوى الجزائية العامة لوفاة المتسبب في الحادث": (
        "تقرر انقضاء الدعوى الجزائية العامة لوفاة المتسبب في الحادث وفق الموجب النظامي."
    ),
}

FATALITY_ACTION_NUMBERS = set(range(20, 27))

def _accident_deaths_count() -> int:
    try:
        return int(st.session_state.get("p1_acc_deaths") or 0)
    except (TypeError, ValueError):
        return 0

def _action_key_number(key) -> int:
    try:
        head = str(key or "").strip().split(".", 1)[0].strip()
        return int(head)
    except (TypeError, ValueError):
        return -1

def pluralize_fatality_action_text(text: str, deaths_count: int = None) -> str:
    """ذكاء لغوي لجمع صياغات بنود الوفيات 20–26 عند عدد الوفيات ≥ 2."""
    if deaths_count is None:
        deaths_count = _accident_deaths_count()
    out = str(text or "")
    if int(deaths_count or 0) < 2:
        return out
    # الأطول أولاً حتى لا يُكسر «جثمان المتوفى» إلى «جثمان المتوفين»
    out = out.replace("جثمان المتوفى", "جثامين المتوفين")
    out = out.replace("للمتوفى", "للمتوفين")
    out = out.replace("المتوفى", "المتوفين")
    return out

def action_scenario_text(key: str, deaths_count: int = None) -> str:
    raw = ACTIONS_SCENARIOS.get(key, "")
    if _action_key_number(key) in FATALITY_ACTION_NUMBERS:
        return pluralize_fatality_action_text(raw, deaths_count)
    return raw

def sync_selected_actions():
    selected_keys = [
        key for key in st.session_state.get("selected_actions_multi", [])
        if key in ACTIONS_SCENARIOS
    ]
    if not selected_keys:
        st.session_state["actions_taken_editor"] = ""
        return
    deaths_count = _accident_deaths_count()
    lines = [
        f"{idx}- {action_scenario_text(key, deaths_count)}"
        for idx, key in enumerate(selected_keys, start=1)
    ]
    st.session_state["actions_taken_editor"] = "\n".join(lines)
    st.session_state["_actions_plural_deaths_sig"] = deaths_count

flush_pending_casualty_actions()
if st.session_state.active_tab == MAIN_TAB_OPTIONS[2]:
    st.markdown(
        "<hr style='border:0;height:1px;background:linear-gradient(90deg,transparent,#7dd3fc,transparent);margin:22px 0 14px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown("### 📋 التصنيف والحقوق والإجراءات المتخذة (الصفحة 3)")
    accident_nature_options = [
        "حادث مروري اعتيادي (تلفيات مادية)",
        "حادث مروري جسيم (إصابات)",
        "حادث مروري جسيم (وفاة)",
        "حادث دهس (مشاة)",
        "حادث مفرد لطرف واحد (انقلاب / ارتطام بثابت)",
        "حادث ارتطام بحيوان سائب",
        "حادث مصحوب بهروب من الموقع",
        "حادث مصحوب بشبهة جنائية / حالة غير طبيعية",
        "تحديد تصنيف مخصص",
    ]
    rights_options = [
        "انقضاء الحق الخاص بالتنازل والصلح، ولا يوجد حق عام",
        "قيام الحق الخاص فقط (تنازل أو صلح)",
        "قيام الحق الخاص فقط (مطالبة تأمينية / تقدير)",
        "قيام الحق الخاص فقط (إحالة للمحكمة المرورية)",
        "قيام الحقين العام والخاص معاً (إصابات / وفاة / مخالفة جسيمة)",
        "قيام الحق العام فقط (مع التنازل عن الحق الخاص)",
        "قيام حق مالي لجهة عامة / خاصة (تلفيات ممتلكات)",
        "تحديد حقوق مخصصة",
    ]
    if st.session_state.get("acc_nature_sel") not in accident_nature_options:
        st.session_state.acc_nature_sel = accident_nature_options[0]
    if "acc_nature_custom" not in st.session_state:
        st.session_state.acc_nature_custom = "حادث مروري اعتيادي"
    if st.session_state.get("rights_sel") not in rights_options:
        st.session_state.rights_sel = rights_options[0]
    if "rights_custom" not in st.session_state:
        st.session_state.rights_custom = ""
    if not isinstance(st.session_state.get("selected_actions_multi"), list):
        st.session_state.selected_actions_multi = ["1. صلح وتنازل ميداني نهائي"]
    st.session_state.selected_actions_multi = [
        key for key in st.session_state.selected_actions_multi if key in ACTIONS_SCENARIOS
    ]
    if "actions_taken_editor" not in st.session_state:
        st.session_state.actions_taken_editor = f"1- {ACTIONS_SCENARIOS['1. صلح وتنازل ميداني نهائي']}"
    col_p3_1, col_p3_2 = st.columns(2)
    with col_p3_1:
        selected_nature = st.selectbox(
            "طبيعة وتصنيف الحادث:",
            options=accident_nature_options,
            key="acc_nature_sel"
        )
        if selected_nature == "تحديد تصنيف مخصص":
            accident_nature_val = st.text_input(
                "اكتب طبيعة وتصنيف الحادث:",
                key="acc_nature_custom"
            )
        else:
            accident_nature_val = selected_nature
    with col_p3_2:
        selected_rights = st.selectbox(
            "الحقوق الخاصة والعامة:",
            options=rights_options,
            key="rights_sel"
        )
        if selected_rights == "تحديد حقوق مخصصة":
            rights_status_val = st.text_input(
                "اكتب حالة الحقوق الخاصة والعامة:",
                key="rights_custom"
            )
        else:
            rights_status_val = selected_rights
    st.session_state["accident_nature"] = str(accident_nature_val or "")
    st.session_state["rights_status"] = str(rights_status_val or "")
    # إعادة توليد صياغات بنود الوفيات 20–26 عند تغيّر عدد الوفيات
    _deaths_for_actions = _accident_deaths_count()
    if st.session_state.get("_actions_plural_deaths_sig") != _deaths_for_actions:
        sync_selected_actions()
    st.multiselect(
        "اختر إجراءً واحداً أو ادمج عدة إجراءات معاً (تُرقّم تلقائياً بالأسفل):",
        options=list(ACTIONS_SCENARIOS.keys()),
        key="selected_actions_multi",
        on_change=sync_selected_actions,
    )
    actions_taken_raw = st.text_area(
        "النص النهائي لـ (الإجراءات المتخذة) في التقرير — يمكنك التعديل أو إضافة تفاصيل (مثل نوع العهدة أو اسم المستشفى):",
        height=120,
        key="actions_taken_editor"
    )
    final_actions_html = "<br>".join(
        html.escape(line.strip()) for line in str(actions_taken_raw or "").splitlines() if line.strip()
    )
    st.session_state["final_actions_html"] = final_actions_html
    accident_nature = str(st.session_state.get("accident_nature") or accident_nature_val or "")
    rights_status = str(st.session_state.get("rights_status") or rights_status_val or "")
    if "جنائي" in accident_nature:
        st.markdown("#### 🚨 تفاصيل الشق الجنائي والأمني")
        col1, col2 = st.columns(2)
        with col1:
            participating_agency = st.text_input(
                "الجهة الأمنية المباشرة (مثل: الأفواج الأمنية / الدوريات):",
                placeholder="مثال: سرية المهام - الفوج الأول",
                key="criminal_participating_agency",
            )
            escaped_vehicles = st.text_input(
                "بيانات المركبات الهاربة أو المعترضة (إن وجدت):",
                key="criminal_escaped_vehicles",
            )
        with col2:
            shots_fired = st.selectbox(
                "هل تم إطلاق نار أثناء المطاردة؟",
                ["لا", "نعم - طلقات تحذيرية فقط", "نعم - طلقات تحذيرية ومباشرة لإعطاب المركبة"],
                key="criminal_shots_fired",
            )
            contraband_found = st.selectbox(
                "نتيجة تفتيش المركبة:",
                ["لم يتم العثور على ممنوعات", "تم العثور على ممنوعات (يرفق بمحضر الضبط)"],
                key="criminal_contraband_found",
            )
    else:
        participating_agency = str(st.session_state.get("criminal_participating_agency") or "")
        escaped_vehicles = str(st.session_state.get("criminal_escaped_vehicles") or "")
        shots_fired = str(st.session_state.get("criminal_shots_fired") or "")
        contraband_found = str(st.session_state.get("criminal_contraband_found") or "")
    try:
        sync_permanent_form_data(reason="tab3_actions")
    except Exception:
        pass
_SKETCH_ATTACH_LABEL = "✅ إرفاق صفحة الكروكي"
_SKETCH_OMIT_LABEL = "❌ حذف صفحة الكروكي - حادث قديم"

def _on_sketch_choice_tab4():
    st.session_state.include_sketch = st.session_state.get("include_sketch_choice_tab4") == _SKETCH_ATTACH_LABEL

def _on_sketch_choice_tab5():
    st.session_state.include_sketch = st.session_state.get("include_sketch_choice_tab5") == _SKETCH_ATTACH_LABEL

def _sketch_availability_control(widget_key, on_change):
    """مفتاح الواجهة مستقل عن include_sketch؛ تُحدَّث القيمة الدائمة عبر on_change فقط."""
    if not isinstance(st.session_state.get("include_sketch"), bool):
        st.session_state.include_sketch = True
    selected = _SKETCH_ATTACH_LABEL if st.session_state.include_sketch else _SKETCH_OMIT_LABEL
    # مزامنة مفتاح الواجهة قبل الرسم فقط (لا بعده)
    if st.session_state.get(widget_key) not in (_SKETCH_ATTACH_LABEL, _SKETCH_OMIT_LABEL):
        st.session_state[widget_key] = selected
    elif st.session_state.get(widget_key) != selected and st.session_state.get("_force_sketch_choice_sync"):
        st.session_state[widget_key] = selected
        st.session_state.pop("_force_sketch_choice_sync", None)
    st.radio(
        "حالة الرسم الكروكي في التقرير",
        (_SKETCH_ATTACH_LABEL, _SKETCH_OMIT_LABEL),
        key=widget_key,
        on_change=on_change,
        horizontal=True,
    )
    # لا تسند إلى session_state[widget_key] بعد الرسم — حدّث البيانات فقط
    st.session_state.include_sketch = st.session_state.get(widget_key) == _SKETCH_ATTACH_LABEL

SKETCH_DATA_URL_KEY = "sketch_data_url"
SKETCH_URI_PATH = SAVED_IMAGES_DIR / "adopted_sketch_uri.txt"
AERIAL_DATA_URL_KEY = "aerial_sketch_data_url"
AERIAL_URI_PATH = SAVED_IMAGES_DIR / "adopted_aerial_uri.txt"
AERIAL_STATE_PATH = SAVED_IMAGES_DIR / "adopted_aerial_state.json"
REPORT_MEDIA_MODE_PATH = SAVED_IMAGES_DIR / "report_media_mode.txt"
REPORT_MEDIA_OPTIONS = ("كلاهما", "كروكي فقط", "جوي فقط")
REPORT_MEDIA_MODE_KEY = "report_media_mode"
REPORT_MEDIA_MODE_UI_KEY = "report_media_mode_ui"

def _remember_sketch_data_url(data_uri: str, state_key: str = SKETCH_DATA_URL_KEY):
    image = str(data_uri or "").strip()
    if not image.startswith("data:image/"):
        return
    st.session_state[state_key] = image
    st.session_state[SKETCH_DATA_URL_KEY] = image
    try:
        SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        SKETCH_URI_PATH.write_text(image, encoding="utf-8")
    except OSError:
        pass

def _load_remembered_sketch():
    current = str(st.session_state.get(SKETCH_DATA_URL_KEY) or "").strip()
    if current.startswith("data:image/"):
        return
    if not SKETCH_URI_PATH.is_file():
        return
    try:
        stored = SKETCH_URI_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if stored.startswith("data:image/"):
        st.session_state[SKETCH_DATA_URL_KEY] = stored

def _clear_remembered_sketch():
    for key in (SKETCH_DATA_URL_KEY, "_saved_asphalt_state", "saved_asphalt_state", "_last_sketch_commit_ts"):
        st.session_state.pop(key, None)
    try:
        if SKETCH_URI_PATH.is_file():
            SKETCH_URI_PATH.unlink()
        adopted_png = SAVED_IMAGES_DIR / "adopted_sketch.png"
        if adopted_png.is_file():
            adopted_png.unlink()
    except OSError:
        pass

def _remember_aerial_data_url(data_uri: str, map_state=None):
    image = str(data_uri or "").strip()
    if not image.startswith("data:image/"):
        return
    st.session_state[AERIAL_DATA_URL_KEY] = image
    st.session_state["aerial_sketch_data_url"] = image
    st.session_state["include_aerial"] = True
    state = map_state if isinstance(map_state, dict) else {}
    st.session_state["_saved_satellite_state"] = dict(state)
    st.session_state["saved_satellite_state"] = dict(state)
    try:
        SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        AERIAL_URI_PATH.write_text(image, encoding="utf-8")
        AERIAL_STATE_PATH.write_text(
            json.dumps({
                "state": state,
                "aerial_place": st.session_state.get("aerial_place", "below"),
                "studio_layout_mode": st.session_state.get("_studio_layout_mode")
                    or st.session_state.get("studio_layout_mode")
                    or "🖥️ عرض مزدوج: الكروكي التفاعلي وبجانبه خريطة التصوير الجوي",
                "report_media_mode": st.session_state.get("report_media_mode", "كلاهما"),
                "include_aerial": True,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

def _load_remembered_aerial():
    current = str(st.session_state.get(AERIAL_DATA_URL_KEY) or st.session_state.get("aerial_sketch_data_url") or "").strip()
    restored_image = False
    if not current.startswith("data:image/") and AERIAL_URI_PATH.is_file():
        try:
            stored = AERIAL_URI_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            stored = ""
        if stored.startswith("data:image/"):
            st.session_state[AERIAL_DATA_URL_KEY] = stored
            st.session_state["aerial_sketch_data_url"] = stored
            current = stored
            restored_image = True
    existing_state = st.session_state.get("_saved_satellite_state") or st.session_state.get("saved_satellite_state")
    need_meta = restored_image or not isinstance(existing_state, dict) or not existing_state
    if need_meta and AERIAL_STATE_PATH.is_file():
        try:
            meta = json.loads(AERIAL_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            meta = {}
        if isinstance(meta, dict):
            state = meta.get("state") if isinstance(meta.get("state"), dict) else {}
            if state and (not isinstance(existing_state, dict) or not existing_state):
                st.session_state["_saved_satellite_state"] = dict(state)
                st.session_state["saved_satellite_state"] = dict(state)
            # لا ت overlapping مع ودجتات الجلسة بعد تهيئتها
            if restored_image or "aerial_place_choice" not in st.session_state:
                if meta.get("aerial_place") in ("below", "beside"):
                    st.session_state["aerial_place"] = meta.get("aerial_place")
                    st.session_state["aerial_place_choice"] = (
                        "بجانب الكروكي" if meta.get("aerial_place") == "beside" else "أسفل الكروكي"
                    )
            if restored_image or "_studio_layout_mode" not in st.session_state:
                layout = str(meta.get("studio_layout_mode") or "").strip()
                if layout:
                    st.session_state["studio_layout_mode"] = layout
                    st.session_state["_studio_layout_mode"] = layout
            if restored_image or "report_media_mode" not in st.session_state:
                mode = str(meta.get("report_media_mode") or "").strip()
                if mode in ("كلاهما", "كروكي فقط", "جوي فقط"):
                    st.session_state["report_media_mode"] = mode
                    st.session_state.pop("report_media_mode_ui", None)
            if restored_image and "include_aerial" in meta:
                st.session_state["include_aerial"] = bool(meta.get("include_aerial"))
    if current.startswith("data:image/") and st.session_state.get("include_aerial") is None:
        st.session_state["include_aerial"] = True
    # استرجاع وضع العرض من الملف الدائم إن لزم
    if st.session_state.get("report_media_mode") not in ("كلاهما", "كروكي فقط", "جوي فقط"):
        try:
            if REPORT_MEDIA_MODE_PATH.is_file():
                disk_mode = REPORT_MEDIA_MODE_PATH.read_text(encoding="utf-8").strip()
                if disk_mode in ("كلاهما", "كروكي فقط", "جوي فقط"):
                    st.session_state["report_media_mode"] = disk_mode
                    st.session_state.pop("report_media_mode_ui", None)
        except OSError:
            pass

def _clear_remembered_aerial():
    for key in (
        AERIAL_DATA_URL_KEY,
        "aerial_sketch_data_url",
        "_saved_satellite_state",
        "saved_satellite_state",
        "_last_aerial_commit_ts",
    ):
        st.session_state.pop(key, None)
    st.session_state["include_aerial"] = False
    try:
        for path in (AERIAL_URI_PATH, AERIAL_STATE_PATH):
            if path.is_file():
                path.unlink()
    except OSError:
        pass

# استرجاع الكروكي/الجوي عند كل تشغيل بعد تعريف الدوال — لا تُمسَح عند مغادرة التبويب
try:
    _load_remembered_sketch()
except Exception:
    pass
try:
    _load_remembered_aerial()
except Exception:
    pass
try:
    import bayyinah_persistence as _bp_media
    _bp_media.ensure_media_every_cycle()
except Exception:
    pass
# تصفير ذاكرة المتصفح للكروكي فقط عند «حادث جديد»
if st.session_state.pop("_BAYYINAH_CLEAR_BROWSER_SKETCH_", None):
    st.components.v1.html(
        """
<script>
(function(){
  try {
    var p = window.parent;
    if (p) {
      p.__BAYYINAH_SKETCH_STATE__ = { asphalt: null, aerial: null, clearedAt: Date.now() };
      try { p.localStorage.removeItem("bayyinah_asphalt_editor"); } catch (e1) {}
      try { p.localStorage.removeItem("bayyinah_aerial_editor"); } catch (e2) {}
    }
    try {
      indexedDB.deleteDatabase("BayyinahPersistDB");
    } catch (e3) {}
  } catch (err) {}
})();
</script>
        """,
        height=0,
    )

_ASPHALT_COMP_DIR = Path(__file__).resolve().parent / "asphalt_studio_component"
_asphalt_studio_component = components.declare_component(
    "asphalt_sketch_studio",
    path=str(_ASPHALT_COMP_DIR),
)
_SATELLITE_COMP_DIR = Path(__file__).resolve().parent / "satellite_studio_component"
_satellite_studio_component = components.declare_component(
    "satellite_tactical_studio",
    path=str(_SATELLITE_COMP_DIR),
)

def _store_committed_sketch(data_uri: str, sketch_image_state_key: str):
    image = str(data_uri or "").strip()
    if not image.startswith("data:image/"):
        return
    st.session_state[sketch_image_state_key] = image
    st.session_state[SKETCH_DATA_URL_KEY] = image
    _remember_sketch_data_url(image, SKETCH_DATA_URL_KEY)

_LAYOUT_DUAL = "🖥️ عرض مزدوج: الكروكي التفاعلي وبجانبه خريطة التصوير الجوي"
_LAYOUT_SKETCH = "🛣️ الكروكي التفاعلي بعرض كامل"
_LAYOUT_SAT = "🛰️ خريطة التصوير الجوي بعرض كامل"

def _accept_asphalt_commit(sketch_image_state_key: str, default_loc: str):
    saved_state = st.session_state.get("_saved_asphalt_state")
    result = _asphalt_studio_component(
        default_loc=default_loc,
        saved_state=saved_state,
        key="bayyinah_asphalt_studio_v2",
        default=None,
    )
    if isinstance(result, dict) and result.get("image"):
        last_ts = st.session_state.get("_last_sketch_commit_ts")
        if result.get("ts") != last_ts:
            st.session_state["_last_sketch_commit_ts"] = result.get("ts")
            _store_committed_sketch(result["image"], sketch_image_state_key)
            committed_state = result.get("state") if isinstance(result.get("state"), dict) else {}
            if committed_state.get("fallMeters") is None and isinstance(saved_state, dict) and saved_state.get("fallMeters") is not None:
                committed_state["fallMeters"] = saved_state.get("fallMeters")
            st.session_state["_saved_asphalt_state"] = committed_state
            st.session_state["saved_asphalt_state"] = committed_state
            try:
                import bayyinah_persistence as _bp
                _bp.save_full_workspace(reason="sketch_commit")
            except Exception:
                pass
            st.toast("✅ تم اعتماد الكروكي في تقرير A4 بنجاح!")

def _normalize_satellite_state(raw_state):
    state = dict(raw_state) if isinstance(raw_state, dict) else {}
    center = state.get("center")
    lat = state.get("lat")
    lng = state.get("lng")
    if isinstance(center, (list, tuple)) and len(center) >= 2:
        try:
            lat = float(center[0]) if lat is None else float(lat)
            lng = float(center[1]) if lng is None else float(lng)
        except (TypeError, ValueError):
            pass
    elif lat is not None and lng is not None:
        try:
            state["center"] = [float(lat), float(lng)]
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            pass
    if lat is not None and lng is not None:
        state["lat"] = lat
        state["lng"] = lng
        state["center"] = [lat, lng]
    try:
        state["zoom"] = int(state.get("zoom") or 18)
    except (TypeError, ValueError):
        state["zoom"] = 18
    if not isinstance(state.get("shapes"), list):
        state["shapes"] = []
    provider = str(state.get("provider") or state.get("tileProvider") or "google").strip().lower()
    state["provider"] = "esri" if provider == "esri" else "google"
    state["labelsVisible"] = bool(state.get("labelsVisible", True))
    return state

def _normalize_report_media_mode(mode) -> str:
    text = str(mode or "").strip()
    return text if text in REPORT_MEDIA_OPTIONS else "كلاهما"

def _persist_report_media_mode_disk(mode: str):
    mode = _normalize_report_media_mode(mode)
    try:
        SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_MEDIA_MODE_PATH.write_text(mode, encoding="utf-8")
        if AERIAL_STATE_PATH.is_file():
            try:
                meta = json.loads(AERIAL_STATE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                meta = {}
            if isinstance(meta, dict):
                meta["report_media_mode"] = mode
                AERIAL_STATE_PATH.write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
    except OSError:
        pass

def _sync_include_flags_from_media_mode(mode: str):
    mode = _normalize_report_media_mode(mode)
    if mode == "كروكي فقط":
        st.session_state["include_sketch"] = True
        st.session_state["include_aerial"] = False
    elif mode == "جوي فقط":
        st.session_state["include_sketch"] = False
        st.session_state["include_aerial"] = True
    else:
        st.session_state["include_sketch"] = True
        st.session_state["include_aerial"] = True
    return mode

def _sync_report_media_mode_from_flags():
    include_sketch = bool(st.session_state.get("include_sketch", True))
    include_aerial = bool(st.session_state.get("include_aerial", True))
    mode = st.session_state.get(REPORT_MEDIA_MODE_KEY)
    if mode not in REPORT_MEDIA_OPTIONS:
        if include_sketch and include_aerial:
            mode = "كلاهما"
        elif include_aerial and not include_sketch:
            mode = "جوي فقط"
        else:
            mode = "كروكي فقط"
        st.session_state[REPORT_MEDIA_MODE_KEY] = mode
        _persist_report_media_mode_disk(mode)
    return mode

def _apply_report_media_mode(mode: str, *, refresh_ui: bool = False):
    """تحديث قيمة البيانات فقط (ليس مفتاح الواجهة). عند التغيير البرمجي: pop للـ UI ثم rerun."""
    mode = _sync_include_flags_from_media_mode(mode)
    st.session_state[REPORT_MEDIA_MODE_KEY] = mode
    _persist_report_media_mode_disk(mode)
    if refresh_ui:
        st.session_state.pop(REPORT_MEDIA_MODE_UI_KEY, None)

def _on_report_media_mode_ui_change():
    choice = st.session_state.get(REPORT_MEDIA_MODE_UI_KEY)
    _apply_report_media_mode(choice, refresh_ui=False)

def _render_report_media_mode_control():
    """راديو بواجهة مستقلة عن مفتاح الحفظ الدائم لتفادي StreamlitWidgetAlreadyInstantiatedError."""
    _sync_report_media_mode_from_flags()
    current = _normalize_report_media_mode(st.session_state.get(REPORT_MEDIA_MODE_KEY))
    st.session_state[REPORT_MEDIA_MODE_KEY] = current
    # تهيئة مفتاح الواجهة قبل الرسم فقط إن كان غائباً/غير صالح (لا تعدّله بعد الرسم)
    if st.session_state.get(REPORT_MEDIA_MODE_UI_KEY) not in REPORT_MEDIA_OPTIONS:
        st.session_state[REPORT_MEDIA_MODE_UI_KEY] = current
    st.radio(
        "محتوى التقرير المعتمد",
        options=list(REPORT_MEDIA_OPTIONS),
        horizontal=True,
        key=REPORT_MEDIA_MODE_UI_KEY,
        on_change=_on_report_media_mode_ui_change,
    )
    # مزامنة الأعلام من القيمة المحفوظة دون الكتابة على مفتاح الواجهة
    _sync_include_flags_from_media_mode(st.session_state.get(REPORT_MEDIA_MODE_KEY))

def _render_aerial_reference():
    saved_state = _normalize_satellite_state(
        st.session_state.get("_saved_satellite_state") or st.session_state.get("saved_satellite_state")
    )
    sat_result = _satellite_studio_component(
        saved_sat_state=saved_state or None,
        key="bayyinah_satellite_studio_v1",
        default=None,
    )
    if isinstance(sat_result, dict) and str(sat_result.get("image") or "").startswith("data:image/"):
        last_ts = st.session_state.get("_last_aerial_commit_ts")
        if sat_result.get("ts") != last_ts:
            st.session_state["_last_aerial_commit_ts"] = sat_result.get("ts")
            map_state = _normalize_satellite_state(sat_result.get("state"))
            # حفظ فوري دائم عند الاعتماد (نفس أسلوب الكروكي)
            _remember_aerial_data_url(sat_result["image"], map_state)
            try:
                import bayyinah_persistence as _bp
                _bp.save_full_workspace(reason="aerial_commit")
            except Exception:
                pass
            if st.session_state.get(REPORT_MEDIA_MODE_KEY) == "كروكي فقط":
                _apply_report_media_mode("كلاهما", refresh_ui=True)
                st.toast("✅ تم اعتماد التصوير الجوي في تقرير A4 بنجاح!")
                st.rerun()
            st.session_state["include_aerial"] = True
            st.toast("✅ تم اعتماد التصوير الجوي في تقرير A4 بنجاح!")
    aerial_preview = str(st.session_state.get("aerial_sketch_data_url") or "").strip()
    if aerial_preview.startswith("data:image/"):
        st.success("✅ التصوير الجوي محفوظ ومعتمد في التقرير")
        try:
            st.image(base64.b64decode(aerial_preview.split(",", 1)[-1]), width=280)
        except Exception:
            pass
        if st.button("🗑️ حذف التصوير الجوي المعتمد", key="_remove_aerial_sketch"):
            _clear_remembered_aerial()
            # بعد حذف الجوي: إن كان الوضع «جوي فقط» ارجع لـ «كروكي فقط»
            if st.session_state.get(REPORT_MEDIA_MODE_KEY) == "جوي فقط":
                _apply_report_media_mode("كروكي فقط", refresh_ui=True)
            st.rerun()

def render_interactive_asphalt_studio(
    sketch_image_state_key: str = "sketch_data_url",
    location_state_key: str = "p1_acc_location",
):
    """استوديو كروكي أسفلتي مع خريطة التصوير الجوي بجانبه عند الحاجة."""
    default_loc = str(st.session_state.get(location_state_key, "") or "").strip()
    mode_sel = st.session_state.get("_studio_layout_mode") or _LAYOUT_DUAL
    show_sketch = mode_sel != _LAYOUT_SAT
    show_sat = mode_sel != _LAYOUT_SKETCH
    if show_sketch and show_sat:
        col_sketch, col_sat = st.columns([1.35, 1], gap="medium")
        with col_sketch:
            _accept_asphalt_commit(sketch_image_state_key, default_loc)
        with col_sat:
            _render_aerial_reference()
    elif show_sketch:
        _accept_asphalt_commit(sketch_image_state_key, default_loc)
    else:
        _render_aerial_reference()
    preview = str(st.session_state.get(sketch_image_state_key) or st.session_state.get(SKETCH_DATA_URL_KEY) or "")
    if preview.startswith("data:image/"):
        with st.expander("👁️ معاينة الكروكي المعتمد حالياً في ورقة الطباعة A4", expanded=False):
            encoded = preview.split(",", 1)[-1]
            st.image(base64.b64decode(encoded), use_container_width=True)

if st.session_state.active_tab == MAIN_TAB_OPTIONS[1]:
    _load_remembered_sketch()
    _load_remembered_aerial()
    col_sketch_state, col_media, col_layout, col_place = st.columns([1.0, 1.1, 1.5, 1.0])
    with col_sketch_state:
        _sketch_availability_control("include_sketch_choice_tab4", _on_sketch_choice_tab4)
    with col_media:
        _render_report_media_mode_control()
    with col_layout:
        st.radio(
            "نمط عرض التخطيط",
            options=[_LAYOUT_DUAL, _LAYOUT_SKETCH, _LAYOUT_SAT],
            horizontal=True,
            key="_studio_layout_mode",
        )
        # مفتاح مختلف عن مفتاح الواجهة — آمن بعد الرسم
        st.session_state["studio_layout_mode"] = st.session_state.get("_studio_layout_mode")
    with col_place:
        aerial_place_choice = st.radio(
            "موضع لقطة التصوير الجوي",
            ["أسفل الكروكي", "بجانب الكروكي"],
            horizontal=True,
            key="aerial_place_choice",
        )
        # مفتاح مختلف عن مفتاح الواجهة — آمن بعد الرسم
        st.session_state["aerial_place"] = "beside" if str(aerial_place_choice).startswith("بجانب") else "below"
    render_interactive_asphalt_studio(
        sketch_image_state_key="sketch_data_url",
        location_state_key="p1_acc_location",
    )
    if "sketch_road_name" not in st.session_state:
        st.session_state["sketch_road_name"] = str(_read_core_accident_value("p1_acc_location") or "")
    road_name_sign = st.text_input("اسم الطريق الرئيسي", key="sketch_road_name")
    render_compact_sketch_legends(key_prefix="legend_key_")
    legend_keys = [str(st.session_state.get(f"legend_key_{index}") or "") for index in range(1, 11)]

MAX_ACCIDENT_PHOTOS = 15

def convert_gallery_image(uploaded_file):
    """تصغير أي بُعد يتجاوز 1200px ثم تحويل JPEG بجودة 80 قبل Base64."""
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source:
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGB")
            width, height = image.size
            if width > 1200 or height > 1200:
                image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=80, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return None

def build_official_page_footer_html(dept_region: str, dept_section: str) -> str:
    """توليد تذييل رسمي بخطين متوازيين في أسفل كل صفحة A4 مرتبط بإعدادات الإدارة والقسم."""
    region_clean = html.escape(str(dept_region or "").strip())
    section_clean = html.escape(str(dept_section or "").strip())
    if region_clean and section_clean:
        right_txt = region_clean
        center_txt = "الإدارة العامة للمرور"
        left_txt = section_clean
    elif region_clean or section_clean:
        right_txt = "الإدارة العامة للمرور"
        center_txt = "تقرير حادث مروري رسمي"
        left_txt = region_clean or section_clean
    else:
        right_txt = "الإدارة العامة للمرور"
        center_txt = "تقرير حادث مروري رسمي"
        left_txt = "شعبة الحوادث المرورية"
    return f"""
    <div class="official-page-footer" dir="rtl">
        <div class="official-footer-line-primary"></div>
        <div class="official-footer-line-secondary"></div>
        <div class="official-footer-meta">
            <span class="footer-col-right">{right_txt}</span>
            <span class="footer-col-center">❖ {center_txt} ❖</span>
            <span class="footer-col-left">{left_txt}</span>
        </div>
    </div>
    """

def generate_clean_print_html(how_text, results_text, show_numbers=False):
    results_text = _strip_results_lead_in(results_text)
    page_counter_css = """
        @bottom-center {
            content: "صفحة " counter(page) " من " counter(pages);
            font-family: 'Tajawal', sans-serif;
            font-size: 10pt;
            color: #444;
        }
    """ if show_numbers else """
        @bottom-center { content: none !important; }
    """
    return f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تقرير حادث مروري رسمي</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
            
            @page {{
                size: A4 portrait;
                margin: 12mm 15mm 18mm 15mm;
                {page_counter_css}
            }}
            body {{
                font-family: 'Tajawal', sans-serif;
                margin: 0;
                padding: 0;
                color: #000;
                background: #fff;
                direction: rtl;
                font-size: 11px;
                line-height: 1.6;
            }}
            .report-container {{
                width: 100%;
                max-width: 190mm;
                margin: 0 auto;
            }}
            .report-box {{
                border: 1.5px solid #111;
                border-radius: 6px;
                padding: 12px 15px;
                margin-bottom: 12px;
                page-break-inside: avoid; break-inside: avoid; page-break-after: avoid;
                break-inside: avoid;
                background-color: #fff;
            }}
            .section-title {{
                font-weight: 700;
                font-size: 13pt;
                background-color: #f1f5f9 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
                padding: 6px 10px;
                border-bottom: 1.5px solid #111;
                margin: -12px -15px 10px -15px;
                border-radius: 4px 4px 0 0;
            }}
            .content-text {{
                white-space: pre-wrap;
                text-align: justify;
            }}
            /* ضبط الصور والقرائن المرئية لتتلاءم مع الصفحة ولا تسبب صفحات فارغة */
            .evidence-image-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
                margin-top: 10px;
                page-break-inside: avoid; break-inside: avoid; page-break-after: avoid;
                break-inside: avoid;
            }}
            .evidence-image-container img {{
                max-width: 45%;
                max-height: 60mm;
                object-fit: contain;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 3px;
            }}
            .content-text, .report-box {{
                font-size: 11px;
            }}
            @media screen {{
                body {{
                    padding: 20px;
                    background: #e9ecef;
                }}
                .report-container {{
                    background: #fff;
                    padding: 15mm;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.15);
                }}
            }}
            @media print {{
                body, .content-text, .report-box {{
                    font-size: 9px !important;
                }}
            }}
        
</style>
    </head>
    <body>
        <div class="report-container">
            <div class="report-box">
                <div class="section-title">أولاً: كيفية وقوع الحادث (الصياغة الفنية الدقيقة)</div>
                <div class="content-text">{how_text or "لم يتم إدخال نص."}</div>
            </div>
            <div class="report-box">
                <div class="section-title">ثانياً: نتائج الحادث والمسؤولية</div>
                <div class="content-text">{results_text or "لم يتم إدخال نص."}</div>
            </div>
        </div>
        <script>
            window.onload = function() {{
                setTimeout(function() {{ window.print(); }}, 400);
            }};
        </script>
    </body>
    </html>
    """

if st.session_state.active_tab == MAIN_TAB_OPTIONS[3]:
    st.subheader("📸 إرفاق صور موقع الحادث والمركبات للتقرير الرسمي")
    _max_accident_photos = MAX_ACCIDENT_PHOTOS
    if "gallery_photos" not in st.session_state:
        st.session_state.gallery_photos = list(st.session_state.get("accident_photos_data") or [])
    # قصّ القائمة عند الاسترجاع إن تجاوزت الحد الجديد
    if isinstance(st.session_state.gallery_photos, list) and len(st.session_state.gallery_photos) > _max_accident_photos:
        st.session_state.gallery_photos = st.session_state.gallery_photos[:_max_accident_photos]
    if "uploaded_ids" not in st.session_state:
        st.session_state.uploaded_ids = set(st.session_state.get("processed_file_keys") or set())
        for entry in st.session_state.gallery_photos:
            if entry.get("id"):
                st.session_state.uploaded_ids.add(entry["id"])
    # لا تعيّن session_state["mobile_gallery_uploader"] أبداً — أفرغ الرفع بمفتاح ديناميكي
    if "uploader_reset_id" not in st.session_state:
        st.session_state.uploader_reset_id = 0
    try:
        st.session_state.uploader_reset_id = int(st.session_state.uploader_reset_id or 0)
    except (TypeError, ValueError):
        st.session_state.uploader_reset_id = 0
    _gallery_uploader_key = f"mobile_gallery_uploader_{int(st.session_state.uploader_reset_id)}"
    # تنظيف المفتاح الثابت القديم ومفاتيح الرفع القديمة قبل إنشاء الودجت
    st.session_state.pop("mobile_gallery_uploader", None)
    for _stale_key in list(st.session_state.keys()):
        _sk = str(_stale_key)
        if _sk.startswith("mobile_gallery_uploader_") and _sk != _gallery_uploader_key:
            st.session_state.pop(_stale_key, None)
    gallery_uploads = st.file_uploader(
        "📸 اضغط هنا لاختيار صور الحادث من معرض الجوال (حتى 15 صورة)",
        type=None,
        accept_multiple_files=True,
        key=_gallery_uploader_key,
    )
    st.components.v1.html(
        """
<script>
(function () {
  var MAX = 15;
  var EDGE = 1200;
  var QUALITY = 0.80;
  var doc;
  try { doc = window.parent.document; } catch (err) { return; }
  if (!doc || !doc.body) return;
  function compress(file) {
    return new Promise(function (resolve) {
      if (!file || !file.type || file.type.indexOf("image/") !== 0) {
        resolve(null);
        return;
      }
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        var scale = Math.min(1, EDGE / Math.max(img.width || 1, img.height || 1));
        var canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(img.width * scale));
        canvas.height = Math.max(1, Math.round(img.height * scale));
        canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
          URL.revokeObjectURL(url);
          if (!blob) { resolve(file); return; }
          var base = (file.name || "photo").split(".").slice(0, -1).join(".") || "photo";
          resolve(new File([blob], base + ".jpg", {type: "image/jpeg", lastModified: Date.now()}));
        }, "image/jpeg", QUALITY);
      };
      img.onerror = function () {
        URL.revokeObjectURL(url);
        resolve(file);
      };
      img.src = url;
    });
  }
  function bind(input) {
    input.setAttribute("accept", "image/*");
    if (input.dataset.bayyinahGallery === "1") return;
    input.dataset.bayyinahGallery = "1";
    input.addEventListener("change", function (event) {
      if (input.dataset.bayyinahPass === "send") {
        input.dataset.bayyinahPass = "";
        return;
      }
      var files = Array.prototype.slice.call(input.files || []);
      if (!files.length) return;
      event.stopImmediatePropagation();
      event.preventDefault();
      Promise.all(files.slice(0, MAX).map(compress)).then(function (out) {
        var transfer = new DataTransfer();
        out.forEach(function (file) { if (file) transfer.items.add(file); });
        input.dataset.bayyinahPass = "send";
        input.files = transfer.files;
        input.dispatchEvent(new Event("change", {bubbles: true}));
      });
    }, true);
  }
  function scan() {
    var root = doc.querySelector('[class*="st-key-mobile_gallery_uploader"]') || doc;
    root.querySelectorAll('input[type="file"]').forEach(bind);
  }
  if (!doc.body.dataset.bayyinahGalleryObserver) {
    doc.body.dataset.bayyinahGalleryObserver = "1";
    new MutationObserver(scan).observe(doc.body, {childList: true, subtree: true});
  }
  scan();
})();
</script>
        """,
        height=0,
    )
    gallery_photos = st.session_state.gallery_photos
    uploaded_ids = set(st.session_state.uploaded_ids)
    photo_limit_hit = False
    absorbed_uploads = False
    if gallery_uploads:
        for item in gallery_uploads:
            uid = f"{getattr(item, 'name', '')}_{getattr(item, 'size', 0)}"
            if uid in uploaded_ids:
                continue
            if len(gallery_photos) >= _max_accident_photos:
                photo_limit_hit = True
                continue
            image_b64 = convert_gallery_image(item)
            if not image_b64:
                continue
            gallery_photos.append({
                "id": uid,
                "b64": image_b64,
                "caption": "",
            })
            uploaded_ids.add(uid)
            absorbed_uploads = True
        # حتى التكرارات: أفرغ ودجت الرفع بمفتاح ديناميكي بدل تعيين session_state
        absorbed_uploads = True
    st.session_state.gallery_photos = gallery_photos
    st.session_state.uploaded_ids = uploaded_ids
    if photo_limit_hit:
        st.warning("تم الوصول للحد الأقصى (15 صورة).")
    # مزامنة قائمة الحفظ/الاسترجاع بنفس الحد
    st.session_state["accident_photos_data"] = list(gallery_photos[:_max_accident_photos])
    if absorbed_uploads:
        st.session_state.uploader_reset_id = int(st.session_state.get("uploader_reset_id") or 0) + 1
        st.rerun()
    pending_remove = None
    for row_start in range(0, len(gallery_photos), 2):
        cols = st.columns(2)
        for offset, entry in enumerate(gallery_photos[row_start:row_start + 2]):
            number = row_start + offset + 1
            cap_key = f"annex_cap_{entry['id']}"
            if cap_key not in st.session_state:
                st.session_state[cap_key] = entry.get("caption") or ""
            with cols[offset]:
                preview_b64 = entry["b64"].split(",", 1)[-1]
                st.image(base64.b64decode(preview_b64), width=320)
                if st.button("🗑️ حذف هذه الصورة", key=f"del_photo_{entry['id']}"):
                    pending_remove = entry["id"]
                entry["caption"] = st.text_input("تعليق الصورة", key=cap_key)
    if pending_remove:
        st.session_state.gallery_photos = [
            entry for entry in gallery_photos if entry["id"] != pending_remove
        ]
        st.session_state["accident_photos_data"] = list(st.session_state.gallery_photos[:_max_accident_photos])
        st.rerun()
    
if st.session_state.active_tab == MAIN_TAB_OPTIONS[3]:
    _load_remembered_sketch()
    _load_remembered_aerial()
    sketch_src = str(st.session_state.get("sketch_data_url") or "").strip()
    if not sketch_src.startswith("data:image/"):
        adopted_path = SAVED_IMAGES_DIR / "adopted_sketch.png"
        if adopted_path.is_file():
            try:
                sketch_src = "data:image/png;base64," + base64.b64encode(adopted_path.read_bytes()).decode("ascii")
            except OSError:
                sketch_src = ""
    aerial_src = str(st.session_state.get("aerial_sketch_data_url") or st.session_state.get("aerial_data_url") or "").strip()
    media_mode = _sync_report_media_mode_from_flags()
    show_sketch_media = media_mode in ("كلاهما", "كروكي فقط") and bool(st.session_state.get("include_sketch", True))
    show_aerial_media = media_mode in ("كلاهما", "جوي فقط") and bool(st.session_state.get("include_aerial", True))
    if not show_sketch_media:
        sketch_src = ""
    if not show_aerial_media:
        aerial_src = ""
    safe_sketch_src = html.escape(sketch_src, quote=True) if sketch_src.startswith("data:image/") else ""
    safe_aerial_src = html.escape(aerial_src, quote=True) if aerial_src.startswith("data:image/") else ""
    
    def _framed_shot(title, src, alt, max_height, compact=False):
        title_style = (
            "font-weight:800; font-size:10.5px; text-align:center; padding:2px 6px; margin-bottom:2px;"
            if compact else
            "font-weight:800; font-size:12.5px; text-align:center; margin-bottom:1.2mm;"
        )
        frame_pad = "3px" if compact else "1.6mm"
        return (
            f'<div style="border:1.4px solid #000; background:#fff; padding:{frame_pad}; box-sizing:border-box;">'
            f'<div style="{title_style}">{title}</div>'
            f'<img src="{src}" alt="{alt}" style="width:100%; max-height:{max_height}; height:auto; object-fit:contain; display:block; margin:0 auto;">'
            "</div>"
        )
    
    _single_img = "width:100%; max-height:138mm; height:auto; object-fit:contain; display:block; margin:0 auto;"
    if safe_sketch_src and safe_aerial_src and st.session_state.get("aerial_place") == "beside":
        sketch_figure = (
            '<div style="display:flex; justify-content:space-between; width:100%; align-items:stretch;">'
            f'<div style="width:49%;">{_framed_shot("الكروكي التوضيحي", safe_sketch_src, "كروكي الحادث", "70mm", True)}</div>'
            f'<div style="width:49%;">{_framed_shot("التصوير الجوي الفضائي", safe_aerial_src, "لقطة التصوير الجوي", "70mm", True)}</div>'
            "</div>"
        )
    elif safe_sketch_src and safe_aerial_src:
        sketch_figure = (
            _framed_shot("الكروكي التوضيحي", safe_sketch_src, "كروكي الحادث", "70mm", True)
            + '<div style="height:2mm;"></div>'
            + _framed_shot("التصوير الجوي الفضائي", safe_aerial_src, "لقطة التصوير الجوي", "70mm", True)
        )
    elif safe_aerial_src:
        sketch_figure = (
            f'<img src="{safe_aerial_src}" alt="لقطة التصوير الجوي" style="{_single_img}">'
        )
    elif safe_sketch_src:
        sketch_figure = (
            f'<img src="{safe_sketch_src}" alt="كروكي الحادث" style="{_single_img}">'
        )
    else:
        sketch_figure = '<div style="width:100%;height:135mm;border:1.5px solid #000;border-radius:4px;background:#fff;"></div>'
    logo_src = get_base64_image("traffic_logo.png")
    sig_officer = _signature_data_url("signature.png", "signature.jpg", "signature.jpeg")
    stored_sig = str(st.session_state.get("sig_base64") or "").strip()
    if not sig_officer and stored_sig.startswith("data:image/"):
        sig_officer = stored_sig
    elif not sig_officer and stored_sig:
        sig_officer = get_base64_image(stored_sig)
    sig_supervisor = _signature_data_url(
        "signature_supervisor.png",
        "signature_supervisor.jpg",
        "signature_supervisor.jpeg",
    )
    sig_manager = _signature_data_url(
        "signature_manager.png",
        "signature_manager.jpg",
        "signature_manager.jpeg",
    )
    def build_header():
        logo_html = f'<img src="{logo_src}" alt="شعار المرور">' if logo_src else '<div class="logo-fallback">الأمن العام<br>المرور</div>'
        return f"""
        <div class="header-Title">بسم الله الرحمن الرحيم</div>
        <div class="header-box">
            <div class="header-right">
                المملكة العربية السعودية<br>وزارة الداخلية<br>الأمن العام<br>الإدارة العامة للمرور<br>{dept_region}<br>{dept_branch}
            </div>
            <div class="header-logo">{logo_html}</div>
            <div class="header-center">
                الرقم: ...........................<br>
                التاريخ: ..........................<br>
                المشفوعات: ....................<br>
                الموضوع: .......................
            </div>
        </div>
        """
    # قراءة كل حقول A4 من session_state فقط — لا تعتمد على متغيرات محلية عبر التبويبات
    _a4 = load_a4_report_fields_from_session()
    _party_columns = list(_PARTY_TABLE_COLUMNS)
    _vehicle_columns = list(_VEHICLE_TABLE_COLUMNS)
    parties_df = _a4["parties_df"]
    vehicles_df = _a4["vehicles_df"]
    acc_num = _a4["acc_num"]
    acc_date = _a4["acc_date"]
    acc_time = _a4["acc_time"]
    acc_loc = _a4["acc_loc"]
    acc_type = _a4["acc_type"]
    acc_injuries = _a4["acc_injuries"]
    acc_deaths = _a4["acc_deaths"]
    acc_weather = _a4["acc_weather"]
    acc_cause = _a4["acc_cause"]
    acc_results = _a4["acc_results"]
    acc_how = _a4["acc_how"]
    accident_nature = str(_a4["accident_nature"] or "")
    accident_nature_val = str(_a4["accident_nature_val"] or accident_nature)
    rights_status = str(_a4["rights_status"] or "")
    rights_status_val = str(_a4["rights_status_val"] or rights_status)
    participating_agency = _a4["participating_agency"]
    escaped_vehicles = _a4["escaped_vehicles"]
    shots_fired = _a4["shots_fired"]
    contraband_found = _a4["contraband_found"]
    road_name_sign = _a4["road_name_sign"]
    legend_keys = _a4["legend_keys"]
    final_actions_html = _a4["final_actions_html"]
    liability_html = _a4["liability_html"]
    
    parties_head = "".join(f"<th>{label}</th>" for _key, label in _party_columns)
    vehicles_head = "".join(f"<th>{label}</th>" for _key, label in _vehicle_columns)
    if not isinstance(parties_df, pd.DataFrame):
        parties_df = pd.DataFrame(st.session_state.get("parties") or [])
    if not isinstance(vehicles_df, pd.DataFrame):
        vehicles_df = pd.DataFrame(st.session_state.get("vehicles") or [])
    # تنظيف None/NaN قبل الطباعة + مزامنة صفات الأطراف بأسماء السائقين
    if not parties_df.empty:
        _a4_parties, _ = _normalize_party_qualification_rows(_frame_records(parties_df))
        parties_df = pd.DataFrame(_a4_parties)
    _a4_vehicles_records = (
        _frame_records(vehicles_df) if isinstance(vehicles_df, pd.DataFrame) and not vehicles_df.empty
        else list(st.session_state.get("vehicles") or [])
    )
    _a4_party_records = (
        _frame_records(parties_df) if isinstance(parties_df, pd.DataFrame) and not parties_df.empty
        else list(st.session_state.get("parties") or [])
    )
    refresh_party_role_titles(parties=_a4_party_records, vehicles=_a4_vehicles_records, force=False)
    parties_rows = ""
    for _, row in parties_df.iterrows():
        cells = []
        role_val = _page1_cell(row.get("المشاركة", ""))
        for key, _label in _party_columns:
            if key == "التأهيل":
                cells.append(f"<td style=\"text-align:center; vertical-align:middle;\">{_party_qualification_cell_html(role_val, row.get(key, ''))}</td>")
            else:
                # عمود الأطراف: الطرف الأول/الثاني فقط كما في جدول الإدخال (بدون قائد/نوع/اسم)
                cells.append(f"<td>{html.escape(_page1_cell(row.get(key, '')))}</td>")
        parties_rows += "<tr>" + "".join(cells) + "</tr>"
    vehicles_rows = ""
    for _, row in vehicles_df.iterrows():
        vehicles_rows += "<tr>" + "".join(
            f"<td>{html.escape(_page1_cell(row.get(key, '')))}</td>" for key, _label in _vehicle_columns
        ) + "</tr>"
    _p1_party_count = int(parties_df.shape[0]) if isinstance(parties_df, pd.DataFrame) else 0
    p1_page_class = "page report-page page-flow page-p1"
    if _p1_party_count > 3:
        p1_page_class += " compact-rows"
    acc_num = _page1_cell(acc_num)
    acc_date = _page1_cell(acc_date)
    acc_time = _page1_cell(acc_time)
    acc_loc = _page1_cell(acc_loc)
    acc_type = _page1_cell(acc_type)
    acc_injuries = _page1_cell(acc_injuries)
    acc_deaths = _page1_cell(acc_deaths)
    acc_weather = _page1_cell(acc_weather)
    acc_cause = _page1_cell(acc_cause)
    acc_results = _page1_cell(acc_results)
    acc_how = _page1_cell(acc_how)
    dept_region = _page1_cell(dept_region)
    dept_branch = _page1_cell(dept_branch)
    officer_1_name = _page1_cell(st.session_state.get("officer_1_name") or officer_1_name)
    officer_1_rank = _page1_cell(st.session_state.get("officer_1_rank") or officer_1_rank)
    officer_2_name = _page1_cell(st.session_state.get("officer_2_name") or officer_2_name)
    officer_2_rank = _page1_cell(st.session_state.get("officer_2_rank") or officer_2_rank)
    manager_name = _page1_cell(st.session_state.get("manager_name") or manager_name)
    manager_rank = _page1_cell(st.session_state.get("manager_rank") or manager_rank)
    # أعمدة جدول معد التقرير الفعلية فقط — بلا td/th فارغة يساراً؛ colspan = عدد الأعمدة
    sign_headers = [
        "إجراءات الحوادث",
        "مشرف الحوادث",
        f"مدير {dept_branch}",
    ]
    sign_names = [officer_1_name, officer_2_name, manager_name]
    sign_ranks = [officer_1_rank, officer_2_rank, manager_rank]
    sign_sig_boxes = [
        _signature_box(sig_officer),
        _signature_box(sig_supervisor),
        _signature_box(sig_manager),
    ]
    sign_col_count = len(sign_headers)
    sign_colgroup = "".join('<col style="width:33.33%">' for _ in range(sign_col_count))
    sign_header_cells = "".join(f"<th>{html.escape(h)}</th>" for h in sign_headers)
    sign_name_cells = "".join(f"<td>الاسم: {html.escape(str(n or ''))}</td>" for n in sign_names)
    sign_rank_cells = "".join(f"<td>الرتبة: {html.escape(str(r or ''))}</td>" for r in sign_ranks)
    sign_sig_cells = "".join(f"<td>{box}</td>" for box in sign_sig_boxes)
    assert sign_col_count == len(sign_names) == len(sign_ranks) == len(sign_sig_boxes)
    accident_nature_val = _page1_cell(accident_nature_val)
    rights_status_val = _page1_cell(rights_status_val)
    participating_agency = _page1_cell(participating_agency)
    escaped_vehicles = _page1_cell(escaped_vehicles)
    shots_fired = _page1_cell(shots_fired)
    contraband_found = _page1_cell(contraband_found)
    road_name_sign = _page1_cell(road_name_sign)
    acc_results = _strip_results_lead_in(acc_results)
    results_html = "<br>".join(html.escape(line) for line in str(acc_results or "").split("\n") if line.strip())
    acc_how_html = html.escape(str(acc_how or "")).replace("\n", "<br>")
    a4_autofit_base_font_px = _estimate_a4_autofit_base_font_px(
        results_text=str(acc_results or ""),
        how_text=str(acc_how or ""),
        liability_html=str(liability_html or ""),
        actions_html=str(final_actions_html or ""),
        rights_text=str(rights_status_val or ""),
    )
    criminal_details_html = ""
    accident_nature = str(
        st.session_state.get("accident_nature")
        or accident_nature_val
        or accident_nature
        or ""
    )
    if "جنائي" in accident_nature:
        criminal_details_html = f"""
            <div class="table-scroll"><table>
                <tr><th>تفاصيل الشق الجنائي والأمني</th></tr>
                <tr><td style="text-align:right;">الجهة الأمنية المباشرة: {html.escape(str(participating_agency or ""))}</td></tr>
                <tr><td style="text-align:right;">بيانات المركبات الهاربة أو المعترضة: {html.escape(str(escaped_vehicles or ""))}</td></tr>
                <tr><td style="text-align:right;">هل تم إطلاق نار أثناء المطاردة؟ {html.escape(str(shots_fired or ""))}</td></tr>
                <tr><td style="text-align:right;">نتيجة تفتيش المركبة: {html.escape(str(contraband_found or ""))}</td></tr>
            </table></div>
        """
    official_footer_html = build_official_page_footer_html(
        st.session_state.get("p1_dept_region", dept_region),
        st.session_state.get("p1_dept_branch", dept_branch),
    )
    # صفحات ديناميكية: 1–6، 7–12، 13–15 مع ترقيم متسلسل حتى 15
    photos_list = list(st.session_state.get("gallery_photos") or [])[:MAX_ACCIDENT_PHOTOS]
    include_sketch = (
        (st.session_state.get("include_sketch", True) is True and bool(safe_sketch_src))
        or (st.session_state.get("include_aerial", True) is True and bool(safe_aerial_src))
        or bool(safe_sketch_src or safe_aerial_src)
    )
    photos_pages_html = ""
    photos_per_page = 6
    annex_first_page = 5 if include_sketch else 4
    for page_idx in range(0, len(photos_list[:MAX_ACCIDENT_PHOTOS]), photos_per_page):
        page_photos = photos_list[page_idx:page_idx + photos_per_page]
        if not page_photos:
            continue
        photo_cards = ""
        for offset, entry in enumerate(page_photos):
            number = page_idx + offset + 1
            safe_caption = html.escape(entry.get("caption") or "")
            photo_cards += f"""
        <div class="photo-card">
            <img src="{entry['b64']}" alt="صورة {number}">
            <div class="photo-meta">{number}<br>{safe_caption}</div>
        </div>
        """
        page_number = annex_first_page + (page_idx // photos_per_page)
        photos_pages_html += f"""
        <div class="page report-page photo-annex">
            {build_header()}
            <div class="section-badge">ملحق الصور الفوتوغرافية لموقع الحادث</div>
            <div class="photo-grid">{photo_cards}</div>
            {official_footer_html}
        </div>
        """
    page_number_css = ""
    body_class = ""
    sketch_page_html = ""
    legend_cells = []
    for legend_index, legend_line in enumerate(legend_keys, start=1):
        legend_text = html.escape(str(legend_line or "").strip())
        if not legend_text:
            continue
        legend_cells.append(
            f"<td style=\"font-size:10px; padding:3px 6px; text-align:right; line-height:1.2;\">({legend_index}) {legend_text}</td>"
        )
    legend_rows = ""
    for pair_start in range(0, len(legend_cells), 2):
        pair = legend_cells[pair_start:pair_start + 2]
        if len(pair) == 1:
            pair.append("<td></td>")
        legend_rows += "<tr>" + "".join(pair) + "</tr>"
    legend_table_html = (
        '<table class="sketch-legend" style="width:100%; border-collapse:collapse; margin:2mm 0 0 0; max-height:15mm; overflow:hidden;">'
        f"{legend_rows}</table>"
        if legend_rows else ""
    )
    if include_sketch:
        sketch_page_html = f"""
        <div class="page report-page">
            {build_header()}
            <div class="section-badge">كروكي وتوثيق موقع الحادث</div>
            <div style="width:100%; text-align:center; margin-top:2px;">
                {sketch_figure}
            </div>
            {legend_table_html}
            {official_footer_html}
        </div>
        """
    full_report_html = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@500;700&display=swap');
        @page {{ size: A4 portrait; margin: 0mm; }}
        html, body {{
            height: auto !important; max-height: none !important; margin: 0;
            display: block !important; overflow: visible !important;
        }}
        body {{
            font-family: 'Tajawal', sans-serif; background: #e5e7eb; margin: 0;
        }}
        .report-viewport,
        .report-sheet,
        .report-wrapper,
        .print-container,
        .pages-wrapper,
        .preview-container {{
            display: block !important;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
            box-sizing: border-box;
        }}
        .report-viewport {{
            width: 100%; max-width: none;
            -webkit-overflow-scrolling: touch;
        }}
        .report-sheet {{
            width: 210mm; min-width: 210mm; max-width: 210mm; margin: 0 auto;
            transform: none;
        }}
        :root {{
            --shared-box-font: {a4_autofit_base_font_px}px;
            --shared-line-height: 1.42;
            --shared-box-pad: 14px;
            --section-gap: 10px;
            --a4-box-pad: 14px;
            --a4-box-margin: 12px;
            --a4-badge-margin: 4px;
            --a4-badge-pad-y: 5px;
        }}
        .report-sheet .header-Title,
        .report-sheet .section-badge {{
            font-size: 15px !important; font-weight: 700;
        }}
        .report-sheet .box-content:not(.autofit-box):not(.section-box):not(.content-box):not(.report-box),
        .report-sheet .header-box,
        .report-sheet .photo-meta {{
            font-size: 15px !important; font-weight: 600;
        }}
        .report-sheet th,
        .report-sheet td {{
            font-size: 14px !important; font-weight: 600;
        }}
        .report-sheet th {{ font-weight: 700; }}
        .page, .report-page, .a4-page {{
            --shared-box-font: {a4_autofit_base_font_px}px;
            --shared-line-height: 1.42;
            --shared-box-pad: 14px;
            --section-gap: 10px;
            background: white; width: 210mm; min-width: 210mm; max-width: 210mm;
            min-height: 297mm; height: 297mm; max-height: 297mm;
            margin: 0 auto 20px auto;
            padding: 6mm 11mm 5mm 11mm; box-sizing: border-box; position: relative;
            display: flex; flex-direction: column; justify-content: space-between;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); page-break-after: always;
            transform: none; flex-shrink: 0;
        }}
        /* توحيد صناديق المحتوى (أسماء فهد + الأسماء الفعلية الحالية) */
        .page .section-box,
        .page .content-box,
        .page .report-box,
        .page .box-content.autofit-box,
        .page .liability-box.autofit-box,
        .a4-page .section-box,
        .a4-page .content-box,
        .a4-page .report-box,
        .a4-page .box-content.autofit-box,
        .a4-page .liability-box.autofit-box {{
            font-size: var(--shared-box-font, 13.5px) !important;
            line-height: var(--shared-line-height, 1.42) !important;
            padding: var(--shared-box-pad, 12px) !important;
            padding-bottom: 10px !important;
            margin-bottom: var(--section-gap, 8px) !important;
            box-sizing: border-box;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
            flex-shrink: 0 !important;
        }}
        .page .section-box *:not(.statute-quote):not(.statute-line),
        .page .content-box *:not(.statute-quote):not(.statute-line),
        .page .report-box *:not(.statute-quote):not(.statute-line),
        .page .box-content.autofit-box *:not(.statute-quote):not(.statute-line),
        .a4-page .section-box *:not(.statute-quote):not(.statute-line),
        .a4-page .content-box *:not(.statute-quote):not(.statute-line),
        .a4-page .report-box *:not(.statute-quote):not(.statute-line),
        .a4-page .box-content.autofit-box *:not(.statute-quote):not(.statute-line) {{
            font-size: inherit !important;
            line-height: inherit !important;
        }}
        .page .statute-quote,
        .page .statute-line,
        .a4-page .statute-quote,
        .a4-page .statute-line,
        .page .statute-quote *,
        .page .statute-line *,
        .a4-page .statute-quote *,
        .a4-page .statute-line * {{
            font-size: calc(var(--shared-box-font, 13.5px) * 0.93) !important;
            line-height: var(--shared-line-height, 1.60) !important;
            color: #1d4e89 !important;
            font-weight: 600 !important;
        }}
        .page .statute-quote,
        .page .statute-line,
        .a4-page .statute-quote,
        .a4-page .statute-line {{
            margin: 4px 14px 6px 0;
            white-space: normal;
            overflow-wrap: anywhere;
        }}
        .page .liability-admin-note,
        .a4-page .liability-admin-note {{
            font-weight: 600 !important;
            margin: 6px 0 4px;
        }}
        .page .liability-heading,
        .a4-page .liability-heading,
        .page .liability-nonresp,
        .a4-page .liability-nonresp {{
            font-weight: 700 !important;
            margin-bottom: 4px;
        }}
        .page .liability-preamble,
        .a4-page .liability-preamble {{
            margin-bottom: 8px;
        }}
        .page .liability-reasons,
        .a4-page .liability-reasons {{
            margin: 4px 28px 10px 0;
            padding: 0 6px 0 0;
            list-style-type: none;
        }}
        .page .liability-reason,
        .a4-page .liability-reason {{
            margin-bottom: 6px;
            padding-right: 4px;
            text-indent: 0;
        }}
        .page .liability-block,
        .a4-page .liability-block {{
            margin-bottom: 10px;
        }}
        .page .liability-divider,
        .a4-page .liability-divider {{
            border: 0;
            border-top: 1px dashed #666;
            margin: 10px 0;
        }}
        .page .liability-nonresp,
        .a4-page .liability-nonresp {{
            margin-top: 8px;
            padding-top: 6px;
            border-top: 1px solid #eee;
        }}
        .report-sheet table,
        .report-sheet .table-scroll,
        .report-sheet .box-content,
        .report-sheet .header-box,
        .report-sheet .photo-grid,
        .report-sheet p,
        .report-sheet li {{
            width: 100%; max-width: 100%; box-sizing: border-box;
        }}
        .page-flow {{
            display: flex; flex-direction: column; justify-content: space-between;
            box-sizing: border-box;
        }}
        .page-flow table:not(.sign-table) th,
        .page-flow table:not(.sign-table) td {{
            padding: 4px 7px;
        }}
        .page-flow table.sign-table th,
        .page-flow table.sign-table td {{
            display: table-cell !important;
            width: 33.33% !important;
            padding: 8px 6px !important;
        }}
        .page-body,
        .page-body-flex,
        .autofit-page-body {{
            flex: 1 0 auto;
            min-height: 0;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            gap: var(--section-gap, 8px);
            overflow: visible !important;
            height: auto !important;
            max-height: none !important;
            width: 100%;
            box-sizing: border-box;
        }}
        .page-flow > .table-scroll,
        .page-flow > .box-content,
        .page-body > .table-scroll,
        .page-body > .box-content,
        .page-body-flex > .table-scroll,
        .page-body-flex > .box-content {{
            flex: 0 0 auto;
            min-height: 0;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
            flex-shrink: 0 !important;
        }}
        .page-body > .section-box:last-of-type,
        .page-body > .content-box:last-of-type,
        .page-body > .report-box:last-of-type,
        .page-body > .box-content.autofit-box:last-of-type,
        .page-body-flex > .section-box:last-of-type,
        .page-body-flex > .content-box:last-of-type,
        .page-body-flex > .report-box:last-of-type,
        .page-body-flex > .box-content.autofit-box:last-of-type,
        .autofit-page-body > .box-content.autofit-box:last-of-type {{
            flex-grow: var(--a4-last-box-grow, 0);
        }}
        .page.has-absolute-footer {{
            padding-bottom: calc(18mm + 12mm);
        }}
        .liability-box {{
            overflow: visible !important;
            max-height: none !important;
            min-height: 0;
            height: auto !important;
            flex-shrink: 0 !important;
            padding-bottom: 10px !important;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .autofit-box:not(.sign-table):not(table.sign-table),
        .section-box:not(.sign-table),
        .content-box:not(.sign-table),
        .report-box:not(.sign-table),
        [data-autofit]:not(.sign-table):not(table.sign-table):not([data-autofit="signatures"]) {{
            overflow: visible !important;
            height: auto !important;
            max-height: none !important;
            flex-shrink: 0 !important;
            padding-bottom: 10px !important;
            box-sizing: border-box;
        }}
        .photo-annex {{ page-break-before: always; overflow: visible; }}
        .photo-annex .header-box {{ min-height: 88px; margin-bottom: 6px; padding-bottom: 4px; }}
        .photo-annex .header-logo img {{ height: 72px; max-width: 80px; }}
        .photo-annex .section-badge {{ margin: 4px auto 6px auto; padding: 3px 14px; }}
        .photo-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px 12px;
            align-items: start;
            overflow: visible;
            width: 100%;
        }}
        .photo-card {{
            width: 100%; max-width: 100%; margin-bottom: 0; text-align: center; overflow: visible;
            break-inside: avoid; page-break-inside: avoid;
            box-sizing: border-box;
        }}
        .photo-card img {{
            width: auto; max-width: 100%; max-height: 185px; height: auto; object-fit: contain;
            display: block; margin: 0 auto;
            border: 2px solid #1b4332; border-radius: 6px; background: #fff;
        }}
        /* جدول معد التقرير — قواعد أولية؛ القاعدة النهائية بعد OFFICIAL تتفوق على page-p3/page-flow */
        table.sign-table {{
            display: table !important;
            table-layout: fixed !important;
            width: 100% !important;
            max-width: 100% !important;
            border-collapse: collapse !important;
            border-spacing: 0 !important;
            border: 1.5px solid #444 !important;
            outline: none !important;
            box-shadow: none !important;
            margin: 8px 0 0 0 !important;
            padding: 0 !important;
            background: #fff;
            direction: rtl !important;
            flex-shrink: 0 !important;
        }}
        table.sign-table col {{ width: 33.33% !important; }}
        table.sign-table thead,
        table.sign-table tbody {{ display: table-row-group !important; }}
        table.sign-table tr {{ display: table-row !important; }}
        table.sign-table th,
        table.sign-table td {{
            display: table-cell !important;
            width: 33.33% !important;
            padding: 8px 6px !important;
            box-sizing: border-box !important;
            vertical-align: top !important;
            text-align: center !important;
            border: 1.5px solid #444 !important;
            white-space: normal !important;
        }}
        table.sign-table th[colspan] {{ width: auto !important; }}
        .photo-card .photo-meta {{
            margin-top: 4px; font-weight: 600; font-size: 15px; line-height: 1.35;
            overflow: visible; white-space: normal;
        }}
        .logo-fallback {{
            border: 2px solid #1b4332; border-radius: 50%; width: 80px; height: 80px;
            display: flex; align-items: center; justify-content: center; margin: auto;
            font-weight: bold; color: #1b4332; line-height: 1.25; text-align: center;
        }}
        .header-logo img {{
            height: 110px; width: auto; max-width: 120px; object-fit: contain;
            display: block; margin: 0 auto;
        }}
        .header-Title {{ text-align: center; font-size: 15px; font-weight: 700; margin-bottom: 6px; }}
        .header-box {{
            position: relative; display: flex; justify-content: space-between; align-items: center;
            min-height: 128px; border-bottom: 3px double #1b4332; padding-bottom: 10px;
            margin-bottom: 18px; font-size: 15px; font-weight: 700; line-height: 1.6;
        }}
        .header-right {{ width: 36%; text-align: right; }}
        .header-center {{ width: 36%; text-align: center; }}
        .header-logo {{
            position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
            display: flex; justify-content: center; align-items: center; margin: 0;
        }}
        .section-badge {{
            background: #d8f3dc; border: 1.5px solid #1b4332; border-radius: 6px;
            padding: 5px 25px; font-weight: 700; font-size: 15px; display: table; margin: 14px auto; text-align: center; color: #1b4332;
        }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 6px; font-size: 14px; }}
        th, td {{ border: 1.5px solid #444; padding: 7px 6px; text-align: center; font-size: 14px; font-weight: 600; }}
        th {{ font-weight: 700; background-color: #d8f3dc; color: #1b4332; }}
        .box-content {{
            border: 1.5px solid #444; padding: var(--a4-box-pad, 14px); font-size: 15px; font-weight: bold;
            line-height: 1.9; text-align: right; margin-bottom: var(--a4-box-margin, 16px); min-height: 72px;
        }}
        .box-content.autofit-box,
        .box-content.section-box,
        .box-content.content-box,
        .box-content.report-box {{
            font-size: var(--shared-box-font, 13.5px) !important;
            line-height: var(--shared-line-height, 1.60) !important;
            min-height: 0;
            padding: var(--shared-box-pad, 14px) !important;
            margin-bottom: var(--section-gap, 10px) !important;
        }}
        .page-flow .section-badge {{
            margin: var(--a4-badge-margin, 4px) auto;
            padding: var(--a4-badge-pad-y, 5px) 25px;
        }}
        .box-content.liability-box {{
            overflow: visible !important;
            max-height: none !important;
            min-height: 0;
            height: auto !important;
            flex-shrink: 0 !important;
            padding-bottom: 10px !important;
        }}
        .page-num {{ display: none !important; }}
        .header-Title, .header-box {{
            flex-shrink: 0;
        }}
        .official-page-footer, .official-footer, .page-footer, .footer {{
            position: relative; bottom: auto; left: auto; right: auto;
            width: 100%; margin-top: auto; padding-top: 6mm; flex-shrink: 0;
            box-sizing: border-box; direction: rtl;
            page-break-inside: avoid; break-inside: avoid; page-break-before: avoid; break-before: avoid;
            -webkit-print-color-adjust: exact; print-color-adjust: exact;
        }}
        .official-footer-line-primary {{
            width: 100%; height: 0; border-top: 2.2px solid #1b4332 !important; margin: 0;
        }}
        .official-footer-line-secondary {{
            width: 100%; height: 0; border-top: 0.9px solid #1b4332 !important;
            margin-top: 2.5px; margin-bottom: 5px;
        }}
        .official-footer-meta {{
            display: flex; justify-content: space-between; align-items: center;
            font-size: 11.5px; font-weight: 700; color: #111827 !important;
            line-height: 1.3; padding: 0 2px;
        }}
        .footer-col-right {{ text-align: right; flex: 1; }}
        .footer-col-center {{
            text-align: center; flex: 0 0 auto; font-size: 10.5px; font-weight: 600;
            color: #1b4332 !important; padding: 0 12px;
        }}
        .footer-col-left {{ text-align: left; flex: 1; }}
        .road-sign {{
            background: #2d6a4f; color: white; border: 3px solid white; outline: 3px solid #2d6a4f;
            border-radius: 8px; padding: 10px 18px; font-weight: bold; font-size: 15px; display: inline-block; margin-bottom: 25px;
        }}
        .table-scroll {{ width: 100%; max-width: 100%; }}
        /* === توزيع الصفحة الأولى الموزون (يملأ الورقة بدون فراغ سفلي) === */
        .page-p1 .p1-body-flex {{
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
            padding: 3mm 0 7mm 0 !important;
            min-height: 0 !important;
        }}
        .page-p1:not(.compact-rows) .p1-section-group th {{
            padding: 9px 8px !important;
            font-size: 12.5px !important;
        }}
        .page-p1:not(.compact-rows) .p1-section-group td {{
            padding: 12px 8px !important;
            font-size: 12.5px !important;
        }}
        .page-p1:not(.compact-rows) .section-title,
        .page-p1:not(.compact-rows) .badge-title,
        .page-p1:not(.compact-rows) .section-badge {{
            margin-bottom: 6px !important;
            padding: 5px 18px !important;
        }}
        .page-p1.compact-rows .p1-section-group th,
        .page-p1.compact-rows .p1-section-group td {{
            padding: 5px 6px !important;
            font-size: 11px !important;
        }}
        /* === توزيع الصفحة الثالثة ومساحة التوقيع والختم الرسمي === */
        .page-p3 .p3-body-flex {{
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
            padding: 4mm 0 7mm 0 !important;
            min-height: 0 !important;
        }}
        .page-p3 table:not(.sign-table) th {{
            padding: 8px 10px !important;
            font-size: 13px !important;
        }}
        .page-p3 table:not(.sign-table) td {{
            padding: 10px 12px !important;
            font-size: 12.5px !important;
            line-height: 1.75 !important;
        }}
        .page-p3 table.sign-table th,
        .page-p3 table.sign-table td {{
            padding: 8px 6px !important;
        }}
        .page-p3 td.actions-body {{
            min-height: 18mm !important;
            height: auto !important;
            line-height: 1.85 !important;
            padding: 10px 14px !important;
            vertical-align: top !important;
        }}
        .page-p3 td.actions-body.autofit-box {{
            font-size: var(--shared-box-font, 13.5px) !important;
            line-height: var(--shared-line-height, 1.60) !important;
            overflow: hidden;
        }}
        .page-p3 table.sign-table tr.sig-row td {{
            height: 28mm !important;
            min-height: 28mm !important;
            vertical-align: top !important;
            padding: 8px 6px !important;
        }}
        .page-p1 > .official-page-footer,
        .page-p3 > .official-page-footer {{
            margin-top: 0 !important;
            flex-shrink: 0 !important;
        }}
        @media screen {{
            html, body,
            .report-viewport, .report-sheet, .report-wrapper,
            .print-container, .pages-wrapper, .preview-container {{
                display: block !important;
                height: auto !important;
                max-height: none !important;
                overflow: visible !important;
            }}
            .page, .report-page, .a4-page {{
                width: 210mm !important; min-width: 210mm !important; max-width: 210mm !important;
                min-height: 297mm !important; height: 297mm !important; max-height: 297mm !important;
                margin: 0 auto 20px auto !important;
                overflow: hidden !important;
                transform: none !important;
                display: flex !important; flex-direction: column !important;
                justify-content: space-between !important; box-sizing: border-box !important;
                flex-shrink: 0 !important;
            }}
            .photo-annex, .photo-annex .photo-card, .photo-annex .photo-meta {{
                overflow: visible; max-height: none;
            }}
            .table-scroll, table, .table-scroll table, .box-content, .header-box {{
                width: 100% !important; max-width: 100% !important; box-sizing: border-box;
            }}
            table, .table-scroll table {{ table-layout: fixed; }}
            th, td {{
                white-space: normal; overflow-wrap: anywhere; word-break: break-word;
            }}
        }}
        @media screen and (max-width: 768px) {{
            html, body,
            .report-viewport, .report-sheet, .report-wrapper,
            .print-container, .pages-wrapper, .preview-container {{
                display: block !important;
                height: auto !important;
                max-height: none !important;
                overflow: visible !important;
            }}
            .report-viewport {{ width: 100%; max-width: none; }}
            .page, .report-page, .a4-page {{
                width: 210mm !important; min-width: 210mm !important; max-width: 210mm !important;
                min-height: 297mm !important; height: 297mm !important; max-height: 297mm !important;
                margin: 0 auto 20px auto !important;
                overflow: hidden !important;
                transform: none !important;
                display: flex !important; flex-direction: column !important;
                justify-content: space-between !important; box-sizing: border-box !important;
                flex-shrink: 0 !important;
            }}
            .page-flow {{ justify-content: space-between; }}
            .table-scroll, table, .table-scroll table {{
                table-layout: fixed; width: 100% !important; max-width: 100% !important;
            }}
            th, td {{
                white-space: normal; overflow-wrap: anywhere; word-break: break-word;
            }}
        }}
        @media print {{
            html, body {{
                width: 210mm !important;
                height: auto !important; max-height: none !important;
                display: block !important; overflow: visible !important;
                background: #ffffff; margin: 0 !important; padding: 0 !important;
                -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important;
            }}
            body > div:not(.bayyinah-print-bar),
            .report-viewport, .report-sheet,
            .report-wrapper, .print-container, .pages-wrapper, .preview-container {{
                margin: 0 !important; padding: 0 !important; gap: 0 !important;
                border: none !important; box-shadow: none !important;
                background: transparent !important;
                display: block !important;
                height: auto !important; max-height: none !important;
                overflow: visible !important;
            }}
            button, .no-print, .stButton, .stDownloadButton,
            section[data-testid="stSidebar"], [data-testid="stSidebar"],
            [data-testid="stSidebarContent"], [data-testid="stSidebarHeader"],
            [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
            [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
                display: none !important;
            }}
            .report-viewport {{
                overflow: visible !important; height: auto !important; max-height: none !important;
                width: 210mm; max-width: 210mm; display: block !important;
            }}
            .page, .a4-page, .report-page {{
                width: 210mm !important;
                height: 294mm !important;
                min-height: 294mm !important;
                max-height: 294mm !important;
                margin: 0 auto !important;
                padding: 6mm 11mm 5mm 11mm !important;
                box-sizing: border-box !important;
                overflow: hidden !important;
                border: none !important;
                box-shadow: none !important;
                position: relative !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: space-between !important;
                page-break-after: always !important;
                break-after: page !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
                transform: none !important;
                flex-shrink: 0 !important;
            }}
            .page.page-p2 {{
                height: 294mm !important;
                max-height: 294mm !important;
            }}
            .box-content, .box-content.liability-box, .liability-box,
            .autofit-box:not(.sign-table):not(table.sign-table),
            .section-box:not(.sign-table), .content-box:not(.sign-table), .report-box:not(.sign-table),
            .results-box, .how-happened-box,
            [data-autofit]:not(.sign-table):not(table.sign-table):not([data-autofit="signatures"]),
            td.actions-body {{
                overflow: visible !important;
                max-height: none !important;
                min-height: 0 !important;
                height: auto !important;
                flex-shrink: 0 !important;
                padding-bottom: 10px !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            .page:last-of-type, .a4-page:last-of-type, .report-page:last-of-type,
            .report-sheet > .report-page:last-child {{
                page-break-after: auto !important; break-after: auto !important;
            }}
            .page table:not(.sign-table), .report-page table:not(.sign-table), .a4-page table:not(.sign-table), .box-content {{
                margin-bottom: 6px !important;
            }}
            .table-scroll {{ overflow: visible; max-width: none; }}
            table:not(.sign-table), .table-scroll, .table-scroll table:not(.sign-table), .box-content, .header-box, .photo-grid {{
                width: 100% !important; max-width: 100% !important; min-width: 0 !important;
                box-sizing: border-box; border-collapse: collapse;
            }}
            table:not(.sign-table), .table-scroll table:not(.sign-table) {{ border: 1px solid #000; }}
            th, td {{ border: 1px solid #000 !important; }}
            .report-sheet .header-Title,
            .report-sheet .section-badge {{
                font-size: 15px !important; font-weight: 700;
            }}
            .report-sheet .box-content:not(.autofit-box),
            .report-sheet .header-box,
            .report-sheet .photo-meta,
            .report-sheet p,
            .report-sheet li {{
                font-size: 15px !important; font-weight: 600;
            }}
            .page .section-box,
            .page .content-box,
            .page .report-box,
            .page .box-content.autofit-box,
            .a4-page .section-box,
            .a4-page .content-box,
            .a4-page .report-box,
            .a4-page .box-content.autofit-box {{
                font-size: var(--shared-box-font, 13.5px) !important;
                line-height: var(--shared-line-height, 1.60) !important;
                font-weight: 600;
            }}
            .page .statute-quote,
            .page .statute-line,
            .a4-page .statute-quote,
            .a4-page .statute-line {{
                font-size: calc(var(--shared-box-font, 13.5px) * 0.93) !important;
                color: #1d4e89 !important;
            }}
            .report-sheet th,
            .report-sheet td {{ font-size: 14px !important; font-weight: 600; }}
            .report-sheet th {{ font-weight: 700; }}
            table.sign-table {{
                display: table !important;
                table-layout: fixed !important;
                width: 100% !important;
                max-width: 100% !important;
                border-collapse: collapse !important;
                border-spacing: 0 !important;
                border: 1px solid #000 !important;
                outline: none !important;
                box-shadow: none !important;
                margin: 8px 0 0 0 !important;
                padding: 0 !important;
                direction: rtl !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            table.sign-table col {{ width: 33.33% !important; }}
            table.sign-table thead,
            table.sign-table tbody {{ display: table-row-group !important; }}
            table.sign-table tr {{
                display: table-row !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            table.sign-table th,
            table.sign-table td {{
                display: table-cell !important;
                width: 33.33% !important;
                padding: 8px 6px !important;
                border: 1px solid #000 !important;
                vertical-align: top !important;
                text-align: center !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
                page-break-after: avoid !important;
            }}
            table.sign-table th[colspan] {{ width: auto !important; }}
            .page-flow {{ justify-content: space-between !important; }}
            .page-body, .page-body-flex, .autofit-page-body {{
                flex: 1 0 auto !important;
                min-height: 0 !important;
                height: auto !important;
                max-height: none !important;
                overflow: visible !important;
            }}
            .page-flow .section-badge {{ margin: 4px auto !important; }}
            .page-flow table:not(.sign-table) th,
            .page-flow table:not(.sign-table) td {{ padding: 4px 7px !important; }}
            .page-flow table.sign-table th,
            .page-flow table.sign-table td {{
                display: table-cell !important;
                width: 33.33% !important;
                padding: 8px 6px !important;
            }}
            .official-page-footer, .official-footer, .page-footer, .footer {{
                position: relative !important;
                bottom: auto !important;
                left: auto !important;
                right: auto !important;
                width: 100% !important;
                margin-top: auto !important;
                padding-top: 6mm !important;
                flex-shrink: 0 !important;
                page-break-before: avoid !important;
                break-before: avoid !important;
            }}
            .photo-annex {{
                overflow: hidden; height: 294mm; max-height: 294mm; min-height: 294mm;
                padding: 7mm 11mm 6mm 11mm;
            }}
            .photo-annex .photo-card, .photo-annex .photo-meta {{ overflow: visible; max-height: none; }}
            .photo-annex .header-logo img {{ height: 72px; max-width: 80px; }}
            .header-logo img {{ height: 110px; max-width: 120px; }}
            .page-p1 .p1-body-flex {{
                flex: 1 1 auto !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: space-between !important;
                padding: 3mm 0 7mm 0 !important;
                min-height: 0 !important;
            }}
            .page-p1:not(.compact-rows) .p1-section-group th {{
                padding: 9px 8px !important;
                font-size: 12.5px !important;
            }}
            .page-p1:not(.compact-rows) .p1-section-group td {{
                padding: 12px 8px !important;
                font-size: 12.5px !important;
            }}
            .page-p1:not(.compact-rows) .section-title,
            .page-p1:not(.compact-rows) .badge-title,
            .page-p1:not(.compact-rows) .section-badge {{
                margin-bottom: 6px !important;
                padding: 5px 18px !important;
            }}
            .page-p1.compact-rows .p1-section-group th,
            .page-p1.compact-rows .p1-section-group td {{
                padding: 5px 6px !important;
                font-size: 11px !important;
            }}
            .page-p3 .p3-body-flex {{
                flex: 1 1 auto !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: space-between !important;
                padding: 4mm 0 7mm 0 !important;
                min-height: 0 !important;
            }}
            .page-p3 table:not(.sign-table) th {{
                padding: 8px 10px !important;
                font-size: 13px !important;
            }}
            .page-p3 table:not(.sign-table) td {{
                padding: 10px 12px !important;
                font-size: 12.5px !important;
                line-height: 1.75 !important;
            }}
            .page-p3 td.actions-body {{
                min-height: 18mm !important;
                height: auto !important;
                line-height: 1.85 !important;
                padding: 10px 14px !important;
                vertical-align: top !important;
            }}
            .page-p3 td.actions-body.autofit-box {{
                font-size: var(--shared-box-font, 13.5px) !important;
                line-height: var(--shared-line-height, 1.60) !important;
                overflow: hidden !important;
            }}
            .page-p3 table.sign-table tr.sig-row td {{
                height: 28mm !important;
                min-height: 28mm !important;
                vertical-align: top !important;
                padding: 8px 6px !important;
            }}
            .page-p1 > .official-page-footer,
            .page-p3 > .official-page-footer {{
                margin-top: 0 !important;
                flex-shrink: 0 !important;
            }}
        }}
        {page_number_css}
        {OFFICIAL_A4_HIGH_CONTRAST_CSS}
        /* === SIGN_TABLE_FINAL: يتفوق على page-p3 / page-flow / OFFICIAL لمنع فراغ يسار وإطار مزدوج === */
        table.sign-table {{
            display: table !important;
            table-layout: fixed !important;
            width: 100% !important;
            max-width: 100% !important;
            min-width: 100% !important;
            border-collapse: collapse !important;
            border-spacing: 0 !important;
            border: 1.5px solid #000 !important;
            outline: none !important;
            box-shadow: none !important;
            margin: 8px 0 0 0 !important;
            padding: 0 !important;
            direction: rtl !important;
            background: #fff !important;
            flex: 0 0 auto !important;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
            transform: none !important;
        }}
        table.sign-table col {{ width: 33.33% !important; }}
        table.sign-table thead,
        table.sign-table tbody {{ display: table-row-group !important; width: auto !important; }}
        table.sign-table tr {{ display: table-row !important; width: auto !important; }}
        table.sign-table th,
        table.sign-table td {{
            display: table-cell !important;
            width: 33.33% !important;
            padding: 8px 6px !important;
            box-sizing: border-box !important;
            vertical-align: top !important;
            text-align: center !important;
            border: 1px solid #000 !important;
            background-clip: padding-box !important;
            white-space: normal !important;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
            float: none !important;
            position: static !important;
        }}
        table.sign-table th[colspan] {{
            width: auto !important;
        }}
        table.sign-table tr.sig-row td {{
            height: 28mm !important;
            min-height: 28mm !important;
            padding: 8px 6px !important;
        }}
    
</style>
    <script>
    function fitReportFrame() {{
      var bar = document.querySelector(".no-print");
      var sheet = document.querySelector(".report-sheet");
      var height = 16;
      if (bar) height += bar.offsetHeight;
      if (sheet) {{
        var pageSum = 0;
        var pages = sheet.querySelectorAll(".page, .a4-page");
        for (var i = 0; i < pages.length; i++) {{
          pageSum += Math.max(pages[i].offsetHeight || 0, pages[i].scrollHeight || 0) + 24;
        }}
        height += Math.max(sheet.scrollHeight || 0, pageSum);
      }} else {{
        height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
      }}
      if (window.frameElement) {{
        window.frameElement.style.height = Math.ceil(height) + "px";
        window.frameElement.style.overflow = "visible";
      }}
    }}
    function _a4PageOverflow(page, footer, safetyPx) {{
      if (!page) return 0;
      var pageBox = page.getBoundingClientRect();
      var limitBottom = pageBox.bottom - Math.max(8, safetyPx || 8);
      if (footer) {{
        var footerTop = footer.getBoundingClientRect().top;
        limitBottom = Math.min(limitBottom, footerTop - Math.max(8, safetyPx || 8));
      }}
      var overflow = 0;
      var kids = page.children;
      for (var i = 0; i < kids.length; i++) {{
        var el = kids[i];
        if (!el || el === footer) continue;
        if (el.classList && (
          el.classList.contains("official-page-footer") ||
          el.classList.contains("official-footer") ||
          el.classList.contains("page-footer") ||
          el.classList.contains("footer")
        )) continue;
        var bottom = el.getBoundingClientRect().bottom;
        overflow = Math.max(overflow, bottom - limitBottom);
        overflow = Math.max(overflow, el.scrollHeight - el.clientHeight);
      }}
      overflow = Math.max(overflow, page.scrollHeight - page.clientHeight);
      return overflow;
    }}
    function _a4CollectBalanceBoxes(page) {{
      return page.querySelectorAll(
        ".section-box, .content-box, .report-box, .box-content.autofit-box, .liability-box.autofit-box, [data-autofit]"
      );
    }}
    function _a4ApplySharedSpacing(page, padPx, sectionGap, badgeMargin, badgePadY) {{
      page.style.setProperty("--shared-box-pad", padPx.toFixed(2) + "px");
      page.style.setProperty("--section-gap", sectionGap.toFixed(2) + "px");
      page.style.setProperty("--a4-box-pad", padPx.toFixed(2) + "px");
      page.style.setProperty("--a4-box-margin", sectionGap.toFixed(2) + "px");
      page.style.setProperty("--a4-badge-margin", badgeMargin.toFixed(2) + "px");
      page.style.setProperty("--a4-badge-pad-y", badgePadY.toFixed(2) + "px");
      var body = page.querySelector(".page-body, .page-body-flex, .autofit-page-body");
      if (body) body.style.setProperty("gap", sectionGap.toFixed(2) + "px", "important");
      var boxes = _a4CollectBalanceBoxes(page);
      for (var i = 0; i < boxes.length; i++) {{
        if (boxes[i].classList && boxes[i].classList.contains("box-content")) {{
          boxes[i].style.setProperty("padding", padPx.toFixed(2) + "px", "important");
          boxes[i].style.setProperty("margin-bottom", sectionGap.toFixed(2) + "px", "important");
        }}
      }}
      var badges = page.querySelectorAll(".section-badge");
      for (var b = 0; b < badges.length; b++) {{
        badges[b].style.setProperty("margin", badgeMargin.toFixed(2) + "px auto", "important");
        badges[b].style.setProperty("padding", badgePadY.toFixed(2) + "px 25px", "important");
      }}
    }}
    function _a4ApplySharedFont(page, fontPx, lineHeight) {{
      page.style.setProperty("--shared-box-font", fontPx.toFixed(2) + "px");
      page.style.setProperty("--shared-line-height", String(lineHeight));
    }}
    function _a4SetLastBoxGrow(page, grow) {{
      page.style.setProperty("--a4-last-box-grow", String(grow));
      var boxes = page.querySelectorAll(
        ".page-body > .box-content.autofit-box, .page-body-flex > .box-content.autofit-box, .autofit-page-body > .box-content.autofit-box, .page-body > .section-box, .page-body-flex > .section-box"
      );
      for (var i = 0; i < boxes.length; i++) {{
        boxes[i].style.flexGrow = "0";
      }}
      if (boxes.length) {{
        boxes[boxes.length - 1].style.flexGrow = String(grow);
      }}
    }}
    function _a4UnlockTextBoxes(root) {{
      if (!root || !root.querySelectorAll) return;
      root.querySelectorAll("[data-autofit]").forEach(function(el) {{
        if (!el.getAttribute("data-oldfit")) {{
          el.setAttribute("data-oldfit", el.getAttribute("data-autofit") || "1");
        }}
        el.removeAttribute("data-autofit");
      }});
      root.querySelectorAll(
        ".box-content, .autofit-box, .section-box, .content-box, .report-box, .results-box, .how-happened-box, .liability-box, [data-oldfit], td.actions-body"
      ).forEach(function(el) {{
        if (el.classList && el.classList.contains("sign-table")) return;
        if (el.closest && el.closest("table.sign-table, .sign-table")) return;
        el.style.setProperty("height", "auto", "important");
        el.style.setProperty("max-height", "none", "important");
        el.style.setProperty("overflow", "visible", "important");
        el.style.setProperty("flex-shrink", "0", "important");
        el.style.setProperty("padding-bottom", "10px", "important");
      }});
    }}
    function autoBalanceReportPages() {{
      /* قياس .report-page بـ 295mm؛ صفّر min-height قبل القياس؛ ابدأ 13.5/1.42؛ حد أدنى 10.5؛ badge≥12.5 */
      var pages = document.querySelectorAll(".report-page, .a4-page, .page");
      var initialBase = 13.5;
      var minFont = 10.5;
      var step = 0.25;
      var lineHeight = 1.42;
      document.documentElement.style.setProperty("--shared-box-font", initialBase.toFixed(2) + "px");
      document.documentElement.style.setProperty("--shared-line-height", String(lineHeight));
      for (var p = 0; p < pages.length; p++) {{
        var page = pages[p];
        if (!page || page.classList.contains("photo-annex")) continue;
        if (page.classList.contains("report-sheet") || page.classList.contains("report-viewport")) continue;
        _a4UnlockTextBoxes(page);
        var footer = page.querySelector(".official-page-footer, .official-footer, .page-footer, .footer");
        if (footer) {{
          page.classList.remove("has-absolute-footer");
          footer.style.setProperty("flex-shrink", "0", "important");
        }}
        var boxes = page.querySelectorAll(
          ".box-content, .autofit-box, .section-box, .content-box, .report-box, .results-box, .how-happened-box, .liability-box, [data-oldfit], td.actions-body"
        );
        if (!boxes.length) continue;
        var ruler = document.createElement("div");
        ruler.style.cssText = "position:absolute;top:0;left:0;width:1px;height:295mm;visibility:hidden;pointer-events:none;";
        page.appendChild(ruler);
        var maxH = ruler.offsetHeight || 1116;
        page.removeChild(ruler);
        /* قبل الحلقة: صفّر min-height وheight auto وهامش تذييل 8px مؤقتاً */
        page.style.setProperty("min-height", "0", "important");
        page.style.setProperty("height", "auto", "important");
        page.style.setProperty("max-height", "none", "important");
        page.style.setProperty("overflow", "visible", "important");
        if (footer) footer.style.setProperty("margin-top", "8px", "important");
        var body = page.querySelector(".page-body, .page-body-flex, .autofit-page-body");
        var badges = page.querySelectorAll(".section-badge");
        function applyBalanceFont(fontPx) {{
          _a4SetLastBoxGrow(page, 0);
          _a4ApplySharedFont(page, fontPx, lineHeight);
          if (body) body.style.setProperty("gap", "6px", "important");
          for (var bi = 0; bi < boxes.length; bi++) {{
            var bx = boxes[bi];
            if (bx.closest && bx.closest(".sign-table")) continue;
            bx.style.setProperty("font-size", fontPx.toFixed(2) + "px", "important");
            bx.style.setProperty("line-height", String(lineHeight), "important");
            bx.style.setProperty("height", "auto", "important");
            bx.style.setProperty("max-height", "none", "important");
            bx.style.setProperty("overflow", "visible", "important");
            bx.style.setProperty("flex-shrink", "0", "important");
          }}
          for (var b = 0; b < badges.length; b++) {{
            badges[b].style.setProperty("font-size", Math.max(12.5, fontPx).toFixed(2) + "px", "important");
          }}
        }}
        var fontPx = initialBase;
        applyBalanceFont(fontPx);
        /* لا تصغّر إن المحتوى ≤ maxH؛ إن زاد قلّل 0.25px وتوقف عند أول مقاس يدخل */
        if (page.scrollHeight > maxH + 0.5) {{
          while (fontPx > minFont + 0.001) {{
            fontPx = Math.max(minFont, +(fontPx - step).toFixed(2));
            applyBalanceFont(fontPx);
            if (page.scrollHeight <= maxH + 0.5) break;
            if (fontPx <= minFont + 0.001) break;
          }}
        }}
        page.style.setProperty("min-height", "296mm", "important");
        if (footer) footer.style.setProperty("margin-top", "auto", "important");
      }}
      fitReportFrame();
    }}
    function autoFitReportPages() {{ autoBalanceReportPages(); }}
    function _scheduleAutoBalance() {{
      autoBalanceReportPages();
      setTimeout(autoBalanceReportPages, 60);
      setTimeout(autoBalanceReportPages, 250);
      setTimeout(fitReportFrame, 320);
    }}
    document.addEventListener("DOMContentLoaded", _scheduleAutoBalance);
    window.addEventListener("load", _scheduleAutoBalance);
    window.addEventListener("beforeprint", autoBalanceReportPages);
    window.addEventListener("resize", function() {{
      autoBalanceReportPages();
      fitReportFrame();
    }});
    if (document.fonts && document.fonts.ready) {{
      document.fonts.ready.then(function() {{ _scheduleAutoBalance(); }}).catch(function() {{}});
    }}
    document.addEventListener("load", function() {{ autoBalanceReportPages(); fitReportFrame(); }}, true);
    setTimeout(_scheduleAutoBalance, 40);
    setTimeout(_scheduleAutoBalance, 400);
    </script>
    </head>
    <body class="{body_class}">
        <div class="report-viewport">
        <div class="report-sheet">
        <div class="{p1_page_class}">
            {build_header()}
            <div class="p1-body-flex">
                <div class="p1-section-group">
                    <div class="section-badge">تقرير حادث مروري</div>
                    <div class="section-badge badge-sub">معلومات الحادث</div>
                    <div class="table-scroll"><table>
                        <tr>
                            <th>رقم الحادث</th><th>تاريخ الحادث</th><th>الوقت</th><th>موقع الحادث</th>
                            <th>نوع الحادث</th><th>عدد الإصابات</th><th>عدد الوفيات</th><th>الطقس</th><th>سبب الحادث</th>
                        </tr>
                        <tr>
                            <td>{acc_num}</td><td>{acc_date}</td><td>{acc_time}</td><td>{acc_loc}</td>
                            <td>{acc_type}</td><td>{acc_injuries}</td><td>{acc_deaths}</td><td>{acc_weather}</td><td>{acc_cause}</td>
                        </tr>
                    </table></div>
                </div>
                <div class="p1-section-group">
                    <div class="section-badge badge-sub">معلومات أطراف الحادث</div>
                    <div class="table-scroll"><table>
                        <tr>{parties_head}</tr>
                        {parties_rows}
                    </table></div>
                </div>
                <div class="p1-section-group">
                    <div class="section-badge badge-sub">معلومات المركبات</div>
                    <div class="table-scroll"><table>
                        <tr>{vehicles_head}</tr>
                        {vehicles_rows}
                    </table></div>
                </div>
            </div>
            {official_footer_html}
        </div>
        <div class="page report-page page-flow page-p2">
            {build_header()}
            <div class="page-body page-body-flex autofit-page-body">
            <div class="section-badge">نتائج الحادث</div>
            <div class="box-content autofit-box section-box content-box report-box results-box" data-autofit="results">{results_html}</div>
            <div class="section-badge">كيفية وقوع الحادث</div>
            <div class="box-content autofit-box section-box content-box report-box how-happened-box" data-autofit="how">{acc_how_html}</div>
            {liability_html}
            </div>
            {official_footer_html}
        </div>
            <div class="page report-page page-three page-flow page-p3">
            {build_header()}
            <div class="p3-body-flex page-body page-body-flex">
                <div class="table-scroll"><table>
                    <tr><th>طبيعة وتصنيف الحادث</th></tr>
                    <tr><td>{html.escape(accident_nature_val or "")}</td></tr>
                </table></div>
                <div class="table-scroll"><table>
                    <tr><th>الحقوق الخاصة والعامة</th></tr>
                    <tr><td class="autofit-box" data-autofit="rights">{html.escape(rights_status_val or "")}</td></tr>
                </table></div>
                <div class="table-scroll"><table>
                    <tr><th>الإجراءات المتخذة</th></tr>
                    <tr><td class="actions-body autofit-box" data-autofit="actions">{final_actions_html}</td></tr>
                </table></div>
                {criminal_details_html}
                <table class="sign-table" role="table">
                    <colgroup>{sign_colgroup}</colgroup>
                    <thead>
                    <tr><th colspan="{sign_col_count}">معد التقرير</th></tr>
                    <tr>{sign_header_cells}</tr>
                    </thead>
                    <tbody>
                    <tr>{sign_name_cells}</tr>
                    <tr>{sign_rank_cells}</tr>
                    <tr class="sig-row">{sign_sig_cells}</tr>
                    </tbody>
                </table>
            </div>
            {official_footer_html}
        </div>
        {sketch_page_html}
        {photos_pages_html}
        </div>
        </div>
    </body>
    </html>
    """
    try:
        full_report_html = _bayyinah_a4.inject_into_report_html(full_report_html)
    except Exception:
        pass
    st.session_state["_cached_full_report_html"] = full_report_html
else:
    full_report_html = st.session_state.get("_cached_full_report_html", "")
    try:
        full_report_html = _bayyinah_a4.inject_into_report_html(full_report_html)
    except Exception:
        pass
if st.session_state.active_tab == MAIN_TAB_OPTIONS[3]:
    render_direct_print_button(
        full_report_html,
        label="🖨️ طباعة التقرير بصيغة A4 / حفظ كـ PDF",
        btn_id="tab4",
    )
    st.subheader("📄 معاينة حية للتقرير قبل الطباعة")
    st.components.v1.html(full_report_html, height=1200, scrolling=True)
inject_tab_completion_badges(_report_tab_done_flags())
st.markdown("""
<style>
@media screen and (max-width: 768px) {
  html body section.stSidebar[data-testid="stSidebar"][data-collapsed="true"],
  html body section[data-testid="stSidebar"][aria-expanded="false"] {
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
    transform: none !important;
    overflow: hidden !important;
  }
}

</style>
""", unsafe_allow_html=True)
with header_slot:
    render_compact_command_header(
        on_save_callback=_quick_save_from_header,
        on_reset_callback=_reset_new_accident,
        report_html=full_report_html,
    )
    _save_banner = st.session_state.pop("_save_success_banner", None)
    if _save_banner:
        st.success(f"تم الحفظ بنجاح — آخر حفظ: {_save_banner}")

# --- تلوين شرائح المواد النظامية والإجراءات المتخذة باللون الأحمر الهادئ ---
st.markdown("""<style id="final-red-tags-only">
.stMultiSelect span[data-baseweb="tag"],
[data-testid="stMultiSelect"] span[data-baseweb="tag"],
.stMultiSelect [data-baseweb="tag"] {
    background: linear-gradient(135deg, #991b1b 0%, #7f1d1d 100%) !important;
    background-color: #991b1b !important;
    color: #ffffff !important;
    border: 1px solid #fca5a5 !important;
    box-shadow: none !important;
    text-shadow: none !important;
}
.stMultiSelect span[data-baseweb="tag"] *,
[data-testid="stMultiSelect"] span[data-baseweb="tag"] * {
    color: #ffffff !important;
    fill: #ffffff !important;
}

</style>""", unsafe_allow_html=True)

try:
    ensure_core_accident_fields_from_vault()
    sync_page1_to_vault(
        extra_keys=list(PAGE1_EXTRA_SYNC_KEYS),
        write_disk=True,
        allow_blank_overwrite=False,
    )
except Exception:
    pass
try:
    _bayyinah_persist.finalize_run()
except Exception:
    pass


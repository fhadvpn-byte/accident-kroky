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
    if parsed:
        st.session_state[sel_y_key], st.session_state[sel_m_key], st.session_state[sel_d_key] = parsed
    else:
        st.session_state.setdefault(sel_y_key, today_y)
        st.session_state.setdefault(sel_m_key, today_m)
        st.session_state.setdefault(sel_d_key, None)
    if manual_key not in st.session_state:
        st.session_state[manual_key] = current_val

    def commit_date(year: int, month: int, day: int):
        formatted = f"{int(year):04d}/{int(month):02d}/{int(day):02d}"
        st.session_state[sel_y_key] = int(year)
        st.session_state[sel_m_key] = int(month)
        st.session_state[sel_d_key] = int(day)
        st.session_state[state_key] = formatted
        st.session_state[manual_key] = formatted
        st.session_state[f"{state_key}_sync_parts"] = True
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
                st.session_state[manual_key] = ""
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
        if sync_parts or st.session_state.get(month_ui_key) not in HIJRI_MONTHS:
            st.session_state[month_ui_key] = active_m
        if sync_parts or st.session_state.get(year_ui_key) not in years_list:
            st.session_state[year_ui_key] = active_y
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

def save_permanent_dept_staff(data: dict):
    st.session_state["_perm_dept_staff"] = dict(data)
    try:
        DEPT_STAFF_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

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
        save_permanent_dept_staff(current)
        _mirror_dept_staff_local_storage(current)
        st.toast("تم حفظ الإعدادات الثابتة", icon="💾")

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
        existing = str(st.session_state.get(target_key, "") or "").strip()
        existing_lines = [ln.strip() for ln in existing.splitlines() if ln.strip()]
        for art in selected_articles:
            cite = _official_article_cite(art)
            formatted_art = f"استناداً إلى {cite} من نظام المرور ولائحته التنفيذية." if "المادة" in cite and "نظام المرور" not in cite else cite
            if formatted_art not in existing_lines:
                existing_lines.append(formatted_art)
        st.session_state[target_key] = "\n".join(existing_lines)

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
    st.session_state["actions_taken_editor"] = "\n".join(
        f"{i}- {ACTIONS_SCENARIOS[k]}" for i, k in enumerate(cur_acts, 1) if k in ACTIONS_SCENARIOS
    )

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
    if v1 and v1.lower() != "none":
        cur_p1 = str(st.session_state.get(p1_title_key, ""))
        if cur_p1 in ("", "قائد المركبة الأولى (الطرف الأول)") or cur_p1.startswith("قائد المركبة الأولى ("):
            st.session_state[p1_title_key] = f"قائد المركبة الأولى ({v1})"
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
    st.session_state["actions_taken_editor"] = "\n".join(
        f"{i}- {ACTIONS_SCENARIOS[k]}" for i, k in enumerate(cur_acts, 1) if k in ACTIONS_SCENARIOS
    )

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
                st.session_state["_p1_vault"][key] = cloned
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

def sync_page1_to_vault(extra_keys: list = None, write_disk: bool = False):
    """يحدّث الخزنة في الذاكرة فقط. الكتابة للقرص تتم عند الحفظ اليدوي."""
    if "_p1_vault" not in st.session_state:
        st.session_state["_p1_vault"] = dict(ALL_PAGE1_DEFAULTS)
    keys_to_sync = list(ALL_PAGE1_DEFAULTS.keys()) + list(PAGE1_EXTRA_SYNC_KEYS) + list(extra_keys or [])
    for key in keys_to_sync:
        if key in st.session_state:
            st.session_state["_p1_vault"][key] = _clone_page1_value(st.session_state[key])
    if not write_disk:
        return
    try:
        P1_AUTOSAVE_PATH.write_text(
            json.dumps(st.session_state["_p1_vault"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

def _mirror_page1_fields():
    hijri = str(st.session_state.get("hijri_date") or "")
    st.session_state["p1_acc_date"] = hijri
    parts = hijri.split("/")
    if len(parts) == 3:
        st.session_state["p1_acc_year"] = parts[0]
        st.session_state["p1_acc_month"] = parts[1]
        st.session_state["p1_acc_day"] = parts[2]
    st.session_state["p1_acc_type"] = st.session_state.get("p1_acc_type_choice") or ""
    st.session_state["p1_acc_weather"] = st.session_state.get("p1_acc_weather_choice") or ""
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
        return
    filtered = {key: p1_data[key] for key in ALL_PAGE1_DEFAULTS if key in p1_data}
    for key in PAGE1_EXTRA_SYNC_KEYS:
        if key in p1_data:
            filtered[key] = p1_data[key]
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
        "بناءً على المعاينة الفنية وتطبيق قواعد المساءلة المرورية واستناداً إلى المادة (50/1) من نظام المرور ولائحته التنفيذية.\n"
        "عدم التأكد من خلو الطريق وأخذ الحيطة والحذر اللازمين قبل المناورة أو التجاوز."
    ),
    "p2_reasons": (
        "استناداً إلى المادة (54) والمادة (57) من نظام المرور ولائحته التنفيذية.\n"
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
    # الصورة الجوية تُحفظ في ملف دائم منفصل (مثل الكروكي) وليست داخل JSON الضخم
    data_to_save.pop("aerial_sketch_data_url", None)
    data_to_save.pop("sketch_data_url", None)
    data_to_save["page1_data"] = export_page1_payload()
    aerial_img = str(st.session_state.get("aerial_sketch_data_url") or "")
    sat_state = st.session_state.get("saved_satellite_state") or st.session_state.get("_saved_satellite_state") or {}
    if aerial_img.startswith("data:image/"):
        _remember_aerial_data_url(aerial_img, sat_state if isinstance(sat_state, dict) else {})
        data_to_save["has_aerial_image"] = True
        data_to_save["satellite_img_b64"] = True
    else:
        data_to_save["has_aerial_image"] = False
        data_to_save["satellite_img_b64"] = False
    sketch_img = str(st.session_state.get("sketch_data_url") or "")
    data_to_save["has_sketch_image"] = sketch_img.startswith("data:image/")
    data_to_save["report_media_mode"] = st.session_state.get("report_media_mode", "كلاهما")
    data_to_save["include_aerial"] = bool(st.session_state.get("include_aerial", True))
    data_to_save["include_sketch"] = bool(st.session_state.get("include_sketch", True))
    data_to_save["aerial_place"] = st.session_state.get("aerial_place", "below")
    data_to_save["studio_layout_mode"] = st.session_state.get("studio_layout_mode") or st.session_state.get("_studio_layout_mode")
    data_to_save["saved_satellite_state"] = sat_state if isinstance(sat_state, dict) else {}
    now_str = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d | %I:%M:%S %p")
    data_to_save["last_saved_time"] = now_str
    st.session_state["last_saved_time"] = now_str
    try:
        with open(DRAFT_FILE_PATH, "w", encoding="utf-8") as draft_file:
            json.dump(data_to_save, draft_file, ensure_ascii=False, indent=2)
        return True
    except OSError as error:
        st.error(f"حدث خطأ أثناء حفظ المسودة: {error}")
        return False

def clear_all_work():
    capture_sidebar_before_reset()
    if os.path.exists(DRAFT_FILE_PATH):
        try:
            os.remove(DRAFT_FILE_PATH)
        except OSError:
            pass
    for key, default_val in DEFAULT_REPORT_STATE.items():
        st.session_state[key] = default_val
    st.session_state.law_selection_sig = ()
    st.session_state["confirm_clear"] = False
    reset_page1_payload()
    st.session_state["_restore_perm_sidebar"] = True
    _clear_remembered_aerial()

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
                margin: 0 !important;
                padding: 0 !important;
                background: #ffffff !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
            body > div:not(.bayyinah-print-bar),
            .report-viewport, .report-sheet,
            .report-wrapper, .pages-wrapper, .preview-container {
                margin: 0 !important;
                padding: 0 !important;
                gap: 0 !important;
                border: none !important;
                box-shadow: none !important;
                background: transparent !important;
                display: block !important;
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
                justify-content: flex-start !important;
                page-break-after: always !important;
                break-after: page !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
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
            .page table, .report-page table, .a4-page table,
            .box-content {
                margin-bottom: 6px !important;
            }
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
        acc_no = str(st.session_state.get("p1_acc_number", "") or "").strip()
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
    with col_print:
        render_direct_print_button(report_html or "", label="🖨️ طباعة فورية A4", btn_id="top")
    with col_new:
        if st.button("🆕 حادث جديد", key="_top_cmd_reset", use_container_width=True):
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
    done_tab1 = _filled("p1_acc_number") or _filled("hijri_date") or _filled("p1_acc_location") or has_party_name
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
.page table, .report-page table {
    border-collapse: collapse !important;
    border: 1.5px solid #000000 !important;
    width: 100% !important;
}
.page th, .report-page th {
    background-color: #dcefe4 !important;
    color: #000000 !important;
    font-weight: 800 !important;
    border: 1.1px solid #000000 !important;
    padding: 5px 8px !important;
}
.page td, .report-page td {
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
    sync_page1_to_vault()
    if save_current_work():
        st.toast("تم حفظ جميع بيانات التقرير والصفحات بنجاح", icon="💾")

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
    if how_text:
        st.session_state.technical_description = _upsert_marked_block(
            st.session_state.get("technical_description", ""),
            how_text,
        )
    if results_text:
        st.session_state.accident_results = _upsert_marked_block(
            st.session_state.get("accident_results", ""),
            results_text,
        )
    if legal_text:
        merged_reasons = _upsert_marked_block(
            st.session_state.get("p1_reasons", st.session_state.get("legal_opinion", "")),
            legal_text,
        )
        st.session_state.p1_reasons = merged_reasons
        st.session_state.legal_opinion = merged_reasons
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
    st.session_state.technical_description = _strip_marked_block(st.session_state.get("technical_description", ""))
    st.session_state.accident_results = _strip_marked_block(st.session_state.get("accident_results", ""))
    st.session_state.p1_reasons = _strip_marked_block(st.session_state.get("p1_reasons", st.session_state.get("legal_opinion", "")))
    st.session_state.legal_opinion = st.session_state.p1_reasons
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
    if how_text:
        st.session_state.technical_description = _upsert_marked_block(
            st.session_state.get("technical_description", ""),
            how_text,
        )
    if results_text:
        st.session_state.accident_results = _upsert_marked_block(
            st.session_state.get("accident_results", ""),
            results_text,
        )
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
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    reset_page1_payload()
    st.session_state["_restore_perm_sidebar"] = True
    try:
        for adopted_name in (
            "adopted_sketch.png",
            "adopted_sketch_uri.txt",
            "adopted_aerial_uri.txt",
            "adopted_aerial_state.json",
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

def build_liability_section_html(p1_title, p1_ratio, p1_reasons, p2_title, p2_ratio, p2_reasons):
    def format_bullets(text):
        if not text:
            return ""
        lines = [html.escape(line.strip().lstrip("-•* ")) for line in str(text).splitlines() if line.strip()]
        if not lines:
            return ""
        items = "".join([f"<li style='margin-bottom: 5px;'>{line}</li>" for line in lines])
        return f"<ul style='margin: 6px 22px 10px 0; padding: 0; list-style-type: disc;'>{items}</ul>"

    p1_ratio = int(p1_ratio or 0)
    p2_ratio = int(p2_ratio or 0)
    safe_p1_title = html.escape(str(p1_title or ""))
    safe_p2_title = html.escape(str(p2_title or ""))
    blocks = []
    is_shared = p1_ratio > 0 and p2_ratio > 0
    if p1_ratio > 0:
        header_prefix = "أولاً: " if is_shared else ""
        blocks.append(
            f"<div style='margin-bottom: 10px;'>"
            f"<div style='font-weight: bold; font-size: 15px; margin-bottom: 4px;'>"
            f"{header_prefix}إدانة ({safe_p1_title}) بنسبة ({p1_ratio}%) من المسؤولية، وذلك للأسباب والمواد النظامية التالية:"
            f"</div>"
            f"{format_bullets(p1_reasons)}"
            f"</div>"
        )
    if is_shared:
        blocks.append("<hr style='border: 0; border-top: 1px dashed #666; margin: 10px 0;'>")
    if p2_ratio > 0:
        header_prefix = "ثانياً: " if is_shared else ""
        blocks.append(
            f"<div style='margin-bottom: 8px;'>"
            f"<div style='font-weight: bold; font-size: 15px; margin-bottom: 4px;'>"
            f"{header_prefix}إدانة ({safe_p2_title}) بنسبة ({p2_ratio}%) من المسؤولية، وذلك للأسباب والمواد النظامية التالية:"
            f"</div>"
            f"{format_bullets(p2_reasons)}"
            f"</div>"
        )
    if p1_ratio == 100 and p2_ratio == 0:
        blocks.append(
            f"<div style='font-weight: bold; font-size: 14.5px; margin-top: 8px; padding-top: 6px; border-top: 1px solid #eee;'>"
            f"• عدم مسؤولية ({safe_p2_title}) عن الحادث (نسبة المسؤولية 0%)."
            f"</div>"
        )
    elif p2_ratio == 100 and p1_ratio == 0:
        blocks.append(
            f"<div style='font-weight: bold; font-size: 14.5px; margin-top: 8px; padding-top: 6px; border-top: 1px solid #eee;'>"
            f"• عدم مسؤولية ({safe_p1_title}) عن الحادث (نسبة المسؤولية 0%)."
            f"</div>"
        )
    inner_content = "".join(blocks)
    return (
        f"<div style='text-align: center; margin-top: 14px; margin-bottom: 8px;'>"
        f"<span style='display: inline-block; border: 1.5px solid #000; border-radius: 6px; padding: 4px 28px; font-weight: bold; font-size: 16px; background-color: #f4f4f4;'>"
        f"الرأي والمسؤولية"
        f"</span>"
        f"</div>"
        f"<div style='border: 1.5px solid #000; padding: 12px 16px; direction: rtl; text-align: right; font-size: 14.5px; line-height: 1.65; background-color: #fff;'>"
        f"{inner_content}"
        f"</div>"
    )

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
        background: #0f294a !important;
        border: 1px solid #38bdf8 !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        text-shadow: none !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] span,
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] span,
    span[data-baseweb="tag"] span {
        color: #ffffff !important;
        font-weight: 600 !important;
        text-shadow: none !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] svg,
    span[data-baseweb="tag"] svg {
        color: #fca5a5 !important;
        fill: #fca5a5 !important;
    }
    [data-testid="stSelectbox"] svg,
    [data-testid="stMultiSelect"] svg,
    [data-testid="stDateInput"] svg,
    [data-testid="stNumberInput"] svg {
        fill: #00f2fe !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
    span[data-baseweb="tag"] svg {
        fill: #fca5a5 !important;
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
        transform: scale(1.04);
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
        transform: scale(1.05);
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
st.radio(
    "أقسام التقرير",
    options=MAIN_TAB_OPTIONS,
    horizontal=True,
    key="active_tab",
    label_visibility="collapsed",
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
        st.session_state.p1_acc_location = st.session_state.pop("acc_loc_override")
    elif st.session_state.get("acc_loc_value") and not st.session_state.get("p1_acc_location"):
        st.session_state.p1_acc_location = st.session_state.get("acc_loc_value")
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
    # منتقيات الوقت والتاريخ خارج النموذج (تحتوي popover/أزرار)
    picker_c1, picker_c2 = st.columns(2, gap="medium")
    with picker_c1:
        accident_time = render_smart_time_picker(state_key="p1_acc_time", label="الوقت")
        acc_time = accident_time
    with picker_c2:
        accident_date = render_luxury_hijri_picker(state_key="hijri_date", label="تاريخ الحادث (هجري)")
        acc_date = accident_date
        st.session_state.p1_acc_date = accident_date
        st.session_state.hijri_manual_date = accident_date

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
        r1_c1, r1_c2, r1_c3 = st.columns(3, gap="medium")
        with r1_c1:
            acc_num = st.text_input("رقم الحادث", key="p1_acc_number")
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
            acc_loc = st.text_input("موقع الحادث", key="p1_acc_location")
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
        acc_cause = st.text_input("سبب الحادث الرئيسي (المختصر)", key="p1_acc_cause")
        st.divider()
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
        _mirror_page1_fields()
        sync_page1_to_vault(extra_keys=list(PAGE1_EXTRA_SYNC_KEYS), write_disk=False)
        st.toast("تم اعتماد بيانات الحادث والأطراف في الجلسة", icon="✅")
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
        if save_current_work():
            st.toast("تم حفظ جميع بيانات التقرير والصفحات بنجاح", icon="💾")
    _vehicle_rows = list(st.session_state.get("vehicles") or [])

    def _vehicle_type_at(index):
        if index < len(_vehicle_rows) and isinstance(_vehicle_rows[index], dict):
            return str(_vehicle_rows[index].get("نوع المركبة") or "")
        return ""

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
        "label": "المادة (8/ج) - قيادة المركبة دون وجود وثيقة تأمين سارية المفعول وقت الحادث",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "resultPoint": "قيادة المركبة دون وثيقة تأمين سارية المفعول وقت وقوع الحادث.",
        "technicalDraft": "ثبت من خلال تدقيق بيانات المركبة عدم وجود وثيقة تأمين سارية المفعول تغطي المسؤولية المدنية تجاه الغير وقت وقوع الحادث.",
        "legalOpinion": "تطبيق أحكام المادة (8/ج) من نظام المرور بشأن عدم وجود تأمين ساري المفعول، مع قيام المسؤولية المدنية المباشرة على المتسبب.",
    },
    {
        "id": "art_28",
        "code": "المادة (28)",
        "label": "المادة (28) - التسبب في حادث نتيجة نقل حمولة زائدة أو بارزة أو غير مؤمنة",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "resultPoint": "عدم تأمين الحمولة أو تجاوز الأبعاد والأوزان النظامية مما أدى لوقوع الحادث.",
        "technicalDraft": "وقع الحادث نتيجة إهمال قائد المركبة في ربط وتأمين الحمولة المنقولة بشكل آمن، مما أدى إلى سقوطها/بروزها واصطدام الطرف الآخر بها.",
        "legalOpinion": "ثبوت المسؤولية التقصيرية استناداً للمادة (28) من نظام المرور لمخالفة ضوابط وشروط نقل الحمولة.",
    },
    {
        "id": "art_32_1",
        "code": "المادة (32/1)",
        "label": "المادة (32/1) - قيادة المركبة قبل الحصول على رخصة قيادة أو برخصة غير مناسبة أو مسحوبة",
        "category": "الأهلية والتأمين والحمولة",
        "isQuasiCriminal": False,
        "resultPoint": "عدم حمل قائد المركبة لرخصة قيادة نظامية تخوله قيادة المركبة وقت الحادث.",
        "technicalDraft": "تبين عند استجواب أطراف الحادث وفحص الوثائق أن السائق يقود المركبة دون الحصول على رخصة قيادة نظامية تخوله القيادة.",
        "legalOpinion": "مخالفة صريحة للمادة (32/1) من نظام المرور لقيادة مركبة دون رخصة قيادة، ويحال للجهة المختصة لتطبيق العقوبات النظامية.",
    },
    {
        "id": "art_50_1_1",
        "code": "المادة (50/1/1)",
        "label": "المادة (50/1/1) - عدم التزام أقصى الجانب الأيمن من الطريق أو السير غير النظامي في المسارات",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "عدم التزام المركبة بالمسار النظامي المحدد على الطريق.",
        "technicalDraft": "عدم تقيد قائد المركبة بخطوط المسارات الأرضية والخروج الجزئي عن الحارة المرورية المخصصة له أثناء السير.",
        "legalOpinion": "تحمل المسؤولية المرورية لمخالفة المادة (50/1/1) من نظام المرور ولائحته التنفيذية.",
    },
    {
        "id": "art_50_1_2",
        "code": "المادة (50/1/2)",
        "label": "المادة (50/1/2) - عدم التقيد بحدود المسارات المحددة على الطريق أو التعدي على المسار المجاور",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "عدم التقيد بحدود المسار المحدد نظاماً والتعدي على المسار المجاور.",
        "technicalDraft": "كما تبين من المعاينة الفنية عدم تقيد قائد المركبة بحدود المسار المحدد له نظاماً على الطريق والتعدي على المسار المجاور مما أدى إلى وقوع الاصطدام، وذلك بالمخالفة لأحكام المادة (50/1/2) من نظام المرور ولائحته التنفيذية.",
        "legalOpinion": "ثبوت المسؤولية المرورية استناداً للمادة (50/1/2) لعدم التقيد بحدود المسارات المحددة أو التعدي على المسار المجاور.",
    },
    {
        "id": "art_50_1_4",
        "code": "المادة (50/1/4)",
        "label": "المادة (50/1/4) - الانحراف المفاجئ أو تغيير المسار دون إشارة ضوئية ودون التأكد من خلو المسار",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "الانحراف المفاجئ والدخول على مسار مركبة أخرى دون تأكد من خلوه.",
        "technicalDraft": "قام قائد المركبة بالانتقال المفاجئ من مساره إلى المسار المجاور دون إعطاء الإشارة التنبيهية المسبقة ودون التحقق من خلو المسار، مما قطع خط سير المركبة الأخرى وأدى للاصطدام.",
        "legalOpinion": "ثبوت المسؤولية استناداً للمادة (50/1/4) نتيجة الانحراف المفاجئ وعدم مراعاة أولوية المركبات السائرة في مسارها الصحيح.",
    },
    {
        "id": "art_50_2_1",
        "code": "المادة (50/2/1)",
        "label": "المادة (50/2/1) - الانعطاف أو الدوران للخلف (اليوتيرن) بشكل غير نظامي",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "الدوران للخلف أو الانعطاف من مسار غير مخصص ودون تأمين الطريق.",
        "technicalDraft": "شرع قائد المركبة في إجراء عملية دوران للخلف (يوتيرن) / انعطاف بشكل خاطئ دون التأكد من خلو الطريق ودون إعطاء الأفضلية للمركبات القادمة في الاتجاه الصحيح.",
        "legalOpinion": "قيام المسؤولية التقصيرية استناداً للمادة (50/2/1) لمخالفة قواعد الانعطاف والدوران.",
    },
    {
        "id": "art_50_3_1",
        "code": "المادة (50/3/1)",
        "label": "المادة (50/3/1) - التجاوز الخاطئ أو التجاوز في المنعطفات والمرتفعات وعند انعدام الرؤية",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "التجاوز غير النظامي في منطقة يحظر فيها التجاوز شرعاً ونظاماً.",
        "technicalDraft": "تجاوز قائد المركبة للمركبات التي أمامه في منطقة محظورة التجاوز (منعطف / مرتفع / مسار مفرد غير خالٍ) مما أدى إلى اعتراض مسار المركبة المقابلة ووقوع التصادم.",
        "legalOpinion": "ثبوت الخطأ المروري الموجب للمسؤولية وفق المادة (50/3/1) من نظام المرور.",
    },
    {
        "id": "art_50_4_1",
        "code": "المادة (50/4/1)",
        "label": "المادة (50/4/1) - عدم ترك مسافة أمان كافية بين المركبات أثناء السير (الاصطدام من الخلف)",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "عدم ترك مسافة أمان كافية تمكن السائق من التوقف الآمن.",
        "technicalDraft": "سير المركبة خلف المركبة المتضررة مباشرة دون ترك مسافة أمان كافية تتناسب مع السرعة والظروف المحيطة، مما أفقد السائق القدرة على التوقف عند تهدئة المركبة الأمامية واصطدامه بمؤخرتها.",
        "legalOpinion": "قيام المسؤولية على المركبة الخلفية استناداً للمادة (50/4/1) لعدم ترك مسافة الأمان النظامية.",
    },
    {
        "id": "art_50_5_1",
        "code": "المادة (50/5/1)",
        "label": "المادة (50/5/1) - عدم إعطاء أولوية المرور في التقاطعات غير المنظمة أو للقادم من طريق رئيسي",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "الدخول إلى التقاطع أو الطريق الرئيسي دون إعطاء الأفضلية النظامية.",
        "technicalDraft": "دخول قائد المركبة من طريق فرعي إلى طريق رئيسي (أو تقاطع) دون التوقف التام ودون منح أولوية العبور للمركبات السائرة في الطريق ذي الأفضلية.",
        "legalOpinion": "ثبوت المسؤولية لمخالفة قواعد الأولوية في التقاطعات المنصوص عليها في المادة (50/5/1).",
    },
    {
        "id": "art_50_5_5",
        "code": "المادة (50/5/5)",
        "label": "المادة (50/5/5) - عدم إعطاء الأولوية للمركبات الموجودة داخل الدوار",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "الدخول إلى الدوار دون منح الأفضلية للمركبات السائرة داخله.",
        "technicalDraft": "ولوج قائد المركبة إلى حرم الدوار مباشرة دون التريث وإعطاء أولوية المرور للمركبة المتواجدة فعلياً داخل مسار الدوار.",
        "legalOpinion": "تطبيق المسؤولية المرورية بموجب المادة (50/5/5) لإخلال السائق بأفضلية السير داخل الدوار.",
    },
    {
        "id": "art_50_7_1",
        "code": "المادة (50/7/1)",
        "label": "المادة (50/7/1) - الوقوف الخاطئ أو الوقوف في الأماكن المحظورة دون تأمين المركبة",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "إيقاف المركبة في مكان محظور يشكل عائقاً لحركة السير.",
        "technicalDraft": "إيقاف المركبة في موقع يمنع فيه الوقوف نظاماً ودون تشغيل الإشارات التحذيرية أو وضع المثلث العاكس، مما شكل عائقاً خطراً على نهر الطريق.",
        "legalOpinion": "ثبوت المسؤولية (الكلية أو الجزئية) استناداً للمادة (50/7/1) لمخالفة ضوابط الوقوف والتوقف.",
    },
    {
        "id": "art_50_8_1",
        "code": "المادة (50/8/1)",
        "label": "المادة (50/8/1) - الرجوع إلى الخلف (الريوس) دون حذر أو الدخول لطريق عام بالرجوع للخلف",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "الرجوع إلى الخلف دون التأكد من خلو المسار الخلفي.",
        "technicalDraft": "قيام قائد المركبة بالرجوع إلى الخلف (الريوس) دون التحقق التام من خلو الحيز الخلفي للمركبة، مما أدى إلى الاصطدام بالطرف الآخر.",
        "legalOpinion": "قيام المسؤولية الكاملة على المركبة المتراجعة للخلف استناداً للمادة (50/8/1).",
    },
    {
        "id": "art_50_9_1",
        "code": "المادة (50/9/1)",
        "label": "المادة (50/9/1) - تجاوز السرعة النظامية المحددة على الطريق أو عدم مراعاة الظروف الجوية",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "قيادة المركبة بسرعة تتجاوز الحد النظامي المسموح به على الطريق.",
        "technicalDraft": "قيادة المركبة بسرعة عالية تتجاوز السرعة المقررة نظاماً (وفق آثار الفرملة وشدة التلفيات)، مما أفقد السائق السيطرة على المركبة عند تفاجئه بالحدث المروري.",
        "legalOpinion": "ثبوت التعدي والتفريط بمخالفة المادة (50/9/1) لتجاوز السرعة النظامية.",
    },
    {
        "id": "art_50_9_5_a",
        "code": "المادة (50/9/5/أ)",
        "label": "المادة (50/9/5/أ) - تجاوز السرعة داخل الأحياء السكنية أو عدم التهدئة عند المعابر",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "عدم التهدئة وتجاوز السرعة الآمنة داخل النطاق السكني.",
        "technicalDraft": "سير المركبة داخل منطقة سكنية بسرعة غير متناسبة مع طبيعة الطريق الحيوية، وعدم التهدئة الكافية لتفادي المخاطر المتوقعة.",
        "legalOpinion": "ثبوت المسؤولية المرورية استناداً للمادة (50/9/5/أ) لعدم الالتزام بحدود السرعة داخل الأحياء.",
    },
    {
        "id": "art_50_10_1",
        "code": "المادة (50/10/1)",
        "label": "المادة (50/10/1) - السير ليلاً أو أثناء الضباب والغبار دون استخدام الأنوار النظامية",
        "category": "قواعد السير والأولويات (المادة 50)",
        "isQuasiCriminal": False,
        "resultPoint": "إغفال تشغيل أنوار المركبة أثناء السير الليلي أو تدني الرؤية.",
        "technicalDraft": "قيادة المركبة في ظروف رؤية منخفضة (ليلاً / ضباب / غبار) دون إضاءة الأنوار الأمامية والخلفية النظامية، مما حال دون رؤيتها من قبل مستخدمي الطريق.",
        "legalOpinion": "تحمل المسؤولية التقصيرية استناداً للمادة (50/10/1) لمخالفة قواعد استخدام الأنوار.",
    },
    {
        "id": "art_51_1_signal",
        "code": "المادة (51/1 - إشارة)",
        "label": "المادة (51/1) - عدم التقيد بالإشارات الضوئية (قطع الإشارة الحمراء)",
        "category": "المخالفات الخطرة وتجهيزات السلامة (51 - 58)",
        "isQuasiCriminal": False,
        "resultPoint": "تجاوز الإشارة الضوئية الحمراء ودخول التقاطع أثناء أولوية الاتجاه الآخر.",
        "technicalDraft": "عدم امتثال قائد المركبة لدلالة الإشارة الضوئية الحمراء التي تلزمه بالتوقف التام، واستمراره في عبور التقاطع مما أدى لاصطدامه بالمركبة العابرة بشكل نظامي.",
        "legalOpinion": "ثبوت التعدي الصريح بمخالفة المادة (51/1) لقطع الإشارة الضوئية الحمراء، وهي من المخالفات الموجبة للتوقيف عند اقترانها بإصابة خطيرة أو وفاة.",
    },
    {
        "id": "art_51_1_wrong_way",
        "code": "المادة (51/1 - عكس سير)",
        "label": "المادة (51/1) - السير عكس اتجاه الحركة المقرر على الطريق",
        "category": "المخالفات الخطرة وتجهيزات السلامة (51 - 58)",
        "isQuasiCriminal": False,
        "resultPoint": "قيادة المركبة بعكس اتجاه السير النظامي للطريق.",
        "technicalDraft": "سلوك قائد المركبة مساراً معاكساً لاتجاه الحركة المرورية المحددة باللوحات الإرشادية والعلامات الأرضية، مما أدى إلى وقوع تصادم وجهاً لوجه.",
        "legalOpinion": "ثبوت المسؤولية الكاملة والتعدي الجسيم بموجب المادة (51/1) للسير عكس الاتجاه.",
    },
    {
        "id": "art_52_53",
        "code": "المادة (52 و 53)",
        "label": "المادة (52 و 53) - ترك عوائق على الطريق أو إجراء حفريات وأعمال طرق دون لوحات تحذيرية",
        "category": "المخالفات الخطرة وتجهيزات السلامة (51 - 58)",
        "isQuasiCriminal": False,
        "resultPoint": "وجود عوائق أو أعمال طرق غير مؤمنة بوسائل السلامة والتحذير.",
        "technicalDraft": "وقوع الحادث نتيجة اصطدام المركبة بعائق / حفريات في حرم الطريق خلت من الحواجز الخرسانية والإضاءات التحذيرية المسبقة على المسافة النظامية.",
        "legalOpinion": "تحميل الجهة المنفذة / المتسبب المسؤولية استناداً للمادتين (52 و 53) للإخلال باشتراطات سلامة الطريق.",
    },
    {
        "id": "art_55_1",
        "code": "المادة (55/1)",
        "label": "المادة (55/1) - دهس المشاة أو عدم إعطاء الأولوية للمشاة في المسارات المخصصة",
        "category": "المخالفات الخطرة وتجهيزات السلامة (51 - 58)",
        "isQuasiCriminal": False,
        "resultPoint": "عدم التهدئة وإعطاء الأفضلية للمشاة أثناء عبورهم الطريق.",
        "technicalDraft": "عدم انتباه قائد المركبة وعدم تخفيفه للسرعة عند الاقتراب من منطقة عبور المشاة، مما أدى إلى صدم عابر الطريق بجسم المركبة.",
        "legalOpinion": "ثبوت المسؤولية التقصيرية استناداً للمادة (55/1) لعدم مراعاة سلامة وأولوية المشاة.",
    },
    {
        "id": "art_57_1_lane_markings",
        "code": "المادة (57/1 - خطوط أرضية)",
        "label": "المادة (57/1) - عدم التقيد بالخطوط الأرضية والعلامات المرورية المنظمة للمسارات",
        "category": "المخالفات الخطرة وتجهيزات السلامة (51 - 58)",
        "isQuasiCriminal": False,
        "resultPoint": "عدم التقيد بالخطوط الأرضية والعلامات المرورية المنظمة للمسارات.",
        "technicalDraft": "كما اتضح من المعاينة الفنية عدم التزام قائد المركبة بالخطوط الأرضية والعلامات المرورية المحددة لتنظيم المسارات على الطريق وتجاوز الخط الفاصل بين المسارات بشكل غير نظامي، خلافاً لأحكام المادة (57/1) من نظام المرور.",
        "legalOpinion": "ثبوت المسؤولية المرورية استناداً للمادة (57/1) لعدم التقيد بالخطوط الأرضية والعلامات المرورية المنظمة للمسارات.",
    },
    {
        "id": "art_57_1_distraction",
        "code": "المادة (57/1 - انشغال)",
        "label": "المادة (57/1) - الانشغال بغير الطريق (استخدام الجوال باليد أثناء القيادة)",
        "category": "المخالفات الخطرة وتجهيزات السلامة (51 - 58)",
        "isQuasiCriminal": False,
        "resultPoint": "انشغال السائق عن متابعة الطريق باستخدام الهاتف المتنقل أثناء القيادة.",
        "technicalDraft": "انصراف انتباه قائد المركبة عن مراقبة الطريق نتيجة انشغاله باستخدام جهاز الهاتف المحمول، مما أدى لعدم اتخاذه أي رد فعل لتفادي الاصطدام.",
        "legalOpinion": "ثبوت التفريط والإهمال بموجب المادة (57/1) للانشغال بغير الطريق أثناء القيادة.",
    },
    {
        "id": "art_57_1_sudden_stop",
        "code": "المادة (57/1 - وقوف مباغت)",
        "label": "المادة (57/1) - الوقوف المباغت في نهر الطريق دون مبرر أو ضرورة مرورية",
        "category": "المخالفات الخطرة وتجهيزات السلامة (51 - 58)",
        "isQuasiCriminal": False,
        "resultPoint": "التوقف المفاجئ غير المبرر في مسار السير النشط.",
        "technicalDraft": "قيام قائد المركبة باستخدام المكابح بصورة فجائية والتوقف التام في وسط المسار دون وجود عائق أمامه أو مبرر مروري، مما فاجأ المركبة الخلفية.",
        "legalOpinion": "ثبوت المسؤولية (الكلية أو المشتركة) بموجب المادة (57/1) للوقوف المباغت المخل بسلامة السير.",
    },
    {
        "id": "art_58_1",
        "code": "المادة (58/1)",
        "label": "المادة (58/1) - قيادة مركبة خالية من تجهيزات السلامة (خلل المكابح أو تلف الإطارات)",
        "category": "المخالفات الخطرة وتجهيزات السلامة (51 - 58)",
        "isQuasiCriminal": False,
        "resultPoint": "عدم صلاحية المركبة فنياً للسير (تلف الإطارات أو عطل المكابح).",
        "technicalDraft": "تبين من الفحص الفني للمركبة وجود خلل فني سابق للحادث يتمثل في (تآكل الإطارات وانفجارها / ضعف منظومة المكابح)، مما أدى لفقدان السيطرة ووقوع الحادث.",
        "legalOpinion": "قيام المسؤولية التقصيرية بموجب المادة (58/1) لقيادة مركبة تفتقر لتجهيزات السلامة الفنية.",
    },
    {
        "id": "art_60_1",
        "code": "المادة (60/1)",
        "label": "المادة (60/1) - ثبوت المسؤولية التقصيرية لاجتماع أركان الخطأ (الإهمال، قلة الاحتراز، مخالفة الأنظمة)",
        "category": "أركان المسؤولية والحق العام (60 - 62)",
        "isQuasiCriminal": False,
        "resultPoint": "تحقق أركان المسؤولية التقصيرية (الخطأ، الضرر، علاقة السببية).",
        "technicalDraft": "اجتماع عناصر الخطأ المروري المتمثلة في الإهمال وقلة الاحتراز وعدم مراعاة الأنظمة المرورية، وارتباطها برابطة سببية مباشرة بالضرر الواقع.",
        "legalOpinion": "ثبوت المسؤولية النظامية كاملة وفق معيار المادة (60/1) من نظام المرور ولائحته التنفيذية.",
    },
    {
        "id": "art_60_2",
        "code": "المادة (60/2)",
        "label": "المادة (60/2) - انتفاء المسؤولية لوقوع الحادث بسبب قوة قاهرة أو خطأ المتضرر الخالص",
        "category": "أركان المسؤولية والحق العام (60 - 62)",
        "isQuasiCriminal": False,
        "resultPoint": "انتفاء الخطأ المروري من جانب السائق لوجود قوة قاهرة أو خطأ المتضرر.",
        "technicalDraft": "ثبت فنياً أن قائد المركبة كان يسير بشكل نظامي واتخذ كافة الاحتياطات الممكنة، إلا أن الحادث وقع لسبب أجنبي لا يد له فيه (قوة قاهرة / خطأ المتضرر المفاجئ).",
        "legalOpinion": "انتفاء المسؤولية والحق العام استناداً للمادة (60/2) من نظام المرور.",
    },
    {
        "id": "art_61_1",
        "code": "المادة (61/1)",
        "label": "المادة (61/1) - ثبوت الحق العام في الحادث ومباشرة إجراءات الاستدلال وإشعار النيابة العامة",
        "category": "أركان المسؤولية والحق العام (60 - 62)",
        "isQuasiCriminal": False,
        "resultPoint": "قيام الحق العام في الواقعة واستكمال محاضر الاستدلال النظامية.",
        "technicalDraft": "نظراً لما نتج عن الحادث من أضرار جسيمة / إصابات بشرية مقترنة بمخالفة مرورية صريحة، فقد ثبت الحق العام في الواقعة.",
        "legalOpinion": "تطبيق المادة (61/1) من نظام المرور وإشعار النيابة العامة ورفع ملف القضية لاستكمال الإجراءات النظامية.",
    },
    {
        "id": "art_62_1",
        "code": "المادة (62/1)",
        "label": "المادة (62/1) - حادث مقترن بتعدٍّ أو تفريط نتج عنه وفاة أو زوال عضو أو تعطيل منفعته",
        "category": "أركان المسؤولية والحق العام (60 - 62)",
        "isQuasiCriminal": False,
        "resultPoint": "وقوع وفاة / إصابة بليغة (زوال عضو أو تعطيل منفعة) نتيجة التعدي أو التفريط.",
        "technicalDraft": "ثبت أن الحادث وقع نتيجة تعدٍّ وتفريط صريح من السائق، وقد أفضى الحادث مباشرة إلى (وفاة / تعطيل منفعة عضو) وفق التقارير الطبية المرفقة.",
        "legalOpinion": "إحالة المتسبب إلى النيابة العامة ثم المحكمة المختصة لتطبيق العقوبة الجزائية المقررة في المادة (62/1) من نظام المرور (السجن حتى 4 سنوات وغرامة حتى 200 ألف ريال أو بإحداهما) مع حفظ الحق الخاص.",
    },
    {
        "id": "art_62_2",
        "code": "المادة (62/2)",
        "label": "المادة (62/2) - حادث مقترن بتعدٍّ أو تفريط نتج عنه إصابة تزيد مدة شفائها على (15) يوماً",
        "category": "أركان المسؤولية والحق العام (60 - 62)",
        "isQuasiCriminal": False,
        "resultPoint": "وقوع إصابة بشرية تتجاوز مدة شفائها (15) يوماً نتيجة التعدي أو التفريط.",
        "technicalDraft": "نتج عن الحادث المروري المقترن بالتعدي والتفريط إصابات جسدية للمتضرر قرر التقرير الطبي الشرعي أن مدة شفائها تزيد على خمسة عشر يوماً.",
        "legalOpinion": "إحالة ملف القضية للنيابة العامة لتطبيق مقتضى المادة (62/2) من نظام المرور (السجن حتى سنتين وغرامة حتى 100 ألف ريال أو بإحداهما).",
    },
    {
        "id": "art_59_1_criminal",
        "code": "المادة (59/1 - شبهة عمد)",
        "label": "🚨 المادة (59/1) - انتفاء صفة الحادث المروري العرضي لوجود شبهة صدم عمدي أو اعتداء (إحالة للشرطة)",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "وجود قرائن فنية ومادية تدل على تعمد الاصطدام وانتفاء الصفة العرضية للحادث.",
        "technicalDraft": "بالمعاينة الفنية الدقيقة لنقاط التصادم، وزوايا الدخول، وغياب آثار الفرملة التفاديّة، مع مضاهاة أقوال الأطراف، تبيّن عدم تطابق الواقعة مع مفهوم الحادث المروري العرضي (غير المقصود)، ووجود قرائن قوية على شبهة الصدم العمدي / المطاردة الجنائية.",
        "legalOpinion": "استناداً للمادة (59/1) من اللائحة التنفيذية لنظام المرور التي تنص على أن (حوادث العمد وما يحدث على المركبة وهي واقفة يختص بالتحقيق فيها أقسام الشرطة)، والمادتين (24 و 27) من نظام الإجراءات الجزائية؛ يوصى بإحالة كامل أوراق المعاملة والأطراف إلى مركز الشرطة المختص / النيابة العامة لوجود شبهة جنائية.",
    },
    {
        "id": "art_63_1_hit_and_run",
        "code": "المادة (63/1 - هروب)",
        "label": "🚨 المادة (63/1) - الهروب من موقع الحادث أو عدم إبلاغ الجهات المختصة أو ترك المصابين",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "مغادرة قائد المركبة لموقع الحادث (هروب) دون توقف أو إبلاغ أو إسعاف المصابين.",
        "technicalDraft": "عقب وقوع الاصطدام مباشرة، تعمّد قائد المركبة المتسببة مغادرة مسرح الحادث والهروب بالمركبة دون التوقف أو إبلاغ الجهات الأمنية أو تقديم المساعدة للمصابين، قبل أن يتم رصده وضبطه.",
        "legalOpinion": "ثبوت مخالفة المادة (63/1) من نظام المرور لفرار السائق من موقع الحادث، وإحالته للنيابة العامة والمحكمة المختصة لتطبيق العقوبة الجزائية (السجن حتى 3 أشهر أو غرامة حتى 10 آلاف ريال أو بهما معاً) بالإضافة لعقوبة الحادث الأصلي.",
    },
    {
        "id": "art_63_1_tampering",
        "code": "المادة (63/1 - تغيير معالم)",
        "label": "🚨 المادة (63/1) - تحريك المركبة أو تغيير وإخفاء معالم وآثار الحادث لتضليل التحقيق",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "التلاعب بمسرح الحادث وتغيير مواقع المركبات أو إخفاء الآثار المادية عمداً.",
        "technicalDraft": "رصدت المعاينة الفنية قيام أحد الأطراف بتحريك المركبة وتغيير معالم مسرح الحادث وإخفاء بعض الآثار المادية قبل وصول باحث الحوادث دون مسوغ نظامي، وذلك بقصد تضليل جهة التحقيق وتغيير نسب المسؤولية.",
        "legalOpinion": "تطبيق أحكام المادة (63/1) من نظام المرور لتعمّد تغيير معالم الحادث، مع مساءلته جزائياً عن تضليل إجراءات الاستدلال.",
    },
    {
        "id": "art_63_2_a_driver_swap",
        "code": "المادة (63/2/أ - استبدال سائق)",
        "label": "🚨 المادة (63/2/أ) - استبدال سائق المركبة الذي ارتكب الحادث أو التواطؤ والمشاركة في ذلك",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "شبهة جنائية باستبدال قائد المركبة الفعلي بشخص آخر للتنصل من المسؤولية أو التغطية التأمينية.",
        "technicalDraft": "من خلال مناقشة الأطراف والشهود ومضاهاة الإصابات الجسدية وتفريغ الكاميرات المحيطة، تبيّن وجود تناقض جوهري يثبت أن الشخص المدعي للقيادة لم يكن هو السائق الفعلي وقت الاصطدام، وأنه تم استبدال السائق بالتواطؤ.",
        "legalOpinion": "ثبوت شبهة التحايل واستبدال السائق المعاقب عليها بموجب المادة (63/2/أ) من نظام المرور (السجن حتى سنتين أو غرامة حتى 100 ألف ريال أو بهما معاً)، ويحال السائق الفعلي والمنتحل والمتواطئ إلى النيابة العامة.",
    },
    {
        "id": "art_63_2_b_staged_accident",
        "code": "المادة (63/2/ب - افتعال حادث)",
        "label": "🚨 المادة (63/2/ب) - افتعال وقوع حادث مروري (حادث صوري / احتيال تأميني أو جنائي)",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "عدم تطابق التلفيات ديناميكياً وثبوت شبهة افتعال الحادث صوريّاً.",
        "technicalDraft": "بعد الفحص الهندسي والفني الدقيق لطبيعة الأضرار على المركبتين، وارتفاعات الصدم، واتجاهات القوى الميكانيكية، تبيّن وجود تلفيات قديمة / غير متطابقة هندسياً بين المركبتين، مما يثبت أن الحادث مفتعل وصوري ولم يقع بالكيفية المبلّغ عنها.",
        "legalOpinion": "استناداً للمادة (63/2/ب) من نظام المرور بشأن جريمة افتعال حادث مروري (السجن حتى سنتين وغرامة حتى 100 ألف ريال)، يوصى برفض التغطية المرورية وإحالة الأطراف للنيابة العامة بتهمة افتعال حادث والاحتيال.",
    },
    {
        "id": "art_64_illegal_repair",
        "code": "المادة (64 - إصلاح بدون تصريح)",
        "label": "🚨 المادة (64) - إصلاح الجسم الخارجي للمركبة بعد الحادث دون تصريح رسمي لإخفاء الآثار",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "مباشرة إصلاح تلفيات الحادث وتعديل هيكل المركبة دون إذن رسمي لطمس الأدلة.",
        "technicalDraft": "تبين قيام مالك المركبة / الورشة بمباشرة أعمال السمكرة والإصلاح للجسم الخارجي للمركبة المتضررة من الحادث دون الحصول على إذن إصلاح نظامي، وذلك بقصد طمس معالم الاصطدام.",
        "legalOpinion": "تطبيق العقوبات المنصوص عليها في المادة (64) من نظام المرور بحق المتسبب والورشة المخالفة، وإحالة الواقعة للتحقيق.",
    },
    {
        "id": "art_68_6_1_intoxication",
        "code": "المادة (68/6/1 - مسكر أو مخدر)",
        "label": "🚨 المادة (68/6/1) - قيادة المركبة تحت تأثير مسكر أو مخدر أو عقاقير محظورة وقت الحادث",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "وجود قائد المركبة في حالة غير طبيعية (تحت تأثير مسكر أو مخدر) وقت وقوع الحادث.",
        "technicalDraft": "لوحظ عند مباشرة الحادث أن قائد المركبة في حالة غير طبيعية (عدم اتزان، تلعثم، انبعاث رائحة مشتبه بها / العثور على مواد محظورة)، مما أدى لفقدانه الإدراك والسيطرة على المركبة ووقوع الحادث.",
        "legalOpinion": "ضبط السائق وتحرير محضر استدلال فوري وإحالته للشرطة والنيابة العامة لتطبيق المادة (68 - جدول المخالفات 6/1) من نظام المرور، وتعد الواقعة من الجرائم الكبيرة الموجبة للتوقيف وفق المادة (112) من نظام الإجراءات الجزائية.",
    },
    {
        "id": "art_68_7_1_plates",
        "code": "المادة (68/7/1 - طمس لوحات)",
        "label": "🚨 المادة (68/7/1) - قيادة مركبة بدون لوحات أو بلوحات غير عائدة لها أو مطموسة المعالم عمداً",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "قيادة المركبة المشتركة في الحادث بلوحات مطموسة / مزورة أو بدون لوحات.",
        "technicalDraft": "تبين من معاينة المركبة وقت الحادث تعمد سائقها إزالة اللوحات المعدنية / طمس أرقامها أو تركيب لوحات لا تعود للمركبة، في قرينة تدل على القصد الجنائي والتهرب من الرصد الأمني.",
        "legalOpinion": "التحفظ على المركبة والسائق وإحالة الملف للشرطة والنيابة العامة لتطبيق المادة (68/7/1) والتحقيق في الشبهة الجنائية المرتبطة بطمس أو تزوير اللوحات.",
    },
    {
        "id": "art_69_drifting",
        "code": "المادة (69 - تفحيط)",
        "label": "🚨 المادة (69) - وقوع حادث مروري ناتج عن ممارسة التفحيط أو الاستعراض المتهور بالمركبة",
        "category": "الحوادث شبه الجنائية والجنائية (إحالة للشرطة/النيابة)",
        "isQuasiCriminal": True,
        "resultPoint": "وقوع الحادث نتيجة ممارسة التفحيط والقيادة الاستعراضية الخطرة.",
        "technicalDraft": "تدل آثار احتكاك الإطارات العرضية الدائرية على سطح الأسفلت وشهادة الشهود على قيام السائق بممارسة التفحيط والاستعراض المتهور، مما أدى لانزلاق المركبة وخروجها عن السيطرة ووقوع الاصطدام.",
        "legalOpinion": "تطبيق العقوبات المشددة المنصوص عليها في المادة (69) من نظام المرور وحجز المركبة وإحالة السائق للنيابة العامة لتوافر ركن التعدي الجسيم.",
    },
]
TRAFFIC_LAW_BY_ID = {article["id"]: article for article in TRAFFIC_LAW_ARTICLES}

def generate_accident_report_fields(selected_article_ids):
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
    results_text = "\n".join(
        f"{index}- {article['resultPoint']} ({_official_article_cite(article['code'])})."
        for index, article in enumerate(selected_articles, start=1)
    )
    technical_draft_text = " كما تبين من المعاينة الفنية أنه ".join(
        article["technicalDraft"] for article in selected_articles
    )
    opinion_lines = "\n".join(f"• {article['legalOpinion']}" for article in selected_articles)
    if has_criminal_suspicion:
        criminal_codes = "، ".join(
            _official_article_cite(article["code"]) for article in selected_articles if article["isQuasiCriminal"]
        )
        legal_opinion_text = (
            "⚠️ تنبيه نظامي (شبهة جنائية / مخالفة جسيمة):\n"
            f"استناداً إلى {criminal_codes} من نظام المرور ولائحته التنفيذية، وبناءً على القرائن الفنية الموثقة أعلاه:\n"
            f"{opinion_lines}\n"
            "وعليه يوصى باستكمال محضر الاستدلال النظامي وإحالة كامل ملف القضية والأطراف إلى (الشرطة المختصة / النيابة العامة) لإعمال شؤونها النظامية."
        )
    else:
        all_codes = "، ".join(_official_article_cite(article["code"]) for article in selected_articles)
        legal_opinion_text = (
            f"بناءً على المعاينة الفنية وتطبيق قواعد المساءلة المرورية واستناداً إلى ({all_codes}) من نظام المرور ولائحته التنفيذية:\n"
            f"{opinion_lines}"
        )
    return {
        "resultsText": results_text,
        "technicalDraftText": technical_draft_text,
        "legalOpinionText": legal_opinion_text,
        "hasCriminalSuspicion": has_criminal_suspicion,
    }

if st.session_state.active_tab == MAIN_TAB_OPTIONS[2]:
    st.subheader("📚 محرك المواد النظامية وفروعها")
    if st.session_state.get("acc_how_override"):
        kept_override = _extract_marked_block(st.session_state.get("technical_description", ""))
        st.session_state.technical_description = _upsert_marked_block(
            st.session_state.pop("acc_how_override"),
            kept_override,
        )
    valid_article_ids = [article["id"] for article in TRAFFIC_LAW_ARTICLES]
    stored_articles = st.session_state.get("selected_articles")
    if not isinstance(stored_articles, list):
        stored_articles = []
    st.session_state.selected_articles = [article_id for article_id in stored_articles if article_id in TRAFFIC_LAW_BY_ID]
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
    selection_signature = tuple(selected_law_ids)
    previous_signature = st.session_state.get("law_selection_sig")
    if previous_signature != selection_signature and not (previous_signature is None and not selected_law_ids):
        st.session_state.law_selection_sig = selection_signature
        kept_results = _extract_marked_block(st.session_state.get("accident_results", ""))
        kept_tech = _extract_marked_block(st.session_state.get("technical_description", ""))
        st.session_state.accident_results = _upsert_marked_block(generated_fields["resultsText"], kept_results)
        st.session_state.technical_description = _upsert_marked_block(generated_fields["technicalDraftText"], kept_tech)
        kept_legal = _extract_marked_block(st.session_state.get("p1_reasons", st.session_state.get("legal_opinion", "")))
        merged_opinion = _upsert_marked_block(generated_fields["legalOpinionText"], kept_legal)
        st.session_state.p1_reasons = merged_opinion
        st.session_state.legal_opinion = merged_opinion
    if generated_fields["hasCriminalSuspicion"]:
        st.warning("تشمل المواد المختارة شقاً جنائياً أو شبه جنائي، وتُحال إلى الشرطة أو النيابة.")
    render_video_evidence_engine()
    acc_results = st.text_area(
        "نتائج الحادث (نقاط مرقمة)",
        key="accident_results",
        height=110
    )
    acc_how = st.text_area(
        "كيفية وقوع الحادث (الصياغة الفنية الدقيقة)",
        key="technical_description",
        height=140
    )
    if "p1_title_input" not in st.session_state:
        st.session_state.p1_title_input = DEFAULT_REPORT_STATE["p1_title_input"]
    if "p2_custom_title" not in st.session_state:
        st.session_state.p2_custom_title = DEFAULT_REPORT_STATE["p2_custom_title"]
    if "p1_reasons" not in st.session_state:
        st.session_state.p1_reasons = DEFAULT_REPORT_STATE["p1_reasons"]
    if "p2_reasons" not in st.session_state:
        st.session_state.p2_reasons = DEFAULT_REPORT_STATE["p2_reasons"]
    if not isinstance(st.session_state.get("custom_p1_ratio"), int):
        try:
            st.session_state.custom_p1_ratio = int(st.session_state.get("custom_p1_ratio") or 75)
        except (TypeError, ValueError):
            st.session_state.custom_p1_ratio = 75
    st.markdown("### ⚖️ الرأي وتوزيع نسب المسؤولية")
    _liability_party_rows = _party_rows_for_liability(st.session_state.get("parties") or [])
    _license_violation_parties = _unqualified_driver_parties(st.session_state.get("parties") or [])
    # استبعاد الراكب/المشاة من قوائم توزيع المسؤولية ومخالفات رخصة القيادة
    if _liability_party_rows:
        _liab_labels = [
            f"{(p.get('الطرف') or 'طرف')} — {(p.get('الاسم') or 'بدون اسم')} | {(p.get('التأهيل') or '')}"
            for p in _liability_party_rows
        ]
        st.caption("أطراف توزيع المسؤولية (السائقون فقط — الراكب/المشاة مستبعدون): " + " · ".join(_liab_labels))
    if _license_violation_parties:
        _lic_labels = [
            f"{(p.get('الطرف') or 'طرف')} — {(p.get('الاسم') or 'سائق')}"
            for p in _license_violation_parties
        ]
        st.info("مخالفات رخصة القيادة المحتملة (سائق غير مؤهل فقط): " + " · ".join(_lic_labels))
        # لا تُقترح مادة الرخصة على راكب/مشاة
        if "art_32_1" not in (st.session_state.get("selected_articles") or []):
            st.caption("يمكن إدراج المادة (32/1) يدوياً للسائق غير المؤهل عند الحاجة.")
    ratio_options = [
        "100% الطرف الأول | 0% الطرف الثاني",
        "75% الطرف الأول | 25% الطرف الثاني",
        "50% الطرف الأول | 50% الطرف الثاني",
        "25% الطرف الأول | 75% الطرف الثاني",
        "0% الطرف الأول | 100% الطرف الثاني",
        "نسبة مخصصة",
    ]
    if st.session_state.get("liability_ratio_select") not in ratio_options:
        st.session_state.liability_ratio_select = ratio_options[0]
    selected_ratio = st.selectbox(
        "توزيع نسبة الخطأ والمسؤولية:",
        options=ratio_options,
        key="liability_ratio_select"
    )
    ratio_lookup = {
        "100% الطرف الأول | 0% الطرف الثاني": (100, 0),
        "75% الطرف الأول | 25% الطرف الثاني": (75, 25),
        "50% الطرف الأول | 50% الطرف الثاني": (50, 50),
        "25% الطرف الأول | 75% الطرف الثاني": (25, 75),
        "0% الطرف الأول | 100% الطرف الثاني": (0, 100),
    }
    if selected_ratio == "نسبة مخصصة":
        c_r1, c_r2 = st.columns(2)
        with c_r1:
            p1_ratio = st.number_input(
                "نسبة إدانة الطرف الأول (%)",
                min_value=0,
                max_value=100,
                step=5,
                key="custom_p1_ratio"
            )
        with c_r2:
            p2_ratio = 100 - int(p1_ratio)
            st.info(f"نسبة إدانة الطرف الثاني التلقائية: **{p2_ratio}%**")
    else:
        p1_ratio, p2_ratio = ratio_lookup[selected_ratio]
    p1_ratio = int(p1_ratio)
    p2_ratio = int(p2_ratio)
    c_t1, c_t2 = st.columns(2)
    with c_t1:
        p1_title = st.text_input(
            "صفة الطرف الأول في التقرير:",
            key="p1_title_input"
        )
    with c_t2:
        p2_role_options = [
            "قائد المركبة الثانية (الطرف الثاني)",
            "عابر الطريق (المشاة)",
            "قائد الدراجة النارية / الهوائية",
            "تحديد صفة مخصصة",
        ]
        if st.session_state.get("p2_role_select") not in p2_role_options:
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
    if p1_ratio > 0:
        p1_reasons = st.text_area(
            f"المواد النظامية وأسباب إدانة {p1_title} ({p1_ratio}%) — (كل سبب في سطر جديد):",
            height=110,
            key="p1_reasons"
        )
    else:
        p1_reasons = st.session_state.get("p1_reasons", "")
    if p2_ratio > 0:
        p2_reasons = st.text_area(
            f"المواد النظامية وأسباب إدانة {p2_title} ({p2_ratio}%) — (كل سبب في سطر جديد):",
            height=110,
            key="p2_reasons"
        )
    else:
        p2_reasons = st.session_state.get("p2_reasons", "")
    liability_html = build_liability_section_html(
        p1_title=p1_title,
        p1_ratio=p1_ratio,
        p1_reasons=p1_reasons,
        p2_title=p2_title,
        p2_ratio=p2_ratio,
        p2_reasons=p2_reasons,
    )
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
}

def sync_selected_actions():
    selected_keys = [
        key for key in st.session_state.get("selected_actions_multi", [])
        if key in ACTIONS_SCENARIOS
    ]
    if not selected_keys:
        st.session_state["actions_taken_editor"] = ""
        return
    lines = [f"{idx}- {ACTIONS_SCENARIOS[key]}" for idx, key in enumerate(selected_keys, start=1)]
    st.session_state["actions_taken_editor"] = "\n".join(lines)

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
    st.session_state.accident_nature = accident_nature_val
    st.session_state.rights_status = rights_status_val
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
    accident_nature = accident_nature_val
    rights_status = rights_status_val
    participating_agency = ""
    escaped_vehicles = ""
    shots_fired = ""
    contraband_found = ""
    if "جنائي" in (accident_nature_val or ""):
        st.markdown("#### 🚨 تفاصيل الشق الجنائي والأمني")
        col1, col2 = st.columns(2)
        with col1:
            participating_agency = st.text_input(
                "الجهة الأمنية المباشرة (مثل: الأفواج الأمنية / الدوريات):",
                placeholder="مثال: سرية المهام - الفوج الأول",
            )
            escaped_vehicles = st.text_input("بيانات المركبات الهاربة أو المعترضة (إن وجدت):")
        with col2:
            shots_fired = st.selectbox(
                "هل تم إطلاق نار أثناء المطاردة؟",
                ["لا", "نعم - طلقات تحذيرية فقط", "نعم - طلقات تحذيرية ومباشرة لإعطاب المركبة"],
            )
            contraband_found = st.selectbox(
                "نتيجة تفتيش المركبة:",
                ["لم يتم العثور على ممنوعات", "تم العثور على ممنوعات (يرفق بمحضر الضبط)"],
            )
_SKETCH_ATTACH_LABEL = "✅ إرفاق صفحة الكروكي"
_SKETCH_OMIT_LABEL = "❌ حذف صفحة الكروكي - حادث قديم"

def _on_sketch_choice_tab4():
    st.session_state.include_sketch = st.session_state.get("include_sketch_choice_tab4") == _SKETCH_ATTACH_LABEL

def _on_sketch_choice_tab5():
    st.session_state.include_sketch = st.session_state.get("include_sketch_choice_tab5") == _SKETCH_ATTACH_LABEL

def _sketch_availability_control(widget_key, on_change):
    if not isinstance(st.session_state.get("include_sketch"), bool):
        st.session_state.include_sketch = True
    selected = _SKETCH_ATTACH_LABEL if st.session_state.include_sketch else _SKETCH_OMIT_LABEL
    if st.session_state.get(widget_key) != selected:
        st.session_state[widget_key] = selected
    st.radio(
        "حالة الرسم الكروكي في التقرير",
        (_SKETCH_ATTACH_LABEL, _SKETCH_OMIT_LABEL),
        key=widget_key,
        on_change=on_change,
        horizontal=True,
    )
    st.session_state.include_sketch = st.session_state.get(widget_key) == _SKETCH_ATTACH_LABEL

SKETCH_DATA_URL_KEY = "sketch_data_url"
SKETCH_URI_PATH = SAVED_IMAGES_DIR / "adopted_sketch_uri.txt"
AERIAL_DATA_URL_KEY = "aerial_sketch_data_url"
AERIAL_URI_PATH = SAVED_IMAGES_DIR / "adopted_aerial_uri.txt"
AERIAL_STATE_PATH = SAVED_IMAGES_DIR / "adopted_aerial_state.json"

def _remember_sketch_data_url(data_uri: str, state_key: str = SKETCH_DATA_URL_KEY):
    st.session_state[state_key] = data_uri
    try:
        SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        SKETCH_URI_PATH.write_text(data_uri, encoding="utf-8")
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
            if restored_image and "include_aerial" in meta:
                st.session_state["include_aerial"] = bool(meta.get("include_aerial"))
    if current.startswith("data:image/") and st.session_state.get("include_aerial") is None:
        st.session_state["include_aerial"] = True

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

# استرجاع الجوي عند كل تشغيل بعد تعريف الدوال (لا autosave للحقول النصية)
try:
    _load_remembered_aerial()
except Exception:
    pass

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

def _sync_report_media_mode_from_flags():
    include_sketch = bool(st.session_state.get("include_sketch", True))
    include_aerial = bool(st.session_state.get("include_aerial", True))
    mode = st.session_state.get("report_media_mode")
    if mode not in ("كلاهما", "كروكي فقط", "جوي فقط"):
        if include_sketch and include_aerial:
            mode = "كلاهما"
        elif include_aerial and not include_sketch:
            mode = "جوي فقط"
        else:
            mode = "كروكي فقط"
        st.session_state["report_media_mode"] = mode
    return mode

def _apply_report_media_mode(mode: str):
    if mode == "كروكي فقط":
        st.session_state["include_sketch"] = True
        st.session_state["include_aerial"] = False
    elif mode == "جوي فقط":
        st.session_state["include_sketch"] = False
        st.session_state["include_aerial"] = True
    else:
        mode = "كلاهما"
        st.session_state["include_sketch"] = True
        st.session_state["include_aerial"] = True
    st.session_state["report_media_mode"] = mode

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
            if st.session_state.get("report_media_mode") == "كروكي فقط":
                _apply_report_media_mode("كلاهما")
            else:
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
        _sync_report_media_mode_from_flags()
        media_choice = st.radio(
            "محتوى التقرير المعتمد",
            options=["كلاهما", "كروكي فقط", "جوي فقط"],
            horizontal=True,
            key="report_media_mode",
        )
        _apply_report_media_mode(media_choice)
    with col_layout:
        st.radio(
            "نمط عرض التخطيط",
            options=[_LAYOUT_DUAL, _LAYOUT_SKETCH, _LAYOUT_SAT],
            horizontal=True,
            key="_studio_layout_mode",
        )
        st.session_state["studio_layout_mode"] = st.session_state.get("_studio_layout_mode")
    with col_place:
        aerial_place_choice = st.radio(
            "موضع لقطة التصوير الجوي",
            ["أسفل الكروكي", "بجانب الكروكي"],
            horizontal=True,
            key="aerial_place_choice",
        )
        st.session_state["aerial_place"] = "beside" if str(aerial_place_choice).startswith("بجانب") else "below"
    render_interactive_asphalt_studio(
        sketch_image_state_key="sketch_data_url",
        location_state_key="p1_acc_location",
    )
    if "sketch_road_name" not in st.session_state:
        st.session_state["sketch_road_name"] = str(st.session_state.get("p1_acc_location") or "")
    road_name_sign = st.text_input("اسم الطريق الرئيسي", key="sketch_road_name")
    render_compact_sketch_legends(key_prefix="legend_key_")
    legend_keys = [str(st.session_state.get(f"legend_key_{index}") or "") for index in range(1, 11)]

def convert_gallery_image(uploaded_file):
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source:
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGB")
            image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=82)
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
    _max_accident_photos = 10
    if "gallery_photos" not in st.session_state:
        st.session_state.gallery_photos = list(st.session_state.get("accident_photos_data") or [])
    if "uploaded_ids" not in st.session_state:
        st.session_state.uploaded_ids = set(st.session_state.get("processed_file_keys") or set())
        for entry in st.session_state.gallery_photos:
            if entry.get("id"):
                st.session_state.uploaded_ids.add(entry["id"])
    gallery_uploads = st.file_uploader(
        "📸 اضغط هنا لاختيار صور الحادث من معرض الجوال (حتى 10 صور)",
        type=None,
        accept_multiple_files=True,
        key="mobile_gallery_uploader",
    )
    st.components.v1.html(
        """
<script>
(function () {
  var MAX = 10;
  var EDGE = 1200;
  var QUALITY = 0.78;
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
            number = len(gallery_photos) + 1
            gallery_photos.append({
                "id": uid,
                "b64": image_b64,
                "caption": "",
            })
            uploaded_ids.add(uid)
    st.session_state.gallery_photos = gallery_photos
    st.session_state.uploaded_ids = uploaded_ids
    if photo_limit_hit:
        st.warning("تم الوصول للحد الأقصى (10 صور).")
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
    # قيم آمنة عند عدم رسم التبويب النشط في هذا التشغيل
    try:
        _party_columns
    except NameError:
        _party_columns = list(_PARTY_TABLE_COLUMNS)
    try:
        _vehicle_columns
    except NameError:
        _vehicle_columns = list(_VEHICLE_TABLE_COLUMNS)
    try:
        parties_df
    except NameError:
        parties_df = pd.DataFrame(st.session_state.get("parties") or [])
    try:
        vehicles_df
    except NameError:
        vehicles_df = pd.DataFrame(st.session_state.get("vehicles") or [])
    try:
        acc_num
    except NameError:
        acc_num = st.session_state.get("p1_acc_number", "")
    try:
        acc_date
    except NameError:
        acc_date = st.session_state.get("hijri_date") or st.session_state.get("p1_acc_date", "")
    try:
        acc_time
    except NameError:
        acc_time = st.session_state.get("p1_acc_time", "")
    try:
        acc_loc
    except NameError:
        acc_loc = st.session_state.get("p1_acc_location", "")
    try:
        acc_type
    except NameError:
        acc_type = st.session_state.get("p1_acc_type_choice") or st.session_state.get("p1_acc_type", "")
    try:
        acc_injuries
    except NameError:
        acc_injuries = st.session_state.get("p1_acc_injuries", 0)
    try:
        acc_deaths
    except NameError:
        acc_deaths = st.session_state.get("p1_acc_deaths", 0)
    try:
        acc_weather
    except NameError:
        acc_weather = st.session_state.get("p1_acc_weather_choice") or st.session_state.get("p1_acc_weather", "")
    try:
        acc_cause
    except NameError:
        acc_cause = st.session_state.get("p1_acc_cause", "")
    try:
        acc_results
    except NameError:
        acc_results = st.session_state.get("accident_results", "")
    try:
        acc_how
    except NameError:
        acc_how = st.session_state.get("technical_description", "")
    try:
        accident_nature_val
    except NameError:
        accident_nature_val = st.session_state.get("accident_nature") or st.session_state.get("acc_nature_sel", "")
    try:
        rights_status_val
    except NameError:
        rights_status_val = st.session_state.get("rights_status") or st.session_state.get("rights_sel", "")
    try:
        participating_agency
    except NameError:
        participating_agency = ""
    try:
        escaped_vehicles
    except NameError:
        escaped_vehicles = ""
    try:
        shots_fired
    except NameError:
        shots_fired = ""
    try:
        contraband_found
    except NameError:
        contraband_found = ""
    try:
        road_name_sign
    except NameError:
        road_name_sign = st.session_state.get("sketch_road_name", "")
    try:
        legend_keys
    except NameError:
        legend_keys = [str(st.session_state.get(f"legend_key_{index}") or "") for index in range(1, 11)]
    try:
        final_actions_html
    except NameError:
        _actions_raw = str(st.session_state.get("actions_taken_editor") or "")
        final_actions_html = "<br>".join(html.escape(line.strip()) for line in _actions_raw.splitlines() if line.strip())
    
    parties_head = "".join(f"<th>{label}</th>" for _key, label in _party_columns)
    vehicles_head = "".join(f"<th>{label}</th>" for _key, label in _vehicle_columns)
    if not isinstance(parties_df, pd.DataFrame):
        parties_df = pd.DataFrame(st.session_state.get("parties") or [])
    if not isinstance(vehicles_df, pd.DataFrame):
        vehicles_df = pd.DataFrame(st.session_state.get("vehicles") or [])
    # تنظيف None/NaN قبل الطباعة
    if not parties_df.empty:
        _a4_parties, _ = _normalize_party_qualification_rows(_frame_records(parties_df))
        parties_df = pd.DataFrame(_a4_parties)
    parties_rows = ""
    for _, row in parties_df.iterrows():
        cells = []
        role_val = _page1_cell(row.get("المشاركة", ""))
        for key, _label in _party_columns:
            if key == "التأهيل":
                cells.append(f"<td style=\"text-align:center; vertical-align:middle;\">{_party_qualification_cell_html(role_val, row.get(key, ''))}</td>")
            else:
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
    accident_nature_val = _page1_cell(accident_nature_val)
    rights_status_val = _page1_cell(rights_status_val)
    participating_agency = _page1_cell(participating_agency)
    escaped_vehicles = _page1_cell(escaped_vehicles)
    shots_fired = _page1_cell(shots_fired)
    contraband_found = _page1_cell(contraband_found)
    road_name_sign = _page1_cell(road_name_sign)
    results_html = "<br>".join(html.escape(line) for line in acc_results.split("\n") if line.strip())
    acc_how_html = html.escape(acc_how).replace("\n", "<br>")
    criminal_details_html = ""
    if "جنائي" in (accident_nature or ""):
        criminal_details_html = f"""
            <div class="table-scroll"><table>
                <tr><th>تفاصيل الشق الجنائي والأمني</th></tr>
                <tr><td style="text-align:right;">الجهة الأمنية المباشرة: {html.escape(participating_agency)}</td></tr>
                <tr><td style="text-align:right;">بيانات المركبات الهاربة أو المعترضة: {html.escape(escaped_vehicles)}</td></tr>
                <tr><td style="text-align:right;">هل تم إطلاق نار أثناء المطاردة؟ {html.escape(shots_fired)}</td></tr>
                <tr><td style="text-align:right;">نتيجة تفتيش المركبة: {html.escape(contraband_found)}</td></tr>
            </table></div>
        """
    official_footer_html = build_official_page_footer_html(
        st.session_state.get("p1_dept_region", dept_region),
        st.session_state.get("p1_dept_branch", dept_branch),
    )
    photos_list = list(st.session_state.gallery_photos or [])
    include_sketch = (
        (st.session_state.get("include_sketch", True) is True and bool(safe_sketch_src))
        or (st.session_state.get("include_aerial", True) is True and bool(safe_aerial_src))
        or bool(safe_sketch_src or safe_aerial_src)
    )
    photos_pages_html = ""
    photos_per_page = 6
    annex_first_page = 5 if include_sketch else 4
    for page_idx in range(0, len(photos_list), photos_per_page):
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
        html, body {{ height: 100%; margin: 0; }}
        body {{
            font-family: 'Tajawal', sans-serif; background: #e5e7eb; margin: 0;
            display: flex; flex-direction: column; overflow: hidden;
        }}
        .report-viewport {{
            flex: 1 1 auto; width: 100%; max-width: none;
            overflow: auto; -webkit-overflow-scrolling: touch;
        }}
        .report-sheet {{
            width: 210mm; min-width: 210mm; max-width: 210mm; margin: 0 auto;
            transform: none;
        }}
        .report-sheet .header-Title,
        .report-sheet .section-badge {{
            font-size: 15px !important; font-weight: 700;
        }}
        .report-sheet .box-content,
        .report-sheet .header-box,
        .report-sheet .photo-meta,
        .report-sheet p,
        .report-sheet li {{
            font-size: 15px !important; font-weight: 600;
        }}
        .report-sheet th,
        .report-sheet td {{
            font-size: 14px !important; font-weight: 600;
        }}
        .report-sheet th {{ font-weight: 700; }}
        .page, .report-page, .a4-page {{
            background: white; width: 210mm; min-width: 210mm; max-width: 210mm;
            min-height: 297mm; height: auto; margin: 0 auto 8mm auto;
            padding: 6mm 11mm 5mm 11mm; box-sizing: border-box; position: relative;
            display: flex; flex-direction: column; justify-content: flex-start;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); page-break-after: always;
            transform: none;
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
            display: flex; flex-direction: column; justify-content: flex-start;
        }}
        .page-flow .section-badge {{
            margin: 4px auto;
        }}
        .page-flow th, .page-flow td {{
            padding: 4px 7px;
        }}
        .page-flow > .table-scroll,
        .page-flow > .box-content {{
            flex: 0 0 auto;
        }}
        .photo-annex {{ page-break-before: always; overflow: visible; }}
        .photo-annex .header-box {{ min-height: 88px; margin-bottom: 6px; padding-bottom: 4px; }}
        .photo-annex .header-logo img {{ height: 72px; max-width: 80px; }}
        .photo-annex .section-badge {{ margin: 4px auto 6px auto; padding: 3px 14px; }}
        .photo-grid {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; overflow: visible; }}
        .photo-card {{
            width: 48%; margin-bottom: 8px; text-align: center; overflow: visible;
            break-inside: avoid; page-break-inside: avoid;
        }}
        .photo-card img {{
            width: auto; max-width: 100%; max-height: 185px; height: auto; object-fit: contain;
            display: block; margin: 0 auto;
            border: 2px solid #1b4332; border-radius: 6px; background: #fff;
        }}
        .page-three .sign-table {{ margin-top: 8px; }}
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
            border: 1.5px solid #444; padding: 14px; font-size: 15px; font-weight: bold;
            line-height: 1.9; text-align: right; margin-bottom: 16px; min-height: 110px;
        }}
        .page-num {{ display: none !important; }}
        .official-page-footer, .official-footer, .page-footer, .footer {{
            position: relative; bottom: auto; left: auto; right: auto;
            width: 100%; margin-top: auto; padding-top: 5mm; flex-shrink: 0;
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
        .page-p3 table th {{
            padding: 8px 10px !important;
            font-size: 13px !important;
        }}
        .page-p3 table td {{
            padding: 10px 12px !important;
            font-size: 12.5px !important;
            line-height: 1.75 !important;
        }}
        .page-p3 td.actions-body {{
            min-height: 28mm !important;
            height: 28mm !important;
            line-height: 1.85 !important;
            padding: 10px 14px !important;
            vertical-align: top !important;
        }}
        .page-p3 tr.sig-row td {{
            height: 28mm !important;
            min-height: 28mm !important;
            vertical-align: top !important;
            padding-top: 8px !important;
        }}
        .page-p1 > .official-page-footer,
        .page-p3 > .official-page-footer {{
            margin-top: 0 !important;
            flex-shrink: 0 !important;
        }}
        @media screen {{
            html, body, .report-viewport {{ overflow: auto; }}
            .report-sheet, .page, .report-page, .a4-page {{
                width: 210mm !important; min-width: 210mm !important; max-width: 210mm !important;
                min-height: 297mm !important; height: auto !important;
                transform: none !important;
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
            .page.page-p1, .page.page-p3 {{
                height: 297mm !important;
                max-height: 297mm !important;
                overflow: hidden !important;
            }}
        }}
        @media screen and (max-width: 768px) {{
            .report-viewport {{ overflow: auto; width: 100%; max-width: none; }}
            .report-sheet, .page, .report-page, .a4-page {{
                width: 210mm !important; min-width: 210mm !important; max-width: 210mm !important;
                min-height: 297mm !important; height: auto !important;
                transform: none !important;
            }}
            .page-flow {{ justify-content: flex-start; }}
            .table-scroll, table, .table-scroll table {{
                table-layout: fixed; width: 100% !important; max-width: 100% !important;
            }}
            th, td {{
                white-space: normal; overflow-wrap: anywhere; word-break: break-word;
            }}
            .page.page-p1, .page.page-p3 {{
                height: 297mm !important;
                max-height: 297mm !important;
                overflow: hidden !important;
            }}
        }}
        @media print {{
            html, body {{
                width: 210mm !important; height: auto; display: block; overflow: visible;
                background: #ffffff; margin: 0 !important; padding: 0 !important;
                -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important;
            }}
            body > div:not(.bayyinah-print-bar),
            .report-viewport, .report-sheet,
            .report-wrapper, .pages-wrapper, .preview-container {{
                margin: 0 !important; padding: 0 !important; gap: 0 !important;
                border: none !important; box-shadow: none !important;
                background: transparent !important; display: block !important;
            }}
            button, .no-print, .stButton, .stDownloadButton,
            section[data-testid="stSidebar"], [data-testid="stSidebar"],
            [data-testid="stSidebarContent"], [data-testid="stSidebarHeader"],
            [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
            [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
                display: none !important;
            }}
            .report-viewport {{ overflow: visible; height: auto; width: 210mm; max-width: 210mm; }}
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
                justify-content: flex-start !important;
                page-break-after: always !important;
                break-after: page !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
                transform: none !important;
            }}
            .page:last-of-type, .a4-page:last-of-type, .report-page:last-of-type,
            .report-sheet > .report-page:last-child {{
                page-break-after: auto !important; break-after: auto !important;
            }}
            .page table, .report-page table, .a4-page table, .box-content {{
                margin-bottom: 6px !important;
            }}
            .table-scroll {{ overflow: visible; max-width: none; }}
            table, .table-scroll, .table-scroll table, .box-content, .header-box, .photo-grid {{
                width: 100% !important; max-width: 100% !important; min-width: 0 !important;
                box-sizing: border-box; border-collapse: collapse;
            }}
            table, .table-scroll table {{ border: 1px solid #000; }}
            th, td {{ border: 1px solid #000 !important; }}
            .report-sheet .header-Title,
            .report-sheet .section-badge {{
                font-size: 15px !important; font-weight: 700;
            }}
            .report-sheet .box-content,
            .report-sheet .header-box,
            .report-sheet .photo-meta,
            .report-sheet p,
            .report-sheet li {{
                font-size: 15px !important; font-weight: 600;
            }}
            .report-sheet th,
            .report-sheet td {{ font-size: 14px !important; font-weight: 600; }}
            .report-sheet th {{ font-weight: 700; }}
            .sign-table, .sign-table tr, .sign-table td {{
                page-break-inside: avoid !important;
                break-inside: avoid !important;
                page-break-after: avoid !important;
            }}
            .page-flow {{ justify-content: flex-start !important; }}
            .page-flow .section-badge {{ margin: 4px auto !important; }}
            .page-flow th, .page-flow td {{ padding: 4px 7px !important; }}
            .official-page-footer, .official-footer, .page-footer, .footer {{
                position: relative !important;
                bottom: auto !important;
                left: auto !important;
                right: auto !important;
                width: 100% !important;
                margin-top: auto !important;
                padding-top: 5mm !important;
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
            .page-p3 table th {{
                padding: 8px 10px !important;
                font-size: 13px !important;
            }}
            .page-p3 table td {{
                padding: 10px 12px !important;
                font-size: 12.5px !important;
                line-height: 1.75 !important;
            }}
            .page-p3 td.actions-body {{
                min-height: 28mm !important;
                height: 28mm !important;
                line-height: 1.85 !important;
                padding: 10px 14px !important;
                vertical-align: top !important;
            }}
            .page-p3 tr.sig-row td {{
                height: 28mm !important;
                min-height: 28mm !important;
                vertical-align: top !important;
                padding-top: 8px !important;
            }}
            .page-p1 > .official-page-footer,
            .page-p3 > .official-page-footer {{
                margin-top: 0 !important;
                flex-shrink: 0 !important;
            }}
        }}
        {page_number_css}
        {OFFICIAL_A4_HIGH_CONTRAST_CSS}
    </style>
    <script>
    function fitReportFrame() {{
      var bar = document.querySelector(".no-print");
      var sheet = document.querySelector(".report-sheet");
      var height = 16;
      if (bar) height += bar.offsetHeight;
      if (sheet) height += sheet.scrollHeight;
      else height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
      if (window.frameElement) window.frameElement.style.height = Math.ceil(height) + "px";
    }}
    window.addEventListener("load", fitReportFrame);
    window.addEventListener("resize", fitReportFrame);
    document.addEventListener("load", fitReportFrame, true);
    setTimeout(fitReportFrame, 60);
    setTimeout(fitReportFrame, 400);
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
        <div class="page report-page page-flow">
            {build_header()}
            <div class="section-badge">نتائج الحادث</div>
            <div class="box-content">نتج عن الحادث :<br>{results_html}</div>
            <div class="section-badge">كيفية وقوع الحادث</div>
            <div class="box-content">{acc_how_html}</div>
            {liability_html}
            {official_footer_html}
        </div>
        <div class="page report-page page-three page-flow page-p3">
            {build_header()}
            <div class="p3-body-flex">
                <div class="table-scroll"><table>
                    <tr><th>طبيعة وتصنيف الحادث</th></tr>
                    <tr><td>{html.escape(accident_nature_val or "")}</td></tr>
                </table></div>
                <div class="table-scroll"><table>
                    <tr><th>الحقوق الخاصة والعامة</th></tr>
                    <tr><td>{html.escape(rights_status_val or "")}</td></tr>
                </table></div>
                <div class="table-scroll"><table>
                    <tr><th>الإجراءات المتخذة</th></tr>
                    <tr><td class="actions-body">{final_actions_html}</td></tr>
                </table></div>
                {criminal_details_html}
                <div class="table-scroll"><table class="sign-table">
                    <tr><th colspan="3">معد التقرير</th></tr>
                    <tr><th>إجراءات الحوادث</th><th>مشرف الحوادث</th><th>مدير {dept_branch}</th></tr>
                    <tr><td>الاسم: {officer_1_name}</td><td>الاسم: {officer_2_name}</td><td>الاسم: {manager_name}</td></tr>
                    <tr><td>الرتبة: {officer_1_rank}</td><td>الرتبة: {officer_2_rank}</td><td>الرتبة: {manager_rank}</td></tr>
                    <tr class="sig-row"><td>{_signature_box(sig_officer)}</td><td>{_signature_box(sig_supervisor)}</td><td>{_signature_box(sig_manager)}</td></tr>
                </table></div>
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
    st.session_state["_cached_full_report_html"] = full_report_html
else:
    full_report_html = st.session_state.get("_cached_full_report_html", "")
if st.session_state.active_tab == MAIN_TAB_OPTIONS[3]:
    render_direct_print_button(
        full_report_html,
        label="🖨️ طباعة التقرير بصيغة A4 / حفظ كـ PDF",
        btn_id="tab4",
    )
    st.subheader("📄 معاينة حية للتقرير قبل الطباعة")
    st.components.v1.html(full_report_html, height=850, scrolling=False)
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

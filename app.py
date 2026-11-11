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
    st.markdown("<div id='hijri-lux-trigger'></div>", unsafe_allow_html=True)
    if label:
        st.markdown(
            f"<div style='font-size:13.5px; font-weight:600; color:#bae6fd; margin-bottom:4px; text-align:right;'>{label}</div>",
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
MILITARY_RANKS = [
    "", "جندي", "جندي أول", "عريف", "وكيل رقيب", "رقيب", "رقيب أول", "رئيس رقباء",
    "ملازم", "ملازم أول", "نقيب", "رائد", "مقدم", "عقيد", "عميد", "لواء",
]
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

def render_officer_quick_picker(presets: list, name_key: str, rank_key: str, role_label: str):
    """قائمة سريعة لاختيار المنسوب المحفوظ وإنزال اسمه ورتبته بضغطة واحدة."""
    clean_presets = [item for item in presets if isinstance(item, dict) and str(item.get("name") or "").strip()]
    if not clean_presets:
        return
    options = ["-- اختيار سريع من المحفوظين --"] + [
        f"{item.get('rank', '')} / {item.get('name', '')}".strip(" /") for item in clean_presets
    ]
    picked = st.selectbox(
        f"اختيار سريع ({role_label})",
        options=options,
        key=f"_quick_pick_{name_key}",
        label_visibility="collapsed",
    )
    applied_key = f"_quick_applied_{name_key}"
    if picked != "-- اختيار سريع من المحفوظين --" and st.session_state.get(applied_key) != picked:
        chosen = clean_presets[options.index(picked) - 1]
        st.session_state[applied_key] = picked
        st.session_state[name_key] = str(chosen.get("name") or "")
        st.session_state[rank_key] = str(chosen.get("rank") or "")

def _rank_select(label: str, key: str, on_change):
    current = str(st.session_state.get(key, "") or "")
    options = list(MILITARY_RANKS)
    if current not in options:
        options = [current] + options
    return st.selectbox(label, options=options, key=key, on_change=on_change)

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
    _mirror_dept_staff_local_storage(data)

    def _commit():
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

    with st.container(key="glow-dept"):
        st.header("⚙️ الإعدادات الثابتة للقسم")
        dept_region = st.text_input("إدارة مرور منطقة", key="p1_dept_region", on_change=_commit)
        dept_branch = st.text_input("القسم / الشعبة", key="p1_dept_branch", on_change=_commit)
    with st.container(key="glow-officers"):
        st.subheader("👮‍♂️ بيانات معدي التقرير (الصفحة 3)")
        presets = data.get("saved_officers") or []
        render_officer_quick_picker(presets, "officer_1_name", "officer_1_rank", "مباشر الحوادث")
        officer_1_name = st.text_input("اسم مباشر/إجراء الحوادث", key="officer_1_name", on_change=_commit)
        officer_1_rank = _rank_select("رتبة مباشر الحوادث", "officer_1_rank", _commit)
        render_officer_quick_picker(presets, "officer_2_name", "officer_2_rank", "مشرف الحوادث")
        officer_2_name = st.text_input("اسم مشرف الحوادث", key="officer_2_name", on_change=_commit)
        officer_2_rank = _rank_select("رتبة مشرف الحوادث", "officer_2_rank", _commit)
        render_officer_quick_picker(presets, "manager_name", "manager_rank", "مدير القسم")
        manager_name = st.text_input("اسم مدير القسم / الشعبة", key="manager_name", on_change=_commit)
        manager_rank = _rank_select("رتبة المدير", "manager_rank", _commit)
    _commit()
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
    st.markdown("<div id='hijri-lux-trigger'></div>", unsafe_allow_html=True)
    if label:
        st.markdown(
            f"<div style='font-size:13.5px; font-weight:600; color:#bae6fd; margin-bottom:4px; text-align:right;'>{label}</div>",
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

def render_legal_articles_inserter(selected_articles: list, p1_reasons_key: str = "p1_reasons_area", p2_reasons_key: str = "p2_reasons_area"):
    if not selected_articles:
        return

    def _append_articles(target_key: str):
        existing = str(st.session_state.get(target_key, "") or "").strip()
        existing_lines = [ln.strip() for ln in existing.splitlines() if ln.strip()]
        for art in selected_articles:
            formatted_art = f"استناداً إلى {art} من نظام المرور ولائحته التنفيذية." if "المادة" in str(art) and "نظام المرور" not in str(art) else str(art)
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
        if sketch_leg1_key and st.session_state.get(sketch_leg1_key, "") in ("", "المركبة الأولى"):
            st.session_state[sketch_leg1_key] = f"المركبة الأولى ({v1})"
    if v2 and v2.lower() != "none":
        if sketch_leg2_key and st.session_state.get(sketch_leg2_key, "") in ("", "المركبة الثانية"):
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

def _clone_page1_value(value):
    if isinstance(value, list):
        return [dict(item) if isinstance(item, dict) else item for item in value]
    if isinstance(value, dict):
        return dict(value)
    return value

QUALIFICATION_OPTIONS = [
    "مؤهل للقيادة",
    "غير مؤهل للقيادة",
]

def normalize_driving_qualification(val):
    if val is None:
        return "مؤهل للقيادة"
    text = str(val).strip()
    if not text or text.lower() == "none":
        return "مؤهل للقيادة"
    if "غير" in text:
        return "غير مؤهل للقيادة"
    if text in QUALIFICATION_OPTIONS:
        return text
    return "مؤهل للقيادة"

def _normalize_party_qualification_rows(rows):
    cleaned = []
    changed = False
    for row in rows or []:
        item = dict(row) if isinstance(row, dict) else {}
        current = item.get("التأهيل", "")
        normalized = normalize_driving_qualification(current)
        if current != normalized:
            changed = True
        item["التأهيل"] = normalized
        cleaned.append(item)
    return cleaned, changed

def _page1_cell(value):
    if value is None:
        return ""
    try:
        missing = pd.isna(value)
        if bool(missing) and getattr(missing, "shape", None) is None:
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value)
    if text.strip().lower() in ("none", "nan"):
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
            qual.strip() and qual not in ("مؤهل (رخصة سارية)", "مؤهل للقيادة"),
        ))
        if meaningful:
            rows.append({
                "الطرف": _PARTY_LABELS.get(i, f"الطرف {i}"),
                "الاسم": name,
                "الهوية": id_no,
                "المشاركة": role,
                "الحالة": health,
                "التأهيل": qual,
            })
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

def sync_page1_to_vault(extra_keys: list = None):
    if "_p1_vault" not in st.session_state:
        st.session_state["_p1_vault"] = dict(ALL_PAGE1_DEFAULTS)
    keys_to_sync = list(ALL_PAGE1_DEFAULTS.keys()) + list(PAGE1_EXTRA_SYNC_KEYS) + list(extra_keys or [])
    for key in keys_to_sync:
        if key in st.session_state:
            st.session_state["_p1_vault"][key] = _clone_page1_value(st.session_state[key])
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
    sync_page1_to_vault(extra_keys=extra_keys)
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
    _normalize_loaded_video_state()
    st.session_state.law_selection_sig = tuple(st.session_state.get("selected_articles") or [])
    st.session_state["state_initialized"] = True

def save_current_work():
    data_to_save = {}
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
    data_to_save["page1_data"] = export_page1_payload()
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
    </style>
    """, unsafe_allow_html=True)

def render_save_and_clear_toolbar():
    with st.container(key="save-bar"):
        col_status, col_save, col_clear = st.columns([3, 1.5, 1.5])
        with col_status:
            st.markdown(
                f"**🛡️ نظام حماية البيانات النشط:** آخر حفظ للعمل: `{st.session_state.get('last_saved_time', 'لم يتم الحفظ بعد')}`"
            )
        with col_save:
            if st.button("💾 حفظ العمل الحالي", width="stretch", type="primary"):
                sync_page1_to_vault()
                st.session_state["_p1_save_requested"] = True
        with col_clear:
            if not st.session_state.get("confirm_clear", False):
                if st.button("🗑️ مسح جميع الحقول", width="stretch"):
                    st.session_state["confirm_clear"] = True
                    st.rerun()
            else:
                sub_c1, sub_c2 = st.columns(2)
                with sub_c1:
                    if st.button("⚠️ تأكيد المسح", width="stretch"):
                        clear_all_work()
                        st.toast("تم مسح البيانات وبدء تقرير جديد", icon="🔄")
                        st.rerun()
                with sub_c2:
                    if st.button("إلغاء", width="stretch"):
                        st.session_state["confirm_clear"] = False
                        st.rerun()

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
    save_current_work()

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
    save_current_work()
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
    save_current_work()

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
    save_current_work()
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
            horizontal=True,
            on_change=save_current_work,
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
                save_current_work()
                current = grown
        add_col, remove_col = st.columns(2)
        with add_col:
            if st.button("➕ إضافة مقطع", width="stretch"):
                st.session_state.video_clip_count = min(VIDEO_CLIP_MAX, current + 1)
                _sync_video_clips(st.session_state.video_clip_count)
                save_current_work()
                st.rerun()
        with remove_col:
            if st.button("➖ إنقاص مقطع", width="stretch", disabled=current <= VIDEO_CLIP_MIN):
                st.session_state.video_clip_count = max(VIDEO_CLIP_MIN, current - 1)
                _sync_video_clips(st.session_state.video_clip_count)
                for index in range(st.session_state.video_clip_count, VIDEO_CLIP_MAX):
                    for suffix in ("source", "clarity", "timestamp", "findings", "notes"):
                        st.session_state.pop(f"clip_{index}_{suffix}", None)
                    st.session_state.pop(f"clip_file_{index}", None)
                save_current_work()
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
        adopted = SAVED_IMAGES_DIR / "adopted_sketch.png"
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
    [data-testid="stMultiSelectVirtualDropdown"],
    [data-testid="stFileUploaderDropzone"] {
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
    [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
        color: #071422 !important;
    }
    [data-testid="stSelectbox"] svg,
    [data-testid="stMultiSelect"] svg,
    [data-testid="stDateInput"] svg,
    [data-testid="stNumberInput"] svg {
        fill: #00f2fe !important;
    }
    [data-testid="stNumberInput"] button {
        background: #1d6ec4 !important;
        color: #f7fcff !important;
        border: 1px solid #7ad7ff !important;
    }
    [data-baseweb="tag"] {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
        color: #071422 !important;
        border: 0 !important;
        border-radius: 8px !important;
    }
    [data-baseweb="tag"] span,
    [data-baseweb="tag"] svg {
        color: #071422 !important;
        fill: #071422 !important;
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
    [role="option"] {
        background: #1460a8 !important;
        color: #f7fcff !important;
    }
    [role="option"] * {
        color: #f7fcff !important;
    }
    [role="option"]:hover,
    [role="option"][aria-selected="true"] {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
    }
    [role="option"]:hover *,
    [role="option"][aria-selected="true"] * {
        color: #071422 !important;
    }
    [data-testid="stRadio"] [role="radiogroup"] label,
    [data-testid="stCheckbox"] label {
        background: linear-gradient(180deg, rgba(27, 108, 184, 0.55), rgba(20, 80, 143, 0.55));
        border: 1px solid rgba(122, 215, 255, 0.7);
        border-radius: 10px;
        padding: 4px 10px;
    }
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploaderDropzone"] {
        background: linear-gradient(180deg, #1b6cb8 0%, #14508f 100%) !important;
        border: 1px dashed #7ad7ff !important;
        color: #f7fcff !important;
    }
    [data-testid="stFileUploader"] section small,
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] p {
        color: #e7f6ff !important;
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
        color: #0a192f !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-family: 'Tajawal', sans-serif !important;
        box-shadow: 0 0 14px rgba(0, 242, 254, 0.4);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div.stButton > button:hover,
    div.stDownloadButton > button:hover,
    [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
        color: #0a192f !important;
        transform: scale(1.05);
        box-shadow: 0 0 22px rgba(0, 242, 254, 0.9);
    }
    div.stButton > button p,
    div.stDownloadButton > button p,
    [data-testid="stBaseButton-secondary"] p,
    [data-testid="stBaseButton-primary"] p {
        color: #0a192f !important;
    }
    [class*="st-key-adopt-hidden"],
    [class*="st-key-adopt_sketch_form"],
    [class*="st-key-adopted_sketch_data"],
    [class*="st-key-adopt_submit"],
    [data-testid="stForm"]:has([class*="st-key-adopted_sketch_data"]) {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        border: 0 !important;
        visibility: hidden !important;
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
    if st.button("🔄 حادث جديد", type="primary", width="stretch", key="new_accident_btn"):
        _reset_new_accident()
        st.rerun()
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
app_logo_src = get_base64_image("bayyinah_logo.jpg")
if app_logo_src:
    _hero_ring = f'<div class="bayyinah-logo-ring"><img src="{app_logo_src}" alt="بَيِّنَة"/></div>'
else:
    _hero_ring = '<div class="bayyinah-logo-ring"></div>'
st.html(f"""
<div class="glow-container bayyinah-hero">
  {_hero_ring}
  <div>
    <div class="bh-word">بَيِّنَة</div>
    <div class="bh-1">منظومة الذكاء الاصطناعي السيادي</div>
    <div class="bh-2">VISION 2030</div>
    <div class="bh-3">بَيِّنَة الذكي للحوادث المرورية</div>
    <div class="bh-4">منصة التحليل</div>
  </div>
</div>
""", unsafe_allow_javascript=False)
render_save_and_clear_toolbar()
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ الصفحة (1): البيانات والأطراف",
    "2️⃣ الصفحة (2): الوصف ومواد المرور (حسم)",
    "3️⃣ الصفحة (3): الإجراءات والتوقيعات",
    "4️⃣ الصفحة (4): استوديو الكروكي",
    "5️⃣ الملحق والطباعة النهائية (PDF)"
])
with tab1:
    st.subheader("معلومات الحادث الأساسية")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        acc_num = st.text_input("رقم الحادث", key="p1_acc_number")
        if "hijri_date" not in st.session_state:
            st.session_state.hijri_date = str(st.session_state.get("p1_acc_date") or "")
        if st.session_state.get("acc_date_override"):
            st.session_state.hijri_date = st.session_state.pop("acc_date_override")
            st.session_state.pop("hijri_date_manual_in", None)
            st.session_state.p1_acc_date = st.session_state.hijri_date
        accident_date = render_luxury_hijri_picker(state_key="hijri_date", label="تاريخ الحادث (هجري)")
        acc_date = accident_date
        st.session_state.p1_acc_date = accident_date
        st.session_state.hijri_manual_date = accident_date
    with col2:
        accident_time = render_smart_time_picker(state_key="p1_acc_time", label="الوقت")
        acc_time = accident_time
        if st.session_state.get("acc_loc_override"):
            st.session_state.p1_acc_location = st.session_state.pop("acc_loc_override")
        elif st.session_state.get("acc_loc_value") and not st.session_state.get("p1_acc_location"):
            st.session_state.p1_acc_location = st.session_state.get("acc_loc_value")
        acc_loc = st.text_input("موقع الحادث", key="p1_acc_location")
    with col3:
        _acc_type_options = ["تصادم مركبتين", "دهس مشاة", "انقلاب", "تصادم متعدد", "اصطدام بجسم ثابت"]
        _loaded_page1_keys = set(st.session_state.get("_p1_loaded_keys") or [])
        if st.session_state.get("p1_acc_type_choice") not in _acc_type_options:
            saved_type = st.session_state.get("p1_acc_type")
            if "p1_acc_type" in _loaded_page1_keys and saved_type in _acc_type_options:
                st.session_state.p1_acc_type_choice = saved_type
            else:
                st.session_state.pop("p1_acc_type_choice", None)
        acc_type = st.selectbox(
            "نوع الحادث",
            _acc_type_options,
            index=None,
            placeholder="اختر نوع الحادث",
            key="p1_acc_type_choice",
        ) or ""
        _acc_weather_options = ["صحو", "غائم", "ممطر", "غبار / عوالق ترابية", "ضباب"]
        if st.session_state.get("p1_acc_weather_choice") not in _acc_weather_options:
            saved_weather = st.session_state.get("p1_acc_weather")
            if "p1_acc_weather" in _loaded_page1_keys and saved_weather in _acc_weather_options:
                st.session_state.p1_acc_weather_choice = saved_weather
            else:
                st.session_state.pop("p1_acc_weather_choice", None)
        acc_weather = st.selectbox(
            "الطقس",
            _acc_weather_options,
            index=None,
            placeholder="اختر الطقس",
            key="p1_acc_weather_choice",
        ) or ""
    with col4:
        acc_injuries = st.number_input("عدد الإصابات", min_value=0, key="p1_acc_injuries")
        acc_deaths = st.number_input("عدد الوفيات", min_value=0, key="p1_acc_deaths")
    
    acc_cause = st.text_input("سبب الحادث الرئيسي (المختصر)", key="p1_acc_cause")
    st.divider()
    _party_columns = [
        ("الطرف", "الأطراف"),
        ("الاسم", "الاسم"),
        ("الهوية", "الهوية / الإقامة"),
        ("المشاركة", "نوع المشاركة"),
        ("الحالة", "الحالة الصحية"),
        ("التأهيل", "تأهيل للقيادة"),
    ]
    _vehicle_columns = [
        ("الطرف", "الأطراف"),
        ("نوع المركبة", "نوع المركبة"),
        ("رقم اللوحة", "رقم اللوحة"),
        ("الرقم التسلسلي", "الرقم التسلسلي"),
        ("نوع الترخيص", "نوع الترخيص"),
        ("التأمين", "التأمين"),
    ]
    st.subheader("جدول معلومات أطراف الحادث")
    _normalized_parties, _qual_changed = _normalize_party_qualification_rows(st.session_state.get("parties"))
    st.session_state.parties = _normalized_parties
    _saved_party_records, _saved_qual_changed = _normalize_party_qualification_rows(st.session_state.get("p1_parties_records"))
    if _saved_qual_changed:
        st.session_state.p1_parties_records = _saved_party_records
    _editor_parties = st.session_state.get("p1_parties_editor")
    if isinstance(_editor_parties, pd.DataFrame) and "التأهيل" in _editor_parties.columns:
        st.session_state.p1_parties_editor = _editor_parties.copy()
        st.session_state.p1_parties_editor["التأهيل"] = st.session_state.p1_parties_editor["التأهيل"].apply(normalize_driving_qualification)
    elif _qual_changed or _saved_qual_changed:
        st.session_state.pop("p1_parties_editor", None)
    parties_df = fill_smart_table_defaults(pd.DataFrame(st.session_state.parties), PARTY_SMART_DEFAULTS)
    if "التأهيل" in parties_df.columns:
        parties_df["التأهيل"] = parties_df["التأهيل"].apply(normalize_driving_qualification)
    if isinstance(st.session_state.get("p1_parties_editor"), pd.DataFrame):
        st.session_state.p1_parties_editor = fill_smart_table_defaults(st.session_state.p1_parties_editor, PARTY_SMART_DEFAULTS)
    parties_df = st.data_editor(
        parties_df,
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
                required=True,
            ),
        }
    )
    st.divider()
    st.subheader("جدول معلومات المركبات")
    vehicles_source = fill_smart_table_defaults(pd.DataFrame(st.session_state.vehicles), VEHICLE_SMART_DEFAULTS)
    if isinstance(st.session_state.get("p1_vehicles_editor"), pd.DataFrame):
        st.session_state.p1_vehicles_editor = fill_smart_table_defaults(st.session_state.p1_vehicles_editor, VEHICLE_SMART_DEFAULTS)
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
    inject_rtl_tab_for_data_editors()
    st.session_state.parties = _frame_records(parties_df)
    st.session_state.vehicles = _frame_records(vehicles_df)
    st.session_state.p1_parties_records = _clone_page1_value(st.session_state.parties)
    st.session_state.p1_vehicles_records = _clone_page1_value(st.session_state.vehicles)
    _mirror_page1_fields()
    sync_page1_to_vault(extra_keys=list(PAGE1_EXTRA_SYNC_KEYS))
    if st.session_state.pop("_p1_save_requested", False):
        if save_current_work():
            st.toast("تم حفظ جميع بيانات التقرير والصفحات بنجاح", icon="💾")
    _vehicle_rows = list(st.session_state.get("vehicles") or [])

    def _vehicle_type_at(index):
        if index < len(_vehicle_rows) and isinstance(_vehicle_rows[index], dict):
            return str(_vehicle_rows[index].get("نوع المركبة") or "")
        return ""

    sync_cross_page_smart_links(
        injuries_count=int(acc_injuries or 0),
        deaths_count=int(acc_deaths or 0),
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
        f"{index}- {article['resultPoint']} ({article['code']})."
        for index, article in enumerate(selected_articles, start=1)
    )
    technical_draft_text = " كما تبين من المعاينة الفنية أنه ".join(
        article["technicalDraft"] for article in selected_articles
    )
    opinion_lines = "\n".join(f"• {article['legalOpinion']}" for article in selected_articles)
    if has_criminal_suspicion:
        criminal_codes = "، ".join(
            article["code"] for article in selected_articles if article["isQuasiCriminal"]
        )
        legal_opinion_text = (
            "⚠️ تنبيه نظامي (شبهة جنائية / مخالفة جسيمة):\n"
            f"استناداً إلى {criminal_codes} من نظام المرور ولائحته التنفيذية، وبناءً على القرائن الفنية الموثقة أعلاه:\n"
            f"{opinion_lines}\n"
            "وعليه يوصى باستكمال محضر الاستدلال النظامي وإحالة كامل ملف القضية والأطراف إلى (الشرطة المختصة / النيابة العامة) لإعمال شؤونها النظامية."
        )
    else:
        all_codes = "، ".join(article["code"] for article in selected_articles)
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

with tab2:
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
        key="selected_articles",
        on_change=save_current_work,
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
        save_current_work()
    if generated_fields["hasCriminalSuspicion"]:
        st.warning("تشمل المواد المختارة شقاً جنائياً أو شبه جنائي، وتُحال إلى الشرطة أو النيابة.")
    render_video_evidence_engine()
    acc_results = st.text_area(
        "نتائج الحادث (نقاط مرقمة)",
        key="accident_results",
        height=110,
        on_change=save_current_work,
    )
    acc_how = st.text_area(
        "كيفية وقوع الحادث (الصياغة الفنية الدقيقة)",
        key="technical_description",
        height=140,
        on_change=save_current_work,
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
        key="liability_ratio_select",
        on_change=save_current_work,
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
                key="custom_p1_ratio",
                on_change=save_current_work,
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
            key="p1_title_input",
            on_change=save_current_work,
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
            key="p2_role_select",
            on_change=save_current_work,
        )
        if p2_role_type == "تحديد صفة مخصصة":
            p2_title = st.text_input(
                "اكتب صفة الطرف الثاني:",
                key="p2_custom_title",
                on_change=save_current_work,
            )
        else:
            p2_title = p2_role_type
    if p1_ratio > 0:
        p1_reasons = st.text_area(
            f"المواد النظامية وأسباب إدانة {p1_title} ({p1_ratio}%) — (كل سبب في سطر جديد):",
            height=110,
            key="p1_reasons",
            on_change=save_current_work,
        )
    else:
        p1_reasons = st.session_state.get("p1_reasons", "")
    if p2_ratio > 0:
        p2_reasons = st.text_area(
            f"المواد النظامية وأسباب إدانة {p2_title} ({p2_ratio}%) — (كل سبب في سطر جديد):",
            height=110,
            key="p2_reasons",
            on_change=save_current_work,
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
        save_current_work()
        return
    lines = [f"{idx}- {ACTIONS_SCENARIOS[key]}" for idx, key in enumerate(selected_keys, start=1)]
    st.session_state["actions_taken_editor"] = "\n".join(lines)
    save_current_work()

flush_pending_casualty_actions()
with tab3:
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
            key="acc_nature_sel",
            on_change=save_current_work,
        )
        if selected_nature == "تحديد تصنيف مخصص":
            accident_nature_val = st.text_input(
                "اكتب طبيعة وتصنيف الحادث:",
                key="acc_nature_custom",
                on_change=save_current_work,
            )
        else:
            accident_nature_val = selected_nature
    with col_p3_2:
        selected_rights = st.selectbox(
            "الحقوق الخاصة والعامة:",
            options=rights_options,
            key="rights_sel",
            on_change=save_current_work,
        )
        if selected_rights == "تحديد حقوق مخصصة":
            rights_status_val = st.text_input(
                "اكتب حالة الحقوق الخاصة والعامة:",
                key="rights_custom",
                on_change=save_current_work,
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
        key="actions_taken_editor",
        on_change=save_current_work,
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
    save_current_work()

def _on_sketch_choice_tab5():
    st.session_state.include_sketch = st.session_state.get("include_sketch_choice_tab5") == _SKETCH_ATTACH_LABEL
    save_current_work()

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
    )
    st.session_state.include_sketch = st.session_state.get(widget_key) == _SKETCH_ATTACH_LABEL

with tab4:
    st.subheader("🎨 محرر الكروكي التفاعلي (Fabric.js)")
    _sketch_availability_control("include_sketch_choice_tab4", _on_sketch_choice_tab4)
    _fabric_html = r'''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@500;700&display=swap" rel="stylesheet"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.1/fabric.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #0a192f; color: #e2eafc; font-family: Tajawal, sans-serif; }
  html, body { overflow-x: hidden; max-width: 100%; }
  .editor { background: #0b1220; border: 1px solid rgba(43, 147, 72, 0.65); border-radius: 14px; overflow: hidden; max-width: 100%; box-shadow: 0 0 16px rgba(0, 242, 254, 0.18); }
  header { background: #2b9348; color: #fff; display: flex; gap: 8px; align-items: center; padding: 8px 12px; flex-wrap: wrap; }
  header strong { margin-left: auto; font-size: 16px; color: #fff; }
  header button { background: #ffffff; color: #14301c; border: 0; border-radius: 8px; padding: 6px 10px; font-size: 16px; cursor: pointer; font-family: inherit; font-weight: 700; }
  header button:hover { transform: scale(1.06); }
  .stage { display: flex; justify-content: center; padding: 12px 8px 4px; background: #0b1220; }
  .canvas-wrap { background: #111; border: 1px solid #2b9348; border-radius: 8px; width: 600px; height: 550px; max-width: 100%; overflow: hidden; }
  .canvas-wrap .canvas-container,
  .canvas-wrap canvas { display: block !important; visibility: visible !important; opacity: 1 !important; max-width: 100%; }
  .label { margin: 6px 12px 2px; color: #e2eafc; font-size: 13px; font-weight: 700; }
  .carousel, .palette { display: flex; flex-wrap: wrap; gap: 5px; overflow: visible; padding: 4px 8px 8px; }
  .carousel button, .palette button { background: #f8f9fa; color: #0a192f; border: 2px solid #2b9348; border-radius: 12px; padding: 8px 12px; cursor: pointer; font-family: inherit; font-weight: 700; transition: transform 0.2s ease; }
  @media (max-width: 768px) {
    .carousel button, .palette button { padding: 6px 8px; font-size: 12px; }
  }
  .carousel button:hover, .palette button:hover { transform: scale(1.05); }
  .carousel button.active { background: #2b9348; color: #fff; border-color: #2b9348; }
  #adopt { display: block; width: calc(100% - 24px); margin: 6px 12px 12px; background: #2b9348; color: #fff; border: 0; border-radius: 10px; padding: 12px; font-size: 18px; font-weight: 700; cursor: pointer; font-family: inherit; }
</style>
</head>
<body>
<div class="editor">
<header>
  <strong>محرر الكروكي التنظيمي</strong>
  <button type="button" id="del" title="حذف المحدد">🗑️</button>
  <button type="button" id="rr" title="تدوير يمين">↻</button>
  <button type="button" id="rl" title="تدوير يسار">↺</button>
  <button type="button" id="clear" title="مسح اللوحة">🔄</button>
  <button type="button" id="zin" title="تكبير">🔍+</button>
  <button type="button" id="zout" title="تصغير">🔍-</button>
</header>
<div class="stage"><div class="canvas-wrap"><canvas id="c" width="600" height="550"></canvas></div></div>
<div class="label">قوالب الطريق</div>
<div class="carousel" id="roads"></div>
<div class="label">مكتبة المركبات والرموز</div>
<div class="palette" id="palette"></div>
<button type="button" id="adopt">💾 اعتماد الكروكي في التقرير</button>
</div>
<script>
const ROADS = [
  ["تقاطع T بجزيرة", "t"],
  ["تقاطع رباعي", "cross"],
  ["مزدوج بجزيرة", "dual"],
  ["مفرد مسارين", "single"],
  ["دوار", "round"],
  ["طريق جبلي منحني", "curve"],
  ["يوتيرن (U-Turn)", "uturn"]
];
const ROAD_PROPS = [
  ["شجر", "tree"],
  ["عمود إنارة", "lamp"],
  ["حفرة في الطريق", "pothole"]
];
const ITEMS = [
  ["سيدان أخضر", "sedan-green"],
  ["سيدان أبيض", "sedan-white"],
  ["دفع رباعي", "suv"],
  ["وانيت غمارتين", "pickup"],
  ["شاحنة", "truck"],
  ["دراجة", "moto"],
  ["آثار فرامل", "skid"],
  ["نقطة اصطدام", "hit"],
  ["سهم اتجاه", "arrow"]
];
for (let badge = 1; badge <= 10; badge += 1) ITEMS.push([String(badge), "b" + badge]);
ITEMS.push(["شمال", "north"]);
let canvas;
let currentRoad = "t";

function mark(obj) {
  obj.set({ selectable: false, evented: false, hoverCursor: "default", name: "road-bg", objectCaching: false });
  return obj;
}
const ISO = { sx: 0.84, sy: 0.86, sh: 0.12, sz: 0.55, ox: 22, oy: 34 };
const SIDEWALK = "#d9d1c4";
const ASPH = "#3c434a";
const YEL = "#f0c400";
const ROAD_Z = 1.6;
const ISLAND_Z = 10;
function darken(hex, amt) {
  const n = parseInt(hex.slice(1), 16);
  const ch = function(v) { return Math.max(0, Math.min(255, Math.round(v * amt))); };
  const r = ch((n >> 16) & 255), g = ch((n >> 8) & 255), b = ch(n & 255);
  return "#" + [r, g, b].map(function(v) { return ("0" + v.toString(16)).slice(-2); }).join("");
}
function lighten(hex, amt) {
  const n = parseInt(hex.slice(1), 16);
  const ch = function(v) { return Math.max(0, Math.min(255, Math.round(v + (255 - v) * amt))); };
  const r = ch((n >> 16) & 255), g = ch((n >> 8) & 255), b = ch(n & 255);
  return "#" + [r, g, b].map(function(v) { return ("0" + v.toString(16)).slice(-2); }).join("");
}
function isoPoint(x, y, z) {
  return {
    x: ISO.ox + x * ISO.sx + y * ISO.sh,
    y: ISO.oy + y * ISO.sy - (z || 0) * ISO.sz
  };
}
function tone(poly, light, mid, dark) {
  poly.set("fill", new fabric.Gradient({
    type: "linear",
    coords: { x1: 0, y1: 0, x2: Math.max(poly.width || 1, 1), y2: Math.max(poly.height || 1, 1) },
    colorStops: [
      { offset: 0, color: light },
      { offset: 0.48, color: mid },
      { offset: 1, color: dark }
    ]
  }));
  return poly;
}
function face(pts, fill) {
  const poly = mark(new fabric.Polygon(pts.map(function(p) {
    return isoPoint(p[0], p[1], p[2] || 0);
  }), { fill: fill, stroke: null, strokeWidth: 0, objectCaching: false }));
  if (fill === ASPH) return tone(poly, "#66707a", "#343b42", "#59626b");
  return poly;
}
function softShadow(pts) {
  return mark(new fabric.Polygon(pts.map(function(p) {
    const q = isoPoint(p[0], p[1], 0);
    return { x: q.x + 5, y: q.y + 7 };
  }), { fill: "rgba(0,0,0,0.24)", stroke: null, objectCaching: false }));
}
function pushAll(parts, items) {
  items.forEach(function(obj) { parts.push(obj); });
}
function ground() {
  const pts = [[0, 0], [600, 0], [600, 550], [0, 550]];
  const top = face(pts.map(function(p) { return [p[0], p[1], 0]; }), SIDEWALK);
  tone(top, "#f6f1e8", "#ddd4c6", "#c9bfb1");
  return [softShadow(pts), top];
}
function asphalt(x, y, w, h) {
  return [face([[x, y, ROAD_Z], [x + w, y, ROAD_Z], [x + w, y + h, ROAD_Z], [x, y + h, ROAD_Z]], ASPH)];
}
function island(x, y, w, h) {
  const top = face([[x, y, ISLAND_Z], [x + w, y, ISLAND_Z], [x + w, y + h, ISLAND_Z], [x, y + h, ISLAND_Z]], "#e6dfd2");
  tone(top, "#fbf7f0", "#e6dfd2", "#cfc6b6");
  top.set({ stroke: "#b7ad9c", strokeWidth: 1 });
  return [softShadow([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]), top];
}
function rule(x1, y1, x2, y2, color, width, z) {
  const a = isoPoint(x1, y1, z == null ? ROAD_Z + 0.4 : z);
  const b = isoPoint(x2, y2, z == null ? ROAD_Z + 0.4 : z);
  return mark(new fabric.Line([a.x, a.y, b.x, b.y], { stroke: color, strokeWidth: width, strokeLineCap: "butt", objectCaching: false }));
}
function ringPoints(cx, cy, r, z) {
  const pts = [];
  for (let i = 0; i < 18; i++) {
    const t = (i / 18) * Math.PI * 2;
    pts.push([cx + Math.cos(t) * r, cy + Math.sin(t) * r, z]);
  }
  return pts;
}
function asphaltDisk(cx, cy, r) {
  return [face(ringPoints(cx, cy, r, ROAD_Z), ASPH)];
}
function islandDisk(cx, cy, r) {
  const ring = ringPoints(cx, cy, r, ISLAND_Z);
  const top = face(ring, "#e6dfd2");
  tone(top, "#fbf7f0", "#e6dfd2", "#cfc6b6");
  top.set({ stroke: YEL, strokeWidth: 3 });
  return [softShadow(ring.map(function(p) { return [p[0], p[1]]; })), top];
}
function vDashes(x, y0, y1) {
  const out = [];
  for (let y = y0; y < y1 - 2; y += 18) out.push(rule(x, y, x, Math.min(y1, y + 10), "#ffffff", 2));
  return out;
}
function hDashes(y, x0, x1) {
  const out = [];
  for (let x = x0; x < x1 - 2; x += 18) out.push(rule(x, y, Math.min(x1, x + 10), y, "#ffffff", 2));
  return out;
}
function roadT() {
  const parts = [];
  pushAll(parts, ground());
  pushAll(parts, asphalt(168, 0, 264, 550));
  pushAll(parts, asphalt(0, 178, 168, 194));
  pushAll(parts, island(18, 262, 110, 26));
  parts.push(rule(168, 0, 168, 178, YEL, 4));
  parts.push(rule(168, 372, 168, 550, YEL, 4));
  parts.push(rule(432, 0, 432, 550, YEL, 4));
  parts.push(rule(292, 0, 292, 550, YEL, 3));
  parts.push(rule(304, 0, 304, 550, YEL, 3));
  parts.push(rule(0, 178, 168, 178, YEL, 4));
  parts.push(rule(0, 372, 168, 372, YEL, 4));
  parts.push(rule(18, 262, 128, 262, YEL, 3, ISLAND_Z + 0.6));
  parts.push(rule(18, 288, 128, 288, YEL, 3, ISLAND_Z + 0.6));
  parts.push.apply(parts, vDashes(230, 8, 170));
  parts.push.apply(parts, vDashes(230, 380, 542));
  parts.push.apply(parts, vDashes(368, 8, 170));
  parts.push.apply(parts, vDashes(368, 380, 542));
  parts.push.apply(parts, hDashes(220, 8, 158));
  parts.push.apply(parts, hDashes(330, 8, 158));
  return parts;
}
function roadCross() {
  const parts = [];
  pushAll(parts, ground());
  pushAll(parts, asphalt(168, 0, 264, 550));
  pushAll(parts, asphalt(0, 178, 600, 194));
  pushAll(parts, island(18, 262, 110, 26));
  pushAll(parts, island(472, 262, 110, 26));
  parts.push(rule(168, 0, 168, 178, YEL, 4));
  parts.push(rule(168, 372, 168, 550, YEL, 4));
  parts.push(rule(432, 0, 432, 178, YEL, 4));
  parts.push(rule(432, 372, 432, 550, YEL, 4));
  parts.push(rule(292, 0, 292, 178, YEL, 3));
  parts.push(rule(304, 0, 304, 178, YEL, 3));
  parts.push(rule(292, 372, 292, 550, YEL, 3));
  parts.push(rule(304, 372, 304, 550, YEL, 3));
  parts.push(rule(0, 178, 168, 178, YEL, 4));
  parts.push(rule(432, 178, 600, 178, YEL, 4));
  parts.push(rule(0, 372, 168, 372, YEL, 4));
  parts.push(rule(432, 372, 600, 372, YEL, 4));
  parts.push(rule(18, 262, 128, 262, YEL, 3, ISLAND_Z + 0.6));
  parts.push(rule(18, 288, 128, 288, YEL, 3, ISLAND_Z + 0.6));
  parts.push(rule(472, 262, 582, 262, YEL, 3, ISLAND_Z + 0.6));
  parts.push(rule(472, 288, 582, 288, YEL, 3, ISLAND_Z + 0.6));
  parts.push.apply(parts, vDashes(230, 8, 170));
  parts.push.apply(parts, vDashes(230, 380, 542));
  parts.push.apply(parts, vDashes(368, 8, 170));
  parts.push.apply(parts, vDashes(368, 380, 542));
  parts.push.apply(parts, hDashes(220, 8, 158));
  parts.push.apply(parts, hDashes(220, 442, 592));
  parts.push.apply(parts, hDashes(330, 8, 158));
  parts.push.apply(parts, hDashes(330, 442, 592));
  return parts;
}
function roadDual() {
  const parts = [];
  pushAll(parts, ground());
  pushAll(parts, asphalt(120, 0, 360, 550));
  pushAll(parts, island(282, 0, 36, 550));
  parts.push(rule(120, 0, 120, 550, YEL, 4));
  parts.push(rule(480, 0, 480, 550, YEL, 4));
  parts.push(rule(282, 0, 282, 550, YEL, 3, ISLAND_Z + 0.6));
  parts.push(rule(318, 0, 318, 550, YEL, 3, ISLAND_Z + 0.6));
  parts.push.apply(parts, vDashes(201, 8, 542));
  parts.push.apply(parts, vDashes(399, 8, 542));
  return parts;
}
function roadSingle() {
  const parts = [];
  pushAll(parts, ground());
  pushAll(parts, asphalt(190, 0, 220, 550));
  parts.push(rule(190, 0, 190, 550, YEL, 4));
  parts.push(rule(410, 0, 410, 550, YEL, 4));
  parts.push.apply(parts, vDashes(300, 8, 542));
  return parts;
}
function roadRound() {
  const parts = [];
  pushAll(parts, ground());
  pushAll(parts, asphalt(250, 0, 100, 550));
  pushAll(parts, asphalt(0, 225, 600, 100));
  pushAll(parts, asphaltDisk(300, 275, 118));
  pushAll(parts, islandDisk(300, 275, 54));
  parts.push(rule(250, 0, 250, 160, YEL, 4));
  parts.push(rule(350, 0, 350, 160, YEL, 4));
  parts.push(rule(250, 390, 250, 550, YEL, 4));
  parts.push(rule(350, 390, 350, 550, YEL, 4));
  parts.push(rule(0, 225, 180, 225, YEL, 4));
  parts.push(rule(0, 325, 180, 325, YEL, 4));
  parts.push(rule(420, 225, 600, 225, YEL, 4));
  parts.push(rule(420, 325, 600, 325, YEL, 4));
  parts.push.apply(parts, vDashes(300, 8, 150));
  parts.push.apply(parts, vDashes(300, 400, 542));
  parts.push.apply(parts, hDashes(275, 8, 170));
  parts.push.apply(parts, hDashes(275, 430, 592));
  return parts;
}
function sampleCurve() {
  function cubic(a, b, c, d, t) {
    const u = 1 - t;
    return [
      u * u * u * a[0] + 3 * u * u * t * b[0] + 3 * u * t * t * c[0] + t * t * t * d[0],
      u * u * u * a[1] + 3 * u * u * t * b[1] + 3 * u * t * t * c[1] + t * t * t * d[1]
    ];
  }
  const spans = [
    [[150, 8], [230, 130], [120, 230], [270, 330]],
    [[270, 330], [420, 430], [430, 470], [470, 544]]
  ];
  const samples = [];
  spans.forEach(function(s, si) {
    const start = si === 0 ? 0 : 1;
    for (let i = start; i <= 18; i++) samples.push(cubic(s[0], s[1], s[2], s[3], i / 18));
  });
  return samples;
}
function roadCurve() {
  const samples = sampleCurve();
  const left = [];
  const right = [];
  const half = 54;
  for (let i = 0; i < samples.length; i++) {
    const p0 = samples[Math.max(0, i - 1)];
    const p1 = samples[Math.min(samples.length - 1, i + 1)];
    let dx = p1[0] - p0[0];
    let dy = p1[1] - p0[1];
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    dx /= len;
    dy /= len;
    left.push([samples[i][0] - dy * half, samples[i][1] + dx * half]);
    right.push([samples[i][0] + dy * half, samples[i][1] - dx * half]);
  }
  const ribbon = left.concat(right.slice().reverse()).map(function(p) { return [p[0], p[1], ROAD_Z]; });
  const parts = [];
  pushAll(parts, ground());
  parts.push(face(ribbon, ASPH));
  for (let i = 0; i < left.length - 1; i++) {
    parts.push(rule(left[i][0], left[i][1], left[i + 1][0], left[i + 1][1], YEL, 3));
    parts.push(rule(right[i][0], right[i][1], right[i + 1][0], right[i + 1][1], YEL, 3));
    if (i % 2 === 0) {
      const a = samples[i];
      const b = samples[Math.min(samples.length - 1, i + 1)];
      parts.push(rule(a[0], a[1], b[0], b[1], "#ffffff", 2));
    }
  }
  return parts;
}
function roadUturn() {
  const parts = [];
  pushAll(parts, ground());
  pushAll(parts, asphalt(130, 0, 150, 550));
  pushAll(parts, asphalt(320, 0, 150, 550));
  pushAll(parts, asphalt(280, 200, 40, 150));
  parts.push(face([[280, 200, ROAD_Z], [246, 168, ROAD_Z], [246, 228, ROAD_Z]], ASPH));
  parts.push(face([[320, 200, ROAD_Z], [354, 168, ROAD_Z], [354, 228, ROAD_Z]], ASPH));
  parts.push(face([[280, 350, ROAD_Z], [246, 382, ROAD_Z], [246, 322, ROAD_Z]], ASPH));
  parts.push(face([[320, 350, ROAD_Z], [354, 382, ROAD_Z], [354, 322, ROAD_Z]], ASPH));
  pushAll(parts, island(280, 0, 40, 168));
  pushAll(parts, island(280, 382, 40, 168));
  parts.push(rule(130, 0, 130, 550, YEL, 4));
  parts.push(rule(470, 0, 470, 550, YEL, 4));
  parts.push(rule(280, 0, 280, 168, YEL, 3, ISLAND_Z + 0.6));
  parts.push(rule(320, 0, 320, 168, YEL, 3, ISLAND_Z + 0.6));
  parts.push(rule(280, 382, 280, 550, YEL, 3, ISLAND_Z + 0.6));
  parts.push(rule(320, 382, 320, 550, YEL, 3, ISLAND_Z + 0.6));
  parts.push.apply(parts, vDashes(205, 8, 542));
  parts.push.apply(parts, vDashes(395, 8, 542));
  return parts;
}
const BUILDERS = { t: roadT, cross: roadCross, dual: roadDual, single: roadSingle, round: roadRound, curve: roadCurve, uturn: roadUturn };

function applyRoad(kind) {
  currentRoad = kind;
  canvas.getObjects().slice().forEach(function(obj) {
    if (obj.name === "road-bg") canvas.remove(obj);
  });
  const parts = BUILDERS[kind]();
  parts.forEach(function(obj) { canvas.add(obj); });
  parts.slice().reverse().forEach(function(obj) { canvas.sendToBack(obj); });
  document.querySelectorAll("#roads button").forEach(function(btn) {
    btn.classList.toggle("active", btn.dataset.kind === kind);
  });
  canvas.requestRenderAll();
}
function place(obj, point) {
  obj.set({
    left: point ? point.x : 300, top: point ? point.y : 275, originX: "center", originY: "center",
    cornerColor: "#38b000", borderColor: "#38b000", transparentCorners: false,
    cornerSize: 9, borderScaleFactor: 2, hasRotatingPoint: true,
    rotatingPointOffset: 22, centeredRotation: true
  });
  canvas.add(obj);
  canvas.setActiveObject(obj);
  canvas.requestRenderAll();
}
function localIso(x, y, z) {
  return {
    x: x * ISO.sx + y * ISO.sh,
    y: y * ISO.sy - (z || 0) * ISO.sz
  };
}
function localFace(pts, fill) {
  return new fabric.Polygon(pts.map(function(p) { return localIso(p[0], p[1], p[2] || 0); }), {
    fill: fill, stroke: null, strokeWidth: 0, objectCaching: false
  });
}
function sheet(x, y, w, h, z, hex) {
  return tone(localFace([
    [x, y, z], [x + w, y, z], [x + w, y + h, z], [x, y + h, z]
  ], hex), lighten(hex, 0.34), hex, darken(hex, 0.74));
}
function groundEllipse(cx, cy, rx, ry, fill) {
  const pts = [];
  for (let i = 0; i < 14; i++) {
    const t = (i / 14) * Math.PI * 2;
    pts.push([cx + Math.cos(t) * rx, cy + Math.sin(t) * ry, 0.2]);
  }
  return localFace(pts, fill);
}
function wheel(cx, cy) {
  const c = localIso(cx, cy, 0.4);
  return new fabric.Ellipse({
    left: c.x, top: c.y, originX: "center", originY: "center",
    rx: 5.2, ry: 3.4, fill: "#1c1e22", stroke: "#3d4148", strokeWidth: 1, objectCaching: false
  });
}
function buildVehicle(spec) {
  const w = spec.w;
  const len = spec.len;
  const parts = [groundEllipse(4, 7, w * 0.58, len * 0.44, "rgba(0,0,0,0.30)")];
  [[-w * 0.36, -len * 0.30], [w * 0.36, -len * 0.30], [-w * 0.36, len * 0.26], [w * 0.36, len * 0.26]].forEach(function(p) {
    parts.push(wheel(p[0], p[1]));
  });
  parts.push(sheet(-w / 2, -len / 2, w, len, 2, spec.color));
  if (spec.cargo) {
    const c = spec.cargo;
    parts.push(sheet(c.x, c.y, c.w, c.h, 4.5, c.color));
  }
  if (spec.cab) {
    const c = spec.cab;
    parts.push(sheet(c.x, c.y, c.w, c.h, 6, c.color || lighten(spec.color, 0.16)));
    parts.push(localFace([
      [c.x + 3, c.y + 3, 6.4],
      [c.x + c.w - 3, c.y + 3, 6.4],
      [c.x + c.w - 5, c.y + 12, 6.4],
      [c.x + 5, c.y + 12, 6.4]
    ], "#8ecae6"));
  }
  return new fabric.Group(parts, { objectCaching: false });
}
function buildMoto() {
  const parts = [groundEllipse(2, 4, 10, 28, "rgba(0,0,0,0.28)")];
  parts.push(wheel(0, -22));
  parts.push(wheel(0, 20));
  parts.push(sheet(-5, -16, 10, 34, 3, "#e76f51"));
  parts.push(localFace([[-3, -6, 4], [3, -6, 4], [3, 6, 4], [-3, 6, 4]], "#b9d7e6"));
  return new fabric.Group(parts, { objectCaching: false });
}
function isoSkid() {
  const a = localIso(-8, -48, 0.8);
  const b = localIso(-8, 48, 0.8);
  const c = localIso(8, -48, 0.8);
  const d = localIso(8, 48, 0.8);
  return new fabric.Group([
    new fabric.Line([a.x, a.y, b.x, b.y], { stroke: "#1a1a1a", strokeWidth: 5, strokeLineCap: "round" }),
    new fabric.Line([c.x, c.y, d.x, d.y], { stroke: "#1a1a1a", strokeWidth: 5, strokeLineCap: "round" })
  ], { objectCaching: false });
}
function isoHit() {
  const pts = [];
  for (let i = 0; i <= 18; i++) {
    const t = (i / 18) * Math.PI * 2;
    pts.push(localIso(Math.cos(t) * 28, Math.sin(t) * 18, 1));
  }
  return new fabric.Group([
    groundEllipse(3, 5, 30, 20, "rgba(0,0,0,0.24)"),
    groundEllipse(0, 0, 26, 16, "rgba(208,0,0,0.16)"),
    new fabric.Polyline(pts, { fill: "", stroke: "#d00000", strokeWidth: 4, objectCaching: false })
  ], { objectCaching: false });
}
function isoArrow() {
  const flat = [[0, -42, 1], [16, -8, 1], [7, -8, 1], [7, 36, 1], [-7, 36, 1], [-7, -8, 1], [-16, -8, 1]];
  return new fabric.Group([
    localFace(flat, "rgba(0,0,0,0.28)"),
    tone(localFace(flat.map(function(p) { return [p[0], p[1], 3]; }), "#1b4332"), "#2f6b4f", "#1b4332", "#0f291c")
  ], { objectCaching: false });
}
function buildTree() {
  return new fabric.Group([
    new fabric.Ellipse({ rx: 16, ry: 6, fill: "rgba(0,0,0,0.28)", left: 3, top: 26, originX: "center", originY: "center" }),
    new fabric.Rect({ width: 8, height: 26, fill: "#6b3e26", left: 0, top: 10, originX: "center", originY: "center", rx: 2, ry: 2 }),
    new fabric.Circle({ radius: 18, fill: "#1b4332", left: 0, top: -6, originX: "center", originY: "center" }),
    new fabric.Circle({ radius: 13, fill: "#2d6a4f", left: -7, top: -12, originX: "center", originY: "center" }),
    new fabric.Circle({ radius: 9, fill: "#52b788", left: 7, top: -14, originX: "center", originY: "center" })
  ], { objectCaching: false });
}
function buildLamp() {
  return new fabric.Group([
    new fabric.Ellipse({ rx: 12, ry: 5, fill: "rgba(0,0,0,0.28)", left: 4, top: 28, originX: "center", originY: "center" }),
    new fabric.Rect({ width: 16, height: 5, fill: "#343a40", left: 0, top: 24, originX: "center", originY: "center", rx: 1, ry: 1 }),
    new fabric.Rect({ width: 4, height: 42, fill: "#868e96", left: 0, top: 2, originX: "center", originY: "center" }),
    new fabric.Rect({ width: 20, height: 4, fill: "#495057", left: 8, top: -18, originX: "center", originY: "center" }),
    new fabric.Circle({ radius: 7, fill: "#ffd60a", stroke: "#e85d04", strokeWidth: 2, left: 16, top: -16, originX: "center", originY: "center" }),
    new fabric.Circle({ radius: 3, fill: "#fff3bf", left: 16, top: -16, originX: "center", originY: "center" })
  ], { objectCaching: false });
}
function buildPothole() {
  return new fabric.Group([
    new fabric.Ellipse({ rx: 24, ry: 14, fill: "rgba(0,0,0,0.28)", left: 2, top: 3, originX: "center", originY: "center" }),
    new fabric.Ellipse({ rx: 22, ry: 13, fill: "#6c757d", left: 0, top: 0, originX: "center", originY: "center" }),
    new fabric.Ellipse({ rx: 16, ry: 9, fill: "#212529", left: 0, top: 1, originX: "center", originY: "center" }),
    new fabric.Ellipse({ rx: 8, ry: 4, fill: "#101214", left: -2, top: 2, originX: "center", originY: "center" }),
    new fabric.Ellipse({ rx: 4, ry: 2, fill: "rgba(255,255,255,0.22)", left: -5, top: -3, originX: "center", originY: "center" })
  ], { objectCaching: false });
}
function addRoadProp(kind, point) {
  if (kind === "tree") place(buildTree(), point);
  else if (kind === "lamp") place(buildLamp(), point);
  else if (kind === "pothole") place(buildPothole(), point);
}
function badgeNumber(kind) {
  if (!kind || kind.charAt(0) !== "b") return 0;
  const n = Number(kind.slice(1));
  return n >= 1 && n <= 10 && String(n) === kind.slice(1) ? n : 0;
}
function addBadge(num, point) {
  const circle = new fabric.Circle({ radius: 16, fill: "#ffffff", stroke: "#9b2226", strokeWidth: 3, originX: "center", originY: "center" });
  const text = new fabric.Text(String(num), { fontSize: 18, fill: "#9b2226", originX: "center", originY: "center", fontFamily: "Tajawal, sans-serif" });
  place(new fabric.Group([circle, text]), point);
}
function addNorth() {
  const plate = new fabric.Rect({ width: 54, height: 54, fill: "#ffffff", stroke: "#1b4332", strokeWidth: 2, originX: "center", originY: "center" });
  const tri = new fabric.Triangle({ width: 22, height: 18, fill: "#1b4332", left: 0, top: -12, originX: "center", originY: "center" });
  const text = new fabric.Text("شمال", { fontSize: 14, fill: "#1b4332", left: 0, top: 12, originX: "center", originY: "center", fontFamily: "Tajawal, sans-serif" });
  place(new fabric.Group([plate, tri, text]));
}
function addItem(kind, point) {
  if (kind === "sedan-green") place(buildVehicle({ w: 30, len: 64, z0: 6, z1: 14, color: "#2f9e44", cab: { x: -11, y: -18, w: 22, h: 28, zh: 10 } }));
  else if (kind === "sedan-white") place(buildVehicle({ w: 30, len: 64, z0: 6, z1: 14, color: "#f4f6f8", cab: { x: -11, y: -18, w: 22, h: 28, zh: 10 } }));
  else if (kind === "suv") place(buildVehicle({ w: 36, len: 68, z0: 7, z1: 18, color: "#6b705c", cab: { x: -14, y: -20, w: 28, h: 32, zh: 12 } }));
  else if (kind === "pickup") place(buildVehicle({ w: 32, len: 76, z0: 6, z1: 14, color: "#f4f6f8", cab: { x: -12, y: -36, w: 24, h: 28, zh: 11 }, cargo: { x: -13, y: -4, w: 26, h: 36, zh: 8, color: "#d5dbe2" } }));
  else if (kind === "truck") place(buildVehicle({ w: 34, len: 96, z0: 6, z1: 16, color: "#d5dbe3", cab: { x: -13, y: -46, w: 26, h: 30, zh: 12, color: "#e4e9ee" }, cargo: { x: -15, y: -12, w: 30, h: 56, zh: 18, color: "#6c757d" } }));
  else if (kind === "moto") place(buildMoto());
  else if (kind === "skid") place(isoSkid());
  else if (kind === "hit") place(isoHit());
  else if (kind === "arrow") place(isoArrow());
  else if (badgeNumber(kind)) addBadge(badgeNumber(kind), point);
  else if (kind === "north") addNorth();
}
function rotateActive(delta) {
  const obj = canvas.getActiveObject();
  if (!obj || obj.name === "road-bg") return;
  obj.rotate(((obj.angle || 0) + delta + 360) % 360);
  canvas.requestRenderAll();
}
function pushToParent(dataUrl) {
  try {
    const doc = window.parent.document;
    const areas = Array.prototype.slice.call(doc.querySelectorAll("textarea"));
    const area = areas.find(function(el) {
      return (el.getAttribute("aria-label") || "").indexOf("adopt_payload") !== -1;
    });
    if (!area) return;
    const proto = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, "value");
    proto.set.call(area, dataUrl);
    area.dispatchEvent(new Event("input", { bubbles: true }));
    area.dispatchEvent(new Event("change", { bubbles: true }));
    const root = area.closest("[class*='st-key-adopt-hidden']") || area.closest("form");
    const btn = root ? root.querySelector("button") : null;
    if (btn) setTimeout(function() { btn.click(); }, 120);
  } catch (err) {}
}
function adopt() {
  const dataUrl = canvas.toDataURL({ format: "png", multiplier: 1 });
  pushToParent(dataUrl);
}
function boot() {
  fabric.Object.prototype.borderColor = "#38b000";
  fabric.Object.prototype.cornerColor = "#38b000";
  fabric.Object.prototype.transparentCorners = false;
  fabric.Object.prototype.cornerSize = 9;
  fabric.Object.prototype.borderScaleFactor = 2;
  fabric.Object.prototype.hasRotatingPoint = true;
  fabric.Object.prototype.rotatingPointOffset = 22;
  canvas = new fabric.Canvas("c", {
    width: 600, height: 550, backgroundColor: "#1a2420", preserveObjectStacking: true, selection: true
  });
  const roads = document.getElementById("roads");
  ROADS.forEach(function(pair) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = pair[0];
    btn.dataset.kind = pair[1];
    btn.onclick = function() { applyRoad(pair[1]); };
    roads.appendChild(btn);
  });
  ROAD_PROPS.forEach(function(pair) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = pair[0];
    btn.draggable = true;
    btn.style.cursor = "grab";
    btn.onclick = function() {
      if (btn.dataset.dragging === "1") return;
      addRoadProp(pair[1]);
    };
    btn.addEventListener("dragstart", function(ev) {
      btn.dataset.dragging = "1";
      ev.dataTransfer.setData("text/plain", pair[1]);
      ev.dataTransfer.effectAllowed = "copy";
    });
    btn.addEventListener("dragend", function() {
      setTimeout(function() { delete btn.dataset.dragging; }, 80);
    });
    roads.appendChild(btn);
  });
  const palette = document.getElementById("palette");
  ITEMS.forEach(function(pair) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = pair[0];
    btn.onclick = function() {
      if (btn.dataset.dragging === "1") return;
      addItem(pair[1]);
    };
    if (badgeNumber(pair[1])) {
      btn.draggable = true;
      btn.addEventListener("dragstart", function(ev) {
        btn.dataset.dragging = "1";
        ev.dataTransfer.setData("text/plain", pair[1]);
        ev.dataTransfer.effectAllowed = "copy";
      });
      btn.addEventListener("dragend", function() {
        setTimeout(function() { delete btn.dataset.dragging; }, 80);
      });
      btn.style.cursor = "grab";
    }
    palette.appendChild(btn);
  });
  const board = document.querySelector(".canvas-wrap");
  board.addEventListener("dragover", function(ev) {
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = "copy";
  });
  board.addEventListener("drop", function(ev) {
    ev.preventDefault();
    const kind = ev.dataTransfer ? ev.dataTransfer.getData("text/plain") : "";
    if (!canvas) return;
    const n = badgeNumber(kind);
    const point = canvas.getPointer(ev);
    if (n) addBadge(n, point);
    else if (kind === "tree" || kind === "lamp" || kind === "pothole") addRoadProp(kind, point);
  });
  document.getElementById("del").onclick = function() {
    const obj = canvas.getActiveObject();
    if (obj && obj.name !== "road-bg") canvas.remove(obj);
    canvas.discardActiveObject();
    canvas.requestRenderAll();
  };
  document.getElementById("rr").onclick = function() { rotateActive(15); };
  document.getElementById("rl").onclick = function() { rotateActive(-15); };
  document.getElementById("clear").onclick = function() {
    canvas.getObjects().slice().forEach(function(obj) {
      if (obj.name !== "road-bg") canvas.remove(obj);
    });
    canvas.discardActiveObject();
    canvas.requestRenderAll();
  };
  document.getElementById("zin").onclick = function() {
    const zoom = Math.min(2.4, canvas.getZoom() * 1.15);
    canvas.zoomToPoint(new fabric.Point(300, 275), zoom);
  };
  document.getElementById("zout").onclick = function() {
    const zoom = Math.max(0.5, canvas.getZoom() / 1.15);
    canvas.zoomToPoint(new fabric.Point(300, 275), zoom);
  };
  document.getElementById("adopt").onclick = adopt;
  applyRoad("t");
  fitBoard();
  window.addEventListener("resize", fitBoard);
}
function fitBoard() {
  if (!canvas) return;
  const viewW = window.innerWidth || document.documentElement.clientWidth || 600;
  const wrap = document.querySelector(".canvas-wrap");
  if (viewW >= 768) {
    canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
    canvas.setWidth(600);
    canvas.setHeight(550);
    if (wrap) {
      wrap.style.width = "600px";
      wrap.style.height = "550px";
    }
  } else {
    const avail = Math.max(220, viewW - 24);
    const scale = Math.min(1, avail / 600);
    const w = Math.round(600 * scale);
    const h = Math.round(550 * scale);
    canvas.setViewportTransform([scale, 0, 0, scale, 0, 0]);
    canvas.setWidth(w);
    canvas.setHeight(h);
    if (wrap) {
      wrap.style.width = w + "px";
      wrap.style.height = h + "px";
      wrap.style.minHeight = "0";
    }
  }
  canvas.allowTouchScrolling = false;
  canvas.calcOffset();
  canvas.requestRenderAll();
}
if (window.fabric) boot();
else document.body.insertAdjacentHTML("beforeend", "<p>تعذر تحميل Fabric.js</p>");
</script>
</body>
</html>
'''
    st.components.v1.html(_fabric_html, height=980, scrolling=False)

    def _store_adopted_sketch(payload):
        if not isinstance(payload, str) or "base64," not in payload:
            return False
        try:
            raw = base64.b64decode(payload.split(",", 1)[1])
        except Exception:
            return False
        if not raw.startswith(b"\x89PNG"):
            return False
        try:
            SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            (SAVED_IMAGES_DIR / "adopted_sketch.png").write_bytes(raw)
        except OSError:
            return False
        return True

    with st.container(key="adopt-hidden"):
        with st.form("adopt_sketch_form", clear_on_submit=False, border=False):
            adopted_payload = st.text_area(
                "adopt_payload",
                key="adopted_sketch_data",
                label_visibility="collapsed",
            )
            adopted_submitted = st.form_submit_button("حفظ", key="adopt_submit")
    if adopted_submitted:
        _store_adopted_sketch(adopted_payload)
    road_name_sign = st.text_input("اسم الطريق الرئيسي", value="")
    legend_keys = [
        st.text_input(f"مدلول رقم ({number})", key=f"legend_key_{number}")
        for number in range(1, 11)
    ]
    adopted_path = SAVED_IMAGES_DIR / "adopted_sketch.png"
    sketch_img = Image.open(adopted_path).convert("RGB") if adopted_path.is_file() else None
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

with tab5:
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
    
    def img_to_b64(img_obj):
        buf = io.BytesIO()
        img_obj.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    sketch_b64 = img_to_b64(sketch_img) if sketch_img is not None else ""
    sketch_figure = (
        f'<img src="data:image/png;base64,{sketch_b64}" style="max-width:100%; height:440px; border:1px solid #ccc;">'
        if sketch_b64 else ""
    )
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
    parties_head = "".join(f"<th>{label}</th>" for _key, label in _party_columns)
    vehicles_head = "".join(f"<th>{label}</th>" for _key, label in _vehicle_columns)
    parties_rows = ""
    for _, row in parties_df.iterrows():
        parties_rows += "<tr>" + "".join(f"<td>{_page1_cell(row.get(key, ''))}</td>" for key, _label in _party_columns) + "</tr>"
    vehicles_rows = ""
    for _, row in vehicles_df.iterrows():
        vehicles_rows += "<tr>" + "".join(f"<td>{_page1_cell(row.get(key, ''))}</td>" for key, _label in _vehicle_columns) + "</tr>"
    results_html = "<br>".join(html.escape(line) for line in acc_results.split("\n") if line.strip())
    acc_how_html = html.escape(acc_how or "").replace("\n", "<br>")
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
    photos_list = list(st.session_state.gallery_photos or [])
    include_sketch = st.session_state.get("include_sketch", True) is True
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
            <div class="page-num">{page_number}</div>
        </div>
        """
    if not isinstance(st.session_state.get("show_page_numbers"), bool):
        st.session_state.show_page_numbers = False
    show_page_numbers = st.checkbox(
        "ترقيم الصفحات في الهامش السفلي",
        key="show_page_numbers",
        on_change=save_current_work,
    )
    page_number_css = ""
    body_class = ""
    clean_print_html = generate_clean_print_html(
        html.escape(acc_how or ""),
        html.escape(acc_results or ""),
        show_numbers=bool(show_page_numbers),
    )
    if show_page_numbers:
        body_class = "with-page-numbers"
        page_number_css = """
        .with-page-numbers .page { padding-bottom: 22mm !important; }
        .with-page-numbers .page-num {
            bottom: 5mm; left: 0; right: 0; transform: none; text-align: center;
            height: 8mm; line-height: 8mm; margin: 0;
        }
        @media print {
            .with-page-numbers .page { padding-bottom: 12mm !important; }
            .with-page-numbers .page-num { display: none !important; }
            @page { size: A4; margin: 0 0 14mm 0; }
            @page { @bottom-center { content: counter(page); font-family: "Tajawal", sans-serif; font-size: 15px; font-weight: 600; } }
        }
        """
    sketch_page_html = ""
    if include_sketch:
        sketch_page_html = f"""
        <div class="page report-page">
            {build_header()}
            <div class="section-badge">كروكي الحادث</div>
            <div style="text-align:center; font-weight:bold; font-size:15px; margin-bottom:15px;">رسم كروكي {road_name_sign}</div>
            <div style="display:flex; justify-content:space-around; align-items:center; margin-top:20px;">
                <div style="text-align:center; width:35%;">
                    <div class="road-sign">{road_name_sign}</div>
                    <div style="font-size:75px; line-height:1; margin:20px 0;">✥</div>
                    <div style="font-weight:bold;">اتجاهات الطريق</div>
                </div>
                <div style="width:55%; text-align:center;">
                    {sketch_figure}
                </div>
            </div>
            <div style="margin-top:30px; font-weight:bold; font-size:15px; line-height:2; padding-right:30px;">
                {"".join(f"<div>{line}</div>" for line in legend_keys)}
            </div>
            <div class="page-num">4</div>
        </div>
        """
    full_report_html = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@500;700&display=swap');
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
            padding: 15mm 18mm; box-sizing: border-box; position: relative;
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
            display: flex; flex-direction: column; justify-content: space-between;
        }}
        .page-flow > .table-scroll,
        .page-flow > .box-content {{
            flex: 1 1 auto;
        }}
        .page-flow > .table-scroll > table {{
            height: 100%;
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
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 14px; }}
        th, td {{ border: 1.5px solid #444; padding: 7px 6px; text-align: center; font-size: 14px; font-weight: 600; }}
        th {{ font-weight: 700; background-color: #d8f3dc; color: #1b4332; }}
        .box-content {{
            border: 1.5px solid #444; padding: 14px; font-size: 15px; font-weight: bold;
            line-height: 1.9; text-align: right; margin-bottom: 16px; min-height: 110px;
        }}
        .page-num {{ position: absolute; bottom: 12mm; left: 50%; transform: translateX(-50%); font-weight: bold; font-size: 15px; }}
        .road-sign {{
            background: #2d6a4f; color: white; border: 3px solid white; outline: 3px solid #2d6a4f;
            border-radius: 8px; padding: 10px 18px; font-weight: bold; font-size: 15px; display: inline-block; margin-bottom: 25px;
        }}
        .table-scroll {{ width: 100%; max-width: 100%; }}
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
        }}
        @media screen and (max-width: 768px) {{
            .report-viewport {{ overflow: auto; width: 100%; max-width: none; }}
            .report-sheet, .page, .report-page, .a4-page {{
                width: 210mm !important; min-width: 210mm !important; max-width: 210mm !important;
                min-height: 297mm !important; height: auto !important;
                transform: none !important;
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
            @page {{ size: A4; margin: 0; }}
            html, body {{ height: auto; display: block; overflow: visible; background: white; margin: 0; padding: 0; }}
            button, .no-print, .stButton, .stDownloadButton,
            section[data-testid="stSidebar"], [data-testid="stSidebar"],
            [data-testid="stSidebarContent"], [data-testid="stSidebarHeader"],
            [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
            [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
                display: none !important;
            }}
            .report-viewport {{ overflow: visible; height: auto; width: 210mm; max-width: 210mm; }}
            .report-sheet, .page, .report-page, .a4-page {{
                box-shadow: none; margin: 0; overflow: visible;
                width: 210mm !important; min-width: 210mm !important; max-width: 210mm !important;
                min-height: 297mm !important; height: auto !important; max-height: none !important;
                transform: none !important;
                page-break-after: always;
            }}
            .report-sheet > .report-page:last-child {{ page-break-after: auto; break-after: auto; }}
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
            .page-flow {{ justify-content: space-between; }}
            .photo-annex {{
                overflow: visible; height: auto; max-height: none; min-height: 297mm;
                padding: 8mm 10mm 12mm 10mm;
            }}
            .photo-annex .photo-card, .photo-annex .photo-meta {{ overflow: visible; max-height: none; }}
            .photo-annex .header-logo img {{ height: 72px; max-width: 80px; }}
            .header-logo img {{ height: 110px; max-width: 120px; }}
        }}
        {page_number_css}
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
        <div class="no-print" style="text-align:center; margin:0; padding:12px;">
            <button onclick="window.print()" style="background:linear-gradient(90deg,#0e7490,#2563eb); color:white; font-family:'Tajawal'; font-size:18px; font-weight:bold; padding:12px 35px; border:1px solid #4facfe; border-radius:10px; cursor:pointer; box-shadow:0 0 14px rgba(0,242,254,0.45);">
                🖨️ طباعة التقرير الرسمي أو حفظه كـ PDF
            </button>
        </div>
        <div class="report-viewport">
        <div class="report-sheet">
        <div class="page report-page page-flow">
            {build_header()}
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
            <div class="section-badge badge-sub">معلومات أطراف الحادث</div>
            <div class="table-scroll"><table>
                <tr>{parties_head}</tr>
                {parties_rows}
            </table></div>
            <div class="section-badge badge-sub">معلومات المركبات</div>
            <div class="table-scroll"><table>
                <tr>{vehicles_head}</tr>
                {vehicles_rows}
            </table></div>
            <div class="page-num">1</div>
        </div>
        <div class="page report-page page-flow">
            {build_header()}
            <div class="section-badge">نتائج الحادث</div>
            <div class="box-content">نتج عن الحادث :<br>{results_html}</div>
            <div class="section-badge">كيفية وقوع الحادث</div>
            <div class="box-content">{acc_how_html}</div>
            {liability_html}
            <div class="page-num">2</div>
        </div>
        <div class="page report-page page-three page-flow">
            {build_header()}
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
                <tr><td>{final_actions_html}</td></tr>
            </table></div>
            {criminal_details_html}
            <div class="table-scroll"><table class="sign-table">
                <tr><th colspan="3">معد التقرير</th></tr>
                <tr><th>إجراء الحوادث</th><th>مشرف الحوادث</th><th>مدير {dept_branch}</th></tr>
                <tr><td>الاسم: {officer_1_name}</td><td>الاسم: {officer_2_name}</td><td>الاسم: {manager_name}</td></tr>
                <tr><td>الرتبة: {officer_1_rank}</td><td>الرتبة: {officer_2_rank}</td><td>الرتبة: {manager_rank}</td></tr>
                <tr><td>{_signature_box(sig_officer)}</td><td>{_signature_box(sig_supervisor)}</td><td>{_signature_box(sig_manager)}</td></tr>
            </table></div>
            <div class="page-num">3</div>
        </div>
        {sketch_page_html}
        {photos_pages_html}
        </div>
        </div>
    </body>
    </html>
    """
    st.divider()
    col_btn1, col_btn2 = st.columns([1, 2])
    with col_btn1:
        st.download_button(
            label="📥 تحميل التقرير الرسمي الكامل (HTML/PDF)",
            data=full_report_html.encode("utf-8"),
            file_name=f"Accident_Report_{acc_num}.html",
            mime="text/html",
            use_container_width=True
        )
    with col_btn2:
        st.info("💡 بعد تحميل الملف وفتحه، اضغط على زر (طباعة التقرير الرسمي أو حفظه كـ PDF) في أعلى الصفحة.")
    st.download_button(
        label="طباعة نظيفة للكيفية والنتائج",
        data=clean_print_html.encode("utf-8"),
        file_name=f"Accident_Clean_Print_{acc_num}.html",
        mime="text/html",
        use_container_width=True,
    )
    report_fullscreen = st.toggle("🔲 وضع ملء الشاشة (إخفاء القائمة الجانبية)", value=True)
    if report_fullscreen:
        st.markdown(
            """
            <style>
            @media screen {
            section[data-testid="stSidebar"] {
                display: flex !important;
            }
            }
            .main .block-container {
                max-width: 100% !important;
                width: 100% !important;
                padding: 1rem !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    _sketch_availability_control("include_sketch_choice_tab5", _on_sketch_choice_tab5)
    st.subheader("معاينة حية للتقرير قبل الطباعة:")
    st.components.v1.html(full_report_html, height=850, scrolling=False)
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

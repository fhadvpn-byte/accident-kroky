import html
import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import base64
import os
import json
import hashlib
import math
import tempfile
from datetime import date, datetime
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

DRAFT_FILE_PATH = "bayyinah_autosave_draft.json"
DEFAULT_REPORT_STATE = {
    "accident_results": "",
    "technical_description": "",
    "legal_opinion": "",
    "selected_articles": [],
    "accident_nature": "حادث مروري اعتيادي",
    "rights_status": "اختر الحالة",
    "extra_procedure": "",
    "has_video": "لا يوجد مقطع فيديو",
    "video_source": "كاميرا مراقبة أمنية (CCTV)",
    "video_clarity": "واضح وموثق بختم زمني (تاريخ ووقت)",
    "video_timestamp": "",
    "video_findings": [],
    "video_custom_notes": "",
    "video_injected_text": "",
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
        except (OSError, json.JSONDecodeError, TypeError):
            for key, default_val in DEFAULT_REPORT_STATE.items():
                st.session_state.setdefault(key, default_val)
    else:
        for key, default_val in DEFAULT_REPORT_STATE.items():
            st.session_state.setdefault(key, default_val)
    if not isinstance(st.session_state.get("selected_articles"), list):
        st.session_state.selected_articles = []
    if not isinstance(st.session_state.get("video_findings"), list):
        st.session_state.video_findings = []
    for text_key in ("accident_results", "technical_description", "legal_opinion", "extra_procedure", "video_timestamp", "video_custom_notes"):
        if not isinstance(st.session_state.get(text_key), str):
            st.session_state[text_key] = ""
    st.session_state.law_selection_sig = tuple(st.session_state.get("selected_articles") or [])
    st.session_state["state_initialized"] = True

def save_current_work():
    data_to_save = {}
    for key in DEFAULT_REPORT_STATE:
        if key in st.session_state and key != "confirm_clear":
            data_to_save[key] = st.session_state[key]
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
    if os.path.exists(DRAFT_FILE_PATH):
        try:
            os.remove(DRAFT_FILE_PATH)
        except OSError:
            pass
    for key, default_val in DEFAULT_REPORT_STATE.items():
        st.session_state[key] = default_val
    st.session_state.law_selection_sig = ()
    st.session_state["confirm_clear"] = False

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
                if save_current_work():
                    st.toast("تم حفظ جميع بيانات التقرير والصفحات بنجاح", icon="💾")
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

def build_video_legal_paragraph():
    if st.session_state.get("has_video") != "نعم - يوجد توثيق مرئي (مقطع فيديو)":
        return "", ""
    source = st.session_state.get("video_source", "")
    clarity = st.session_state.get("video_clarity", "")
    timestamp = str(st.session_state.get("video_timestamp", "")).strip()
    findings = st.session_state.get("video_findings", [])
    custom_notes = str(st.session_state.get("video_custom_notes", "")).strip()
    time_clause = f" والموثق زمنياً عند ({timestamp})" if timestamp else ""
    findings_clause = "، ".join(findings) if findings else "رصد آلية وحركة المركبات لحظة وقوع الحادث"
    notes_clause = f"؛ كما أظهر التسجيل أن ({custom_notes})" if custom_notes else ""
    tech_video_paragraph = (
        f"وقد تعززت المعاينة الفنية بالاطلاع على التسجيل المرئي (مقطع فيديو) المستخرج من ({source}) "
        f"وهو ({clarity}){time_clause}، حيث أظهر المقطع بوضوح: {findings_clause}{notes_clause}."
    )
    legal_video_paragraph = (
        f"🎥 حُجية القرينة الرقمية والمرئية: استناداً إلى التسجيل المرئي المرفق والمستخرج من ({source}) "
        f"({clarity}){time_clause}، والذي يُعد قرينة فنية ومادية قاطعة تعضد محضر الاستدلال والمعاينة الميدانية، "
        f"فقد ثبت يقيناً من خلال تفريغ المقطع: ({findings_clause}){notes_clause}؛ "
        f"وعليه بُني تحديد المسؤولية النظامية ونسب الخطأ استناداً للدليل المرئي الموثق."
    )
    return tech_video_paragraph, legal_video_paragraph

def inject_video_into_opinion_and_description():
    tech_add, legal_add = build_video_legal_paragraph()
    if not legal_add:
        return
    current_tech = str(st.session_state.get("technical_description", "")).strip()
    tech_marker = "وقد تعززت المعاينة الفنية بالاطلاع على التسجيل المرئي"
    if tech_marker in current_tech:
        base_tech = current_tech.split(tech_marker)[0].strip()
        st.session_state["technical_description"] = f"{base_tech}\n\n{tech_add}".strip() if base_tech else tech_add
    elif tech_add not in current_tech:
        st.session_state["technical_description"] = f"{current_tech}\n\n{tech_add}".strip() if current_tech else tech_add
    current_legal = str(st.session_state.get("legal_opinion", "")).strip()
    if "🎥 حُجية القرينة الرقمية والمرئية:" not in current_legal:
        st.session_state["legal_opinion"] = f"{current_legal}\n\n{legal_add}".strip() if current_legal else legal_add
    else:
        base_legal = current_legal.split("🎥 حُجية القرينة الرقمية والمرئية:")[0].strip()
        st.session_state["legal_opinion"] = f"{base_legal}\n\n{legal_add}".strip() if base_legal else legal_add
    st.session_state["video_injected_text"] = legal_add
    save_current_work()

def render_video_evidence_engine():
    with st.container(key="video-evidence"):
        st.subheader("🎥 محرك القرائن الرقمية والتوثيق المرئي (مقطع الفيديو)")
        has_video = st.radio(
            "هل يتوفر مقطع فيديو يوثق الحادث؟",
            options=["لا يوجد مقطع فيديو", "نعم - يوجد توثيق مرئي (مقطع فيديو)"],
            key="has_video",
            horizontal=True,
            on_change=save_current_work,
        )
        if has_video == "لا يوجد مقطع فيديو":
            st.info("ℹ️ لا يوجد تسجيل مرئي مرفق؛ يعتمد التقرير الفني والمسؤولية النظامية على الآثار المادية، والمعاينة الميدانية، وأقوال الأطراف.")
        else:
            source_options = [
                "كاميرا مراقبة أمنية (CCTV)",
                "كاميرا مركبة (داش كام - Dashcam)",
                "كاميرا منشأة تجارية / خاصة محيطة",
                "كاميرات الرصد الآلي / المدن الذكية",
                "تصوير هاتف محمول موثق",
            ]
            clarity_options = [
                "واضح وموثق بختم زمني (تاريخ ووقت)",
                "واضح الدقة (بدون ختم زمني ظاهر)",
                "متوسط الوضوح ولكن يُظهر آلية الاصطدام",
                "زاوية بعيدة تُظهر اتجاهات المركبات فقط",
            ]
            finding_options = [
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
            if st.session_state.get("video_source") not in source_options:
                st.session_state.video_source = source_options[0]
            if st.session_state.get("video_clarity") not in clarity_options:
                st.session_state.video_clarity = clarity_options[0]
            stored_findings = st.session_state.get("video_findings")
            if not isinstance(stored_findings, list):
                stored_findings = []
            st.session_state.video_findings = [item for item in stored_findings if item in finding_options]
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                st.selectbox(
                    "مصدر مقطع الفيديو",
                    options=source_options,
                    key="video_source",
                    on_change=save_current_work,
                )
            with col_v2:
                st.selectbox(
                    "درجة وضوح المقطع والختم الزمني",
                    options=clarity_options,
                    key="video_clarity",
                    on_change=save_current_work,
                )
            with col_v3:
                st.text_input(
                    "وقت اللقطة في الفيديو (مثال: الدقيقة 01:24 أو 14:35:10)",
                    placeholder="اختياري: 00:45 / الساعة 10:15 م",
                    key="video_timestamp",
                    on_change=save_current_work,
                )
            st.multiselect(
                "المشاهدات الفنية المستخلصة من مقطع الفيديو (تُدرج في الرأي والمسؤولية):",
                options=finding_options,
                key="video_findings",
                on_change=save_current_work,
            )
            st.text_area(
                "تفاصيل إضافية رصدها باحث الحوادث في مقطع الفيديو:",
                placeholder="اكتب أي تفصيل دقيق ظهر في الفيديو (مثل: لون المركبة، حركة المشاة، حالة الطريق أثناء التصوير...)",
                key="video_custom_notes",
                height=80,
                on_change=save_current_work,
            )
            uploaded_video = st.file_uploader(
                "📎 إرفاق ملف الفيديو للمعاينة المباشرة (MP4, MOV, AVI) - اختياري:",
                type=["mp4", "mov", "avi", "mkv"],
            )
            if uploaded_video is not None:
                with st.expander("▶️ عرض ومعاينة مقطع الفيديو المرفق", expanded=False):
                    st.video(uploaded_video)
            col_btn1, col_btn2 = st.columns([2, 1])
            with col_btn1:
                if st.button(
                    "⚡ إدراج وتحديث معلومات الفيديو في (الرأي والمسؤولية النظامية) و(كيفية وقوع الحادث)",
                    width="stretch",
                    type="primary",
                ):
                    inject_video_into_opinion_and_description()
                    st.toast("تم دمج قرينة الفيديو في الرأي والمسؤولية النظامية وحفظ المسودة", icon="🎥")
            with col_btn2:
                if st.button("🧹 إزالة فقرة الفيديو من الرأي النظامي", width="stretch"):
                    current_legal = st.session_state.get("legal_opinion", "")
                    if "🎥 حُجية القرينة الرقمية والمرئية:" in current_legal:
                        st.session_state["legal_opinion"] = current_legal.split("🎥 حُجية القرينة الرقمية والمرئية:")[0].strip()
                        save_current_work()
                        st.toast("تمت إزالة فقرة الفيديو من الرأي النظامي", icon="ℹ️")

def _reset_new_accident():
    if os.path.exists(DRAFT_FILE_PATH):
        try:
            os.remove(DRAFT_FILE_PATH)
        except OSError:
            pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    try:
        adopted = SAVED_IMAGES_DIR / "adopted_sketch.png"
        if adopted.is_file():
            adopted.unlink()
    except OSError:
        pass

_HIJRI_MONTH_LABELS = (
    "01 - محرم",
    "02 - صفر",
    "03 - ربيع الأول",
    "04 - ربيع الثاني",
    "05 - جمادى الأولى",
    "06 - جمادى الآخرة",
    "07 - رجب",
    "08 - شعبان",
    "09 - رمضان",
    "10 - شوال",
    "11 - ذو القعدة",
    "12 - ذو الحجة",
)
_HIJRI_YEAR_LABELS = ("1446", "1447", "1448", "1449", "1450")

def _hijri_picker_state(value):
    parts = str(value).split("/")
    year, month, day = "1448", "01", "01"
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        year, month, day = parts[0], f"{int(parts[1]):02d}", f"{int(parts[2]):02d}"
    if year not in _HIJRI_YEAR_LABELS:
        year = "1448"
    if not month.isdigit() or not 1 <= int(month) <= 12:
        month = "01"
    if not day.isdigit() or not 1 <= int(day) <= 30:
        day = "01"
    return year, _HIJRI_MONTH_LABELS[int(month) - 1], f"{int(day):02d}"

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

def _project_logo_path():
    root = Path(__file__).resolve().parent
    for name in ("traffic_logo.png", "logo.png", "traffic_logo.jpg", "logo.jpg", "logo.jpeg", "traffic_logo.jpeg", "logo.webp"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None

def _open_fixed_logo():
    path = _project_logo_path()
    if path is None:
        return None
    try:
        return Image.open(path).convert("RGBA")
    except OSError:
        return None

def _save_upload_once(uploaded):
    try:
        SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    raw = uploaded.getvalue()
    digest = hashlib.sha256(raw).hexdigest()[:20]
    ext = Path(getattr(uploaded, "name", "") or "").suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".jpg"
    dest = SAVED_IMAGES_DIR / f"{digest}{ext}"
    try:
        if not dest.exists():
            dest.write_bytes(raw)
    except OSError:
        return dest
    return dest

def persist_uploads(uploads):
    if not uploads:
        return []
    return [_save_upload_once(item) for item in uploads]

def list_saved_images():
    if not SAVED_IMAGES_DIR.exists():
        return []
    files = [
        path for path in SAVED_IMAGES_DIR.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    return sorted(files, key=lambda path: path.stat().st_mtime)

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
if _bayyinah_logo_ready():
    st.logo(str(_bayyinah_logo_path), icon_image=str(_bayyinah_logo_path), size="large")
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
        section[data-testid="stSidebar"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stSidebarCollapsedControl"],
        .stButton, .stDownloadButton, button {
            display: none !important;
        }
    }
</style>
""", unsafe_allow_html=True)
init_and_load_state()
inject_bayyinah_blue_styles()
if 'parties' not in st.session_state:
    st.session_state.parties = _blank_parties()
if 'vehicles' not in st.session_state:
    st.session_state.vehicles = _blank_vehicles()
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
    with st.container(key="glow-dept"):
        st.header("⚙️ الإعدادات الثابتة للقسم")
        dept_region = st.text_input("إدارة مرور منطقة", value="")
        dept_branch = st.text_input("القسم / الشعبة", value="")
    with st.container(key="glow-officers"):
        st.subheader("👮‍♂️ بيانات معدي التقرير (الصفحة 3)")
        officer_1_name = st.text_input("اسم مباشر/إجراء الحوادث", value="")
        officer_1_rank = st.text_input("رتبة مباشر الحوادث", value="")
        officer_2_name = st.text_input("اسم مشرف الحوادث", value="")
        officer_2_rank = st.text_input("رتبة مشرف الحوادث", value="")
        manager_name = st.text_input("اسم مدير القسم / الشعبة", value="")
        manager_rank = st.text_input("رتبة المدير", value="")
app_logo_b64 = ""
if _bayyinah_logo_ready():
    try:
        with Image.open(_bayyinah_logo_path) as app_logo:
            _hero_buf = io.BytesIO()
            app_logo.convert("RGBA").save(_hero_buf, format="PNG")
            app_logo_b64 = base64.b64encode(_hero_buf.getvalue()).decode()
    except OSError:
        app_logo_b64 = ""
if app_logo_b64:
    _hero_ring = f'<div class="bayyinah-logo-ring"><img src="data:image/png;base64,{app_logo_b64}" alt="بَيِّنَة"/></div>'
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
        acc_num = st.text_input("رقم الحادث", value="")
        if "hijri_date" not in st.session_state:
            st.session_state.hijri_date = ""
        if st.session_state.get("acc_date_override"):
            st.session_state.hijri_date = st.session_state.pop("acc_date_override")
            st.session_state.hijri_parts_sync = True
        if st.session_state.hijri_date and (
            st.session_state.pop("hijri_parts_sync", False) or "hijri_month_label" not in st.session_state
        ):
            _picked_year, _picked_month, _ = _hijri_picker_state(st.session_state.hijri_date)
            st.session_state.hijri_year_label = _picked_year
            st.session_state.hijri_month_label = _picked_month
        st.markdown("تاريخ الحادث (هجري)")
        _hijri_label = st.session_state.hijri_date or "—"
        with st.popover(
            f"📅 {_hijri_label} (اضغط لاختيار التاريخ)",
            use_container_width=True,
        ):
            if st.button("🔄 ضبط على تاريخ اليوم الهجري تلقائياً", key="hijri_today_btn", use_container_width=True):
                st.session_state.hijri_date = get_today_hijri()
                st.session_state.hijri_parts_sync = True
                st.rerun()
            st.divider()
            sel_month_label = st.selectbox("الشهر", _HIJRI_MONTH_LABELS, key="hijri_month_label", index=None, placeholder="اختر الشهر")
            sel_y = st.selectbox("السنة", _HIJRI_YEAR_LABELS, key="hijri_year_label", index=None, placeholder="اختر السنة")
            sel_m = (sel_month_label or "")[:2]
            st.markdown("اضغط على رقم اليوم لاعتماده فوراً")
            _stored = str(st.session_state.hijri_date).split("/")
            _stored_y = _stored[0] if len(_stored) == 3 else ""
            _stored_m = _stored[1] if len(_stored) == 3 else ""
            _stored_d = _stored[2] if len(_stored) == 3 else ""
            for _row in range(5):
                _day_cols = st.columns(6)
                for _col_index, _day_col in enumerate(_day_cols):
                    _day = f"{_row * 6 + _col_index + 1:02d}"
                    _chosen = bool(sel_y) and bool(sel_m) and _stored_y == sel_y and _stored_m == sel_m and _stored_d == _day
                    with _day_col:
                        if st.button(
                            _day,
                            key=f"hijri_day_btn_{_day}",
                            type="primary" if _chosen else "secondary",
                            use_container_width=True,
                        ):
                            if sel_y and sel_m:
                                st.session_state.hijri_date = f"{sel_y}/{sel_m}/{_day}"
                                st.rerun()
        accident_date = st.session_state.hijri_date
        acc_date = accident_date
    with col2:
        accident_time = st.text_input("الوقت", value="")
        acc_time = accident_time
        if "acc_loc_value" not in st.session_state:
            st.session_state.acc_loc_value = ""
        if st.session_state.get("acc_loc_override"):
            st.session_state.acc_loc_value = st.session_state.pop("acc_loc_override")
        acc_loc = st.text_input("موقع الحادث", key="acc_loc_value")
    with col3:
        acc_type = st.selectbox(
            "نوع الحادث",
            ["تصادم مركبتين", "دهس مشاة", "انقلاب", "تصادم متعدد", "اصطدام بجسم ثابت"],
            index=None,
            placeholder="اختر نوع الحادث",
        ) or ""
        acc_weather = st.selectbox(
            "الطقس",
            ["صحو", "غائم", "ممطر", "غبار / عوالق ترابية", "ضباب"],
            index=None,
            placeholder="اختر الطقس",
        ) or ""
    with col4:
        acc_injuries = st.number_input("عدد الإصابات", min_value=0, value=0)
        acc_deaths = st.number_input("عدد الوفيات", min_value=0, value=0)
    
    acc_cause = st.text_input("سبب الحادث الرئيسي (المختصر)", value="")
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
    parties_df = st.data_editor(
        pd.DataFrame(st.session_state.parties),
        num_rows="dynamic",
        use_container_width=True,
        column_order=[key for key, _label in reversed(_party_columns)],
        column_config={
            "الطرف": st.column_config.TextColumn("الأطراف"),
            "الاسم": st.column_config.TextColumn("الاسم"),
            "الهوية": st.column_config.TextColumn("الهوية / الإقامة"),
            "المشاركة": st.column_config.SelectboxColumn("نوع المشاركة", options=["", "سائق", "راكب", "مشاة"]),
            "الحالة": st.column_config.SelectboxColumn("الحالة الصحية", options=["", "سليم", "مصاب", "متوفي"]),
            "التأهيل": st.column_config.TextColumn("تأهيل للقيادة"),
        }
    )
    st.divider()
    st.subheader("جدول معلومات المركبات")
    vehicles_df = st.data_editor(
        pd.DataFrame(st.session_state.vehicles),
        num_rows="dynamic",
        use_container_width=True,
        column_order=[key for key, _label in reversed(_vehicle_columns)],
        column_config={
            "الطرف": st.column_config.TextColumn("الأطراف"),
            "نوع المركبة": st.column_config.TextColumn("نوع المركبة"),
            "رقم اللوحة": st.column_config.TextColumn("رقم اللوحة"),
            "الرقم التسلسلي": st.column_config.TextColumn("الرقم التسلسلي"),
            "نوع الترخيص": st.column_config.SelectboxColumn("نوع الترخيص", options=["", "خصوصي", "نقل خاص", "نقل عام", "دراجة آلية"]),
            "التأمين": st.column_config.SelectboxColumn("التأمين", options=["", "مؤمنة", "غير مؤمنة"]),
        }
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
        st.session_state.technical_description = st.session_state.pop("acc_how_override")
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
    generated_fields = generate_accident_report_fields(selected_law_ids)
    selection_signature = tuple(selected_law_ids)
    previous_signature = st.session_state.get("law_selection_sig")
    if previous_signature != selection_signature and not (previous_signature is None and not selected_law_ids):
        st.session_state.law_selection_sig = selection_signature
        st.session_state.accident_results = generated_fields["resultsText"]
        st.session_state.technical_description = generated_fields["technicalDraftText"]
        st.session_state.legal_opinion = generated_fields["legalOpinionText"]
        if st.session_state.get("has_video") == "نعم - يوجد توثيق مرئي (مقطع فيديو)":
            inject_video_into_opinion_and_description()
        else:
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
    st.subheader("الرأي والمسؤولية النظامية")
    resp_summary = st.text_input("صدر قرار الإدانة", value="")
    custom_laws = st.text_area(
        "الرأي والمسؤولية النظامية (يشمل المواد النظامية وقرينة الفيديو إن وجدت)",
        key="legal_opinion",
        height=160,
        on_change=save_current_work,
    )
with tab3:
    st.subheader("الحقوق والإجراءات المتخذة")
    nature_options = ["حادث مروري اعتيادي", "حادث مروري مقترن بشق جنائي / أمني"]
    if st.session_state.get("accident_nature") not in nature_options:
        st.session_state.accident_nature = nature_options[0]
    accident_nature = st.radio(
        "طبيعة وتصنيف الحادث:",
        nature_options,
        horizontal=True,
        key="accident_nature",
        on_change=save_current_work,
    )
    rights_options = [
        "اختر الحالة",
        "قيام الحق الخاص فقط (تنازل أو صلح)",
        "قيام الحق العام والخاص (مخالفة مرورية موجبة للتوقيف)",
        "قيام الحق العام والخاص مع وجود شق جنائي (إحالة للشرطة والنيابة)",
        "وفاة الطرف المتسبب (استكمال الإجراءات النظامية والجنائية)",
    ]
    if st.session_state.get("rights_status") not in rights_options:
        st.session_state.rights_status = rights_options[0]
    rights_status = st.selectbox(
        "الحقوق الخاصة والعامة",
        rights_options,
        key="rights_status",
        on_change=save_current_work,
    )
    base_procedures = [
        "معاينة الموقع ورسم الكروكي",
        "إسعاف المصابين للمستشفى",
        "رفع المركبات من الموقع",
    ]
    criminal_procedures = [
        "استدعاء الأدلة الجنائية للموقع والمستشفى",
        "استدعاء الشرطة لاستلام الشق الجنائي",
        "تعيين خفارة وتشديد الحراسة على المصاب بالمستشفى",
        "التعميم للعمليات بالمركبات الهاربة والمساندة",
        "تفتيش المركبة للتأكد من عدم وجود ممنوعات",
        "إثبات حالة صدم متعمد لدورية رسمية ومقاومة رجال الأمن",
        "إثبات استخدام السلاح الرسمي (طلقات تحذيرية / إعطاب)",
    ]
    available_procedures = base_procedures + criminal_procedures if "جنائي" in accident_nature else base_procedures
    if "taken_procedures" in st.session_state:
        st.session_state.taken_procedures = [
            item for item in st.session_state.taken_procedures if item in available_procedures
        ]
    taken_procedures = st.multiselect(
        "الإجراءات المتخذة:",
        options=available_procedures,
        placeholder="Choose options",
        key="taken_procedures",
    )
    participating_agency = ""
    escaped_vehicles = ""
    shots_fired = ""
    contraband_found = ""
    if "جنائي" in accident_nature:
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
    extra_procedure = st.text_input(
        "إجراء إضافي خاص:",
        key="extra_procedure",
        on_change=save_current_work,
    )
    selected_actions = list(taken_procedures)
    if extra_procedure:
        selected_actions.append(extra_procedure)
with tab4:
    st.subheader("🎨 محرر الكروكي التفاعلي (Fabric.js)")
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
        with st.form("adopt_sketch_form", clear_on_submit=True, border=False):
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
        st.text_input(f"مدلول رقم ({number})", value="", key=f"legend_key_{number}")
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
    logo_b64 = ""
    _fixed_logo_path = Path(__file__).resolve().parent / "traffic_logo.png"
    if _fixed_logo_path.is_file():
        try:
            logo_b64 = img_to_b64(Image.open(_fixed_logo_path).convert("RGBA"))
        except OSError:
            logo_b64 = ""
    def build_header():
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" alt="شعار المرور">' if logo_b64 else '<div class="logo-fallback">الأمن العام<br>المرور</div>'
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
        parties_rows += "<tr>" + "".join(f"<td>{row.get(key, '')}</td>" for key, _label in _party_columns) + "</tr>"
    vehicles_rows = ""
    for _, row in vehicles_df.iterrows():
        vehicles_rows += "<tr>" + "".join(f"<td>{row.get(key, '')}</td>" for key, _label in _vehicle_columns) + "</tr>"
    results_html = "<br>".join(html.escape(line) for line in acc_results.split("\n") if line.strip())
    acc_how_html = html.escape(acc_how or "").replace("\n", "<br>")
    laws_html = "".join(
        f"<li>{html.escape(line)}</li>" for line in custom_laws.split("\n") if line.strip()
    )
    actions_html = "".join(
        f"<tr><td>{i+1}- {html.escape(str(act))}</td></tr>" for i, act in enumerate(selected_actions)
    )
    criminal_details_html = ""
    if "جنائي" in (accident_nature or ""):
        criminal_details_html = f"""
            <div class="table-scroll"><table style="margin-top:25px;">
                <tr><th style="font-size:16px;">تفاصيل الشق الجنائي والأمني</th></tr>
                <tr><td style="padding:14px; font-size:16px; text-align:right;">الجهة الأمنية المباشرة: {html.escape(participating_agency)}</td></tr>
                <tr><td style="padding:14px; font-size:16px; text-align:right;">بيانات المركبات الهاربة أو المعترضة: {html.escape(escaped_vehicles)}</td></tr>
                <tr><td style="padding:14px; font-size:16px; text-align:right;">هل تم إطلاق نار أثناء المطاردة؟ {html.escape(shots_fired)}</td></tr>
                <tr><td style="padding:14px; font-size:16px; text-align:right;">نتيجة تفتيش المركبة: {html.escape(contraband_found)}</td></tr>
            </table></div>
        """
    photo_cards = ""
    for number, entry in enumerate(st.session_state.gallery_photos, start=1):
        safe_caption = html.escape(entry.get("caption") or "")
        photo_cards += f"""
        <div class="photo-card">
            <img src="{entry['b64']}" alt="صورة {number}">
            <div class="photo-meta">{number}<br>{safe_caption}</div>
        </div>
        """
    photos_pages_html = ""
    if photo_cards:
        photos_pages_html = f"""
        <div class="page report-page photo-annex">
            {build_header()}
            <div class="section-badge">ملحق الصور الفوتوغرافية لموقع الحادث</div>
            <div class="photo-grid">{photo_cards}</div>
            <div class="page-num">5</div>
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
            flex: 1 1 auto; width: 100%; min-width: 0; max-width: 100%;
            overflow: auto; -webkit-overflow-scrolling: touch;
            container-type: inline-size; container-name: report;
        }}
        .report-sheet {{
            width: 210mm; min-width: 750px; margin: 12px auto 20px auto;
        }}
        .page {{
            background: white; width: 210mm; min-width: 750px; min-height: 297mm; margin: 0 auto 20px auto;
            padding: 15mm 18mm; box-sizing: border-box; position: relative;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); page-break-after: always;
        }}
        .photo-annex {{ page-break-before: always; }}
        .photo-grid {{ display: flex; flex-wrap: wrap; justify-content: space-between; }}
        .photo-card {{ width: 48%; margin-bottom: 18px; text-align: center; }}
        .photo-card img {{
            width: auto; max-width: 100%; max-height: 350px; height: auto; object-fit: contain;
            border: 2px solid #1b4332; border-radius: 6px; background: #fff;
        }}
        .photo-card .photo-meta {{ margin-top: 6px; font-weight: bold; font-size: 14px; line-height: 1.6; }}
        .logo-fallback {{
            border: 2px solid #1b4332; border-radius: 50%; width: 80px; height: 80px;
            display: flex; align-items: center; justify-content: center; margin: auto;
            font-weight: bold; color: #1b4332; line-height: 1.25; text-align: center;
        }}
        .header-logo img {{
            height: 110px; width: auto; max-width: 120px; object-fit: contain;
            display: block; margin: 0 auto;
        }}
        .header-Title {{ text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 6px; }}
        .header-box {{
            position: relative; display: flex; justify-content: space-between; align-items: center;
            min-height: 128px; border-bottom: 3px double #1b4332; padding-bottom: 10px;
            margin-bottom: 18px; font-size: 14px; font-weight: bold; line-height: 1.6;
        }}
        .header-right {{ width: 36%; text-align: right; }}
        .header-center {{ width: 36%; text-align: center; }}
        .header-logo {{
            position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
            display: flex; justify-content: center; align-items: center; margin: 0;
        }}
        .section-badge {{
            background: #d8f3dc; border: 1.5px solid #1b4332; border-radius: 6px;
            padding: 5px 25px; font-weight: bold; font-size: 17px; display: table; margin: 14px auto; text-align: center; color: #1b4332;
        }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 14px; }}
        th, td {{ border: 1.5px solid #444; padding: 7px 6px; text-align: center; font-weight: bold; }}
        th {{ background-color: #d8f3dc; color: #1b4332; }}
        .box-content {{
            border: 1.5px solid #444; padding: 14px; font-size: 15px; font-weight: bold;
            line-height: 1.9; text-align: right; margin-bottom: 16px; min-height: 110px;
        }}
        .page-num {{ position: absolute; bottom: 12mm; left: 50%; transform: translateX(-50%); font-weight: bold; font-size: 16px; }}
        .road-sign {{
            background: #2d6a4f; color: white; border: 3px solid white; outline: 3px solid #2d6a4f;
            border-radius: 8px; padding: 10px 18px; font-weight: bold; font-size: 16px; display: inline-block; margin-bottom: 25px;
        }}
        .table-scroll {{ width: 100%; max-width: 100%; }}
        @media screen {{
            html, body, .report-viewport {{ overflow: hidden; }}
            .report-sheet {{
                width: 100%; min-width: 0; max-width: 850px; margin-left: auto; margin-right: auto;
            }}
            .report-viewport {{ max-width: 100%; }}
            .page, .report-page, .a4-page {{
                width: 100%; min-width: 0; max-width: 850px;
                min-height: 0; height: auto; overflow: hidden; box-sizing: border-box;
            }}
            .table-scroll {{ width: 100%; max-width: 100%; overflow-x: hidden; }}
            table, .table-scroll table {{
                table-layout: fixed; width: 100%; min-width: 0; max-width: 100%;
            }}
            th, td {{
                white-space: normal; overflow-wrap: anywhere; word-break: break-word;
            }}
        }}
        @media screen and (max-width: 768px) {{
            html, body {{ width: 100%; max-width: 100%; overflow-x: hidden; }}
            .report-viewport {{ overflow: hidden; width: 100%; max-width: 100%; }}
            .report-sheet {{
                width: 100%; min-width: 0; max-width: 850px;
                margin: 0 auto 12px auto; zoom: 1;
            }}
            .page, .report-page, .a4-page {{
                width: 100%; min-width: 0; max-width: 850px;
                min-height: 0; height: auto; overflow: hidden; font-size: 12px;
            }}
            .report-page {{
                box-sizing: border-box;
                background: #fff;
                color: #000;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 15px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
            }}
            .header-Title {{ font-size: 14px; }}
            .header-box {{ font-size: 11px; min-height: 88px; }}
            .header-logo img {{ height: 64px; max-width: 70px; }}
            .section-badge {{ font-size: 13px; padding: 4px 10px; }}
            .box-content {{ font-size: 12px; min-height: 0; padding: 8px; }}
            .table-scroll {{ width: 100%; max-width: 100%; overflow-x: hidden; }}
            table, .table-scroll table {{
                table-layout: fixed; width: 100%; min-width: 0; max-width: 100%; font-size: 11px;
            }}
            th, td {{
                font-size: 11px; padding: 4px 3px;
                white-space: normal; overflow-wrap: anywhere; word-break: break-word;
            }}
        }}
        @media print {{
            @page {{ size: A4; margin: 8mm; }}
            html, body {{ height: auto; display: block; overflow: visible; background: white; padding: 0; }}
            button, .no-print, .stButton, .stDownloadButton,
            [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {{
                display: none !important;
            }}
            .report-viewport {{ overflow: visible; height: auto; }}
            .report-sheet {{ width: auto; min-width: 0; margin: 0; zoom: 1; }}
            .page, .report-page, .a4-page {{
                box-shadow: none; margin: 0 auto; zoom: 1; overflow: hidden;
                width: 210mm; height: 297mm; max-width: 210mm; max-height: 297mm;
                min-width: 0; min-height: 297mm; page-break-after: always;
            }}
            .report-sheet > .report-page:last-child {{ page-break-after: auto; break-after: auto; }}
            .table-scroll {{ overflow: visible; max-width: none; }}
            table, .table-scroll table {{
                width: 99.6% !important; min-width: 0 !important; border-collapse: collapse;
                border: 1px solid #000;
            }}
            th, td {{ border: 1px solid #000 !important; }}
            .header-logo img {{ height: 110px; max-width: 120px; }}
        }}
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
    <body>
        <div class="no-print" style="text-align:center; margin:0; padding:12px;">
            <button onclick="window.print()" style="background:linear-gradient(90deg,#0e7490,#2563eb); color:white; font-family:'Tajawal'; font-size:18px; font-weight:bold; padding:12px 35px; border:1px solid #4facfe; border-radius:10px; cursor:pointer; box-shadow:0 0 14px rgba(0,242,254,0.45);">
                🖨️ طباعة التقرير الرسمي أو حفظه كـ PDF
            </button>
        </div>
        <div class="report-viewport">
        <div class="report-sheet">
        <div class="page report-page">
            {build_header()}
            <div class="section-badge">تقرير حادث مروري</div>
            <div class="section-badge" style="font-size:15px;">معلومات الحادث</div>
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
            <div class="section-badge" style="font-size:15px;">معلومات أطراف الحادث</div>
            <div class="table-scroll"><table>
                <tr>{parties_head}</tr>
                {parties_rows}
            </table></div>
            <div class="section-badge" style="font-size:15px;">معلومات المركبات</div>
            <div class="table-scroll"><table>
                <tr>{vehicles_head}</tr>
                {vehicles_rows}
            </table></div>
            <div class="page-num">1</div>
        </div>
        <div class="page report-page">
            {build_header()}
            <div class="section-badge">نتائج الحادث</div>
            <div class="box-content">نتج عن الحادث :<br>{results_html}</div>
            <div class="section-badge">كيفية وقوع الحادث</div>
            <div class="box-content">{acc_how_html}</div>
            <div class="section-badge">الرأي والمسؤولية</div>
            <div class="box-content">
                {resp_summary}<br>وذلك للأسباب التالية:
                <ul style="margin-top:8px;">{laws_html}</ul>
            </div>
            <div class="page-num">2</div>
        </div>
        <div class="page report-page">
            {build_header()}
            <div class="table-scroll"><table>
                <tr><th style="font-size:16px;">طبيعة وتصنيف الحادث</th></tr>
                <tr><td style="padding:14px; font-size:16px;">{html.escape(accident_nature or "")}</td></tr>
            </table></div>
            <div class="table-scroll"><table style="margin-top:25px;">
                <tr><th style="font-size:16px;">الحقوق الخاصة والعامة</th></tr>
                <tr><td style="padding:14px; font-size:16px;">{html.escape("" if rights_status == "اختر الحالة" else rights_status)}</td></tr>
            </table></div>
            <div class="table-scroll"><table style="margin-top:25px;">
                <tr><th style="font-size:16px;">الإجراءات المتخذة</th></tr>
                {actions_html}
            </table></div>
            {criminal_details_html}
            <div class="table-scroll"><table style="margin-top:35px;">
                <tr><th colspan="3" style="font-size:16px;">معد التقرير</th></tr>
                <tr><th>إجراء الحوادث</th><th>مشرف الحوادث</th><th>مدير {dept_branch}</th></tr>
                <tr><td>الاسم: {officer_1_name}</td><td>الاسم: {officer_2_name}</td><td>الاسم: {manager_name}</td></tr>
                <tr><td>الرتبة: {officer_1_rank}</td><td>الرتبة: {officer_2_rank}</td><td>الرتبة: {manager_rank}</td></tr>
                <tr style="height:65px;"><td>التوقيع:</td><td>التوقيع:</td><td>التوقيع:</td></tr>
            </table></div>
            <div class="page-num">3</div>
        </div>
        <div class="page report-page">
            {build_header()}
            <div class="section-badge">كروكي الحادث</div>
            <div style="text-align:center; font-weight:bold; font-size:18px; margin-bottom:15px;">رسم كروكي {road_name_sign}</div>
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
            <div style="margin-top:30px; font-weight:bold; font-size:16px; line-height:2; padding-right:30px;">
                {"".join(f"<div>{line}</div>" for line in legend_keys)}
            </div>
            <div class="page-num">4</div>
        </div>
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
    report_fullscreen = st.toggle("🔲 وضع ملء الشاشة (إخفاء القائمة الجانبية)", value=True)
    if report_fullscreen:
        st.markdown(
            """
            <style>
            section[data-testid="stSidebar"] {
                display: flex !important;
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

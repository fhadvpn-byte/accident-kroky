import base64
from datetime import date, datetime
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
import streamlit as st


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
  julian_day = (
      math.floor(365.25 * (year + 4716))
      + math.floor(30.6001 * (month + 1))
      + day
      + gregorian_shift
      - 1524
  )
  lunar = julian_day - 1948440 + 10632
  cycles = math.floor((lunar - 1) / 10631)
  lunar = lunar - 10631 * cycles + 354
  jump = (
      math.floor((10985 - lunar) / 5316) * math.floor((50 * lunar) / 17719)
  ) + (math.floor(lunar / 5670) * math.floor((43 * lunar) / 15238))
  lunar = (
      lunar
      - (math.floor((30 - jump) / 15) * math.floor((17719 * jump) / 50))
      - (math.floor(jump / 16) * math.floor((15238 * jump) / 43))
      + 29
  )
  hijri_month = math.floor((24 * lunar) / 709)
  hijri_day = lunar - math.floor((709 * hijri_month) / 24)
  hijri_year = 30 * cycles + jump - 30
  return f"{int(hijri_year):04d}/{int(hijri_month):02d}/{int(hijri_day):02d}"


def get_today_hijri():
  return gregorian_to_hijri_str(date.today())


def _blank_parties():
  return [
      {
          "الطرف": "الطرف الأول",
          "الاسم": "",
          "الهوية": "",
          "المشاركة": "",
          "الحالة": "",
          "التأهيل": "",
      },
      {
          "الطرف": "الطرف الثاني",
          "الاسم": "",
          "الهوية": "",
          "المشاركة": "",
          "الحالة": "",
          "التأهيل": "",
      },
  ]


def _blank_vehicles():
  return [
      {
          "الطرف": "الطرف الأول",
          "نوع المركبة": "",
          "رقم اللوحة": "",
          "الرقم التسلسلي": "",
          "نوع الترخيص": "",
          "التأمين": "",
      },
      {
          "الطرف": "الطرف الثاني",
          "نوع المركبة": "",
          "رقم اللوحة": "",
          "الرقم التسلسلي": "",
          "نوع الترخيص": "",
          "التأمين": "",
      },
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
  for text_key in (
      "accident_results",
      "technical_description",
      "legal_opinion",
      "extra_procedure",
      "video_timestamp",
      "video_custom_notes",
  ):
    if not isinstance(st.session_state.get(text_key), str):
      st.session_state[text_key] = ""
  if not isinstance(st.session_state.get("show_page_numbers"), bool):
    st.session_state.show_page_numbers = False
  if not isinstance(st.session_state.get("auto_analyze_video"), bool):
    st.session_state.auto_analyze_video = False
  _normalize_loaded_video_state()
  st.session_state.law_selection_sig = tuple(
      st.session_state.get("selected_articles") or []
  )
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
  now_str = datetime.now(ZoneInfo("Asia/Riyadh")).strftime(
      "%Y-%m-%d | %I:%M:%S %p"
  )
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
  st.markdown(
      """
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
    """,
      unsafe_allow_html=True,
  )


def render_save_and_clear_toolbar():
  with st.container(key="save-bar"):
    col_status, col_save, col_clear = st.columns([3, 1.5, 1.5])
    with col_status:
      st.markdown(
          "**🛡️ نظام حماية البيانات النشط:** آخر حفظ للعمل:"
          f" `{st.session_state.get('last_saved_time', 'لم يتم الحفظ بعد')}`"
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
            st.toast("تم مسح

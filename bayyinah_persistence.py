"""حفظ/استرجاع كامل لحالة بينة في مجلد محلي مخفي (.bayyinah_persistence/)."""
from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

_STORE_DIR = Path(__file__).resolve().parent / ".bayyinah_persistence"
_STORE_FILE = _STORE_DIR / "active_workspace.pkl"
_META_FILE = _STORE_DIR / "meta.json"

# مفاتيح الوسائط المعتمدة — تُحفظ وتُسترجع صراحة ولا تُمسَح عند التنقل/الحفظ
MEDIA_KEYS = (
    "sketch_data_url",
    "aerial_sketch_data_url",
    "aerial_data_url",
    "satellite_img_b64",
    "_saved_asphalt_state",
    "saved_asphalt_state",
    "_saved_satellite_state",
    "saved_satellite_state",
    "gallery_photos",
    "accident_photos_data",
    "include_sketch",
    "include_aerial",
    "aerial_place",
    "report_media_mode",
    "studio_layout_mode",
    "_studio_layout_mode",
    "_last_sketch_commit_ts",
    "_last_aerial_commit_ts",
)

# ظل التبويب 3 + مفاتيحه — لا تُحذف أبداً إلا عند حادث جديد
FORM_SHADOW_KEY = "_PERMANENT_FORM_DATA_"
TAB3_KEYS = (
    FORM_SHADOW_KEY,
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
    "results_data_fingerprint",
    "criminal_participating_agency",
    "criminal_escaped_vehicles",
    "criminal_shots_fired",
    "criminal_contraband_found",
    "law_selection_sig",
    "tab3_content_fingerprint",
    "_actions_plural_deaths_sig",
)

_EPHEMERAL_PREFIXES = (
    "FormSubmitter:",
    "$$STREAMLIT",
    "_stcore",
    "_BAYYINAH_",
    "_top_cmd_",
    "_sidebar_save",
    "_bw_",
    "_bfu_",
    "_bclear_",
    "_bde_",
)
_EPHEMERAL_KEYS = frozenset({
    "confirm_clear",
    "_save_success_banner",
    "_sidebar_save_ok",
    "_persist_restored_ok",
    "_last_persisted_stamp",
    "_p1_save_requested",
})
_BUTTONISH = ("btn", "save", "new", "print", "del", "add", "insert", "remove")
# مفاتيح file_uploader / camera_input — لا تُحفظ ولا تُسترجع (تسبب StreamlitValueAssignmentNotAllowedError)
_FILE_CAMERA_WIDGET_EXACT = frozenset({
    "mobile_gallery_uploader",
    "video_bulk_files",
})
_FILE_CAMERA_WIDGET_PREFIXES = (
    "mobile_gallery_uploader_",
    "clip_file_",
    "camera_input_",
)
# مفاتيح محمية: لا تُحذف عند التنقل أو الحفظ أو عدم عرض الودجت
_PROTECTED_KEYS = frozenset(MEDIA_KEYS) | frozenset(TAB3_KEYS) | {FORM_SHADOW_KEY}


def _ensure_dir() -> None:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)


def _is_file_or_camera_widget_key(key: str) -> bool:
    """مفاتيح ودجات الرفع/الكاميرا — ممنوعة من الحفظ والاسترجاع والتعيين في session_state."""
    if not isinstance(key, str) or not key:
        return False
    if key in _FILE_CAMERA_WIDGET_EXACT:
        return True
    if any(key.startswith(prefix) for prefix in _FILE_CAMERA_WIDGET_PREFIXES):
        return True
    if key.endswith("_camera") or key.endswith("_uploader"):
        return True
    if "camera_input" in key:
        return True
    return False


def _is_ephemeral_key(key: str) -> bool:
    if not isinstance(key, str) or not key:
        return True
    # ودجات الملفات/الكاميرا زائلة دائماً حتى لا تُعاد كتابتها في session_state
    if _is_file_or_camera_widget_key(key):
        return True
    # المفاتيح المحمية (ظل التبويب3 والوسائط) لا تُعامل كزائلة أبداً
    if key in _PROTECTED_KEYS or key in TAB3_KEYS:
        return False
    if key in _EPHEMERAL_KEYS:
        return True
    if any(key.startswith(p) for p in _EPHEMERAL_PREFIXES):
        return True
    return False


def _is_blank_media(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict, tuple)) and len(value) == 0:
        return True
    return False


def _pack_obj(obj: Any, depth: int = 0) -> Any:
    if depth > 7:
        return None
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (bytes, bytearray)):
        return {"__b_kind__": "bytes", "data": bytes(obj)}
    if hasattr(obj, "getvalue") and hasattr(obj, "name"):
        try:
            raw = obj.getvalue()
            if hasattr(obj, "seek"):
                try:
                    obj.seek(0)
                except Exception:
                    pass
            return {
                "__b_kind__": "file",
                "name": getattr(obj, "name", "file.bin"),
                "type": getattr(obj, "type", "application/octet-stream"),
                "data": bytes(raw or b""),
            }
        except Exception:
            return None
    cls_mod = getattr(getattr(obj, "__class__", None), "__module__", "") or ""
    if cls_mod.startswith("PIL.") and hasattr(obj, "save"):
        try:
            buf = io.BytesIO()
            obj.save(buf, format="PNG")
            return {"__b_kind__": "pil", "data": buf.getvalue()}
        except Exception:
            return None
    if hasattr(obj, "to_dict"):
        try:
            return {"__b_kind__": "df", "records": obj.to_dict("records")}
        except Exception:
            pass
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            packed = _pack_obj(v, depth + 1)
            if packed is not None or v is None:
                out[str(k)] = packed
        return out
    if isinstance(obj, (list, tuple)):
        return [_pack_obj(x, depth + 1) for x in obj]
    if isinstance(obj, str) and obj.startswith("data:"):
        return obj
    try:
        json.dumps(obj, ensure_ascii=False, default=str)
        return obj
    except Exception:
        return None


class SavedUploadedFile(io.BytesIO):
    def __init__(self, data: bytes, name: str, mime_type: str = "application/octet-stream"):
        super().__init__(data)
        self._raw_data = data
        self.name = name or "attachment.bin"
        self.type = mime_type or "application/octet-stream"
        self.size = len(data)
        self.file_id = hashlib.md5((self.name + str(self.size)).encode("utf-8", "ignore")).hexdigest()

    def getvalue(self) -> bytes:
        return self._raw_data


def _unpack_obj(obj: Any, depth: int = 0) -> Any:
    if depth > 7:
        return obj
    if isinstance(obj, dict):
        kind = obj.get("__b_kind__")
        if kind == "bytes":
            return obj.get("data") or b""
        if kind == "file":
            return SavedUploadedFile(
                obj.get("data") or b"",
                obj.get("name", "file.bin"),
                obj.get("type", "application/octet-stream"),
            )
        if kind == "pil":
            try:
                from PIL import Image
                return Image.open(io.BytesIO(obj.get("data") or b""))
            except Exception:
                return None
        if kind == "df":
            try:
                import pandas as pd
                return pd.DataFrame(obj.get("records") or [])
            except Exception:
                return obj.get("records") or []
        return {k: _unpack_obj(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_unpack_obj(x, depth + 1) for x in obj]
    return obj


def _snapshot_media_explicit() -> dict:
    """لقطة صريحة لمفاتيح الكروكي/الجوي/الصور حتى لا تُسقط من الخزنة."""
    media = {}
    for key in MEDIA_KEYS:
        if key not in st.session_state:
            continue
        packed = _pack_obj(st.session_state.get(key))
        if packed is None and st.session_state.get(key) is not None:
            continue
        try:
            pickle.dumps(packed, protocol=4)
        except Exception:
            continue
        media[key] = packed
    return media


def _snapshot_tab3_explicit() -> dict:
    """لقطة صريحة لمفاتيح التبويب 3 والظل — لا تُحذف عند عدم العرض."""
    out = {}
    for key in TAB3_KEYS:
        if key not in st.session_state:
            continue
        packed = _pack_obj(st.session_state.get(key))
        if packed is None and st.session_state.get(key) is not None:
            continue
        try:
            pickle.dumps(packed, protocol=4)
        except Exception:
            continue
        out[key] = packed
    return out


def _snapshot_session() -> dict:
    snap = {}
    for key, value in list(st.session_state.items()):
        ks = str(key)
        if _is_ephemeral_key(ks):
            continue
        if ks not in _PROTECTED_KEYS and isinstance(value, bool) and any(w in ks.lower() for w in _BUTTONISH):
            continue
        packed = _pack_obj(value)
        if packed is None and value is not None:
            continue
        try:
            pickle.dumps(packed, protocol=4)
        except Exception:
            continue
        snap[ks] = packed
    # فرض مفاتيح الوسائط والتبويب3 فوق اللقطة العامة
    snap.update(_snapshot_media_explicit())
    snap.update(_snapshot_tab3_explicit())
    return snap


def save_full_workspace(reason: str = "manual") -> bool:
    """يحفظ كل الحالة القابلة للتسلسل بما فيها الصور كـ bytes والكروكي/الجوي/التبويب3 صراحة."""
    try:
        _ensure_dir()
        # قبل الحفظ: لا تحذف أي مفاتيح غير معروضة — فقط التقط اللقطة
        snap = _snapshot_session()
        payload = {
            "version": 3,
            "reason": reason,
            "session": snap,
            "media": _snapshot_media_explicit(),
            "tab3": _snapshot_tab3_explicit(),
        }
        fd, tmp_path = tempfile.mkstemp(dir=str(_STORE_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                pickle.dump(payload, fh, protocol=4)
            os.replace(tmp_path, _STORE_FILE)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        meta = {
            "reason": reason,
            "keys": len(snap),
            "has_sketch": bool(str(st.session_state.get("sketch_data_url") or "").startswith("data:")),
            "has_aerial": bool(str(st.session_state.get("aerial_sketch_data_url") or "").startswith("data:")),
            "has_asphalt_state": bool(st.session_state.get("_saved_asphalt_state")),
            "has_satellite_state": bool(
                st.session_state.get("_saved_satellite_state") or st.session_state.get("saved_satellite_state")
            ),
            "has_permanent_form": bool(st.session_state.get(FORM_SHADOW_KEY)),
            "has_tab3_texts": bool(str(st.session_state.get("accident_results") or "").strip()),
            "photos": len(st.session_state.get("gallery_photos") or []),
        }
        _META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        st.session_state["_BAYYINAH_LAST_SAVE_REASON_"] = reason
        return True
    except Exception as error:
        try:
            st.error(f"تعذر الحفظ الكامل للمحطة: {error}")
        except Exception:
            pass
        return False


def _force_restore_keys(session: dict, extra: dict | None, keys) -> int:
    """استرجاع قسري لمفاتيح محددة دون حذف القيم الغنية الحالية."""
    restored = 0
    merged = dict(session or {})
    if isinstance(extra, dict):
        merged.update(extra)
    for key in keys:
        if key not in merged:
            continue
        if _is_file_or_camera_widget_key(str(key)):
            continue
        try:
            value = _unpack_obj(merged[key])
        except Exception:
            continue
        current = st.session_state.get(key) if key in st.session_state else None
        if key in st.session_state and not _is_blank_media(current):
            if _is_blank_media(value):
                continue
            if isinstance(current, str) and current.startswith("data:") and isinstance(value, str) and value.startswith("data:"):
                if len(value) <= len(current):
                    continue
            elif isinstance(current, dict) and current and isinstance(value, dict) and not value:
                continue
            elif key not in (
                "_saved_asphalt_state",
                "saved_asphalt_state",
                "_saved_satellite_state",
                "saved_satellite_state",
                FORM_SHADOW_KEY,
            ) and not (
                isinstance(current, str)
                and not current.startswith("data:")
                and isinstance(value, str)
                and value.startswith("data:")
            ):
                # لا تستبدل قيمة غير فارغة — إلا ظل النموذج حيث ندمج
                if key != FORM_SHADOW_KEY:
                    continue
        try:
            if key == FORM_SHADOW_KEY and isinstance(current, dict) and isinstance(value, dict):
                merged_shadow = dict(value)
                merged_shadow.update({k: v for k, v in current.items() if not _is_blank_media(v)})
                st.session_state[key] = merged_shadow
            else:
                st.session_state[key] = value
            restored += 1
        except Exception:
            continue
    return restored


def _force_restore_media(session: dict, media: dict | None = None) -> int:
    """استرجاع قسري لمفاتيح الوسائط حتى لو وُجدت قيم فارغة في الجلسة."""
    restored = _force_restore_keys(session, media, MEDIA_KEYS)
    if str(st.session_state.get("aerial_sketch_data_url") or "").startswith("data:"):
        st.session_state["aerial_data_url"] = st.session_state.get("aerial_sketch_data_url")
    asphalt = st.session_state.get("_saved_asphalt_state") or st.session_state.get("saved_asphalt_state")
    if isinstance(asphalt, dict) and asphalt:
        st.session_state["_saved_asphalt_state"] = dict(asphalt)
        st.session_state["saved_asphalt_state"] = dict(asphalt)
    sat = st.session_state.get("_saved_satellite_state") or st.session_state.get("saved_satellite_state")
    if isinstance(sat, dict) and sat:
        st.session_state["_saved_satellite_state"] = dict(sat)
        st.session_state["saved_satellite_state"] = dict(sat)
    return restored


def _force_restore_tab3(session: dict, tab3: dict | None = None) -> int:
    """استرجاع قسري لمفاتيح التبويب3 والظل — لا حذف لمفاتيح غير المعروضة."""
    restored = _force_restore_keys(session, tab3, TAB3_KEYS)
    shadow = st.session_state.get(FORM_SHADOW_KEY)
    if isinstance(shadow, dict):
        for key, value in shadow.items():
            if key in TAB3_KEYS and key != FORM_SHADOW_KEY:
                if key not in st.session_state or _is_blank_media(st.session_state.get(key)):
                    if not _is_blank_media(value):
                        st.session_state[key] = value
                        restored += 1
    return restored


def restore_full_workspace() -> bool:
    """يسترجع الحالة المحفوظة؛ الوسائط والتبويب3 يُفرضان دون حذف مفاتيح غير معروضة."""
    first = not st.session_state.get("_BAYYINAH_RESTORED_OK_")
    st.session_state["_BAYYINAH_RESTORED_OK_"] = True
    if not _STORE_FILE.exists():
        return False
    try:
        with open(_STORE_FILE, "rb") as fh:
            payload = pickle.load(fh)
        session = (payload or {}).get("session") or {}
        media = (payload or {}).get("media") or {}
        tab3 = (payload or {}).get("tab3") or {}
        if not isinstance(session, dict):
            return False
        restored = 0
        if first:
            for key, packed in session.items():
                ks = str(key)
                if _is_ephemeral_key(ks) or _is_file_or_camera_widget_key(ks):
                    continue
                if ks in MEDIA_KEYS or ks in TAB3_KEYS:
                    continue  # تُعالج قسرياً أدناه
                if ks in st.session_state and not _is_blank_media(st.session_state.get(ks)):
                    continue
                try:
                    st.session_state[ks] = _unpack_obj(packed)
                    restored += 1
                except Exception:
                    continue
        restored += _force_restore_media(session, media if isinstance(media, dict) else {})
        restored += _force_restore_tab3(session, tab3 if isinstance(tab3, dict) else {})
        return restored > 0
    except Exception:
        return False


def ensure_media_every_cycle() -> None:
    """استرجاع الوسائط والتبويب3 في كل دورة — دون حذف مفاتيح غير معروضة."""
    if st.session_state.get("_BAYYINAH_SKIP_AUTOSAVE_"):
        return
    if not _STORE_FILE.exists():
        return
    try:
        with open(_STORE_FILE, "rb") as fh:
            payload = pickle.load(fh)
        session = (payload or {}).get("session") or {}
        media = (payload or {}).get("media") or {}
        tab3 = (payload or {}).get("tab3") or {}
        _force_restore_media(session if isinstance(session, dict) else {}, media if isinstance(media, dict) else {})
        _force_restore_tab3(session if isinstance(session, dict) else {}, tab3 if isinstance(tab3, dict) else {})
    except Exception:
        pass


def clear_full_workspace() -> None:
    """تصفير الحفظ المحلي — المسح فقط عند حادث جديد."""
    try:
        if _STORE_FILE.exists():
            _STORE_FILE.unlink()
        if _META_FILE.exists():
            _META_FILE.unlink()
    except Exception:
        pass
    for child in list(_STORE_DIR.glob("*")) if _STORE_DIR.exists() else []:
        try:
            if child.is_file():
                child.unlink()
        except Exception:
            pass
    for key in list(MEDIA_KEYS) + list(TAB3_KEYS):
        st.session_state.pop(key, None)
    st.session_state["_BAYYINAH_CLEAR_BROWSER_SKETCH_"] = True


def activate(app_file: str | None = None) -> None:
    """يُستدعى بعد set_page_config لاستعادة الحالة قبل بناء الواجهة."""
    _ensure_dir()
    restore_full_workspace()
    ensure_media_every_cycle()


def finalize_run() -> None:
    """حفظ تلقائي خفيف في نهاية كل تشغيل (تنقل تبويبات/إعادة رسم)."""
    if st.session_state.get("_BAYYINAH_SKIP_AUTOSAVE_"):
        return
    if not (
        st.session_state.get("p1_acc_number")
        or st.session_state.get("parties")
        or st.session_state.get("sketch_data_url")
        or st.session_state.get("aerial_sketch_data_url")
        or st.session_state.get("_saved_asphalt_state")
        or st.session_state.get("gallery_photos")
        or st.session_state.get("selected_articles")
        or st.session_state.get(FORM_SHADOW_KEY)
        or st.session_state.get("accident_results")
    ):
        return
    save_full_workspace(reason="autosave")


def on_tab_change() -> None:
    """يُربط بـ on_change لراديو التبويبات — يحفظ دون مسح مفاتيح التبويب3 أو الصور."""
    # لا تحذف مفاتيح غير المعروضة؛ فقط احفظ اللقطة
    save_full_workspace(reason="tab_change")

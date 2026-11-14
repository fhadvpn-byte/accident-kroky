"""حفظ/استرجاع كامل لحالة بينة في مجلد محلي مخفي (.bayyinah_persistence/)."""
from __future__ import annotations

import base64
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


def _ensure_dir() -> None:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)


def _is_ephemeral_key(key: str) -> bool:
    if not isinstance(key, str) or not key:
        return True
    if key in _EPHEMERAL_KEYS:
        return True
    if any(key.startswith(p) for p in _EPHEMERAL_PREFIXES):
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
    # data-url صور كبيرة تُحفظ كنص
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


def _snapshot_session() -> dict:
    snap = {}
    for key, value in list(st.session_state.items()):
        ks = str(key)
        if _is_ephemeral_key(ks):
            continue
        if isinstance(value, bool) and any(w in ks.lower() for w in _BUTTONISH):
            continue
        packed = _pack_obj(value)
        if packed is None and value is not None:
            continue
        try:
            pickle.dumps(packed, protocol=4)
        except Exception:
            continue
        snap[ks] = packed
    return snap


def save_full_workspace(reason: str = "manual") -> bool:
    """يحفظ كل الحالة القابلة للتسلسل بما فيها الصور كـ bytes."""
    try:
        _ensure_dir()
        snap = _snapshot_session()
        payload = {
            "version": 1,
            "reason": reason,
            "session": snap,
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


def restore_full_workspace() -> bool:
    """يسترجع الحالة المحفوظة إلى session_state إن لم تكن موجودة بعد."""
    if st.session_state.get("_BAYYINAH_RESTORED_OK_"):
        return False
    st.session_state["_BAYYINAH_RESTORED_OK_"] = True
    if not _STORE_FILE.exists():
        return False
    try:
        with open(_STORE_FILE, "rb") as fh:
            payload = pickle.load(fh)
        session = (payload or {}).get("session") or {}
        if not isinstance(session, dict):
            return False
        restored = 0
        for key, packed in session.items():
            ks = str(key)
            if _is_ephemeral_key(ks):
                continue
            if ks in st.session_state:
                continue
            try:
                st.session_state[ks] = _unpack_obj(packed)
                restored += 1
            except Exception:
                continue
        return restored > 0
    except Exception:
        return False


def clear_full_workspace() -> None:
    """تصفير الحفظ المحلي — فقط عند حادث جديد."""
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


def activate(app_file: str | None = None) -> None:
    """يُستدعى بعد set_page_config لاستعادة الحالة قبل بناء الواجهة."""
    _ensure_dir()
    restore_full_workspace()


def finalize_run() -> None:
    """حفظ تلقائي خفيف في نهاية كل تشغيل (تنقل تبويبات/إعادة رسم)."""
    if st.session_state.get("_BAYYINAH_SKIP_AUTOSAVE_"):
        return
    # لا تكتب إن لم توجد أي بيانات ذات معنى بعد
    if not (
        st.session_state.get("p1_acc_number")
        or st.session_state.get("parties")
        or st.session_state.get("sketch_data_url")
        or st.session_state.get("gallery_photos")
        or st.session_state.get("selected_articles")
    ):
        return
    save_full_workspace(reason="autosave")


def on_tab_change() -> None:
    """يُربط بـ on_change لراديو التبويبات."""
    save_full_workspace(reason="tab_change")

"""Visibility キーフレーム テンプレート機能。

- 単一オブジェクト・テンプレ（A1）
- 保存先: Scene 内 + Export/Import JSON
- 録音: アクティブオブジェクトの hide_viewport / hide_render fcurve を、
  最初のキー frame を 0 とした相対オフセットで保存
- 適用: 選択オブジェクト全員に broadcast、現フレームを起点に相対オフセットで配置
- マージ動作: 既存キーは温存、テンプレキーが置かれるフレームのみ上書き
- 補間: 録音時の interpolation を保持
"""

from __future__ import annotations

import json
import os

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from ._base import YatoVisOperator, selected_objects
from .burst_ops import _iter_action_fcurves, insert_visibility_key


_TEMPLATE_CHANNELS = ("hide_viewport", "hide_render")


def _addon_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_templates_path() -> str:
    return os.path.join(_addon_root(), "presets", "default_templates.json")


def _collect_template_keys_from_object(obj) -> list[dict]:
    """obj.animation_data.action から hide_* fcurve のキーを (channel, frame, value, interp) で抽出。"""
    out: list[dict] = []
    ad = getattr(obj, "animation_data", None)
    if ad is None or ad.action is None:
        return out
    for fc in _iter_action_fcurves(ad.action):
        try:
            dp = fc.data_path
        except Exception:
            continue
        if dp not in _TEMPLATE_CHANNELS:
            continue
        for kp in fc.keyframe_points:
            out.append({
                "channel": dp,
                "frame": int(round(kp.co.x)),
                "value": bool(kp.co.y),
                "interpolation": kp.interpolation,
            })
    return out


def _normalize_to_relative(raw_keys: list[dict]) -> list[dict]:
    """frame 絶対値の dict 群を、最小 frame を 0 とした相対オフセット dict 群に変換。"""
    if not raw_keys:
        return []
    base = min(k["frame"] for k in raw_keys)
    return [
        {
            "channel": k["channel"],
            "frame_offset": k["frame"] - base,
            "value": k["value"],
            "interpolation": k.get("interpolation", "CONSTANT"),
        }
        for k in sorted(raw_keys, key=lambda k: (k["frame"], k["channel"]))
    ]


def _template_to_dict(tpl) -> dict:
    return {
        "name": tpl.name,
        "note": tpl.note,
        "keys": [
            {
                "channel": k.channel,
                "frame_offset": int(k.frame_offset),
                "value": bool(k.value),
                "interpolation": k.interpolation,
            }
            for k in tpl.keys
        ],
    }


def _dict_to_template(st, d: dict) -> None:
    tpl = st.templates.add()
    tpl.name = str(d.get("name", "Template"))
    tpl.note = str(d.get("note", ""))
    for k in d.get("keys", []):
        kk = tpl.keys.add()
        kk.channel = str(k.get("channel", "hide_viewport"))
        kk.frame_offset = int(k.get("frame_offset", 0))
        kk.value = bool(k.get("value", False))
        kk.interpolation = str(k.get("interpolation", "CONSTANT"))


def _apply_template_to_object(obj, tpl, anchor_frame: int) -> int:
    """1 オブジェクトにテンプレを適用。挿入キー数を返す。"""
    n = 0
    for k in tpl.keys:
        insert_visibility_key(
            obj,
            k.channel,
            anchor_frame + int(k.frame_offset),
            bool(k.value),
            interpolation=str(k.interpolation) or "CONSTANT",
        )
        n += 1
    return n


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class YATOVIS_OT_template_record(YatoVisOperator):
    """アクティブオブジェクトの hide_viewport / hide_render キーをテンプレ録音。"""
    bl_idname = "yato_vis.template_record"
    bl_label = "Record Template"
    bl_description = (
        "アクティブオブジェクトの hide_viewport / hide_render の全キーを"
        "相対フレームに変換してテンプレ録音"
    )

    name: StringProperty(name="Name", default="Template")
    use_range: BoolProperty(
        name="Limit Frame Range",
        description="指定範囲内のキーのみ録音",
        default=False,
    )
    frame_min: IntProperty(name="Min", default=0)
    frame_max: IntProperty(name="Max", default=250)

    def invoke(self, context, event):  # noqa: ARG002
        scene = context.scene
        self.frame_min = scene.frame_start
        self.frame_max = scene.frame_end
        if not self.name or self.name == "Template":
            obj = context.active_object
            self.name = f"{obj.name} keys" if obj is not None else "Template"
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):  # noqa: ARG002
        layout = self.layout
        layout.prop(self, "name")
        layout.prop(self, "use_range")
        if self.use_range:
            row = layout.row(align=True)
            row.prop(self, "frame_min")
            row.prop(self, "frame_max")

    def run(self, context):
        obj = context.active_object
        if obj is None:
            self.report({"WARNING"}, "アクティブオブジェクトがありません")
            return {"CANCELLED"}
        raw = _collect_template_keys_from_object(obj)
        if self.use_range:
            lo = min(self.frame_min, self.frame_max)
            hi = max(self.frame_min, self.frame_max)
            raw = [k for k in raw if lo <= k["frame"] <= hi]
        if not raw:
            self.report({"WARNING"}, "録音対象の hide_viewport/hide_render キーが見つかりません")
            return {"CANCELLED"}
        rel = _normalize_to_relative(raw)
        st = context.scene.yato_vis
        tpl = st.templates.add()
        tpl.name = self.name or "Template"
        tpl.note = f"recorded from {obj.name}"
        for k in rel:
            kk = tpl.keys.add()
            kk.channel = k["channel"]
            kk.frame_offset = k["frame_offset"]
            kk.value = k["value"]
            kk.interpolation = k["interpolation"]
        st.active_template_index = len(st.templates) - 1
        self.report({"INFO"}, f"Template '{tpl.name}' recorded ({len(tpl.keys)} keys)")
        return {"FINISHED"}


class YATOVIS_OT_template_apply(YatoVisOperator):
    """アクティブテンプレを選択オブジェクト全員に適用（相対・マージ）。"""
    bl_idname = "yato_vis.template_apply"
    bl_label = "Apply Template"
    bl_description = (
        "アクティブテンプレを選択オブジェクト全員に適用。"
        "テンプレの frame_offset=0 のキーが現フレームに来るよう相対配置（既存キーとマージ）"
    )

    template_index: IntProperty(default=-1)
    frame_override: IntProperty(
        name="Anchor Frame",
        description="-1 なら現フレームを使う",
        default=-1,
    )

    def run(self, context):
        st = context.scene.yato_vis
        idx = self.template_index if self.template_index >= 0 else st.active_template_index
        if not (0 <= idx < len(st.templates)):
            self.report({"WARNING"}, "Template が選択されていません")
            return {"CANCELLED"}
        tpl = st.templates[idx]
        if len(tpl.keys) == 0:
            self.report({"WARNING"}, f"Template '{tpl.name}' は空です")
            return {"CANCELLED"}
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        anchor = self.frame_override if self.frame_override >= 0 else context.scene.frame_current
        total = 0
        for o in objs:
            total += _apply_template_to_object(o, tpl, anchor)
        self.report(
            {"INFO"},
            f"Template '{tpl.name}' applied: {total} keys on {len(objs)} obj(s) (anchor F={anchor})",
        )
        return {"FINISHED"}


class YATOVIS_OT_template_remove(YatoVisOperator):
    bl_idname = "yato_vis.template_remove"
    bl_label = "Remove Template"
    bl_description = "アクティブテンプレを削除"

    def run(self, context):
        st = context.scene.yato_vis
        idx = st.active_template_index
        if not (0 <= idx < len(st.templates)):
            self.report({"WARNING"}, "Template が選択されていません")
            return {"CANCELLED"}
        name = st.templates[idx].name
        st.templates.remove(idx)
        st.active_template_index = max(0, min(idx, len(st.templates) - 1))
        self.report({"INFO"}, f"Template '{name}' removed")
        return {"FINISHED"}


class YATOVIS_OT_template_rename(YatoVisOperator):
    bl_idname = "yato_vis.template_rename"
    bl_label = "Rename Template"
    bl_description = "アクティブテンプレをリネーム"

    new_name: StringProperty(name="Name", default="")

    def invoke(self, context, event):  # noqa: ARG002
        st = context.scene.yato_vis
        idx = st.active_template_index
        if not (0 <= idx < len(st.templates)):
            self.report({"WARNING"}, "Template が選択されていません")
            return {"CANCELLED"}
        self.new_name = st.templates[idx].name
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):  # noqa: ARG002
        self.layout.prop(self, "new_name")

    def run(self, context):
        st = context.scene.yato_vis
        idx = st.active_template_index
        if not (0 <= idx < len(st.templates)):
            return {"CANCELLED"}
        st.templates[idx].name = self.new_name or "Template"
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

class YATOVIS_OT_template_load_defaults(YatoVisOperator):
    """同梱の default_templates.json を Scene にロード。"""
    bl_idname = "yato_vis.template_load_defaults"
    bl_label = "Load Default Templates"
    bl_description = "アドオン同梱のデフォルトテンプレを Scene に追加"

    replace: BoolProperty(
        name="Replace Existing",
        description="既存テンプレを全て削除してから読み込む",
        default=False,
    )

    def invoke(self, context, event):  # noqa: ARG002
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):  # noqa: ARG002
        layout = self.layout
        layout.label(text="同梱の default_templates.json を読み込みます")
        layout.prop(self, "replace")

    def run(self, context):
        path = _default_templates_path()
        if not os.path.isfile(path):
            self.report({"ERROR"}, f"デフォルトテンプレが見つかりません: {path}")
            return {"CANCELLED"}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self.report({"ERROR"}, f"JSON 読込失敗: {exc}")
            return {"CANCELLED"}
        st = context.scene.yato_vis
        if self.replace:
            st.templates.clear()
        n = 0
        for d in data.get("templates", []):
            _dict_to_template(st, d)
            n += 1
        st.active_template_index = max(0, len(st.templates) - 1)
        self.report({"INFO"}, f"{n} default templates loaded")
        return {"FINISHED"}


class YATOVIS_OT_template_export_json(YatoVisOperator):
    """全テンプレを JSON ファイルにエクスポート。"""
    bl_idname = "yato_vis.template_export_json"
    bl_label = "Export Templates JSON"
    bl_description = "全テンプレを JSON ファイルにエクスポート"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):  # noqa: ARG002
        if not self.filepath:
            self.filepath = "yato_vis_templates.json"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def run(self, context):
        st = context.scene.yato_vis
        data = {
            "schema": 1,
            "templates": [_template_to_dict(t) for t in st.templates],
        }
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.report({"ERROR"}, f"書き込み失敗: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{len(st.templates)} templates exported → {self.filepath}")
        return {"FINISHED"}


class YATOVIS_OT_template_import_json(YatoVisOperator):
    """JSON ファイルからテンプレをインポート。"""
    bl_idname = "yato_vis.template_import_json"
    bl_label = "Import Templates JSON"
    bl_description = "JSON ファイルからテンプレを追加読み込み"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})
    replace: BoolProperty(name="Replace Existing", default=False)

    def invoke(self, context, event):  # noqa: ARG002
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def run(self, context):
        if not self.filepath or not os.path.isfile(self.filepath):
            self.report({"ERROR"}, "ファイルが見つかりません")
            return {"CANCELLED"}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self.report({"ERROR"}, f"JSON 読込失敗: {exc}")
            return {"CANCELLED"}
        st = context.scene.yato_vis
        if self.replace:
            st.templates.clear()
        n = 0
        for d in data.get("templates", []):
            _dict_to_template(st, d)
            n += 1
        st.active_template_index = max(0, len(st.templates) - 1)
        self.report({"INFO"}, f"{n} templates imported")
        return {"FINISHED"}

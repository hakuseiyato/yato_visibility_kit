"""キーフレーム掃除 Operator。

Kinema の `clear_unchanged_keys` を参考に、選択オブジェクトの fcurve を走査して
「値が一切変化していない」ものを削除する。Visibility 系 / Transform 系 / 全削除
の 3 系統を提供。
"""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from ._base import YatoVisOperator, selected_objects


VIS_PATHS = ("hide_viewport", "hide_render")
TRANSFORM_PATHS = (
    "location",
    "rotation_euler",
    "rotation_quaternion",
    "rotation_axis_angle",
    "scale",
)


def _iter_fcurves(action):
    """Blender 4.3 以前/4.4+ Layered Actions 両対応で (container, fcurve) を yield。

    Kinema からの流用（既存・実績ある実装）。
    """
    if action is None:
        return
    if hasattr(action, "fcurves"):
        container = action.fcurves
        for fc in list(container):
            yield container, fc
        return
    layers = getattr(action, "layers", None) or []
    slots = list(getattr(action, "slots", None) or [])
    for layer in layers:
        strips = getattr(layer, "strips", None) or []
        for strip in strips:
            for slot in slots:
                cb = None
                try:
                    cb = strip.channelbag(slot)
                except Exception:
                    try:
                        cb = strip.channelbag(slot, ensure=False)
                    except Exception:
                        cb = None
                if cb is None:
                    continue
                container = getattr(cb, "fcurves", None)
                if container is None:
                    continue
                for fc in list(container):
                    yield container, fc


def _is_fcurve_unchanged(fc, epsilon: float = 1e-6) -> bool:
    kps = fc.keyframe_points
    if not kps:
        return False
    if len(kps) < 2:
        # 単一キーは「変化なし」だが消すと初期値が失われるので残す
        return False
    values = [kp.co.y for kp in kps]
    return (max(values) - min(values)) < epsilon


def _delete_matching(obj, paths: tuple[str, ...], mode: str) -> int:
    """obj.animation_data.action から data_path が paths のいずれかで始まる fcurve を削除。

    mode:
      REDUNDANT: 値が変化していない fcurve だけ削除
      ALL:       マッチする fcurve を丸ごと削除
    """
    if obj is None or obj.animation_data is None or obj.animation_data.action is None:
        return 0
    action = obj.animation_data.action
    removed = 0
    for container, fc in _iter_fcurves(action):
        try:
            dp = fc.data_path
        except Exception:
            continue
        if not any(dp == p or dp.startswith(p + "[") or dp.startswith(p + ".") for p in paths):
            continue
        if mode == "REDUNDANT" and not _is_fcurve_unchanged(fc):
            continue
        try:
            container.remove(fc)
            removed += 1
        except Exception:
            pass
    return removed


class YATOVIS_OT_clear_keys(YatoVisOperator):
    """選択オブジェクトの fcurve を掃除する統合 Operator。"""
    bl_idname = "yato_vis.clear_keys"
    bl_label = "Clear Keys"
    bl_description = "選択オブジェクトの fcurve を掃除"

    scope: EnumProperty(
        items=(
            ("VIS_REDUNDANT", "Visibility (Redundant)", "値が変化していない hide_viewport/hide_render のキーを削除"),
            ("VIS_ALL", "Visibility (All)", "hide_viewport/hide_render の fcurve を丸ごと削除"),
            ("TF_REDUNDANT", "Transform (Redundant)", "値が変化していない loc/rot/scale のキーを削除"),
            ("TF_ALL", "Transform (All)", "loc/rot/scale の fcurve を丸ごと削除"),
        ),
        default="VIS_REDUNDANT",
    )

    def invoke(self, context, event):  # noqa: ARG002
        if self.scope.endswith("_ALL"):
            return context.window_manager.invoke_props_dialog(self, width=380)
        return self.execute(context)

    def draw(self, context):  # noqa: ARG002
        layout = self.layout
        layout.label(text="Clear Keys", icon="KEY_DEHLT")
        layout.separator()
        if self.scope == "VIS_ALL":
            layout.label(text="hide_viewport / hide_render の fcurve を丸ごと削除します。")
        elif self.scope == "TF_ALL":
            layout.label(text="location / rotation / scale の fcurve を丸ごと削除します。")
        layout.label(text="（Ctrl+Z で取り消せます）", icon="INFO")

    def run(self, context):
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        if self.scope.startswith("VIS"):
            paths = VIS_PATHS
        else:
            paths = TRANSFORM_PATHS
        mode = "REDUNDANT" if self.scope.endswith("_REDUNDANT") else "ALL"
        total = 0
        for o in objs:
            total += _delete_matching(o, paths, mode)
        if total == 0:
            self.report({"INFO"}, "削除対象の fcurve はありませんでした")
        else:
            self.report({"INFO"}, f"Cleanup: {total} fcurves removed ({mode}, {self.scope})")
        return {"FINISHED"}

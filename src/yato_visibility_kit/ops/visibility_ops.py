"""Visibility 操作。

トグルは「全揃え方式」:
  - 1 個でも hide=True があれば → 全て show (False) に
  - 全て show なら → 全て hide (True) に

Auto KF ON 時は変更後の値をキーフレームに記録する。
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty

from ._base import YatoVisOperator, selected_objects


TARGET_ITEMS = (
    ("VIEWPORT", "Viewport", "hide_viewport", "RESTRICT_VIEW_OFF", 0),
    ("RENDER", "Render", "hide_render", "RESTRICT_RENDER_OFF", 1),
    ("SELECT", "Selectable", "hide_select", "RESTRICT_SELECT_OFF", 2),
    ("BOTH", "Viewport+Render", "両方", "HIDE_OFF", 3),
)

MODE_ITEMS = (
    ("TOGGLE", "Toggle", "全揃え方式でトグル", "ARROW_LEFTRIGHT", 0),
    ("SHOW", "Show", "全て表示 (hide=False)", "HIDE_OFF", 1),
    ("HIDE", "Hide", "全て非表示 (hide=True)", "HIDE_ON", 2),
)


_ATTR_MAP = {
    "VIEWPORT": ("hide_viewport",),
    "RENDER": ("hide_render",),
    "SELECT": ("hide_select",),
    "BOTH": ("hide_viewport", "hide_render"),
}

# Auto KF 対象（hide_select は f-curve に乗らないので除外）
_KEYABLE_ATTRS = ("hide_viewport", "hide_render")


def apply_visibility(objs, attrs, mode: str, insert_keyframe: bool = False, frame: int | None = None) -> int:
    """objs に対し attrs (タプル) を mode に従って一括変更。変更件数を返す。

    mode:
      TOGGLE: いずれかの attr が True なら全 False に、全 False なら全 True に
      SHOW:   全て False
      HIDE:   全て True
    """
    if not objs or not attrs:
        return 0
    if mode == "TOGGLE":
        any_hidden = any(getattr(o, a, False) for o in objs for a in attrs)
        new_value = not any_hidden
    elif mode == "SHOW":
        new_value = False
    elif mode == "HIDE":
        new_value = True
    else:
        return 0

    changed = 0
    for o in objs:
        for a in attrs:
            if getattr(o, a, None) is None:
                continue
            if getattr(o, a) != new_value:
                setattr(o, a, new_value)
                changed += 1
            if insert_keyframe and a in _KEYABLE_ATTRS:
                try:
                    o.keyframe_insert(data_path=a, frame=frame)
                except Exception:
                    pass
    return changed


def _should_keyframe(context) -> bool:
    ts = context.scene.tool_settings
    return bool(getattr(ts, "use_keyframe_insert_auto", False))


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class YATOVIS_OT_set_visibility(YatoVisOperator):
    """選択オブジェクトの可視性を一括変更。"""
    bl_idname = "yato_vis.set_visibility"
    bl_label = "Set Visibility"
    bl_description = "選択オブジェクトの hide_viewport / hide_render / hide_select を一括変更"

    target: EnumProperty(items=TARGET_ITEMS, default="VIEWPORT")
    mode: EnumProperty(items=MODE_ITEMS, default="TOGGLE")
    insert_keyframe: BoolProperty(
        name="Insert Keyframe",
        description="変更後の値をキーフレームに記録（hide_select は対象外）",
        default=False,
    )

    def run(self, context):
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        attrs = _ATTR_MAP.get(self.target, ())
        kf = self.insert_keyframe or _should_keyframe(context)
        frame = context.scene.frame_current if kf else None
        changed = apply_visibility(objs, attrs, self.mode, insert_keyframe=kf, frame=frame)
        label = dict((k, v) for k, v, *_ in [(i[0], i[1]) for i in TARGET_ITEMS]).get(
            self.target, self.target
        )
        kf_str = " +KF" if kf else ""
        self.report({"INFO"}, f"{label}: {self.mode} on {len(objs)} object(s), {changed} changed{kf_str}")
        return {"FINISHED"}


class YATOVIS_OT_toggle_auto_keyframe(YatoVisOperator):
    """Blender 標準の Auto Keyframe (赤丸) をトグル。"""
    bl_idname = "yato_vis.toggle_auto_keyframe"
    bl_label = "Toggle Auto Keyframe"
    bl_description = "タイムラインの赤丸 Auto Keyframe を ON/OFF"

    def run(self, context):
        ts = context.scene.tool_settings
        ts.use_keyframe_insert_auto = not ts.use_keyframe_insert_auto
        state = "ON" if ts.use_keyframe_insert_auto else "OFF"
        self.report({"INFO"}, f"Auto Keyframe {state}")
        return {"FINISHED"}


class YATOVIS_OT_key_all(YatoVisOperator):
    """選択オブジェクトの location / rotation / scale を一括キー。

    Active Object パネルに表示されている Transform 値をワンクリックでキーフレーム化する。
    hide_viewport / hide_render は Burst / Templates / Quick Toggle 側で扱うため
    本 Operator では触らない。
    rotation は obj.rotation_mode に従って euler / quaternion / axis_angle を自動選択。
    """
    bl_idname = "yato_vis.key_all"
    bl_label = "Key All"
    bl_description = (
        "選択オブジェクトの location / rotation / scale を現フレームに一括キーフレーム挿入"
        "（Visibility キーには干渉しない）"
    )

    def run(self, context):
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        frame = context.scene.frame_current
        count = 0
        for o in objs:
            tf_paths = ["location", "scale"]
            mode = getattr(o, "rotation_mode", "XYZ")
            if mode == "QUATERNION":
                tf_paths.append("rotation_quaternion")
            elif mode == "AXIS_ANGLE":
                tf_paths.append("rotation_axis_angle")
            else:
                tf_paths.append("rotation_euler")
            for p in tf_paths:
                try:
                    o.keyframe_insert(data_path=p, frame=frame)
                    count += 1
                except Exception:
                    pass
        self.report({"INFO"}, f"{count} transform keys inserted @ frame {frame}")
        return {"FINISHED"}

"""Burst パターンの Operator。

「ここからここまで非表示/表示」を 1 操作で実現する。

Burst パターン:
  F-1: prev_state (anchor)
  F:   new_state  (change)
  F+D: new_state  (hold)
  F+D+1: prev_state (return)

全キーは CONSTANT 補間で挿入。F-1 anchor の prev_state は、操作時点の
obj.hide_viewport 等の現在値から決定する。

Camera Range 版:
  現フレームがどのカメラマーカーのバインド範囲にあるかを判定し、
  その範囲 [A, B-1] に対して下記キーを置く。
    A-1:  prev_state (anchor before head)
    A:    new_state
    B-1:  new_state (hold)
    B:    prev_state (return at tail+1)
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty

from ._base import YatoVisOperator, selected_objects


# hide_viewport / hide_render 両対応
_CHANNELS_MAP = {
    "VIEWPORT": ("hide_viewport",),
    "RENDER": ("hide_render",),
    "BOTH": ("hide_viewport", "hide_render"),
}

TARGET_ITEMS = (
    ("VIEWPORT", "Viewport", "hide_viewport のみ", "RESTRICT_VIEW_OFF", 0),
    ("RENDER", "Render", "hide_render のみ", "RESTRICT_RENDER_OFF", 1),
    ("BOTH", "Viewport+Render", "両方", "HIDE_OFF", 2),
)

STATE_ITEMS = (
    ("HIDE", "Hide", "新状態 = 非表示 (True)"),
    ("SHOW", "Show", "新状態 = 表示 (False)"),
)


def _iter_action_fcurves(action):
    """4.3 以前 / 4.4+ Layered Action 両対応で fcurve を yield。"""
    if action is None:
        return
    if hasattr(action, "fcurves"):
        for fc in list(action.fcurves):
            yield fc
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
                    yield fc


def insert_visibility_key(obj, channel: str, frame: int, value: bool, interpolation: str = "CONSTANT") -> None:
    """obj の channel (hide_viewport/hide_render) に frame で value のキーを打つ。

    setattr → keyframe_insert → 補間設定 → setattr で元値復元 の順。
    元値復元しても fcurve に他キーがなければ frame 評価で value に戻るので、
    視覚上は新状態に従う（これは想定通り）。
    """
    if obj is None:
        return
    if getattr(obj, channel, None) is None:
        return
    saved = getattr(obj, channel)
    try:
        setattr(obj, channel, value)
        try:
            obj.keyframe_insert(data_path=channel, frame=frame)
        except Exception:
            pass
    finally:
        # fcurve に key が打たれていれば、現フレームでの評価は fcurve に任せて OK
        # ただし元値書き換えに伴う side-effect を避けるためここで戻す
        try:
            setattr(obj, channel, saved)
        except Exception:
            pass

    # 挿入したキーの補間を設定
    ad = obj.animation_data
    if ad is None or ad.action is None:
        return
    for fc in _iter_action_fcurves(ad.action):
        try:
            if fc.data_path != channel:
                continue
        except Exception:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 0.5:
                try:
                    kp.interpolation = interpolation
                except Exception:
                    pass
                break


def _apply_burst(obj, channels: tuple, start: int, end: int, new_state: bool) -> int:
    """1 オブジェクトに対して Burst パターンを適用。挿入キー数を返す。

    start: 新状態の最初のフレーム
    end:   新状態の最後のフレーム (start <= end)
    """
    n = 0
    for ch in channels:
        prev_state = bool(getattr(obj, ch, False))
        # F-1 anchor (prev_state)
        insert_visibility_key(obj, ch, start - 1, prev_state, "CONSTANT")
        # F new_state
        insert_visibility_key(obj, ch, start, new_state, "CONSTANT")
        # F+D hold
        if end > start:
            insert_visibility_key(obj, ch, end, new_state, "CONSTANT")
        # F+D+1 return
        insert_visibility_key(obj, ch, end + 1, prev_state, "CONSTANT")
        n += 4 if end > start else 3
    return n


def _find_current_camera_range(scene, frame: int) -> tuple[int, int] | None:
    """現フレームがどのカメラマーカー区間に含まれるかを判定し (start, end) を返す。

    Blender の camera binding は `scene.timeline_markers` のうち `.camera` が
    セットされたものに従う。アクティブなマーカーは「現フレーム以下で最大の frame」。
    range の end は「次のカメラマーカー frame - 1」、なければ scene.frame_end。

    カメラマーカーが 1 つもない場合 None を返す。
    """
    cam_markers = sorted(
        (m for m in scene.timeline_markers if m.camera is not None),
        key=lambda m: m.frame,
    )
    if not cam_markers:
        return None
    active = None
    for m in cam_markers:
        if m.frame <= frame:
            active = m
        else:
            break
    if active is None:
        active = cam_markers[0]
    idx = cam_markers.index(active)
    start = active.frame
    if idx + 1 < len(cam_markers):
        end = cam_markers[idx + 1].frame - 1
    else:
        end = scene.frame_end
    if end < start:
        end = start
    return (start, end)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class YATOVIS_OT_burst(YatoVisOperator):
    """現フレーム起点で Burst パターンキーを挿入。"""
    bl_idname = "yato_vis.burst"
    bl_label = "Burst Visibility"
    bl_description = (
        "現フレーム F を起点に、F-1 に prev_state, F に new_state, "
        "F+duration に hold, F+duration+1 に prev_state のキーを挿入"
    )

    state: EnumProperty(items=STATE_ITEMS, default="HIDE")
    target: EnumProperty(items=TARGET_ITEMS, default="BOTH")
    duration: IntProperty(default=10, min=1, soft_max=240)
    use_scene_duration: BoolProperty(
        name="Use Scene duration",
        description="Scene.yato_vis.burst_duration を使う（OFF なら operator の duration プロパティを使う）",
        default=True,
    )

    def run(self, context):
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        scene = context.scene
        dur = scene.yato_vis.burst_duration if self.use_scene_duration else self.duration
        start = scene.frame_current
        end = start + max(0, dur)
        new_state = (self.state == "HIDE")
        channels = _CHANNELS_MAP.get(self.target, ())
        total = 0
        for o in objs:
            total += _apply_burst(o, channels, start, end, new_state)
        self.report(
            {"INFO"},
            f"Burst {self.state} [{start-1}/{start} … {end}/{end+1}]: {total} keys on {len(objs)} object(s)",
        )
        return {"FINISHED"}


class YATOVIS_OT_set_range_frame(YatoVisOperator):
    """range_start / range_end のいずれかを現フレームで上書き。"""
    bl_idname = "yato_vis.set_range_frame"
    bl_label = "Set Range Frame"
    bl_description = "現フレームを Range Start / End に記録"

    which: EnumProperty(
        items=(("START", "Start", ""), ("END", "End", "")),
        default="START",
    )

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        f = scene.frame_current
        if self.which == "START":
            st.range_start = f
        else:
            st.range_end = f
        self.report({"INFO"}, f"Range {self.which} = {f}")
        return {"FINISHED"}


class YATOVIS_OT_jump_to_range_frame(YatoVisOperator):
    """range_start / range_end のフレームへタイムラインをジャンプ。"""
    bl_idname = "yato_vis.jump_to_range_frame"
    bl_label = "Jump to Range Frame"
    bl_description = "Range Start / End のフレームへタイムラインをジャンプ"

    which: EnumProperty(
        items=(("START", "Start", ""), ("END", "End", "")),
        default="START",
    )

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        target = st.range_start if self.which == "START" else st.range_end
        scene.frame_set(target)
        return {"FINISHED"}


class YATOVIS_OT_burst_range(YatoVisOperator):
    """明示 Start/End 指定で Burst パターンを適用（出現/退場レンジ）。

    Start-1 / Start / End / End+1 の 4 キー（Start==End なら 3 キー）を
    CONSTANT 補間で挿入。Auto KF とは独立に必ずキー挿入する。
    """
    bl_idname = "yato_vis.burst_range"
    bl_label = "Burst Range"
    bl_description = (
        "Range Start から Range End まで Show または Hide。"
        "Start-1 / Start / End / End+1 の 4 キーを CONSTANT で挿入"
    )

    state: EnumProperty(items=STATE_ITEMS, default="SHOW")
    target: EnumProperty(items=TARGET_ITEMS, default="BOTH")

    def run(self, context):
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        scene = context.scene
        st = scene.yato_vis
        start = int(st.range_start)
        end = int(st.range_end)
        if end < start:
            start, end = end, start
        new_state = (self.state == "HIDE")
        channels = _CHANNELS_MAP.get(self.target, ())
        total = 0
        for o in objs:
            total += _apply_burst(o, channels, start, end, new_state)
        self.report(
            {"INFO"},
            f"Range {self.state} [{start-1}/{start} … {end}/{end+1}]: {total} keys on {len(objs)} obj(s)",
        )
        return {"FINISHED"}


class YATOVIS_OT_burst_camera_range(YatoVisOperator):
    """現在のカメラバインド区間 [A, B-1] に対し Burst パターンキーを挿入。

    A-1 / A / B-1 / B にキーを置く。
    """
    bl_idname = "yato_vis.burst_camera_range"
    bl_label = "Burst (Camera Range)"
    bl_description = (
        "現フレームを含むカメラマーカー区間 [A, B-1] にBurst パターンキーを挿入。"
        "A-1 / A / B-1 / B にキーを置く（カメラ切替の前後で元状態に戻す）"
    )

    state: EnumProperty(items=STATE_ITEMS, default="HIDE")
    target: EnumProperty(items=TARGET_ITEMS, default="BOTH")

    def run(self, context):
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        scene = context.scene
        rng = _find_current_camera_range(scene, scene.frame_current)
        if rng is None:
            self.report({"WARNING"}, "カメラ付き Timeline Marker が見つかりません")
            return {"CANCELLED"}
        start, end = rng
        new_state = (self.state == "HIDE")
        channels = _CHANNELS_MAP.get(self.target, ())
        total = 0
        for o in objs:
            total += _apply_burst(o, channels, start, end, new_state)
        self.report(
            {"INFO"},
            f"Burst {self.state} cam-range [{start-1}/{start} … {end}/{end+1}]: {total} keys on {len(objs)} obj(s)",
        )
        return {"FINISHED"}

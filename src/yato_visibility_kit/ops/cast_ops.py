"""Shot Cast — Camera Marker をショットとみなし、Group ごとに出演ショットを設定。

Bake ロジック:
  - Camera Marker をフレーム順に並べる
  - 各 Group について、各 marker 時点での「出演フラグ」を判定（marker_name が
    group.cast_markers に含まれていれば True）
  - 出演フラグが直前と異なる、または最初の marker のとき、hide_viewport と
    hide_render に CONSTANT 補間でキー挿入。連続する同値は省略（CONSTANT が
    値を保持するので冗長キーは不要）
  - Group の COLLECTION メンバはサブコレクション再帰展開した全オブジェクトに
    対して同じパターンを適用（Solo モードは無関係）

UI トグル時の自動 Bake は scene.yato_vis.cast_auto_bake で制御。
"""

from __future__ import annotations

import bpy
from bpy.props import IntProperty, StringProperty

from ._base import YatoVisOperator
from .group_ops import group_all_objects


def _get_camera_markers(scene):
    """カメラ付き Timeline Marker を frame 昇順で返す。"""
    return sorted(
        (m for m in scene.timeline_markers if m.camera is not None),
        key=lambda m: m.frame,
    )


def _group_appears_in(group, marker_name: str) -> bool:
    for c in group.cast_markers:
        if c.marker_name == marker_name:
            return True
    return False


def _set_group_appearance(group, marker_name: str, appears: bool) -> None:
    """group.cast_markers を marker_name について appears 状態に揃える。"""
    existing_idx = -1
    for i, c in enumerate(group.cast_markers):
        if c.marker_name == marker_name:
            existing_idx = i
            break
    if appears:
        if existing_idx < 0:
            entry = group.cast_markers.add()
            entry.marker_name = marker_name
    else:
        if existing_idx >= 0:
            group.cast_markers.remove(existing_idx)


def _insert_visibility_key(obj, channel: str, frame: int, value: bool) -> None:
    """obj.channel に frame で value を CONSTANT 補間でキー挿入。"""
    if obj is None or getattr(obj, channel, None) is None:
        return
    saved = getattr(obj, channel)
    try:
        setattr(obj, channel, value)
        try:
            obj.keyframe_insert(data_path=channel, frame=frame)
        except Exception:
            pass
    finally:
        try:
            setattr(obj, channel, saved)
        except Exception:
            pass
    # CONSTANT 補間に
    ad = obj.animation_data
    if ad is None or ad.action is None:
        return
    action = ad.action
    fcurves_iter = []
    if hasattr(action, "fcurves"):
        fcurves_iter = list(action.fcurves)
    else:
        # Layered Actions
        for layer in getattr(action, "layers", None) or []:
            for strip in getattr(layer, "strips", None) or []:
                for slot in getattr(action, "slots", None) or []:
                    try:
                        cb = strip.channelbag(slot)
                    except Exception:
                        cb = None
                    if cb is None:
                        continue
                    fcurves_iter.extend(getattr(cb, "fcurves", []) or [])
    for fc in fcurves_iter:
        try:
            if fc.data_path != channel:
                continue
        except Exception:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 0.5:
                try:
                    kp.interpolation = "CONSTANT"
                except Exception:
                    pass
                break


def bake_group_cast(scene, group) -> tuple[int, int]:
    """1 Group の cast_markers を hide_viewport / hide_render キーへ反映。

    Shot Cast 優先: 既存の hide_viewport / hide_render fcurve は一度全削除してから
    cast_markers に従って CONSTANT 補間で再構築する。

    Returns: (cleared_fcurves, inserted_keys)
    """
    markers = _get_camera_markers(scene)
    if not markers:
        return (0, 0)
    objs = group_all_objects(group)
    if not objs:
        return (0, 0)
    # 1. 既存の hide_viewport / hide_render fcurve を全削除（Shot Cast を権威に）
    from .keyframe_ops import _delete_matching
    cleared = 0
    for o in objs:
        cleared += _delete_matching(o, ("hide_viewport", "hide_render"), "ALL")
    # 2. cast_markers に従ってキー再挿入
    inserted = 0
    for o in objs:
        prev_visible = None
        for m in markers:
            visible = _group_appears_in(group, m.name)
            if prev_visible is None or visible != prev_visible:
                _insert_visibility_key(o, "hide_viewport", m.frame, not visible)
                _insert_visibility_key(o, "hide_render", m.frame, not visible)
                inserted += 2
            prev_visible = visible
    return (cleared, inserted)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class YATOVIS_OT_cast_toggle(YatoVisOperator):
    """Group の cast_markers をトグル（指定 marker 名で出演 ON/OFF）。

    cast_auto_bake が True なら同時に Bake も実行。
    """
    bl_idname = "yato_vis.cast_toggle"
    bl_label = "Toggle Cast"
    bl_description = "Group の出演 marker をトグル（cast_auto_bake が ON なら同時に Bake）"

    group_index: IntProperty(default=-1)
    marker_name: StringProperty(default="")

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            return {"CANCELLED"}
        if not self.marker_name:
            return {"CANCELLED"}
        g = st.groups[idx]
        currently = _group_appears_in(g, self.marker_name)
        _set_group_appearance(g, self.marker_name, not currently)
        if st.cast_auto_bake:
            cleared, inserted = bake_group_cast(scene, g)
            self.report(
                {"INFO"},
                f"'{g.name}' @ '{self.marker_name}' → "
                f"{'ON' if not currently else 'OFF'}, "
                f"re-baked ({cleared} cleared / {inserted} keys)",
            )
        else:
            self.report(
                {"INFO"},
                f"'{g.name}' @ '{self.marker_name}' → {'ON' if not currently else 'OFF'} (not baked)",
            )
        return {"FINISHED"}


class YATOVIS_OT_cast_bake_group(YatoVisOperator):
    """指定 Group の cast 設定を hide_viewport / hide_render キーへ反映。"""
    bl_idname = "yato_vis.cast_bake_group"
    bl_label = "Bake Cast"
    bl_description = "アクティブ Group の cast 設定を hide_viewport / hide_render キーへ反映"

    group_index: IntProperty(default=-1)

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            self.report({"WARNING"}, "Group が選択されていません")
            return {"CANCELLED"}
        g = st.groups[idx]
        cleared, inserted = bake_group_cast(scene, g)
        self.report(
            {"INFO"},
            f"Re-baked '{g.name}': {cleared} fcurves cleared, {inserted} keys inserted",
        )
        return {"FINISHED"}


class YATOVIS_OT_cast_bake_all(YatoVisOperator):
    """全 Group の cast 設定を一括 Bake。"""
    bl_idname = "yato_vis.cast_bake_all"
    bl_label = "Bake All Cast"
    bl_description = "全 Group の cast 設定を hide_viewport / hide_render キーへ反映"

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        total_cleared = 0
        total_inserted = 0
        for g in st.groups:
            cleared, inserted = bake_group_cast(scene, g)
            total_cleared += cleared
            total_inserted += inserted
        self.report(
            {"INFO"},
            f"Re-baked {len(st.groups)} group(s): "
            f"{total_cleared} fcurves cleared, {total_inserted} keys inserted",
        )
        return {"FINISHED"}


class YATOVIS_OT_cast_clear_group(YatoVisOperator):
    """指定 Group の hide_viewport / hide_render fcurve を全削除。"""
    bl_idname = "yato_vis.cast_clear_group"
    bl_label = "Clear Visibility Keys"
    bl_description = "Group メンバの hide_viewport / hide_render fcurve を丸ごと削除"

    group_index: IntProperty(default=-1)

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            return {"CANCELLED"}
        g = st.groups[idx]
        from .keyframe_ops import _delete_matching
        total = 0
        for o in group_all_objects(g):
            total += _delete_matching(o, ("hide_viewport", "hide_render"), "ALL")
        self.report({"INFO"}, f"Cleared '{g.name}': {total} fcurves")
        return {"FINISHED"}


def get_visibility_keyframes(obj) -> list[tuple[str, int]]:
    """obj の hide_viewport / hide_render の全キーフレーム frame を返す。

    結果: [(channel, frame), ...] 重複なし、frame 昇順。
    """
    out: set[tuple[str, int]] = set()
    ad = getattr(obj, "animation_data", None)
    if ad is None or ad.action is None:
        return []
    action = ad.action
    fcurves_iter = []
    if hasattr(action, "fcurves"):
        fcurves_iter = list(action.fcurves)
    else:
        for layer in getattr(action, "layers", None) or []:
            for strip in getattr(layer, "strips", None) or []:
                for slot in getattr(action, "slots", None) or []:
                    try:
                        cb = strip.channelbag(slot)
                    except Exception:
                        cb = None
                    if cb is None:
                        continue
                    fcurves_iter.extend(getattr(cb, "fcurves", []) or [])
    for fc in fcurves_iter:
        try:
            dp = fc.data_path
        except Exception:
            continue
        if dp not in ("hide_viewport", "hide_render"):
            continue
        for kp in fc.keyframe_points:
            out.add((dp, int(round(kp.co.x))))
    return sorted(out, key=lambda x: (x[1], x[0]))


def _eval_hide_viewport_at(obj, frame: int) -> bool:
    """obj の hide_viewport を指定フレームで評価。

    fcurve があれば fcurve.evaluate を使い、なければ現在値を返す。
    scene.frame_set を呼ばないので副作用なし。
    """
    if obj is None:
        return False
    ad = getattr(obj, "animation_data", None)
    if ad is not None and ad.action is not None:
        action = ad.action
        fcurves_iter = []
        if hasattr(action, "fcurves"):
            fcurves_iter = list(action.fcurves)
        else:
            for layer in getattr(action, "layers", None) or []:
                for strip in getattr(layer, "strips", None) or []:
                    for slot in getattr(action, "slots", None) or []:
                        try:
                            cb = strip.channelbag(slot)
                        except Exception:
                            cb = None
                        if cb is None:
                            continue
                        fcurves_iter.extend(getattr(cb, "fcurves", []) or [])
        for fc in fcurves_iter:
            try:
                if fc.data_path == "hide_viewport":
                    return bool(fc.evaluate(frame) >= 0.5)
            except Exception:
                continue
    return bool(getattr(obj, "hide_viewport", False))


class YATOVIS_OT_cast_import_from_visibility(YatoVisOperator):
    """各カメラマーカー先頭フレームでの可視状態から cast_markers を逆取り込み。

    各 Group の所属オブジェクトについて、marker.frame での hide_viewport を
    fcurve.evaluate で評価し、1 個でも可視 (False) なら "出演" と判定。
    既存の cast_markers は全置換される（手動設定が消えるので明示操作のみ）。
    """
    bl_idname = "yato_vis.cast_import_from_visibility"
    bl_label = "Import Cast from Visibility"
    bl_description = (
        "各カメラマーカー先頭フレームで hide_viewport を評価し、"
        "各 Group の cast_markers に逆取り込み（既存設定は全置換）"
    )

    def invoke(self, context, event):  # noqa: ARG002
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):  # noqa: ARG002
        layout = self.layout
        layout.label(text="現在のアニメーションから Cast 設定を取り込みます", icon="IMPORT")
        layout.label(text="既存の cast_markers は全置換されます", icon="ERROR")

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        markers = _get_camera_markers(scene)
        if not markers:
            self.report({"WARNING"}, "カメラ付き Timeline Marker がありません")
            return {"CANCELLED"}
        if len(st.groups) == 0:
            self.report({"WARNING"}, "Group がありません")
            return {"CANCELLED"}
        total_on = 0
        for g in st.groups:
            objs = group_all_objects(g)
            if not objs:
                # 空 Group はスキップ
                continue
            g.cast_markers.clear()
            for m in markers:
                # 1 個でも可視ならこの shot に出演
                any_visible = any(not _eval_hide_viewport_at(o, m.frame) for o in objs)
                if any_visible:
                    entry = g.cast_markers.add()
                    entry.marker_name = m.name
                    total_on += 1
        self.report(
            {"INFO"},
            f"Imported cast: {total_on} ON cells across {len(st.groups)} group(s) × {len(markers)} shot(s)",
        )
        return {"FINISHED"}


class YATOVIS_OT_jump_to_keyframe(YatoVisOperator):
    """指定フレームへタイムラインジャンプ（hide_* キー探索用）。"""
    bl_idname = "yato_vis.jump_to_keyframe"
    bl_label = "Jump to Keyframe"
    bl_description = "指定フレームへタイムラインをジャンプ"

    frame: IntProperty(default=0)

    def run(self, context):
        context.scene.frame_set(self.frame)
        return {"FINISHED"}

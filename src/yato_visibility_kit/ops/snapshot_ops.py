"""Transform Snapshot Operator。

matrix_basis (parent local) を 16 float で保存し、復元時は
`obj.matrix_basis = ...` で書き戻す。rotation_mode 非依存。

Restore に insert_keyframe フラグを持たせ、Auto KF 連動と
明示的なキー打ちを両立。
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from mathutils import Matrix

from ._base import YatoVisOperator, selected_objects


def _mat_to_flat(m) -> list[float]:
    """Matrix を行優先 16 float のフラットリストに。"""
    return [m[i][j] for i in range(4) for j in range(4)]


def _flat_to_mat(flat) -> Matrix:
    m = Matrix.Identity(4)
    for i in range(4):
        for j in range(4):
            m[i][j] = flat[i * 4 + j]
    return m


def _save_object(entry, obj) -> None:
    entry.object_ref = obj
    entry.matrix_basis = _mat_to_flat(obj.matrix_basis)
    entry.matrix_world = _mat_to_flat(obj.matrix_world)


def _restore_object(entry, obj, insert_keyframe: bool = False, frame: int | None = None) -> None:
    m = _flat_to_mat(entry.matrix_basis)
    obj.matrix_basis = m
    if insert_keyframe:
        for path in ("location", "rotation_euler", "rotation_quaternion", "scale"):
            try:
                obj.keyframe_insert(data_path=path, frame=frame)
            except Exception:
                pass


def _should_keyframe(context) -> bool:
    return bool(getattr(context.scene.tool_settings, "use_keyframe_insert_auto", False))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class YATOVIS_OT_snapshot_create(YatoVisOperator):
    bl_idname = "yato_vis.snapshot_create"
    bl_label = "Create Snapshot"
    bl_description = "選択オブジェクトの現在の Transform を新規 Snapshot に保存"

    name: StringProperty(name="Name", default="Snapshot")

    def invoke(self, context, event):  # noqa: ARG002
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):  # noqa: ARG002
        self.layout.prop(self, "name")

    def run(self, context):
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        st = context.scene.yato_vis
        snap = st.snapshots.add()
        snap.name = self.name or "Snapshot"
        for o in objs:
            e = snap.entries.add()
            _save_object(e, o)
        st.active_snapshot_index = len(st.snapshots) - 1
        self.report({"INFO"}, f"Snapshot '{snap.name}' saved ({len(snap.entries)} entries)")
        return {"FINISHED"}


class YATOVIS_OT_snapshot_overwrite(YatoVisOperator):
    bl_idname = "yato_vis.snapshot_overwrite"
    bl_label = "Overwrite Snapshot"
    bl_description = "アクティブ Snapshot を選択オブジェクトの現在 Transform で上書き"

    def run(self, context):
        st = context.scene.yato_vis
        idx = st.active_snapshot_index
        if not (0 <= idx < len(st.snapshots)):
            self.report({"WARNING"}, "Snapshot が選択されていません")
            return {"CANCELLED"}
        objs = selected_objects(context)
        if not objs:
            self.report({"WARNING"}, "オブジェクトが選択されていません")
            return {"CANCELLED"}
        snap = st.snapshots[idx]
        snap.entries.clear()
        for o in objs:
            e = snap.entries.add()
            _save_object(e, o)
        self.report({"INFO"}, f"Snapshot '{snap.name}' overwritten ({len(snap.entries)} entries)")
        return {"FINISHED"}


class YATOVIS_OT_snapshot_remove(YatoVisOperator):
    bl_idname = "yato_vis.snapshot_remove"
    bl_label = "Remove Snapshot"
    bl_description = "アクティブ Snapshot を削除"

    def run(self, context):
        st = context.scene.yato_vis
        idx = st.active_snapshot_index
        if not (0 <= idx < len(st.snapshots)):
            self.report({"WARNING"}, "Snapshot が選択されていません")
            return {"CANCELLED"}
        name = st.snapshots[idx].name
        st.snapshots.remove(idx)
        st.active_snapshot_index = max(0, min(idx, len(st.snapshots) - 1))
        self.report({"INFO"}, f"Snapshot '{name}' removed")
        return {"FINISHED"}


class YATOVIS_OT_snapshot_restore(YatoVisOperator):
    bl_idname = "yato_vis.snapshot_restore"
    bl_label = "Restore Snapshot"
    bl_description = "Snapshot の Transform を対象オブジェクトに復元"

    scope: EnumProperty(
        items=(
            ("ALL", "All Entries", "Snapshot に含まれる全オブジェクトを復元"),
            ("SELECTED", "Selected Only", "Snapshot ∩ 現在選択中のオブジェクトのみ復元"),
        ),
        default="ALL",
    )
    insert_keyframe: BoolProperty(
        name="Insert Keyframe",
        description="復元と同時に loc/rot/scale にキー挿入（Auto KF ON でも適用）",
        default=False,
    )

    def run(self, context):
        st = context.scene.yato_vis
        idx = st.active_snapshot_index
        if not (0 <= idx < len(st.snapshots)):
            self.report({"WARNING"}, "Snapshot が選択されていません")
            return {"CANCELLED"}
        snap = st.snapshots[idx]
        sel_names = {o.name for o in selected_objects(context)}
        kf = self.insert_keyframe or _should_keyframe(context)
        frame = context.scene.frame_current if kf else None
        restored = 0
        skipped = 0
        for e in snap.entries:
            o = e.object_ref
            if o is None:
                skipped += 1
                continue
            if self.scope == "SELECTED" and o.name not in sel_names:
                continue
            try:
                _restore_object(e, o, insert_keyframe=kf, frame=frame)
                restored += 1
            except Exception:
                skipped += 1
        kf_str = " +KF" if kf else ""
        msg = f"Restore '{snap.name}': {restored} restored"
        if skipped:
            msg += f", {skipped} skipped (dead refs)"
        msg += kf_str
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class YATOVIS_OT_snapshot_clean_dead_refs(YatoVisOperator):
    bl_idname = "yato_vis.snapshot_clean_dead_refs"
    bl_label = "Clean Dead Snapshot Refs"
    bl_description = "全 Snapshot から削除済みオブジェクト参照を取り除く"

    def run(self, context):
        st = context.scene.yato_vis
        removed = 0
        for snap in st.snapshots:
            i = len(snap.entries) - 1
            while i >= 0:
                if snap.entries[i].object_ref is None:
                    snap.entries.remove(i)
                    removed += 1
                i -= 1
        self.report({"INFO"}, f"{removed} dead entry(ies) removed")
        return {"FINISHED"}

"""PropertyGroup 定義。

データモデル:
  Scene.yato_vis (YatoVisSceneSettings)
    ├ groups: CollectionProperty(YatoVisGroup)
    │   ├ members: CollectionProperty(YatoVisGroupMember)
    │   │   member_type ∈ {OBJECT, COLLECTION}
    │   └ cast_markers: CollectionProperty(YatoVisCastMarker)
    │       Camera Marker 名のリスト。ここに含まれるショットでは Group が出演
    ├ snapshots: CollectionProperty(YatoVisTransformSnapshot)
    │   └ entries: CollectionProperty(YatoVisSnapshotEntry)
    ├ burst_duration: IntProperty (Burst hold 期間)
    └ range_start / range_end: IntProperty (出現/退場レンジ)
"""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


MEMBER_TYPE_ITEMS = (
    ("OBJECT", "Object", "単一オブジェクト参照", "OBJECT_DATA", 0),
    ("COLLECTION", "Collection", "コレクション参照（Solo モード対応）", "OUTLINER_COLLECTION", 1),
)


class YatoVisGroupMember(PropertyGroup):
    member_type: EnumProperty(
        name="Type",
        items=MEMBER_TYPE_ITEMS,
        default="OBJECT",
    )
    object_ref: PointerProperty(name="Object", type=bpy.types.Object)
    collection_ref: PointerProperty(name="Collection", type=bpy.types.Collection)
    # Collection メンバ専用: Solo モード
    solo_enabled: BoolProperty(
        name="Solo",
        description="1 オブジェクトだけ表示し、ほか全てを hide_viewport=True にする",
        default=False,
    )
    solo_target: PointerProperty(
        name="Solo Target",
        type=bpy.types.Object,
        description="Solo モード時に表示するオブジェクト",
    )


class YatoVisCastMarker(PropertyGroup):
    """Camera Marker 名の参照。Group.cast_markers の要素として「このショットに出る」を示す。"""
    marker_name: StringProperty(name="Marker", default="")


def _bound_object_poll(self, obj):
    """Group の COLLECTION メンバ内のオブジェクトのみ選択可能にする。"""
    for m in self.members:
        if m.member_type == "COLLECTION" and m.collection_ref is not None:
            try:
                if obj.name in m.collection_ref.objects:
                    return True
            except Exception:
                pass
            return False
    return True


def _bound_object_update(self, context):
    """bound_object 変更時、Collection メンバの Solo target に同期 + 即適用。"""
    if self.bound_object is None:
        return
    for m in self.members:
        if m.member_type != "COLLECTION" or m.collection_ref is None:
            continue
        if self.bound_object.name not in m.collection_ref.objects:
            continue
        m.solo_target = self.bound_object
        if not m.solo_enabled:
            m.solo_enabled = True
        try:
            from ..ops.group_ops import _apply_solo  # noqa: PLC0415
            scene = getattr(context, "scene", None)
            kf = False
            frame = None
            if scene is not None:
                kf = bool(scene.tool_settings.use_keyframe_insert_auto)
                if kf:
                    frame = scene.frame_current
            _apply_solo(m, insert_keyframe=kf, frame=frame)
        except Exception:
            pass
        break


class YatoVisGroup(PropertyGroup):
    name: StringProperty(name="Name", default="Group")
    members: CollectionProperty(type=YatoVisGroupMember)
    expand: BoolProperty(default=False)
    is_auto: BoolProperty(default=False)
    bound_object: PointerProperty(
        name="Bound",
        type=bpy.types.Object,
        poll=_bound_object_poll,
        update=_bound_object_update,
        description="この Group が現在代表しているオブジェクト。"
                    "Collection メンバを持つ場合、変更すると Solo target に同期して即時表示切替",
    )
    # Shot Cast: この Group が出演する Camera Marker 名のリスト
    cast_markers: CollectionProperty(type=YatoVisCastMarker)


class YatoVisSnapshotEntry(PropertyGroup):
    object_ref: PointerProperty(name="Object", type=bpy.types.Object)
    matrix_basis: FloatVectorProperty(size=16, subtype="MATRIX")
    matrix_world: FloatVectorProperty(size=16, subtype="MATRIX")


class YatoVisTransformSnapshot(PropertyGroup):
    name: StringProperty(name="Name", default="Snapshot")
    entries: CollectionProperty(type=YatoVisSnapshotEntry)


class YatoVisSceneSettings(PropertyGroup):
    groups: CollectionProperty(type=YatoVisGroup)
    active_group_index: IntProperty(default=0)
    snapshots: CollectionProperty(type=YatoVisTransformSnapshot)
    active_snapshot_index: IntProperty(default=0)
    # Auto-detect 用: 親コレクション名
    parent_collection_name: StringProperty(
        name="Parent Collection",
        description="Auto-detect 対象の親コレクション名。直下の子コレクションを 1 キャラとして扱う",
        default="_Chara",
    )
    # Burst パターン
    burst_duration: IntProperty(
        name="Burst Duration",
        description="Burst Hide/Show の hold 期間",
        default=10, min=1, soft_max=240,
    )
    range_start: IntProperty(
        name="Range Start",
        description="Show/Hide from Start to End の開始フレーム",
        default=1,
    )
    range_end: IntProperty(
        name="Range End",
        description="Show/Hide from Start to End の終了フレーム",
        default=30,
    )
    # Shot Cast 用: 自動 Bake モード（チェックボックス変更で即キー反映）
    cast_auto_bake: BoolProperty(
        name="Auto Bake",
        description="Shot Cast のチェックボックス変更時に自動でキーフレームへ反映",
        default=True,
    )

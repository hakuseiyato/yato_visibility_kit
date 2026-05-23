"""PropertyGroup 定義。

データモデル:
  Scene.yato_vis (YatoVisSceneSettings)
    ├ groups: CollectionProperty(YatoVisGroup)
    │   └ members: CollectionProperty(YatoVisGroupMember)
    │       member_type ∈ {OBJECT, COLLECTION}
    │       Collection の場合は Solo モード対応
    └ snapshots: CollectionProperty(YatoVisTransformSnapshot)
        └ entries: CollectionProperty(YatoVisSnapshotEntry)
            matrix_basis / matrix_world を 16 float で保持
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


class YatoVisGroup(PropertyGroup):
    name: StringProperty(name="Name", default="Group")
    members: CollectionProperty(type=YatoVisGroupMember)
    expand: BoolProperty(default=False)


class YatoVisSnapshotEntry(PropertyGroup):
    object_ref: PointerProperty(name="Object", type=bpy.types.Object)
    # matrix_basis (parent local transform) — 復元のメイン
    matrix_basis: FloatVectorProperty(size=16, subtype="MATRIX")
    # matrix_world — フォールバック / デバッグ
    matrix_world: FloatVectorProperty(size=16, subtype="MATRIX")


class YatoVisTransformSnapshot(PropertyGroup):
    name: StringProperty(name="Name", default="Snapshot")
    entries: CollectionProperty(type=YatoVisSnapshotEntry)


class YatoVisSceneSettings(PropertyGroup):
    groups: CollectionProperty(type=YatoVisGroup)
    active_group_index: IntProperty(default=0)
    snapshots: CollectionProperty(type=YatoVisTransformSnapshot)
    active_snapshot_index: IntProperty(default=0)

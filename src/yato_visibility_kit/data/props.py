"""PropertyGroup 定義。

データモデル:
  Scene.yato_vis (YatoVisSceneSettings)
    ├ groups: CollectionProperty(YatoVisGroup)
    │   └ members: CollectionProperty(YatoVisGroupMember)
    │       member_type ∈ {OBJECT, COLLECTION}
    │       Collection の場合は Solo モード対応
    ├ snapshots: CollectionProperty(YatoVisTransformSnapshot)
    │   └ entries: CollectionProperty(YatoVisSnapshotEntry)
    │       matrix_basis / matrix_world を 16 float で保持
    ├ templates: CollectionProperty(YatoVisTemplate)
    │   └ keys: CollectionProperty(YatoVisTemplateKey)
    │       channel ∈ {hide_viewport, hide_render}
    │       frame_offset / value / interpolation
    └ burst_duration: IntProperty (Burst パターンの hold 期間, デフォルト 10)
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


CHANNEL_ITEMS = (
    ("hide_viewport", "Viewport", "Object Properties > Visibility > Viewport", "RESTRICT_VIEW_OFF", 0),
    ("hide_render", "Render", "Object Properties > Visibility > Render", "RESTRICT_RENDER_OFF", 1),
)


class YatoVisTemplateKey(PropertyGroup):
    """テンプレ内の単一キーフレーム。frame_offset は最初のキーを 0 とした相対値。"""
    channel: EnumProperty(items=CHANNEL_ITEMS, default="hide_viewport")
    frame_offset: IntProperty(default=0)
    value: BoolProperty(default=False)
    # CONSTANT / LINEAR / BEZIER の文字列を保持（Blender enum と互換）
    interpolation: StringProperty(default="CONSTANT")


class YatoVisTemplate(PropertyGroup):
    name: StringProperty(name="Name", default="Template")
    note: StringProperty(name="Note", default="")
    keys: CollectionProperty(type=YatoVisTemplateKey)


class YatoVisSceneSettings(PropertyGroup):
    groups: CollectionProperty(type=YatoVisGroup)
    active_group_index: IntProperty(default=0)
    snapshots: CollectionProperty(type=YatoVisTransformSnapshot)
    active_snapshot_index: IntProperty(default=0)
    templates: CollectionProperty(type=YatoVisTemplate)
    active_template_index: IntProperty(default=0)
    # Burst パターンの hold 期間（フレーム数）
    burst_duration: IntProperty(
        name="Burst Duration",
        description="Burst Hide/Show の hold 期間。F=現フレームから F+duration まで新状態を保持し、F+duration+1 で元に戻す",
        default=10,
        min=1,
        soft_max=240,
    )

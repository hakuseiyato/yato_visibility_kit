"""yato_visibility_kit.ops — Operator 一括 register。"""

from __future__ import annotations

import bpy

from . import (
    _base,
    visibility_ops,
    group_ops,
    snapshot_ops,
    keyframe_ops,
)


_CLASSES = (
    visibility_ops.YATOVIS_OT_set_visibility,
    visibility_ops.YATOVIS_OT_toggle_auto_keyframe,
    visibility_ops.YATOVIS_OT_key_visibility,
    keyframe_ops.YATOVIS_OT_clear_keys,
    group_ops.YATOVIS_OT_group_create,
    group_ops.YATOVIS_OT_group_remove,
    group_ops.YATOVIS_OT_group_add_selection,
    group_ops.YATOVIS_OT_group_add_collection,
    group_ops.YATOVIS_OT_group_remove_member,
    group_ops.YATOVIS_OT_group_select,
    group_ops.YATOVIS_OT_group_set_visibility,
    group_ops.YATOVIS_OT_solo_apply,
    group_ops.YATOVIS_OT_solo_step,
    group_ops.YATOVIS_OT_group_clean_dead_refs,
    snapshot_ops.YATOVIS_OT_snapshot_create,
    snapshot_ops.YATOVIS_OT_snapshot_overwrite,
    snapshot_ops.YATOVIS_OT_snapshot_remove,
    snapshot_ops.YATOVIS_OT_snapshot_restore,
    snapshot_ops.YATOVIS_OT_snapshot_clean_dead_refs,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

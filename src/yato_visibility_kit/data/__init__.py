"""yato_visibility_kit.data — PropertyGroup 一括 register。"""

from __future__ import annotations

import bpy

from . import props


_CLASSES = (
    # 親子順: 子要素クラスを先に register
    props.YatoVisGroupMember,
    props.YatoVisGroup,
    props.YatoVisSnapshotEntry,
    props.YatoVisTransformSnapshot,
    props.YatoVisSceneSettings,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.yato_vis = bpy.props.PointerProperty(type=props.YatoVisSceneSettings)


def unregister() -> None:
    try:
        del bpy.types.Scene.yato_vis
    except Exception:
        pass
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

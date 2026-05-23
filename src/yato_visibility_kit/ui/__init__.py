"""yato_visibility_kit.ui — Panel / UIList 登録。"""

from __future__ import annotations

import bpy

from . import main_panel


_CLASSES = (
    main_panel.YATOVIS_UL_groups,
    main_panel.YATOVIS_UL_snapshots,
    main_panel.YATOVIS_PT_main,
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

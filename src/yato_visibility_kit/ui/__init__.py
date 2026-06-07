"""yato_visibility_kit.ui — Panel / UIList 登録。"""

from __future__ import annotations

import bpy

from . import main_panel


# UI クラス登録順:
#   UIList → サブパネル (親 KINEMA_PT_shot_manager は kinema 側で先に登録される)
#
# YATOVIS_PT_main / YATOVIS_PT_shot_cast は廃止。全パネルが kinema の Shots
# パネル配下の子として表示される（bl_parent_id = "KINEMA_PT_shot_manager"）。
# yato_visibility_kit 単体では Visibility 系のサブパネルは表示されなくなる
# （kinema 必須）— これは「完全統合」要件に従う設計判断。
_CLASSES = (
    main_panel.YATOVIS_UL_groups,
    main_panel.YATOVIS_UL_snapshots,
    main_panel.YATOVIS_PT_groups,
    main_panel.YATOVIS_PT_quick,
    main_panel.YATOVIS_PT_burst,
    main_panel.YATOVIS_PT_active,
    main_panel.YATOVIS_PT_snapshots,
)


def register() -> None:
    for cls in _CLASSES:
        try:
            bpy.utils.unregister_class(cls)  # pre-unregister で重複回避
        except Exception:
            pass
        try:
            bpy.utils.register_class(cls)
        except Exception as exc:
            import traceback
            print(f"[yato_visibility_kit:ui] register failed for {cls.__name__}: {exc}")
            traceback.print_exc()


def unregister() -> None:
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

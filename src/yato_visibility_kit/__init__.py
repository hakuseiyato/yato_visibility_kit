"""yato_visibility_kit — 可視性の一括 ON/OFF、グループ管理、Transform スナップショット。

主担当: Yato
リポ:    C:\\Work\\Yato\\Claude\\yato_visibility_kit\\ (GitHub: hakuseiyato/yato_visibility_kit)

スコープ:
  - 3D View > N > Yato タブに Visibility パネル
  - 選択オブジェクトの hide_viewport / hide_render を一括トグル（全揃え方式）
  - Group: Object / Collection 参照、Collection は Solo モード対応（表情差分用途）
  - Transform Snapshot: matrix_basis ベースで保存/復元
  - Auto KF 連動キーフレーム、Redundant キー掃除
"""

bl_info = {
    "name": "Yato Visibility Kit",
    "author": "Yato",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar (N) > Yato > Visibility",
    "description": "Batch visibility toggle, groups, solo mode, and transform snapshots",
    "category": "Object",
}

try:
    import bpy  # noqa: F401
    _HAS_BPY = True
except ImportError:
    _HAS_BPY = False


_REGISTERED = False


def register():
    global _REGISTERED
    if not _HAS_BPY:
        return
    from . import data, ops, ui  # noqa: PLC0415
    if _REGISTERED:
        try:
            unregister()
        except Exception:
            pass
    data.register()
    ops.register()
    ui.register()
    _REGISTERED = True


def unregister():
    global _REGISTERED
    if not _HAS_BPY:
        return
    from . import data, ops, ui  # noqa: PLC0415
    try:
        ui.unregister()
    except Exception:
        pass
    try:
        ops.unregister()
    except Exception:
        pass
    try:
        data.unregister()
    except Exception:
        pass
    _REGISTERED = False

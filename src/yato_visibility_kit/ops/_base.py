"""Operator 基底クラス。

UNDO_GROUPED により可視性の連続トグルが Undo スタックを汚しすぎないようにする。
"""

from __future__ import annotations

import bpy


class YatoVisOperator(bpy.types.Operator):
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):  # type: ignore[override]
        result = self.run(context)
        self._redraw(context)
        return result

    def run(self, context):  # noqa: ARG002
        raise NotImplementedError

    def _redraw(self, context) -> None:
        area = getattr(context, "area", None)
        if area is not None:
            area.tag_redraw()


def selected_objects(context) -> list:
    """選択オブジェクトを返す。アクティブが含まれない VIEW_3D 等の差を吸収。"""
    objs = list(getattr(context, "selected_objects", []) or [])
    if not objs:
        act = getattr(context, "active_object", None)
        if act is not None:
            objs = [act]
    return objs

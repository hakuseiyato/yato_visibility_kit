"""Group 関連 Operator。

Group は Scene.yato_vis.groups に格納される PropertyGroup。メンバは
Object 直指定 / Collection 参照 の 2 種。Collection には Solo モードがあり、
1 個だけ表示してほかは hide_viewport にする（表情差分の切り替え用途）。
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from ._base import YatoVisOperator, selected_objects
from .visibility_ops import (
    MODE_ITEMS,
    TARGET_ITEMS,
    _ATTR_MAP,
    _KEYABLE_ATTRS,
    apply_visibility,
    _should_keyframe,
)


def _group_member_objects(member) -> list:
    """Group メンバから実際のオブジェクト一覧を取り出す。死んだ参照はスキップ。"""
    if member.member_type == "OBJECT":
        o = member.object_ref
        return [o] if o is not None else []
    if member.member_type == "COLLECTION":
        c = member.collection_ref
        if c is None:
            return []
        return [o for o in c.objects if o is not None]
    return []


def group_all_objects(group) -> list:
    out = []
    for m in group.members:
        out.extend(_group_member_objects(m))
    # 重複除去（順序維持）
    seen = set()
    dedup = []
    for o in out:
        if o.name in seen:
            continue
        seen.add(o.name)
        dedup.append(o)
    return dedup


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class YATOVIS_OT_group_create(YatoVisOperator):
    """選択オブジェクト or アクティブコレクションから新規 Group を作成。"""
    bl_idname = "yato_vis.group_create"
    bl_label = "Create Group"
    bl_description = "選択オブジェクト or アクティブコレクションから新規 Group を作成"

    name: StringProperty(name="Name", default="Group")
    source: EnumProperty(
        items=(
            ("SELECTION", "Selection", "選択中オブジェクトをメンバ化"),
            ("ACTIVE_COLLECTION", "Active Collection", "アクティブコレクションを参照"),
        ),
        default="SELECTION",
    )

    def invoke(self, context, event):  # noqa: ARG002
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):  # noqa: ARG002
        layout = self.layout
        layout.prop(self, "name")
        layout.prop(self, "source")

    def run(self, context):
        st = context.scene.yato_vis
        g = st.groups.add()
        g.name = self.name or "Group"
        if self.source == "SELECTION":
            for o in selected_objects(context):
                m = g.members.add()
                m.member_type = "OBJECT"
                m.object_ref = o
        else:
            coll = context.collection
            if coll is None:
                st.groups.remove(len(st.groups) - 1)
                self.report({"WARNING"}, "アクティブコレクションがありません")
                return {"CANCELLED"}
            m = g.members.add()
            m.member_type = "COLLECTION"
            m.collection_ref = coll
        st.active_group_index = len(st.groups) - 1
        self.report({"INFO"}, f"Group '{g.name}' created ({len(g.members)} members)")
        return {"FINISHED"}


class YATOVIS_OT_group_remove(YatoVisOperator):
    bl_idname = "yato_vis.group_remove"
    bl_label = "Remove Group"
    bl_description = "アクティブ Group を削除"

    def run(self, context):
        st = context.scene.yato_vis
        idx = st.active_group_index
        if idx < 0 or idx >= len(st.groups):
            self.report({"WARNING"}, "Group が選択されていません")
            return {"CANCELLED"}
        name = st.groups[idx].name
        st.groups.remove(idx)
        st.active_group_index = max(0, min(idx, len(st.groups) - 1))
        self.report({"INFO"}, f"Group '{name}' removed")
        return {"FINISHED"}


class YATOVIS_OT_group_add_selection(YatoVisOperator):
    """選択オブジェクトをアクティブ Group のメンバに追加。"""
    bl_idname = "yato_vis.group_add_selection"
    bl_label = "Add Selection"
    bl_description = "選択オブジェクトをアクティブ Group のメンバに追加"

    def run(self, context):
        st = context.scene.yato_vis
        idx = st.active_group_index
        if idx < 0 or idx >= len(st.groups):
            self.report({"WARNING"}, "Group が選択されていません")
            return {"CANCELLED"}
        g = st.groups[idx]
        existing = {m.object_ref.name for m in g.members
                    if m.member_type == "OBJECT" and m.object_ref is not None}
        added = 0
        for o in selected_objects(context):
            if o.name in existing:
                continue
            m = g.members.add()
            m.member_type = "OBJECT"
            m.object_ref = o
            added += 1
        self.report({"INFO"}, f"{added} objects added to '{g.name}'")
        return {"FINISHED"}


class YATOVIS_OT_group_add_collection(YatoVisOperator):
    """アクティブコレクションをアクティブ Group のメンバに追加。"""
    bl_idname = "yato_vis.group_add_collection"
    bl_label = "Add Collection"
    bl_description = "アクティブコレクションをアクティブ Group のメンバに追加"

    def run(self, context):
        st = context.scene.yato_vis
        idx = st.active_group_index
        if idx < 0 or idx >= len(st.groups):
            self.report({"WARNING"}, "Group が選択されていません")
            return {"CANCELLED"}
        coll = context.collection
        if coll is None:
            self.report({"WARNING"}, "アクティブコレクションがありません")
            return {"CANCELLED"}
        g = st.groups[idx]
        m = g.members.add()
        m.member_type = "COLLECTION"
        m.collection_ref = coll
        self.report({"INFO"}, f"Collection '{coll.name}' added to '{g.name}'")
        return {"FINISHED"}


class YATOVIS_OT_group_remove_member(YatoVisOperator):
    """指定 Group の指定 member を削除。"""
    bl_idname = "yato_vis.group_remove_member"
    bl_label = "Remove Member"
    bl_description = "Group メンバを削除"

    group_index: IntProperty(default=-1)
    member_index: IntProperty(default=-1)

    def run(self, context):
        st = context.scene.yato_vis
        if not (0 <= self.group_index < len(st.groups)):
            return {"CANCELLED"}
        g = st.groups[self.group_index]
        if not (0 <= self.member_index < len(g.members)):
            return {"CANCELLED"}
        g.members.remove(self.member_index)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Selection / Visibility
# ---------------------------------------------------------------------------

class YATOVIS_OT_group_select(YatoVisOperator):
    """Group メンバを 3D View で選択。"""
    bl_idname = "yato_vis.group_select"
    bl_label = "Select Group"
    bl_description = "Group メンバを 3D View で選択（既存選択を置換）"

    group_index: IntProperty(default=-1)
    extend: BoolProperty(default=False)

    def run(self, context):
        st = context.scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            self.report({"WARNING"}, "Group が選択されていません")
            return {"CANCELLED"}
        if not self.extend:
            bpy.ops.object.select_all(action="DESELECT")
        count = 0
        last = None
        for o in group_all_objects(st.groups[idx]):
            try:
                o.select_set(True)
                last = o
                count += 1
            except Exception:
                pass
        if last is not None:
            context.view_layer.objects.active = last
        self.report({"INFO"}, f"{count} objects selected")
        return {"FINISHED"}


class YATOVIS_OT_group_set_visibility(YatoVisOperator):
    """Group メンバの可視性を一括変更。"""
    bl_idname = "yato_vis.group_set_visibility"
    bl_label = "Group Visibility"
    bl_description = "Group メンバの可視性を一括変更"

    group_index: IntProperty(default=-1)
    target: EnumProperty(items=TARGET_ITEMS, default="VIEWPORT")
    mode: EnumProperty(items=MODE_ITEMS, default="TOGGLE")

    def run(self, context):
        st = context.scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            self.report({"WARNING"}, "Group が選択されていません")
            return {"CANCELLED"}
        g = st.groups[idx]
        objs = group_all_objects(g)
        if not objs:
            self.report({"WARNING"}, f"Group '{g.name}' is empty")
            return {"CANCELLED"}
        attrs = _ATTR_MAP.get(self.target, ())
        kf = _should_keyframe(context)
        frame = context.scene.frame_current if kf else None
        changed = apply_visibility(objs, attrs, self.mode, insert_keyframe=kf, frame=frame)
        self.report({"INFO"}, f"Group '{g.name}': {self.mode} {self.target} on {len(objs)} obj(s), {changed} changed")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Solo mode
# ---------------------------------------------------------------------------

def _apply_solo(member, insert_keyframe: bool = False, frame: int | None = None) -> tuple[int, int]:
    """Collection メンバの Solo モードを適用。(shown, hidden) を返す。

    Solo OFF: 全メンバ hide_viewport=False に戻す
    Solo ON:  solo_target だけ hide_viewport=False、ほかは True
    """
    if member.member_type != "COLLECTION" or member.collection_ref is None:
        return (0, 0)
    objs = list(member.collection_ref.objects)
    target = member.solo_target
    shown = 0
    hidden = 0
    for o in objs:
        if member.solo_enabled:
            new_val = (o != target)
        else:
            new_val = False
        if o.hide_viewport != new_val:
            o.hide_viewport = new_val
        if insert_keyframe:
            try:
                o.keyframe_insert(data_path="hide_viewport", frame=frame)
            except Exception:
                pass
        if new_val:
            hidden += 1
        else:
            shown += 1
    return (shown, hidden)


class YATOVIS_OT_solo_apply(YatoVisOperator):
    """指定 Collection メンバの Solo 状態を現在の値で適用。"""
    bl_idname = "yato_vis.solo_apply"
    bl_label = "Apply Solo"
    bl_description = "Solo モードを現在の値で適用（Auto KF ON ならキー挿入）"

    group_index: IntProperty(default=-1)
    member_index: IntProperty(default=-1)

    def run(self, context):
        st = context.scene.yato_vis
        if not (0 <= self.group_index < len(st.groups)):
            return {"CANCELLED"}
        g = st.groups[self.group_index]
        if not (0 <= self.member_index < len(g.members)):
            return {"CANCELLED"}
        member = g.members[self.member_index]
        if member.member_type != "COLLECTION":
            self.report({"WARNING"}, "Solo は Collection メンバ専用です")
            return {"CANCELLED"}
        kf = _should_keyframe(context)
        frame = context.scene.frame_current if kf else None
        shown, hidden = _apply_solo(member, insert_keyframe=kf, frame=frame)
        state = "ON" if member.solo_enabled else "OFF"
        self.report({"INFO"}, f"Solo {state}: {shown} shown / {hidden} hidden")
        return {"FINISHED"}


class YATOVIS_OT_solo_step(YatoVisOperator):
    """Solo target を Collection の次/前のオブジェクトに進める。表情差分めくり用。"""
    bl_idname = "yato_vis.solo_step"
    bl_label = "Solo Step"
    bl_description = "Solo target を Collection 内で順送り/逆送りし、即時適用"

    group_index: IntProperty(default=-1)
    member_index: IntProperty(default=-1)
    direction: EnumProperty(
        items=(("NEXT", "Next", ""), ("PREV", "Prev", "")),
        default="NEXT",
    )

    def run(self, context):
        st = context.scene.yato_vis
        if not (0 <= self.group_index < len(st.groups)):
            return {"CANCELLED"}
        g = st.groups[self.group_index]
        if not (0 <= self.member_index < len(g.members)):
            return {"CANCELLED"}
        member = g.members[self.member_index]
        if member.member_type != "COLLECTION" or member.collection_ref is None:
            self.report({"WARNING"}, "Solo は Collection メンバ専用です")
            return {"CANCELLED"}
        objs = list(member.collection_ref.objects)
        if not objs:
            self.report({"WARNING"}, "Collection が空です")
            return {"CANCELLED"}
        cur = member.solo_target
        if cur is None or cur not in objs:
            new_target = objs[0]
        else:
            i = objs.index(cur)
            i = (i + 1) % len(objs) if self.direction == "NEXT" else (i - 1) % len(objs)
            new_target = objs[i]
        member.solo_target = new_target
        if not member.solo_enabled:
            member.solo_enabled = True
        kf = _should_keyframe(context)
        frame = context.scene.frame_current if kf else None
        _apply_solo(member, insert_keyframe=kf, frame=frame)
        self.report({"INFO"}, f"Solo → {new_target.name}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

class YATOVIS_OT_auto_detect_characters(YatoVisOperator):
    """親コレクション直下の子コレクションをキャラ Group として自動検出。

    検出ロジック:
      - parent_collection_name の Collection を取得
      - 直下の子コレクションごとに Group を作成（または既存を更新）
        * COLLECTION メンバ 1 つ、solo_enabled=True、最初のオブジェクトを solo_target に
        * bound_object は solo_target と同期
      - 再帰下の EMPTY オブジェクトをまとめて Group "Empty" に集約

    Incremental update:
      - 既存の auto Group (is_auto=True) は collection_ref を最新化するが、
        ユーザーが変更した bound_object / solo_target は保持
      - 親コレクション側で消えた auto Group は削除
      - 手動で作った Group (is_auto=False) は触らない
    """
    bl_idname = "yato_vis.auto_detect_characters"
    bl_label = "Auto-detect Characters"
    bl_description = (
        "親コレクション直下の子コレクションをキャラ Group として自動検出。"
        "再帰下の EMPTY は 'Empty' Group にまとめる"
    )

    EMPTY_GROUP_NAME = "Empty"

    def _find_group_by_name(self, st, name: str):
        for g in st.groups:
            if g.name == name:
                return g
        return None

    def _ensure_collection_group(self, st, name: str, coll) -> None:
        g = self._find_group_by_name(st, name)
        if g is None:
            g = st.groups.add()
            g.name = name
            g.is_auto = True
            m = g.members.add()
            m.member_type = "COLLECTION"
            m.collection_ref = coll
            m.solo_enabled = True
            first = next(iter(coll.objects), None)
            if first is not None:
                m.solo_target = first
                # bound_object 経由で Solo 適用も走る
                g.bound_object = first
            return
        # 既存 — collection_ref のみ最新化（ユーザー設定の bound_object/solo_target は保持）
        g.is_auto = True
        coll_member = None
        for m in g.members:
            if m.member_type == "COLLECTION":
                coll_member = m
                break
        if coll_member is None:
            coll_member = g.members.add()
            coll_member.member_type = "COLLECTION"
        coll_member.collection_ref = coll
        # solo_target が collection 外を指していたら救済 (先頭オブジェクトへ)
        if coll_member.solo_target is None or coll_member.solo_target.name not in coll.objects:
            first = next(iter(coll.objects), None)
            if first is not None:
                coll_member.solo_target = first
                if g.bound_object is None or g.bound_object.name not in coll.objects:
                    g.bound_object = first

    def _ensure_empty_group(self, st, empties: list) -> None:
        g = self._find_group_by_name(st, self.EMPTY_GROUP_NAME)
        if g is None:
            g = st.groups.add()
            g.name = self.EMPTY_GROUP_NAME
            g.is_auto = True
        g.is_auto = True
        # メンバを Empty オブジェクト一覧で置き換え（OBJECT メンバのみ）
        # ※ ユーザーが手動追加した OBJECT/COLLECTION メンバがあれば残せないが、
        #    Empty Group は auto 専用想定なので置換でよい
        g.members.clear()
        for e in empties:
            m = g.members.add()
            m.member_type = "OBJECT"
            m.object_ref = e

    def _collect_empties(self, coll, out: list, seen: set) -> None:
        for o in coll.objects:
            if o.type == "EMPTY" and o.name not in seen:
                out.append(o)
                seen.add(o.name)
        for child in coll.children:
            self._collect_empties(child, out, seen)

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        parent_name = st.parent_collection_name.strip()
        if not parent_name:
            self.report({"WARNING"}, "親コレクション名が空です")
            return {"CANCELLED"}
        parent = bpy.data.collections.get(parent_name)
        if parent is None:
            self.report({"WARNING"}, f"親コレクションが見つかりません: '{parent_name}'")
            return {"CANCELLED"}

        # 1. 子コレクションごとに Group を ensure
        child_collections = list(parent.children)
        child_names = {c.name for c in child_collections}
        for coll in child_collections:
            self._ensure_collection_group(st, coll.name, coll)

        # 2. Empty Group ensure
        empties: list = []
        seen: set = set()
        self._collect_empties(parent, empties, seen)
        if empties:
            self._ensure_empty_group(st, empties)
        else:
            # Empty なし: 既存 Empty Group があれば削除
            i = len(st.groups) - 1
            while i >= 0:
                g = st.groups[i]
                if g.name == self.EMPTY_GROUP_NAME and g.is_auto:
                    st.groups.remove(i)
                i -= 1

        # 3. 親コレクション側から消えた auto Group をクリーンアップ
        i = len(st.groups) - 1
        while i >= 0:
            g = st.groups[i]
            if g.is_auto and g.name != self.EMPTY_GROUP_NAME:
                if g.name not in child_names:
                    st.groups.remove(i)
            i -= 1

        # アクティブ index を範囲内に
        st.active_group_index = max(0, min(st.active_group_index, len(st.groups) - 1))

        self.report(
            {"INFO"},
            f"Auto-detect: {len(child_collections)} character(s), {len(empties)} empty object(s)",
        )
        return {"FINISHED"}


class YATOVIS_OT_group_clean_dead_refs(YatoVisOperator):
    """全 Group から死んだ参照（None になった Object/Collection メンバ）を削除。"""
    bl_idname = "yato_vis.group_clean_dead_refs"
    bl_label = "Clean Dead Refs"
    bl_description = "全 Group から削除済みオブジェクト参照を取り除く"

    def run(self, context):
        st = context.scene.yato_vis
        removed = 0
        for g in st.groups:
            i = len(g.members) - 1
            while i >= 0:
                m = g.members[i]
                if m.member_type == "OBJECT" and m.object_ref is None:
                    g.members.remove(i)
                    removed += 1
                elif m.member_type == "COLLECTION" and m.collection_ref is None:
                    g.members.remove(i)
                    removed += 1
                i -= 1
        self.report({"INFO"}, f"{removed} dead member(s) removed")
        return {"FINISHED"}

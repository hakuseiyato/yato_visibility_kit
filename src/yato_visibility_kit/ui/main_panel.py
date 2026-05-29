"""3D View > Sidebar (N) > Yato > Visibility パネル群。

サブパネル構成:
  YATOVIS_PT_main (親)
    ├ YATOVIS_PT_quick      Quick Toggle
    ├ YATOVIS_PT_burst      Burst & Range
    ├ YATOVIS_PT_groups     Groups (+ Active Group detail)
    ├ YATOVIS_PT_shot_cast  Shot Cast (per Camera Marker)
    ├ YATOVIS_PT_active     Active Object Transform / Key
    └ YATOVIS_PT_snapshots  Snapshots

UIList の draw_item は名前が潰れないよう最小限の widget だけを並べる。
"""

from __future__ import annotations

import bpy


CATEGORY = "Yato"


# ---------------------------------------------------------------------------
# UIList
# ---------------------------------------------------------------------------

class YATOVIS_UL_groups(bpy.types.UIList):
    bl_idname = "YATOVIS_UL_groups"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # 名前が読めるよう、行内 widget は最小限に絞る。
        # 詳細操作（bound / select / collection-self toggle 等）は active row の
        # 詳細 box にまとめて出す。
        split = layout.split(factor=0.55, align=True)
        name_icon = "AUTO" if item.is_auto else "GROUP"
        split.prop(item, "name", text="", emboss=False, icon=name_icon)

        right = split.row(align=True)
        # Collection メンバ持ち Group は ◀/▶ で Solo target をめくれる
        coll_member_index = -1
        for mi, m in enumerate(item.members):
            if m.member_type == "COLLECTION" and m.collection_ref is not None:
                coll_member_index = mi
                break
        if coll_member_index >= 0:
            prev_op = right.operator("yato_vis.solo_step", text="", icon="TRIA_LEFT")
            prev_op.group_index = index
            prev_op.member_index = coll_member_index
            prev_op.direction = "PREV"
            next_op = right.operator("yato_vis.solo_step", text="", icon="TRIA_RIGHT")
            next_op.group_index = index
            next_op.member_index = coll_member_index
            next_op.direction = "NEXT"
        # 個別オブジェクトレベル trigger
        op = right.operator("yato_vis.group_set_visibility", text="", icon="HIDE_OFF")
        op.group_index = index
        op.target = "BOTH"; op.mode = "TOGGLE"
        # メンバ数
        alive = 0
        dead = 0
        for m in item.members:
            if m.member_type == "OBJECT":
                if m.object_ref is None: dead += 1
                else: alive += 1
            elif m.member_type == "COLLECTION":
                if m.collection_ref is None: dead += 1
                else: alive += 1
        right.label(text=f"{alive}⚠" if dead else f"{alive}")


class YATOVIS_UL_snapshots(bpy.types.UIList):
    bl_idname = "YATOVIS_UL_snapshots"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="ARMATURE_DATA")
        dead = sum(1 for e in item.entries if e.object_ref is None)
        alive = len(item.entries) - dead
        row.label(text=f"{alive}⚠" if dead else f"{alive}")


# ---------------------------------------------------------------------------
# Main panel (空)
# ---------------------------------------------------------------------------

class YATOVIS_PT_main(bpy.types.Panel):
    bl_label = "Visibility"
    bl_idname = "YATOVIS_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY

    def draw(self, context):
        # 本体は空。子サブパネルが描画する。
        pass


# ---------------------------------------------------------------------------
# Quick Toggle
# ---------------------------------------------------------------------------

class YATOVIS_PT_quick(bpy.types.Panel):
    bl_label = "Quick Toggle"
    bl_idname = "YATOVIS_PT_quick"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY
    bl_parent_id = "YATOVIS_PT_main"

    def draw(self, context):
        layout = self.layout
        sel = len(getattr(context, "selected_objects", []) or [])
        layout.label(text=f"Selected: {sel}", icon="OUTLINER_DATA_MESH")

        row = layout.row(align=True)
        op = row.operator("yato_vis.set_visibility", text="Viewport", icon="RESTRICT_VIEW_OFF")
        op.target = "VIEWPORT"; op.mode = "TOGGLE"
        op = row.operator("yato_vis.set_visibility", text="Render", icon="RESTRICT_RENDER_OFF")
        op.target = "RENDER"; op.mode = "TOGGLE"
        op = row.operator("yato_vis.set_visibility", text="Select", icon="RESTRICT_SELECT_OFF")
        op.target = "SELECT"; op.mode = "TOGGLE"

        row = layout.row(align=True)
        op = row.operator("yato_vis.set_visibility", text="Show All", icon="HIDE_OFF")
        op.target = "BOTH"; op.mode = "SHOW"
        op = row.operator("yato_vis.set_visibility", text="Hide All", icon="HIDE_ON")
        op.target = "BOTH"; op.mode = "HIDE"


# ---------------------------------------------------------------------------
# Burst & Range
# ---------------------------------------------------------------------------

class YATOVIS_PT_burst(bpy.types.Panel):
    bl_label = "Burst & Range"
    bl_idname = "YATOVIS_PT_burst"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY
    bl_parent_id = "YATOVIS_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        st = context.scene.yato_vis

        # 現フレームから N フレーム
        layout.label(text="From current frame:", icon="MARKER_HLT")
        layout.prop(st, "burst_duration", text="Duration")
        row = layout.row(align=True)
        op = row.operator("yato_vis.burst", text="Burst Hide", icon="HIDE_ON")
        op.state = "HIDE"; op.target = "BOTH"; op.use_scene_duration = True
        op = row.operator("yato_vis.burst", text="Burst Show", icon="HIDE_OFF")
        op.state = "SHOW"; op.target = "BOTH"; op.use_scene_duration = True

        # カメラバインド区間
        layout.separator()
        layout.label(text="Camera bind range:", icon="VIEW_CAMERA")
        row = layout.row(align=True)
        op = row.operator("yato_vis.burst_camera_range", text="Cam Hide", icon="HIDE_ON")
        op.state = "HIDE"; op.target = "BOTH"
        op = row.operator("yato_vis.burst_camera_range", text="Cam Show", icon="HIDE_OFF")
        op.state = "SHOW"; op.target = "BOTH"

        # 明示 Start/End
        layout.separator()
        layout.label(text="Explicit range:", icon="PREVIEW_RANGE")
        srow = layout.row(align=True)
        srow.prop(st, "range_start", text="Start")
        op = srow.operator("yato_vis.set_range_frame", text="", icon="REC")
        op.which = "START"
        op = srow.operator("yato_vis.jump_to_range_frame", text="", icon="PLAY")
        op.which = "START"
        erow = layout.row(align=True)
        erow.prop(st, "range_end", text="End")
        op = erow.operator("yato_vis.set_range_frame", text="", icon="REC")
        op.which = "END"
        op = erow.operator("yato_vis.jump_to_range_frame", text="", icon="PLAY")
        op.which = "END"
        arow = layout.row(align=True)
        op = arow.operator("yato_vis.burst_range", text="Show in Range", icon="HIDE_OFF")
        op.state = "SHOW"; op.target = "BOTH"
        op = arow.operator("yato_vis.burst_range", text="Hide in Range", icon="HIDE_ON")
        op.state = "HIDE"; op.target = "BOTH"


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

class YATOVIS_PT_groups(bpy.types.Panel):
    bl_label = "Groups"
    bl_idname = "YATOVIS_PT_groups"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY
    bl_parent_id = "YATOVIS_PT_main"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        st = scene.yato_vis

        # Parent + Auto-detect
        head = layout.row(align=True)
        head.prop(st, "parent_collection_name", text="Parent")
        head.operator("yato_vis.auto_detect_characters", text="", icon="ZOOM_ALL")
        head.operator("yato_vis.group_clean_dead_refs", text="", icon="BRUSH_DATA")

        layout.template_list(
            "YATOVIS_UL_groups", "",
            st, "groups",
            st, "active_group_index",
            rows=6,
        )

        # New / Remove / Add
        btn_row = layout.row(align=True)
        btn_row.operator("yato_vis.group_create", text="New", icon="ADD")
        btn_row.operator("yato_vis.group_remove", text="", icon="REMOVE")
        btn_row.operator("yato_vis.group_add_selection", text="Add Sel", icon="ADD")
        btn_row.operator("yato_vis.group_add_collection", text="+Coll", icon="OUTLINER_COLLECTION")

        # Select buttons (常設)
        sel_row = layout.row(align=True)
        op = sel_row.operator("yato_vis.group_select", text="Select All", icon="RESTRICT_SELECT_OFF")
        op.group_index = -1; op.only_visible = False
        op = sel_row.operator("yato_vis.group_select", text="Select Visible", icon="EYEDROPPER")
        op.group_index = -1; op.only_visible = True

        # --- Active Group detail ---
        if not (0 <= st.active_group_index < len(st.groups)):
            return
        g = st.groups[st.active_group_index]
        idx = st.active_group_index
        detail = layout.box()
        detail.label(text=f"▼ {g.name}", icon="DOT")

        # Bound Object（Collection メンバを持つ場合のみ）
        coll_member_index = -1
        for mi, m in enumerate(g.members):
            if m.member_type == "COLLECTION" and m.collection_ref is not None:
                coll_member_index = mi
                break
        if coll_member_index >= 0:
            brow = detail.row(align=True)
            brow.prop(g, "bound_object", text="Bound")
            prev_op = brow.operator("yato_vis.solo_step", text="", icon="TRIA_LEFT")
            prev_op.group_index = idx
            prev_op.member_index = coll_member_index
            prev_op.direction = "PREV"
            next_op = brow.operator("yato_vis.solo_step", text="", icon="TRIA_RIGHT")
            next_op.group_index = idx
            next_op.member_index = coll_member_index
            next_op.direction = "NEXT"

        # オブジェクトレベル可視性
        ovis_row = detail.row(align=True)
        ovis_row.label(text="Object:", icon="OBJECT_DATA")
        op = ovis_row.operator("yato_vis.group_set_visibility", text="", icon="RESTRICT_VIEW_OFF")
        op.group_index = idx; op.target = "VIEWPORT"; op.mode = "TOGGLE"
        op = ovis_row.operator("yato_vis.group_set_visibility", text="", icon="RESTRICT_RENDER_OFF")
        op.group_index = idx; op.target = "RENDER"; op.mode = "TOGGLE"
        op = ovis_row.operator("yato_vis.group_set_visibility", text="Show All")
        op.group_index = idx; op.target = "BOTH"; op.mode = "SHOW"
        op = ovis_row.operator("yato_vis.group_set_visibility", text="Hide All")
        op.group_index = idx; op.target = "BOTH"; op.mode = "HIDE"

        # コレクション自体の hide
        has_coll = any(m.member_type == "COLLECTION" and m.collection_ref is not None for m in g.members)
        if has_coll:
            cvis_row = detail.row(align=True)
            cvis_row.label(text="Collection:", icon="OUTLINER_COLLECTION")
            op = cvis_row.operator("yato_vis.toggle_collection_hide", text="", icon="HIDE_OFF")
            op.group_index = idx; op.target = "VIEWPORT"; op.mode = "TOGGLE"
            op = cvis_row.operator("yato_vis.toggle_collection_hide", text="", icon="RESTRICT_RENDER_OFF")
            op.group_index = idx; op.target = "RENDER"; op.mode = "TOGGLE"

        # Solo モード詳細
        for mi, m in enumerate(g.members):
            if m.member_type == "COLLECTION" and m.collection_ref is not None:
                solo_row = detail.row(align=True)
                solo_row.prop(m, "solo_enabled", text="Solo", toggle=True, icon="SOLO_ON")
                if m.solo_enabled:
                    solo_row.prop(m, "solo_target", text="")
                    ap = solo_row.operator("yato_vis.solo_apply", text="Apply", icon="CHECKMARK")
                    ap.group_index = idx; ap.member_index = mi
                else:
                    ap = solo_row.operator("yato_vis.solo_apply", text="Show All", icon="HIDE_OFF")
                    ap.group_index = idx; ap.member_index = mi
                break  # 最初の COLLECTION メンバだけ

        # メンバ一覧
        if len(g.members) > 0:
            mbox = detail.box()
            mbox.label(text=f"Members ({len(g.members)})", icon="DOT")
            for mi, m in enumerate(g.members):
                mr = mbox.row(align=True)
                if m.member_type == "OBJECT":
                    mr.label(text="", icon="OBJECT_DATA")
                    mr.prop(m, "object_ref", text="")
                else:
                    mr.label(text="", icon="OUTLINER_COLLECTION")
                    mr.prop(m, "collection_ref", text="")
                rm = mr.operator("yato_vis.group_remove_member", text="", icon="X")
                rm.group_index = idx; rm.member_index = mi

        # Shot Cast 操作（このグループに対する Bake）
        cast_box = detail.box()
        cast_box.label(text="Shot Cast:", icon="MARKER_HLT")
        cast_row = cast_box.row(align=True)
        op = cast_row.operator("yato_vis.cast_bake_group", text="Bake", icon="PLAY")
        op.group_index = idx
        # Solo Bake — bound_object だけ ON 期間中に可視
        op = cast_row.operator(
            "yato_vis.cast_bake_group_solo",
            text="Solo Bake",
            icon="SOLO_ON",
        )
        op.group_index = idx
        # 解除
        op = cast_row.operator("yato_vis.cast_clear_group", text="", icon="TRASH")
        op.group_index = idx

        # キーフレーム一覧 (見えなくなったキーを探す用)
        kf_frames = _collect_group_visibility_frames(g)
        if kf_frames:
            kbox = detail.box()
            kbox.label(text=f"Visibility keys ({len(kf_frames)}):", icon="KEY_HLT")
            # 横並びで最大 12 個まで表示
            kf_row = kbox.row(align=True)
            kf_row.scale_y = 0.8
            for i, f in enumerate(kf_frames[:12]):
                op = kf_row.operator("yato_vis.jump_to_keyframe", text=str(f))
                op.frame = f
            if len(kf_frames) > 12:
                kbox.label(text=f"… +{len(kf_frames) - 12} more")
            clr = kbox.operator("yato_vis.cast_clear_group", text="Clear All Keys", icon="TRASH")
            clr.group_index = idx


def _collect_group_visibility_frames(group) -> list[int]:
    """Group メンバの hide_viewport/hide_render fcurve frame 一覧（重複除去・昇順）。"""
    from ..ops.cast_ops import get_visibility_keyframes
    from ..ops.group_ops import group_all_objects
    frames: set[int] = set()
    for o in group_all_objects(group):
        for _ch, f in get_visibility_keyframes(o):
            frames.add(f)
    return sorted(frames)


# ---------------------------------------------------------------------------
# Shot Cast
# ---------------------------------------------------------------------------

class YATOVIS_PT_shot_cast(bpy.types.Panel):
    bl_label = "Shot Cast"
    bl_idname = "YATOVIS_PT_shot_cast"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY
    bl_parent_id = "YATOVIS_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        st = scene.yato_vis

        # カメラマーカー一覧
        cam_markers = sorted(
            (m for m in scene.timeline_markers if m.camera is not None),
            key=lambda m: m.frame,
        )

        head = layout.row(align=True)
        head.label(text=f"Shots: {len(cam_markers)} / Groups: {len(st.groups)}")
        head.prop(st, "cast_auto_bake", text="Auto Bake", toggle=True, icon="REC")

        if not cam_markers:
            layout.label(text="カメラ付き Timeline Marker がありません", icon="INFO")
            layout.label(text="(Marker > Bind Camera to Marker で作成)")
            return
        if len(st.groups) == 0:
            layout.label(text="Group がありません", icon="INFO")
            return

        # 一括 Bake / Solo Bake / Import
        op_row = layout.row(align=True)
        op_row.operator("yato_vis.cast_bake_all", text="Bake All", icon="PLAY")
        op_row.operator(
            "yato_vis.cast_bake_all_solo",
            text="Solo Bake All",
            icon="SOLO_ON",
        )
        op_row.operator(
            "yato_vis.cast_import_from_visibility",
            text="Import",
            icon="IMPORT",
        )

        # オーファン検出: cast_markers のうち現マーカーに無いものをまとめて表示
        current_marker_names = {m.name for m in cam_markers}
        total_orphans = 0
        for g in st.groups:
            for c in g.cast_markers:
                if c.marker_name not in current_marker_names:
                    total_orphans += 1
        if total_orphans > 0:
            warn = layout.box()
            warn.alert = True
            wrow = warn.row(align=True)
            wrow.label(text=f"⚠ Orphan entries: {total_orphans} (削除/リネーム済 marker)", icon="ERROR")
            op = wrow.operator("yato_vis.cast_remove_orphans", text="Clean All", icon="BRUSH_DATA")
            op.group_index = -1

        # Cast マトリクス: 行 = Group, 列 = Shot
        # 多ショット対応のため 10 個/行で折り返し
        layout.separator()
        layout.label(text="行: Group / 列: Shot (10/行で折り返し)", icon="GROUP")

        CHUNK = 10
        for gi, g in enumerate(st.groups):
            gbox = layout.box()
            grow = gbox.row(align=True)
            if gi == st.active_group_index:
                grow.alert = True
            grow.label(text=g.name, icon="AUTO" if g.is_auto else "GROUP")
            cast_count = len(g.cast_markers)
            grow.label(text=f"{cast_count}/{len(cam_markers)}")
            bake = grow.operator("yato_vis.cast_bake_group", text="", icon="PLAY")
            bake.group_index = gi
            # Solo Bake — bound_object だけ ON 期間中に可視
            solo_bake = grow.operator(
                "yato_vis.cast_bake_group_solo", text="", icon="SOLO_ON",
            )
            solo_bake.group_index = gi

            # ショットボタンを CHUNK 個ずつチャンクして行を作る
            for chunk_start in range(0, len(cam_markers), CHUNK):
                cast_row = gbox.row(align=True)
                cast_row.scale_y = 0.9
                for m in cam_markers[chunk_start:chunk_start + CHUNK]:
                    appears = any(c.marker_name == m.name for c in g.cast_markers)
                    op = cast_row.operator(
                        "yato_vis.cast_toggle",
                        text=m.name,
                        depress=appears,
                    )
                    op.group_index = gi
                    op.marker_name = m.name

            # この Group のオーファンエントリ
            group_orphans = [c.marker_name for c in g.cast_markers
                             if c.marker_name not in current_marker_names]
            if group_orphans:
                orow = gbox.row(align=True)
                orow.alert = True
                orow.label(text=f"⚠ Orphan: {', '.join(group_orphans[:5])}" +
                                (f" +{len(group_orphans)-5}" if len(group_orphans) > 5 else ""),
                            icon="ERROR")
                op = orow.operator("yato_vis.cast_remove_orphans", text="", icon="X")
                op.group_index = gi


# ---------------------------------------------------------------------------
# Active Object
# ---------------------------------------------------------------------------

class YATOVIS_PT_active(bpy.types.Panel):
    bl_label = "Active Object"
    bl_idname = "YATOVIS_PT_active"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY
    bl_parent_id = "YATOVIS_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ts = scene.tool_settings
        act = context.active_object

        head = layout.row(align=True)
        if act is None:
            head.label(text="(none)", icon="OBJECT_DATA")
        else:
            head.label(text=act.name, icon="OBJECT_DATAMODE")

        # キー操作 icon row
        key_row = layout.row(align=True)
        key_row.alignment = "RIGHT"
        key_row.operator(
            "yato_vis.toggle_auto_keyframe",
            text="",
            icon="REC" if ts.use_keyframe_insert_auto else "RADIOBUT_OFF",
            depress=ts.use_keyframe_insert_auto,
        )
        key_row.operator("yato_vis.key_all", text="Key All", icon="KEY_HLT")
        op = key_row.operator("yato_vis.clear_keys", text="", icon="KEY_DEHLT")
        op.scope = "VIS_REDUNDANT"
        op = key_row.operator("yato_vis.clear_keys", text="", icon="TRASH")
        op.scope = "VIS_ALL"

        if act is None:
            return

        col = layout.column(align=True)
        col.prop(act, "location")
        col.prop(act, "rotation_euler")
        col.prop(act, "scale")

        # Match to Active
        match_box = layout.box()
        match_box.label(text="Match Sel → Active:", icon="PIVOT_ACTIVE")
        mrow = match_box.row(align=True)
        op = mrow.operator("yato_vis.match_transform_to_active", text="Loc")
        op.use_location = True; op.use_rotation = False; op.use_scale = False
        op = mrow.operator("yato_vis.match_transform_to_active", text="Rot")
        op.use_location = False; op.use_rotation = True; op.use_scale = False
        op = mrow.operator("yato_vis.match_transform_to_active", text="Scl")
        op.use_location = False; op.use_rotation = False; op.use_scale = True
        op = match_box.operator("yato_vis.match_transform_to_active", text="Match All", icon="CHECKMARK")
        op.use_location = True; op.use_rotation = True; op.use_scale = True

        # Transform fcurve cleanup
        tk_row = layout.row(align=True)
        tk_row.label(text="Clear TF Keys:")
        op = tk_row.operator("yato_vis.clear_keys", text="Redund.")
        op.scope = "TF_REDUNDANT"
        op = tk_row.operator("yato_vis.clear_keys", text="All", icon="TRASH")
        op.scope = "TF_ALL"


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

class YATOVIS_PT_snapshots(bpy.types.Panel):
    bl_label = "Snapshots"
    bl_idname = "YATOVIS_PT_snapshots"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY
    bl_parent_id = "YATOVIS_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        st = context.scene.yato_vis

        head = layout.row(align=True)
        head.label(text=f"Snapshots ({len(st.snapshots)})", icon="ARMATURE_DATA")
        head.operator("yato_vis.snapshot_clean_dead_refs", text="", icon="BRUSH_DATA")

        layout.template_list(
            "YATOVIS_UL_snapshots", "",
            st, "snapshots",
            st, "active_snapshot_index",
            rows=4,
        )

        btn_row = layout.row(align=True)
        btn_row.operator("yato_vis.snapshot_create", text="Save", icon="ADD")
        btn_row.operator("yato_vis.snapshot_overwrite", text="Overwrite", icon="FILE_REFRESH")
        btn_row.operator("yato_vis.snapshot_remove", text="", icon="REMOVE")

        if 0 <= st.active_snapshot_index < len(st.snapshots):
            r_row = layout.row(align=True)
            op = r_row.operator("yato_vis.snapshot_restore", text="Restore All", icon="LOOP_BACK")
            op.scope = "ALL"; op.insert_keyframe = False
            op = r_row.operator("yato_vis.snapshot_restore", text="Selected", icon="RESTRICT_SELECT_OFF")
            op.scope = "SELECTED"; op.insert_keyframe = False

"""3D View > Sidebar (N) > Yato > Visibility パネル。"""

from __future__ import annotations

import bpy


CATEGORY = "Yato"  # N パネルタブ名（Yato 系アドオン共通）


class YATOVIS_UL_groups(bpy.types.UIList):
    bl_idname = "YATOVIS_UL_groups"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="GROUP")

        op = row.operator("yato_vis.group_set_visibility", text="", icon="RESTRICT_VIEW_OFF")
        op.group_index = index
        op.target = "VIEWPORT"
        op.mode = "TOGGLE"

        op = row.operator("yato_vis.group_set_visibility", text="", icon="RESTRICT_RENDER_OFF")
        op.group_index = index
        op.target = "RENDER"
        op.mode = "TOGGLE"

        op = row.operator("yato_vis.group_select", text="", icon="RESTRICT_SELECT_OFF")
        op.group_index = index

        dead = 0
        alive = 0
        for m in item.members:
            if m.member_type == "OBJECT":
                if m.object_ref is None:
                    dead += 1
                else:
                    alive += 1
            elif m.member_type == "COLLECTION":
                if m.collection_ref is None:
                    dead += 1
                else:
                    alive += 1
        if dead > 0:
            row.label(text=f"{alive}+{dead}⚠", icon="ERROR")
        else:
            row.label(text=f"{alive}")


class YATOVIS_UL_snapshots(bpy.types.UIList):
    bl_idname = "YATOVIS_UL_snapshots"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="ARMATURE_DATA")
        dead = sum(1 for e in item.entries if e.object_ref is None)
        alive = len(item.entries) - dead
        if dead > 0:
            row.label(text=f"{alive}+{dead}⚠", icon="ERROR")
        else:
            row.label(text=f"{alive}")


class YATOVIS_UL_templates(bpy.types.UIList):
    bl_idname = "YATOVIS_UL_templates"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="PRESET")
        # 適用ボタン
        ap = row.operator("yato_vis.template_apply", text="", icon="PLAY")
        ap.template_index = index
        row.label(text=f"{len(item.keys)}")


class YATOVIS_PT_main(bpy.types.Panel):
    bl_label = "Visibility"
    bl_idname = "YATOVIS_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY

    def draw(self, context):  # type: ignore[override]
        layout = self.layout
        scene = context.scene
        st = getattr(scene, "yato_vis", None)
        if st is None:
            layout.label(text="yato_vis PropertyGroup が未登録です", icon="ERROR")
            return

        sel_count = len(getattr(context, "selected_objects", []) or [])
        ts = scene.tool_settings

        # --- Quick Toggle ---
        qt = layout.box()
        head = qt.row(align=True)
        head.label(text=f"Quick Toggle (sel: {sel_count})", icon="HIDE_OFF")

        row = qt.row(align=True)
        op = row.operator("yato_vis.set_visibility", text="Viewport", icon="RESTRICT_VIEW_OFF")
        op.target = "VIEWPORT"; op.mode = "TOGGLE"
        op = row.operator("yato_vis.set_visibility", text="Render", icon="RESTRICT_RENDER_OFF")
        op.target = "RENDER"; op.mode = "TOGGLE"
        op = row.operator("yato_vis.set_visibility", text="Select", icon="RESTRICT_SELECT_OFF")
        op.target = "SELECT"; op.mode = "TOGGLE"

        row = qt.row(align=True)
        op = row.operator("yato_vis.set_visibility", text="Show All", icon="HIDE_OFF")
        op.target = "BOTH"; op.mode = "SHOW"
        op = row.operator("yato_vis.set_visibility", text="Hide All", icon="HIDE_ON")
        op.target = "BOTH"; op.mode = "HIDE"

        # --- Burst ---
        bb = layout.box()
        bb.label(text="Burst (range)", icon="MARKER_HLT")
        bb.prop(st, "burst_duration", text="Duration")
        row = bb.row(align=True)
        op = row.operator("yato_vis.burst", text="Burst Hide", icon="HIDE_ON")
        op.state = "HIDE"; op.target = "BOTH"; op.use_scene_duration = True
        op = row.operator("yato_vis.burst", text="Burst Show", icon="HIDE_OFF")
        op.state = "SHOW"; op.target = "BOTH"; op.use_scene_duration = True
        bb.label(text="Camera range (current bind):", icon="VIEW_CAMERA")
        row = bb.row(align=True)
        op = row.operator("yato_vis.burst_camera_range", text="Cam Hide", icon="HIDE_ON")
        op.state = "HIDE"; op.target = "BOTH"
        op = row.operator("yato_vis.burst_camera_range", text="Cam Show", icon="HIDE_OFF")
        op.state = "SHOW"; op.target = "BOTH"

        # --- Groups ---
        gb = layout.box()
        row = gb.row(align=True)
        row.label(text=f"Groups ({len(st.groups)})", icon="GROUP")
        row.operator("yato_vis.group_clean_dead_refs", text="", icon="BRUSH_DATA")

        list_row = gb.row(align=True)
        list_row.template_list(
            "YATOVIS_UL_groups", "",
            st, "groups",
            st, "active_group_index",
            rows=4,
        )

        btn_row = gb.row(align=True)
        btn_row.operator("yato_vis.group_create", text="New", icon="ADD")
        btn_row.operator("yato_vis.group_remove", text="", icon="REMOVE")
        btn_row.operator("yato_vis.group_add_selection", text="Add Sel", icon="ADD")
        btn_row.operator("yato_vis.group_add_collection", text="Add Coll", icon="OUTLINER_COLLECTION")

        if 0 <= st.active_group_index < len(st.groups):
            g = st.groups[st.active_group_index]
            detail = gb.box()
            detail.label(text=f"Members of '{g.name}'", icon="DOT")
            if len(g.members) == 0:
                detail.label(text="(empty)", icon="INFO")
            for mi, m in enumerate(g.members):
                m_box = detail.box()
                m_row = m_box.row(align=True)
                if m.member_type == "OBJECT":
                    m_row.label(text="", icon="OBJECT_DATA")
                    m_row.prop(m, "object_ref", text="")
                else:
                    m_row.label(text="", icon="OUTLINER_COLLECTION")
                    m_row.prop(m, "collection_ref", text="")
                rm = m_row.operator("yato_vis.group_remove_member", text="", icon="X")
                rm.group_index = st.active_group_index
                rm.member_index = mi

                if m.member_type == "COLLECTION" and m.collection_ref is not None:
                    solo_row = m_box.row(align=True)
                    solo_row.prop(m, "solo_enabled", text="Solo", toggle=True, icon="SOLO_ON")
                    if m.solo_enabled:
                        solo_row.prop(m, "solo_target", text="")
                        prev = solo_row.operator("yato_vis.solo_step", text="", icon="TRIA_LEFT")
                        prev.group_index = st.active_group_index
                        prev.member_index = mi
                        prev.direction = "PREV"
                        nxt = solo_row.operator("yato_vis.solo_step", text="", icon="TRIA_RIGHT")
                        nxt.group_index = st.active_group_index
                        nxt.member_index = mi
                        nxt.direction = "NEXT"
                        apply_row = m_box.row(align=True)
                        ap = apply_row.operator("yato_vis.solo_apply", text="Apply Solo", icon="CHECKMARK")
                        ap.group_index = st.active_group_index
                        ap.member_index = mi
                    else:
                        ap = solo_row.operator("yato_vis.solo_apply", text="Show All", icon="HIDE_OFF")
                        ap.group_index = st.active_group_index
                        ap.member_index = mi

        # --- Active Object (Kinema 風 icon row 配置) ---
        act = context.active_object
        ab = layout.box()
        head = ab.row(align=True)
        if act is None:
            head.label(text="Active: (none)", icon="OBJECT_DATA")
        else:
            head.label(text=f"Active: {act.name}", icon="OBJECT_DATAMODE")

        # Kinema 風 icon row（Active Object 内）
        key_row = ab.row(align=True)
        key_row.alignment = "RIGHT"
        key_row.operator(
            "yato_vis.toggle_auto_keyframe",
            text="",
            icon="REC" if ts.use_keyframe_insert_auto else "RADIOBUT_OFF",
            depress=ts.use_keyframe_insert_auto,
        )
        key_row.operator("yato_vis.key_visibility", text="Key All", icon="KEY_HLT")
        op = key_row.operator("yato_vis.clear_keys", text="", icon="KEY_DEHLT")
        op.scope = "VIS_REDUNDANT"
        key_row.operator("yato_vis.template_record", text="", icon="COPYDOWN")
        key_row.operator("yato_vis.template_apply", text="", icon="PASTEDOWN")
        op = key_row.operator("yato_vis.clear_keys", text="", icon="TRASH")
        op.scope = "VIS_ALL"

        if act is None:
            ab.label(text="(no active object)", icon="INFO")
        else:
            col = ab.column(align=True)
            col.prop(act, "location")
            col.prop(act, "rotation_euler")
            col.prop(act, "scale")
            tk_row = ab.row(align=True)
            tk_row.label(text="Clear TF Keys:", icon="KEY_DEHLT")
            op = tk_row.operator("yato_vis.clear_keys", text="Redund.")
            op.scope = "TF_REDUNDANT"
            op = tk_row.operator("yato_vis.clear_keys", text="All", icon="TRASH")
            op.scope = "TF_ALL"

        # --- Templates ---
        tb = layout.box()
        row = tb.row(align=True)
        row.label(text=f"Vis Templates ({len(st.templates)})", icon="PRESET")
        row.operator("yato_vis.template_load_defaults", text="", icon="FILE_REFRESH")

        tb.template_list(
            "YATOVIS_UL_templates", "",
            st, "templates",
            st, "active_template_index",
            rows=4,
        )

        btn_row = tb.row(align=True)
        btn_row.operator("yato_vis.template_record", text="Record", icon="REC")
        btn_row.operator("yato_vis.template_apply", text="Apply to Sel", icon="PLAY")
        btn_row.operator("yato_vis.template_rename", text="", icon="GREASEPENCIL")
        btn_row.operator("yato_vis.template_remove", text="", icon="REMOVE")

        io_row = tb.row(align=True)
        io_row.operator("yato_vis.template_export_json", text="Export", icon="EXPORT")
        io_row.operator("yato_vis.template_import_json", text="Import", icon="IMPORT")

        # --- Snapshots ---
        sb = layout.box()
        row = sb.row(align=True)
        row.label(text=f"Snapshots ({len(st.snapshots)})", icon="ARMATURE_DATA")
        row.operator("yato_vis.snapshot_clean_dead_refs", text="", icon="BRUSH_DATA")

        sb.template_list(
            "YATOVIS_UL_snapshots", "",
            st, "snapshots",
            st, "active_snapshot_index",
            rows=4,
        )

        btn_row = sb.row(align=True)
        btn_row.operator("yato_vis.snapshot_create", text="Save", icon="ADD")
        btn_row.operator("yato_vis.snapshot_overwrite", text="Overwrite", icon="FILE_REFRESH")
        btn_row.operator("yato_vis.snapshot_remove", text="", icon="REMOVE")

        if 0 <= st.active_snapshot_index < len(st.snapshots):
            r_row = sb.row(align=True)
            op = r_row.operator("yato_vis.snapshot_restore", text="Restore (All)", icon="LOOP_BACK")
            op.scope = "ALL"; op.insert_keyframe = False
            op = r_row.operator("yato_vis.snapshot_restore", text="Selected", icon="RESTRICT_SELECT_OFF")
            op.scope = "SELECTED"; op.insert_keyframe = False

"""Shot Cast — Camera Marker をショットとみなし、Group ごとに出演ショットを設定。

Bake ロジック:
  - Camera Marker をフレーム順に並べる
  - 各 Group について、各 marker 時点での「出演フラグ」を判定（marker_name が
    group.cast_markers に含まれていれば True）
  - 出演フラグが直前と異なる、または最初の marker のとき、hide_viewport と
    hide_render に CONSTANT 補間でキー挿入。連続する同値は省略（CONSTANT が
    値を保持するので冗長キーは不要）
  - Group の COLLECTION メンバはサブコレクション再帰展開した全オブジェクトに
    対して同じパターンを適用（Solo モードは無関係）

UI トグル時の自動 Bake は scene.yato_vis.cast_auto_bake で制御。
"""

from __future__ import annotations

import bpy
from bpy.props import IntProperty, StringProperty

from ._base import YatoVisOperator
from .group_ops import group_all_objects


def _get_camera_markers(scene):
    """カメラ付き Timeline Marker を frame 昇順で返す。"""
    return sorted(
        (m for m in scene.timeline_markers if m.camera is not None),
        key=lambda m: m.frame,
    )


# ---------------------------------------------------------------------------
# kinema.shots[] ベースの cast 解決（Phase 2 で導入）
# ---------------------------------------------------------------------------

def _kinema_shots_available(scene) -> bool:
    """scene.kinema.shots[] が canonical schema として使えるか判定。

    `data_format_version >= 2` かつ shots[] が空でないことを条件とする。
    """
    k = getattr(scene, "kinema", None)
    if k is None:
        return False
    dfv = getattr(k, "data_format_version", 1)
    if dfv < 2:
        return False
    try:
        return len(k.shots) > 0
    except Exception:
        return False


def _group_appears_in_shot(scene, group, marker_name: str) -> bool:
    """Phase 2: kinema.shots[] から group の出演を判定。"""
    cast_on, _ = _resolve_cast_state_at_shot(scene, group, marker_name)
    return cast_on


def _resolve_cast_state_at_shot(scene, group, marker_name: str) -> tuple[bool, str]:
    """指定 marker での group の (出演フラグ, solo_target_name) を返す。

    Phase A: shot ごとに **per-cast solo target** を持てるようにする。
    - 出演 ON かつ solo_target_name が指定されていれば、その shot ではその
      object 名だけ可視（group 内の他は hidden）にする solo モード扱い。
    - solo_target_name 空なら group 全員可視（通常モード）。

    Returns: (cast_on, solo_target_name)
    """
    if _kinema_shots_available(scene):
        try:
            target = group.name
        except Exception:
            return (False, "")
        # marker_name で線形検索
        shot = None
        for s in scene.kinema.shots:
            if s.marker_name == marker_name:
                shot = s
                break
        if shot is None:
            return (False, "")
        for c in shot.cast:
            if c.group_name == target and c.enabled:
                solo_name = getattr(c, "solo_target_name", "") or ""
                return (True, solo_name)
        return (False, "")
    # legacy fallback
    return (_group_appears_in(group, marker_name), "")


def _group_appears_in(group, marker_name: str) -> bool:
    """**legacy fallback**: 旧 group.cast_markers から判定。

    Phase 2 以降、`scene.kinema.shots[]` があればそちらを優先。
    """
    try:
        for c in group.cast_markers:
            if c.marker_name == marker_name:
                return True
    except Exception:
        pass
    return False


def _set_group_appearance(group, marker_name: str, appears: bool) -> None:
    """group.cast_markers を marker_name について appears 状態に揃える。"""
    existing_idx = -1
    for i, c in enumerate(group.cast_markers):
        if c.marker_name == marker_name:
            existing_idx = i
            break
    if appears:
        if existing_idx < 0:
            entry = group.cast_markers.add()
            entry.marker_name = marker_name
    else:
        if existing_idx >= 0:
            group.cast_markers.remove(existing_idx)


def _insert_visibility_key(obj, channel: str, frame: int, value: bool) -> None:
    """obj.channel に frame で value を CONSTANT 補間でキー挿入。

    **重要**: Auto Keyframe (use_keyframe_insert_auto) が ON のとき、
    setattr(obj, channel, ...) が現フレームに自動キーを刺してしまう。
    これが入れた直後の `setattr(obj, channel, saved)` で「現フレームでは
    元の値に戻る」キーを上書きして、結果として bake が無効化される。

    対策: bake 中は use_keyframe_insert_auto を一時 OFF にして、終了後に復元。
    """
    if obj is None or getattr(obj, channel, None) is None:
        return
    # Auto Keyframe を一時 OFF（depsgraph mutation 防止）
    scene = None
    try:
        import bpy as _bpy
        scene = _bpy.context.scene
    except Exception:
        pass
    auto_kf_saved = False
    if scene is not None:
        try:
            auto_kf_saved = scene.tool_settings.use_keyframe_insert_auto
            if auto_kf_saved:
                scene.tool_settings.use_keyframe_insert_auto = False
        except Exception:
            auto_kf_saved = False

    saved = getattr(obj, channel)
    try:
        setattr(obj, channel, value)
        try:
            obj.keyframe_insert(data_path=channel, frame=frame)
        except Exception:
            pass
    finally:
        try:
            setattr(obj, channel, saved)
        except Exception:
            pass
        # Auto Keyframe を復元
        if scene is not None and auto_kf_saved:
            try:
                scene.tool_settings.use_keyframe_insert_auto = True
            except Exception:
                pass
    # CONSTANT 補間に
    ad = obj.animation_data
    if ad is None or ad.action is None:
        return
    action = ad.action
    fcurves_iter = []
    if hasattr(action, "fcurves"):
        fcurves_iter = list(action.fcurves)
    else:
        # Layered Actions
        for layer in getattr(action, "layers", None) or []:
            for strip in getattr(layer, "strips", None) or []:
                for slot in getattr(action, "slots", None) or []:
                    try:
                        cb = strip.channelbag(slot)
                    except Exception:
                        cb = None
                    if cb is None:
                        continue
                    fcurves_iter.extend(getattr(cb, "fcurves", []) or [])
    for fc in fcurves_iter:
        try:
            if fc.data_path != channel:
                continue
        except Exception:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 0.5:
                try:
                    kp.interpolation = "CONSTANT"
                except Exception:
                    pass
                break


def _iter_action_fcurves(action):
    """Layered Actions 両対応で fcurve を yield。"""
    if action is None:
        return
    if hasattr(action, "fcurves"):
        for fc in list(action.fcurves):
            yield fc
        return
    for layer in getattr(action, "layers", None) or []:
        for strip in getattr(layer, "strips", None) or []:
            for slot in getattr(action, "slots", None) or []:
                try:
                    cb = strip.channelbag(slot)
                except Exception:
                    cb = None
                if cb is None:
                    continue
                for fc in list(getattr(cb, "fcurves", []) or []):
                    yield fc


def _clear_keys_at_frames(obj, channels: tuple, frames_set: set) -> int:
    """obj の指定 channels (hide_viewport / hide_render 等) の指定フレーム群に
    あるキーフレームポイントだけを削除（fcurve 自体は残す）。

    削除キー数を返す。
    """
    if obj is None or obj.animation_data is None or obj.animation_data.action is None:
        return 0
    removed = 0
    for fc in _iter_action_fcurves(obj.animation_data.action):
        try:
            if fc.data_path not in channels:
                continue
        except Exception:
            continue
        # まず削除対象 kp を集める（インデックスで集めると後段で崩れるため参照保持）
        targets = []
        for kp in fc.keyframe_points:
            if int(round(kp.co.x)) in frames_set:
                targets.append(kp)
        for kp in targets:
            try:
                fc.keyframe_points.remove(kp)
                removed += 1
            except Exception:
                pass
    return removed


def _get_old_marker_frames_to_clear(scene, st) -> set:
    """前回 Bake 時のマーカーのうち、現マーカー名集合に無いもの（=削除/リネーム）の frame 集合。"""
    current_names = {m.name for m in _get_camera_markers(scene)}
    return {entry.frame for entry in st.last_baked_markers if entry.marker_name not in current_names}


def sync_inherit_new_markers(scene, st) -> int:
    """新規追加マーカーについて、直前マーカーの cast 設定を継承する。

    新規 = last_baked_markers に名前が無いもの。
    継承基準 = frame が直前で、かつ last_baked_markers にあった（=前回 Bake 時に
    既知だった）マーカー。

    継承で追加した cast_markers のエントリ数を返す。
    """
    current_markers = _get_camera_markers(scene)
    last_known_names = {e.marker_name for e in st.last_baked_markers}
    new_markers = [m for m in current_markers if m.name not in last_known_names]
    if not new_markers:
        return 0
    inherited = 0
    for nm in new_markers:
        # 直前の既知マーカー（時系列で frame < nm.frame の最大）
        prev = None
        for m in current_markers:
            if m.frame >= nm.frame:
                break
            if m.name in last_known_names:
                prev = m
        if prev is None:
            continue
        for g in st.groups:
            if not any(c.marker_name == prev.name for c in g.cast_markers):
                continue  # prev は OFF だったので継承不要
            if any(c.marker_name == nm.name for c in g.cast_markers):
                continue  # 既に設定済
            entry = g.cast_markers.add()
            entry.marker_name = nm.name
            inherited += 1
    return inherited


def update_last_baked_markers(scene, st) -> None:
    """last_baked_markers を現マーカーで全置換。"""
    st.last_baked_markers.clear()
    for m in _get_camera_markers(scene):
        e = st.last_baked_markers.add()
        e.marker_name = m.name
        e.frame = m.frame


def _resolve_solo_target(group):
    """Group の Solo target を決定。bound_object 優先、なければ最初の COLLECTION メンバの solo_target。"""
    if group.bound_object is not None:
        return group.bound_object
    for m in group.members:
        if m.member_type == "COLLECTION" and m.solo_target is not None:
            return m.solo_target
    return None


def bake_group_cast(scene, group, solo_mode: bool = False,
                    extra_clear_frames: set | None = None) -> tuple[int, int]:
    """1 Group の cast_markers を hide_viewport / hide_render キーへ反映。

    マーカーフレームのキーだけクリア → cast_markers に従って CONSTANT 補間で挿入。
    マーカー外のフレームに手動で打ったキーは温存される。

    extra_clear_frames: 削除されたマーカーの古い frame など、追加でクリアしたい
      フレーム集合（呼び元が _get_old_marker_frames_to_clear で算出）。

    solo_mode=True のとき:
      - bound_object (or 最初の COLLECTION メンバの solo_target) のみ ON 中に可視
      - 同 Group 内の他オブジェクトは ON 中も非表示
      - OFF 期間中は通常モードと同じく全員非表示

    Returns: (cleared_keys, inserted_keys)
    """
    markers = _get_camera_markers(scene)
    if not markers:
        return (0, 0)
    objs = group_all_objects(group)
    if not objs:
        return (0, 0)

    solo_obj = _resolve_solo_target(group) if solo_mode else None

    # クリア対象 frame 集合: 現マーカーフレーム + 削除済マーカーの旧フレーム
    clear_frames = {m.frame for m in markers}
    if extra_clear_frames:
        clear_frames.update(extra_clear_frames)

    cleared = 0
    for o in objs:
        cleared += _clear_keys_at_frames(o, ("hide_viewport", "hide_render"), clear_frames)

    # cast 状態に従ってキー再挿入。
    # **Phase A**: shot ごとに per-cast solo_target_name を尊重する。
    #
    #   shot.cast[group].solo_target_name == "Foo"
    #     → この shot ではこの group の中で "Foo" だけ可視（他は hidden）
    #   solo_target_name 空 + solo_mode=True (group level fallback)
    #     → group.bound_object / member.solo_target を solo に使う
    #   両方無し
    #     → 通常モード (group 全員可視)
    inserted = 0
    for o in objs:
        prev_hidden = None
        for m in markers:
            cast_on, shot_solo_target = _resolve_cast_state_at_shot(
                scene, group, m.name,
            )
            # Solo target を決定（shot 単位 > group 単位）
            effective_solo = ""
            if shot_solo_target:
                effective_solo = shot_solo_target
            elif solo_mode and solo_obj is not None:
                effective_solo = solo_obj.name

            if effective_solo:
                is_solo = (o.name == effective_solo)
                hidden = not (cast_on and is_solo)
            else:
                hidden = not cast_on

            if prev_hidden is None or hidden != prev_hidden:
                _insert_visibility_key(o, "hide_viewport", m.frame, hidden)
                _insert_visibility_key(o, "hide_render", m.frame, hidden)
                inserted += 2
            prev_hidden = hidden
    return (cleared, inserted)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class YATOVIS_OT_cast_toggle(YatoVisOperator):
    """Group の cast_markers をトグル（指定 marker 名で出演 ON/OFF）。

    cast_auto_bake が True なら同時に Bake も実行。
    """
    bl_idname = "yato_vis.cast_toggle"
    bl_label = "Toggle Cast"
    bl_description = "Group の出演 marker をトグル（cast_auto_bake が ON なら同時に Bake）"

    group_index: IntProperty(default=-1)
    marker_name: StringProperty(default="")

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            return {"CANCELLED"}
        if not self.marker_name:
            return {"CANCELLED"}
        g = st.groups[idx]
        currently = _group_appears_in(g, self.marker_name)
        _set_group_appearance(g, self.marker_name, not currently)
        if st.cast_auto_bake:
            # sync (継承) + 削除マーカーの旧フレームを extra clear
            inherited = sync_inherit_new_markers(scene, st)
            extra = _get_old_marker_frames_to_clear(scene, st)
            cleared, inserted = bake_group_cast(scene, g, extra_clear_frames=extra)
            update_last_baked_markers(scene, st)
            inh_str = f", inherited {inherited}" if inherited else ""
            self.report(
                {"INFO"},
                f"'{g.name}' @ '{self.marker_name}' → "
                f"{'ON' if not currently else 'OFF'}, "
                f"baked ({cleared} cleared / {inserted} keys{inh_str})",
            )
        else:
            self.report(
                {"INFO"},
                f"'{g.name}' @ '{self.marker_name}' → {'ON' if not currently else 'OFF'} (not baked)",
            )
        return {"FINISHED"}


class YATOVIS_OT_cast_bake_group(YatoVisOperator):
    """指定 Group の cast 設定を hide_viewport / hide_render キーへ反映。"""
    bl_idname = "yato_vis.cast_bake_group"
    bl_label = "Bake Cast"
    bl_description = "アクティブ Group の cast 設定を hide_viewport / hide_render キーへ反映"

    group_index: IntProperty(default=-1)

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            self.report({"WARNING"}, "Group が選択されていません")
            return {"CANCELLED"}
        g = st.groups[idx]
        inherited = sync_inherit_new_markers(scene, st)
        extra = _get_old_marker_frames_to_clear(scene, st)
        cleared, inserted = bake_group_cast(scene, g, extra_clear_frames=extra)
        update_last_baked_markers(scene, st)
        inh_str = f", inherited {inherited}" if inherited else ""
        self.report(
            {"INFO"},
            f"Baked '{g.name}': {cleared} cleared, {inserted} keys{inh_str}",
        )
        return {"FINISHED"}


class YATOVIS_OT_cast_bake_all(YatoVisOperator):
    """全 Group の cast 設定を一括 Bake。"""
    bl_idname = "yato_vis.cast_bake_all"
    bl_label = "Bake All Cast"
    bl_description = "全 Group の cast 設定を hide_viewport / hide_render キーへ反映"

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        inherited = sync_inherit_new_markers(scene, st)
        extra = _get_old_marker_frames_to_clear(scene, st)
        total_cleared = 0
        total_inserted = 0
        for g in st.groups:
            cleared, inserted = bake_group_cast(scene, g, extra_clear_frames=extra)
            total_cleared += cleared
            total_inserted += inserted
        update_last_baked_markers(scene, st)
        self.report(
            {"INFO"},
            f"Baked {len(st.groups)} group(s): "
            f"{total_cleared} cleared, {total_inserted} keys, inherited {inherited}",
        )
        return {"FINISHED"}


class YATOVIS_OT_cast_bake_group_solo(YatoVisOperator):
    """Solo モードで Bake — bound_object のみ ON 期間中に可視、他は非表示。"""
    bl_idname = "yato_vis.cast_bake_group_solo"
    bl_label = "Bake Cast (Solo)"
    bl_description = (
        "Shot Cast を Solo モードで Bake。"
        "出演 ON のショット中、bound_object (or solo_target) だけ可視、"
        "Group 内の他オブジェクトは非表示にする（表情差分などで 1 個だけ見せる用途）"
    )

    group_index: IntProperty(default=-1)

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            self.report({"WARNING"}, "Group が選択されていません")
            return {"CANCELLED"}
        g = st.groups[idx]
        solo = _resolve_solo_target(g)
        if solo is None:
            self.report(
                {"WARNING"},
                f"'{g.name}' に bound_object / solo_target がありません。通常 Bake をご利用ください",
            )
            return {"CANCELLED"}
        inherited = sync_inherit_new_markers(scene, st)
        extra = _get_old_marker_frames_to_clear(scene, st)
        cleared, inserted = bake_group_cast(scene, g, solo_mode=True, extra_clear_frames=extra)
        update_last_baked_markers(scene, st)
        inh_str = f", inherited {inherited}" if inherited else ""
        self.report(
            {"INFO"},
            f"Solo Bake '{g.name}' (target={solo.name}): "
            f"{cleared} cleared, {inserted} keys{inh_str}",
        )
        return {"FINISHED"}


class YATOVIS_OT_cast_bake_all_solo(YatoVisOperator):
    """全 Group を Solo モードで Bake。Solo target が無い Group は通常 Bake にフォールバック。"""
    bl_idname = "yato_vis.cast_bake_all_solo"
    bl_label = "Bake All (Solo)"
    bl_description = (
        "全 Group を Solo モードで一括 Bake。"
        "bound_object / solo_target が無い Group は通常モードで Bake"
    )

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        inherited = sync_inherit_new_markers(scene, st)
        extra = _get_old_marker_frames_to_clear(scene, st)
        total_cleared = 0
        total_inserted = 0
        solo_count = 0
        for g in st.groups:
            solo = _resolve_solo_target(g)
            use_solo = (solo is not None)
            cleared, inserted = bake_group_cast(scene, g, solo_mode=use_solo, extra_clear_frames=extra)
            total_cleared += cleared
            total_inserted += inserted
            if use_solo:
                solo_count += 1
        update_last_baked_markers(scene, st)
        self.report(
            {"INFO"},
            f"Solo Bake All: {solo_count}/{len(st.groups)} solo, "
            f"{total_cleared} cleared, {total_inserted} keys, inherited {inherited}",
        )
        return {"FINISHED"}


class YATOVIS_OT_cast_clear_group(YatoVisOperator):
    """指定 Group の hide_viewport / hide_render fcurve を全削除。"""
    bl_idname = "yato_vis.cast_clear_group"
    bl_label = "Clear Visibility Keys"
    bl_description = "Group メンバの hide_viewport / hide_render fcurve を丸ごと削除"

    group_index: IntProperty(default=-1)

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        if not (0 <= idx < len(st.groups)):
            return {"CANCELLED"}
        g = st.groups[idx]
        from .keyframe_ops import _delete_matching
        total = 0
        for o in group_all_objects(g):
            total += _delete_matching(o, ("hide_viewport", "hide_render"), "ALL")
        self.report({"INFO"}, f"Cleared '{g.name}': {total} fcurves")
        return {"FINISHED"}


def get_visibility_keyframes(obj) -> list[tuple[str, int]]:
    """obj の hide_viewport / hide_render の全キーフレーム frame を返す。

    結果: [(channel, frame), ...] 重複なし、frame 昇順。
    """
    out: set[tuple[str, int]] = set()
    ad = getattr(obj, "animation_data", None)
    if ad is None or ad.action is None:
        return []
    action = ad.action
    fcurves_iter = []
    if hasattr(action, "fcurves"):
        fcurves_iter = list(action.fcurves)
    else:
        for layer in getattr(action, "layers", None) or []:
            for strip in getattr(layer, "strips", None) or []:
                for slot in getattr(action, "slots", None) or []:
                    try:
                        cb = strip.channelbag(slot)
                    except Exception:
                        cb = None
                    if cb is None:
                        continue
                    fcurves_iter.extend(getattr(cb, "fcurves", []) or [])
    for fc in fcurves_iter:
        try:
            dp = fc.data_path
        except Exception:
            continue
        if dp not in ("hide_viewport", "hide_render"):
            continue
        for kp in fc.keyframe_points:
            out.add((dp, int(round(kp.co.x))))
    return sorted(out, key=lambda x: (x[1], x[0]))


def _eval_hide_viewport_at(obj, frame: int) -> bool:
    """obj の hide_viewport を指定フレームで評価。

    fcurve があれば fcurve.evaluate を使い、なければ現在値を返す。
    scene.frame_set を呼ばないので副作用なし。
    """
    if obj is None:
        return False
    ad = getattr(obj, "animation_data", None)
    if ad is not None and ad.action is not None:
        action = ad.action
        fcurves_iter = []
        if hasattr(action, "fcurves"):
            fcurves_iter = list(action.fcurves)
        else:
            for layer in getattr(action, "layers", None) or []:
                for strip in getattr(layer, "strips", None) or []:
                    for slot in getattr(action, "slots", None) or []:
                        try:
                            cb = strip.channelbag(slot)
                        except Exception:
                            cb = None
                        if cb is None:
                            continue
                        fcurves_iter.extend(getattr(cb, "fcurves", []) or [])
        for fc in fcurves_iter:
            try:
                if fc.data_path == "hide_viewport":
                    return bool(fc.evaluate(frame) >= 0.5)
            except Exception:
                continue
    return bool(getattr(obj, "hide_viewport", False))


class YATOVIS_OT_cast_import_from_visibility(YatoVisOperator):
    """各カメラマーカー先頭フレームでの可視状態から cast_markers を逆取り込み。

    各 Group の所属オブジェクトについて、marker.frame での hide_viewport を
    fcurve.evaluate で評価し、1 個でも可視 (False) なら "出演" と判定。
    既存の cast_markers は全置換される（手動設定が消えるので明示操作のみ）。
    """
    bl_idname = "yato_vis.cast_import_from_visibility"
    bl_label = "Import Cast from Visibility"
    bl_description = (
        "各カメラマーカー先頭フレームで hide_viewport を評価し、"
        "各 Group の cast_markers に逆取り込み（既存設定は全置換）"
    )

    def invoke(self, context, event):  # noqa: ARG002
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):  # noqa: ARG002
        layout = self.layout
        layout.label(text="現在のアニメーションから Cast 設定を取り込みます", icon="IMPORT")
        layout.label(text="既存の cast_markers は全置換されます", icon="ERROR")

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        markers = _get_camera_markers(scene)
        if not markers:
            self.report({"WARNING"}, "カメラ付き Timeline Marker がありません")
            return {"CANCELLED"}
        if len(st.groups) == 0:
            self.report({"WARNING"}, "Group がありません")
            return {"CANCELLED"}
        total_on = 0
        for g in st.groups:
            objs = group_all_objects(g)
            if not objs:
                # 空 Group はスキップ
                continue
            g.cast_markers.clear()
            for m in markers:
                # 1 個でも可視ならこの shot に出演
                any_visible = any(not _eval_hide_viewport_at(o, m.frame) for o in objs)
                if any_visible:
                    entry = g.cast_markers.add()
                    entry.marker_name = m.name
                    total_on += 1
        self.report(
            {"INFO"},
            f"Imported cast: {total_on} ON cells across {len(st.groups)} group(s) × {len(markers)} shot(s)",
        )
        return {"FINISHED"}


class YATOVIS_OT_cast_remove_orphans(YatoVisOperator):
    """Group の cast_markers から、現マーカーに存在しないエントリ（orphan）を削除。"""
    bl_idname = "yato_vis.cast_remove_orphans"
    bl_label = "Remove Orphan Cast Entries"
    bl_description = "現シーンに存在しない Marker を参照している cast_markers エントリを削除"

    group_index: IntProperty(default=-1)

    def run(self, context):
        scene = context.scene
        st = scene.yato_vis
        idx = self.group_index if self.group_index >= 0 else st.active_group_index
        current_names = {m.name for m in _get_camera_markers(scene)}
        removed = 0
        if idx < 0:
            # 全 Group 対象
            for g in st.groups:
                i = len(g.cast_markers) - 1
                while i >= 0:
                    if g.cast_markers[i].marker_name not in current_names:
                        g.cast_markers.remove(i)
                        removed += 1
                    i -= 1
        else:
            if not (0 <= idx < len(st.groups)):
                return {"CANCELLED"}
            g = st.groups[idx]
            i = len(g.cast_markers) - 1
            while i >= 0:
                if g.cast_markers[i].marker_name not in current_names:
                    g.cast_markers.remove(i)
                    removed += 1
                i -= 1
        self.report({"INFO"}, f"Removed {removed} orphan cast entry(ies)")
        return {"FINISHED"}


class YATOVIS_OT_jump_to_keyframe(YatoVisOperator):
    """指定フレームへタイムラインジャンプ（hide_* キー探索用）。"""
    bl_idname = "yato_vis.jump_to_keyframe"
    bl_label = "Jump to Keyframe"
    bl_description = "指定フレームへタイムラインをジャンプ"

    frame: IntProperty(default=0)

    def run(self, context):
        context.scene.frame_set(self.frame)
        return {"FINISHED"}

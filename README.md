# Yato Visibility Kit

Blender 4.2+ / 5.x 用アドオン。オブジェクトの可視性 (`hide_viewport` / `hide_render`) を一括トグルし、保存したグループ単位での切り替え、表情差分用 Solo モード、Transform スナップショットまでをまとめて提供する。

## なぜ作ったか

Blender で個別オブジェクトの可視性を切り替えるとき、Object Properties > Visibility の中まで毎回潜る必要があり、まとめて操作する手段がない。`hide_viewport` / `hide_render` はキーフレームに乗るので、これを N パネルから素早く扱えるとシーン構築・差分アニメの作業が速くなる。

## 機能

### Quick Toggle（選択オブジェクト一括）
- `[Viewport]` `[Render]` `[Select]` のトグル — **全揃え方式**（1 個でも hide があれば全 show、全 show なら全 hide）
- `[Show All]` / `[Hide All]` （Viewport + Render 同時）
- Auto Keyframe（タイムラインの赤丸）と連動。トグル時にキー挿入
- `[Key Visibility]` で現フレームに `hide_viewport` / `hide_render` を一括キー挿入

### Groups
- Object 直指定 / Collection 参照 の混在メンバ
- 行ごとに `[👁][📷][選択]` のインライン操作
- 「選択から作成」「アクティブコレクションから作成」「Add Sel」「Add Coll」
- **Solo モード（Collection メンバ専用・表情差分用）**: Collection 内の 1 個だけ表示、`[◀][▶]` で順送り
- 死んだ参照 ⚠️ 表示 + `Clean Dead Refs`

### Active Object Transform
- N パネル「Item」を切り替えずに、Active の `location` / `rotation_euler` / `scale` を編集

### Snapshots
- 選択オブジェクトの Transform を `matrix_basis` で保存（rotation_mode 非依存）
- Restore は **All** / **Selected** の 2 スコープ
- Auto KF ON 時は復元と同時にキー挿入

### Clear Keys
| ボタン | 動作 |
|---|---|
| Clear Keys > Redund. | `hide_viewport` / `hide_render` で値が変化していない fcurve を削除 |
| Clear Keys > All | `hide_viewport` / `hide_render` の fcurve を丸ごと削除（確認ダイアログ） |
| Clear TF Keys > Redund. | `location` / `rotation_*` / `scale` の同上 |
| Clear TF Keys > All | Transform fcurve を丸ごと削除 |

## インストール（開発版）

```powershell
cd C:\Work\Yato\Claude\yato_visibility_kit
.\scripts\dev_install.ps1
```

`%APPDATA%\Blender Foundation\Blender\<最新バージョン>\extensions\user_default\yato_visibility_kit` に Junction を張る。Blender を再起動し、Edit > Preferences > Add-ons で `Yato Visibility Kit` を有効化。

特定バージョンに張りたい場合:
```powershell
.\scripts\dev_install.ps1 -BlenderVersion "5.0"
```

アンインストール:
```powershell
.\scripts\dev_uninstall.ps1
```

## 使い方

1. 3D View で N キーを押し、サイドバーの **「Yato」** タブを開く
2. **Visibility** パネル内の各セクションを操作
3. Auto KF をオンにすれば、可視性トグルがそのままアニメーションになる（表情差分の切り替えキーがそのまま作れる）

### 表情差分の例
1. 各表情の画像オブジェクトを Collection `Face_Expressions` にまとめる
2. Quick Toggle 横の `New` → `Active Collection` で Group 作成
3. メンバ詳細で `Solo` を ON、`Solo Target` に最初の表情を選択
4. Auto KF ON にしてフレームを進め、`[▶]` で順送りすると差分アニメ完成

## ライセンス

GPL-3.0-or-later

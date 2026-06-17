# JYIMGEditor

JYIMGEditor, also known as "金庸群侠传贴图资源编辑器", is a lightweight sprite and texture resource editor for *Jin Yong Qun Xia Zhuan* and its mods. It focuses on the classic image archive pairs used by the game, including `idx/grp`, `wdx/wmp`, `sdx/smp`, and `fdx/fmp`, while preserving per-frame metadata such as width, height, X offset, and Y offset.

The project was created because the older editor sFishedit (SFE) is useful but incomplete for modern batch editing workflows. It lacks convenient batch PNG import/export, and it can be unstable when editing sprites on modern Windows 11 systems. JYIMGEditor is a new Python/Tkinter implementation intended to make sprite inspection, frame alignment, and bulk editing more practical.

[中文说明](README.md)

## Version 0.5 Highlights

- Selected-sprite PNG export now supports **scale factors** (1/2/4/8/16×) and **grid layouts** (4-in-1 / 9-in-1 / 16-in-1), with a `manifest.csv` recording per-tile offsets. Import automatically reconstructs from the manifest or filename.
- New **GIF animation export**: supports scale factors, transparent background (`#307070` → alpha), and auto-embeds anchor X/Y offsets in the filename along with a `_tr` suffix. Frames are saved independently to prevent merging.
- New **GIF animation import**: auto-detects scale/offsets from filename and scales down, converts alpha → `#307070` with tolerance, and expands merged frames by their duration multiple (120 ms base). Dual import modes: as-is / auto-crop.
- Dual import modes (as-is / auto-crop) apply to both PNG and GIF imports. As-is preserves edge padding so every sprite remains the same size; auto-crop trims transparent edges and corrects X/Y offsets.
- Major keyboard overhaul: legacy number keys 1–4 → F1–F4 + Alt+1–4; number keys now serve as digit index navigation (0.7 s timeout); new shortcuts for Home, End, Insert, Ctrl+T, Ctrl+R, Ctrl+G, Ctrl+Shift+G, Page Up/Down.
- Main-window undo/redo (Ctrl+Z / Ctrl+Shift+Z) for right-click operations, also shown in the context menu.
- Window dimensions are persisted to `config.ini` and are independent of the cell-width setting.
- The About dialog now has a "View Shortcuts" button that shows all keyboard shortcuts in a tabbed table.
- Sprite editor: Enter key confirms dimension/offset changes with undo support; current colour persists across open/close of the editor; selection drag no longer shows Alt tooltips.
- Context menu reorganized: GIF items moved to the file section; insert-blank works with multi-selection; copy/paste supports multiple sprites.

## Version 0.4 Highlights

- Added "画笔/油漆桶" right-click painting modes in the sprite editor. Brush mode supports right-button drag drawing with a 1-pixel line, while bucket mode fills contiguous matching-color regions.
- The sprite editor color swatch can be double-clicked to open the system color picker. Both the sprite editor and color conversion window now accept direct hex color input and map it to the nearest game palette color.
- In the sprite editor zoom canvas, plain mouse wheel or `Ctrl+mouse wheel` switches previous/next sprite, while `Alt+mouse wheel` changes zoom.
- Added main-window keyboard controls: `Delete`, arrow-key selection movement, and `Shift+Home/End` range selection.
- The main archive combobox supports numeric jumping to `fdxNNN/fmpNNN` fight sprite entries, such as `0`, `1`, quick `12`, or quick `117`.
- Split selected PNG import into offset-preserving and no-offset variants. The offset-preserving path reads `manifest.csv`; the no-offset path ignores `manifest.csv` and keeps the replaced sprite's original X/Y offsets.
- Batch offset now starts with blank fields and focuses the X field. Batch resize focuses the width field and supports arrow keys for the top/bottom/left/right anchors.
- Fixed horizontal-flip X offset math: width 38 with X offset 25 now flips to 13 and flips back to 25.
- Context-menu actions that require a selected sprite are disabled when no archive is loaded or no red selection box exists.

## Version 0.3 Highlights

- Added main-window "单元宽度" and "单元高度" controls for live grid-cell and selection-box sizing.
- Added a `[View]` section in `config.ini`; per-row values, unit width/height bases, and dropdown ranges are read from config first, with built-in defaults used only as fallback.
- Sprite editor and color conversion zoom levels are remembered for the current app run. The sprite editor's offset-crosshair and fixed-anchor checkboxes are also remembered until the app restarts.
- All comboboxes support `Home`/`End` for first/last item selection, and child windows now receive focus when opened.
- Expanded the context menu with horizontal flip, copy selected sprites to end, copy selected sprites to end in reverse order, and shift selected sprites forward/backward.
- "复制贴图(带偏移)" now supports copy/paste across two JYIMGEditor processes while preserving dimensions, pixels, and X/Y offsets, using only the standard library.
- Fixed original archive decoding so `#606060` is no longer mistaken for transparency. Original `idx/grp` transparency comes only from RLE skips or unencoded areas.

## Screenshots

### Main Window

![Main window](docs/images/main-window.png)

### Sprite Editor

![Sprite editor](docs/images/sprite-editor.png)

### Color Conversion

![Color conversion](docs/images/color-convert.png)

### Batch X/Y Offset Adjustment

![Batch X/Y offset adjustment](docs/images/batch-offset-dialog.png)

### Batch Width/Height Resize

![Batch width/height resize](docs/images/batch-resize-dialog.png)

### PNG Export Dialog

![PNG export dialog](docs/images/png-export-dialog.png)

### GIF Export Dialog

![GIF export dialog](docs/images/gif-export-dialog.png)

### GIF Demo — Wen Qingqing Sword Animation

Below is a custom-edited sword-wielding female character (Wen Qingqing), exported at 2× scale with transparent background:

![GIF animation demo](docs/images/fmp091_x70_y89_s2_tr.gif)

> This GIF can be directly re-imported via the "Import GIF Animation" function back into the corresponding `fdx091/fmp091` idx/grp archives. The software automatically scales it down and restores the transparent color. The filename `fmp091_x70_y89_s2_tr` encodes the anchor offset `(70, 89)`, the 2× scale marker, and the transparent background marker.

### About · View Shortcuts

Clicking the "查看快捷键" button in the About dialog opens the tabbed shortcut reference:

![About and shortcuts](docs/images/about-and-shortcuts.png)

## Features

- Configurable archive list through `config.ini`, including normal `File0..FileN` entries and fight sprite sequences such as `FightName=fdx***,fmp***`.
- Browse `idx/grp`-style archives with a thumbnail grid, scrolling, multi-selection, Shift range selection, and context menus.
- Configure per-row count, unit width/height bases, and dropdown ranges through the `[View]` section in `config.ini`; UI changes write the current selection back to the config. Window dimensions persist independently of cell width.
- Set the game `data` directory from the UI and save it back to `config.ini`.
- Edit a single sprite: width, height, X/Y offsets, zoom preview, 1× preview, offset crosshair, previous/next frame.
- Sprite editing supports brush and bucket right-click modes. Brush mode can draw by dragging; bucket mode fills contiguous matching-color areas.
- The sprite editor supports double-clicking the current color swatch to open the system color picker, and direct hex color input mapped to the nearest palette color.
- In the sprite editor, pressing Enter on dimension/offset fields applies them immediately with undo support. The current colour is retained across open/close of the editor and resets only on program restart.
- Sprite editor and color conversion zoom levels are remembered for the current app run, then reset to 4× after restart.
- The sprite editor remembers its offset-crosshair and fixed-anchor checkbox states for the current app run without creating extra state files.
- Read and write X/Y offsets as signed 16-bit values, allowing negative offsets.
- Pick colors from pixels with left click, paint pixels with right click, and use the configured transparent color.
- Crop a sprite by dragging a selection rectangle, updating dimensions and offsets accordingly.
- Undo and redo in the sprite editor, with disabled buttons when no step is available. Main window also supports Ctrl+Z / Ctrl+Shift+Z for right-click operations.
- Multi-color conversion window with source/target color slots, direct hex color input, zoom preview, test, restore, undo, redo, and final apply.
- Batch export PNG files with a `manifest.csv` containing `index/file/width/height/xoff/yoff`.
- Batch import PNG files by replacing the whole archive, appending to the end, or inserting after the current selection.
- Export selected sprites with optional scale (1/2/4/8/16×) and grid-layout modes (4-in-1 / 9-in-1 / 16-in-1), with a manifest including per-tile offsets.
- Import PNGs into selected sprites by filename order, with optional manifest-offset reading or offset-preservation. Dual import modes: as-is (keep edge padding) and auto-crop (trim transparent edges and correct offsets).
- Delete multiple selected sprites.
- Batch-adjust relative X/Y offsets for selected sprites, for example `+2`, `2`, or `-2`.
- Batch-resize selected sprites by relative delta or absolute dimensions, with a 3×3 anchor for cropping or padding.
- Horizontally flip selected sprites, reverse selected sprites in place, copy selected sprites to the end, and shift selected sprites forward/backward.
- Copy/paste single or multiple sprites through the system clipboard, and copy/paste sprites with X/Y offsets. Offset-preserving copy works across two running JYIMGEditor processes.
- Insert a blank sprite before the first selected sprite (multi-selection OK), or append a blank sprite to the end.
- Export selected sprites as a GIF animation with optional scale, transparent background, and filename-embedded X/Y offsets.
- Import a GIF animation into selected sprites with automatic scale/offset detection, alpha-to-#307070 conversion, and frame-expansion for merged frames.
- Save with confirmation and automatic `.bak_timestamp` backups for both idx and grp files.
- Prompt before switching archives when there are unsaved changes.
- Newly opened child windows are focused automatically for immediate keyboard use.
- Child windows support `Esc` to close.
- The About dialog includes a "View Shortcuts" button that displays all keyboard shortcuts in a tabbed table.
- `main.py` exposes `UI_FONT_SIZE`, `UI_FONT_FAMILY`, and `MAIN_WINDOW_EXTRA_WIDTH` near the top for local UI tuning.

## Author Page

Bilibili: https://space.bilibili.com/16385

Feel free to follow and send private messages for related questions.

## Improvements over sFishedit/SFE

- Batch PNG export and import with metadata-preserving `manifest.csv` workflow.
- Selected-image import/export with grid layouts (4-in-1 / 9-in-1 / 16-in-1) and automatic reconstruction.
- GIF animation export (scale, transparent background, offset embedding) and import (auto-scale-down, alpha-to-#307070, frame expansion).
- Main-window per-row and unit-size controls, with defaults and ranges configurable in `config.ini`. Window-size persistence independent of cell width.
- Lazy decoding and visible-thumbnail caching for large archives.
- Safer editing workflow with undo/redo, transparent color tools, crop selection, 1× and zoom previews, and offset crosshair preview. Enter key confirms dimension/offset edits instantly.
- Multi-color conversion with preview and delayed application.
- Batch relative offset adjustment for selected sprites.
- More multi-selection organization tools: horizontal flip, copy to end, reverse in place, forward/backward shifting, blank insertion.
- Fuller keyboard workflow: F1–F4 / Alt+1–4 for function windows, digit index navigation, arrow keys / Page Up/Down / Home / End / Insert for browsing, Ctrl+T/R/G/Shift+G for quick actions.
- Richer sprite editing tools: brush drag drawing, bucket fill, hex color input, and double-click system color picking.
- Cross-process offset-preserving sprite copy/paste for moving frames between two open archives (multi-sprite support).
- Main-window right-click operation undo/redo (Ctrl+Z / Ctrl+Shift+Z).
- Original archive decoding no longer treats the nearest palette index to the transparent color as transparent, preventing real colors such as `#606060` from being swallowed.
- A modern Windows-friendly implementation intended to avoid the crashes encountered with the old editor on Windows 11.

## Keyboard Shortcuts

For the full shortcut reference, open the program → "关于" → "查看快捷键" (About → View Shortcuts).

### Main Window

| Shortcut | Action |
|----------|--------|
| Enter | Load / refresh current archive |
| Ctrl+S | Save file |
| Ctrl+A | Select all sprites |
| Ctrl+C / Ctrl+V | Copy to / paste from system clipboard |
| Ctrl+Shift+C / Ctrl+Shift+V | Copy / paste sprite with offset |
| Ctrl+Z / Ctrl+Shift+Z | Undo / redo (right-click operations) |
| Ctrl+N | Append blank sprite to end |
| Ctrl+I | Insert blank sprite before selection |
| Ctrl+T | Flip selected horizontally |
| Ctrl+End | Copy selected to end |
| Ctrl+R | Reverse selected in place |
| Ctrl+G | Export selected as GIF |
| Ctrl+Shift+G | Import GIF animation into selected |
| Delete | Delete selected sprites |
| F1 / Alt+1 | Edit sprite |
| F2 / Alt+2 | Batch adjust X/Y offset |
| F3 / Alt+3 | Batch resize width/height |
| F4 / Alt+4 | Color conversion |
| Home / End | Jump to first / last sprite (single selection) |
| Insert / Ctrl+Insert | Insert blank before / append blank to end |
| Page Up / Page Down | Scroll up/down by one page |
| 0–9 (consecutive) | Jump to sprite by index number (0.7 s timeout) |
| Arrow keys | Move selection |
| Shift+Arrow keys | Extend selection |
| Shift+Home / Shift+End | Select to first / last |
| Mouse wheel (canvas) | Vertical scroll |

### Sprite Editor

| Shortcut | Action |
|----------|--------|
| Ctrl+Z / Ctrl+Shift+Z | Undo / redo |
| Ctrl+C / Ctrl+V | Copy to / paste from system clipboard |
| Ctrl+E | Toggle offset crosshair |
| Ctrl+Q | Toggle fixed X/Y offset anchor |
| Enter (input fields) | Confirm dimension / offset changes |
| ← → | Previous / next sprite |
| Esc | Close editor |
| Mouse wheel | Switch previous / next sprite |
| Ctrl+mouse wheel | Switch previous / next sprite |
| Alt+mouse wheel | Change zoom level |
| Left-click canvas | Pick color |
| Right-click drag canvas | Paint (brush or bucket mode) |
| Left-click drag canvas | Crop sprite |
| Double-click color swatch | System color picker |

### Color Conversion

| Shortcut | Action |
|----------|--------|
| Ctrl+Z / Ctrl+Shift+Z | Undo / redo |
| Left-click swatch | Select current row slot |
| Double-click swatch | System color picker |
| Left-click preview | Pick color from preview |
| Esc | Close window |

## Usage

1. Run the application.
2. Click "设置data路径" and choose the game's `data` directory.
3. Select an archive pair such as `hdgrp.idx/hdgrp.grp` or `wdx/wmp`.
4. Click "贴图查看", or press `Enter`.
5. Double-click or right-click a sprite to edit it.
6. Save with the main "保存" button or `Ctrl+S`. Backups are generated automatically.

## Format Notes

- `idx` stores the ending offset of each image.
- Image 0 spans `0 -> idx[0]`; image N spans `idx[N-1] -> idx[N]`.
- A single `grp` image starts with an 8-byte header: width, height, X offset, Y offset, each little-endian 16-bit.
- Pixel rows are stored with per-row RLE.
- Each RLE segment uses `skip,count`, where `skip` is relative to the previous segment end.
- When decoding original `idx/grp` data, transparency comes only from RLE skips or unencoded areas; the nearest palette index to `#307070` is not treated as transparent.
- The default transparent color is `#307070`. PNG import treats exact `#307070` pixels and alpha-transparent pixels as transparent; GIF import adds tolerance matching for quantization shifts.
- The default palette file is `mmap.col`.

## Build

Python 3, Pillow, and PyInstaller are required. Tkinter is usually bundled with Python on Windows.

```powershell
.\build_exe.ps1
```

If PowerShell execution policy blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

The built executable is written to:

```text
dist\JYIMGEditor.exe
```

## License

Apache License 2.0.

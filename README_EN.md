# JYIMGEditor

JYIMGEditor, also known as "金庸群侠传贴图资源编辑器", is a lightweight sprite and texture resource editor for *Jin Yong Qun Xia Zhuan* and its mods. It focuses on the classic image archive pairs used by the game, including `idx/grp`, `wdx/wmp`, `sdx/smp`, and `fdx/fmp`, while preserving per-frame metadata such as width, height, X offset, and Y offset.

The project was created because the older editor sFishedit (SFE) is useful but incomplete for modern batch editing workflows. It lacks convenient batch PNG import/export, and it can be unstable when editing sprites on modern Windows 11 systems. JYIMGEditor is a new Python/Tkinter implementation intended to make sprite inspection, frame alignment, and bulk editing more practical.

[中文说明](README.md)

## Version 0.4 Highlights

- Added "画笔/油漆桶" right-click painting modes in the sprite editor. Brush mode supports right-button drag drawing with a 1-pixel line, while bucket mode fills contiguous matching-color regions.
- The sprite editor color swatch can be double-clicked to open the system color picker. Both the sprite editor and color conversion window now accept direct hex color input and map it to the nearest game palette color.
- In the sprite editor zoom canvas, plain mouse wheel or `Ctrl+mouse wheel` switches previous/next sprite, while `Alt+mouse wheel` changes zoom.
- Added main-window keyboard controls: `Delete`, number keys `1/2/3/4`, arrow-key selection movement, and `Shift+Home/End` range selection.
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
- Removed the default `frostbite.idx/frostbite.grp` frozen-effect entry from `config.ini`; later `File` entries have been shifted forward.

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

## Features

- Configurable archive list through `config.ini`, including normal `File0..FileN` entries and fight sprite sequences such as `FightName=fdx***,fmp***`.
- Browse `idx/grp`-style archives with a thumbnail grid, scrolling, multi-selection, Shift range selection, and context menus.
- Configure per-row count, unit width/height bases, and dropdown ranges through the `[View]` section in `config.ini`; UI changes write the current selection back to the config.
- Set the game `data` directory from the UI and save it back to `config.ini`.
- Edit a single sprite: width, height, X/Y offsets, zoom preview, 1x preview, offset crosshair, previous/next frame.
- Sprite editing supports brush and bucket right-click modes. Brush mode can draw by dragging; bucket mode fills contiguous matching-color areas.
- The sprite editor supports double-clicking the current color swatch to open the system color picker, and direct hex color input mapped to the nearest palette color.
- Sprite editor and color conversion zoom levels are remembered for the current app run, then reset to 4x after restart.
- The sprite editor remembers its offset-crosshair and fixed-anchor checkbox states for the current app run without creating extra state files.
- Read and write X/Y offsets as signed 16-bit values, allowing negative offsets.
- Pick colors from pixels with left click, paint pixels with right click, and use the configured transparent color.
- Crop a sprite by dragging a selection rectangle, updating dimensions and offsets accordingly.
- Undo and redo in the sprite editor, with disabled buttons when no step is available.
- Multi-color conversion window with source/target color slots, direct hex color input, zoom preview, test, restore, undo, redo, and final apply.
- Batch export PNG files with a `manifest.csv` containing `index/file/width/height/xoff/yoff`.
- Batch import PNG files by replacing the whole archive, appending to the end, or inserting after the current selection.
- Export selected sprites and import the first N PNG files from a folder into N selected sprites by filename order. Selected import can either read offsets from `manifest.csv` or ignore them and keep the replaced sprites' original offsets.
- Delete multiple selected sprites.
- Batch-adjust relative X/Y offsets for selected sprites, for example `+2`, `2`, or `-2`.
- Batch-resize selected sprites by relative delta or absolute dimensions, with a 3x3 anchor for cropping or padding.
- Horizontally flip selected sprites, copy selected sprites to the end, copy selected sprites to the end in reverse order, and shift selected sprites forward/backward.
- Copy/paste a single sprite through the system clipboard, and copy/paste a sprite with its X/Y offsets. Offset-preserving copy writes to the system clipboard, so it works across two running JYIMGEditor processes.
- Insert a blank sprite before the current sprite, or append a blank sprite to the end.
- Save with confirmation and automatic `.bak_timestamp` backups for both idx and grp files.
- Prompt before switching archives when there are unsaved changes.
- Newly opened child windows are focused automatically for immediate keyboard use.
- Child windows support `Esc` to close.
- `main.py` exposes `UI_FONT_SIZE`, `UI_FONT_FAMILY`, and `MAIN_WINDOW_EXTRA_WIDTH` near the top for local UI tuning.

## Author Page

Bilibili: https://space.bilibili.com/16385

Feel free to follow and send private messages for related questions.

## Improvements over sFishedit/SFE

- Batch PNG export and import.
- Metadata-preserving `manifest.csv` workflow.
- Selected-image import/export and batch width/height adjustment.
- Main-window per-row and unit-size controls, with defaults and ranges configurable in `config.ini`.
- Lazy decoding and visible-thumbnail caching for large archives.
- Safer editing workflow with undo/redo, transparent color tools, crop selection, 1x and zoom previews, and offset crosshair preview.
- Multi-color conversion with preview and delayed application.
- Batch relative offset adjustment for selected sprites.
- More multi-selection organization tools: horizontal flip, copy to end, reversed copy to end, and forward/backward shifting.
- Fuller keyboard workflow: move the red selection box with arrow keys, extend to first/last with `Shift+Home/End`, open common actions with number keys, and jump fight archives with numeric combobox input.
- Richer sprite editing tools: brush drag drawing, bucket fill, hex color input, and double-click system color picking.
- Cross-process offset-preserving sprite copy/paste for moving frames between two open archives.
- Original archive decoding no longer treats the nearest palette index to the transparent color as transparent, preventing real colors such as `#606060` from being swallowed.
- A modern Windows-friendly implementation intended to avoid the crashes encountered with the old editor on Windows 11.

## Keyboard Shortcuts

- All comboboxes: `Home` selects the first item, and `End` selects the last item.
- Main window: `Enter` loads or refreshes the current archive, `Ctrl+S` saves, and `Ctrl+A` selects all sprites in the current archive.
- Main window: `Delete` deletes selected sprites; `1` opens sprite editing, `2` opens batch X/Y offset adjustment, `3` opens batch width/height resize, and `4` opens color conversion.
- Main window: arrow keys move the current red selection box; `Shift` extends selection, `Ctrl` keeps existing selections and adds the new landing point; `Shift+Home/End` selects to the first/last sprite.
- Main archive combobox: number keys jump to `fdxNNN/fmpNNN` fight sprite entries, with quick multi-digit input supported.
- Main window: `Ctrl+C` copies the single selected sprite to the system clipboard, and `Ctrl+V` pastes from the clipboard into the single selected sprite.
- Main window: `Ctrl+N` appends a blank sprite to the end, and `Ctrl+I` inserts a blank sprite before the current selection.
- Sprite editor: `Left/Right` or mouse wheel switches to the previous/next sprite, `Alt+mouse wheel` changes zoom, and `Esc` closes the window.
- Sprite editor: `Ctrl+C` copies to the clipboard, `Ctrl+V` pastes from the clipboard, `Ctrl+Z` undoes, and `Ctrl+Shift+Z` redoes.
- Sprite editor: when a color or numeric input has focus, `Ctrl+C/Ctrl+V` keeps normal text copy/paste behavior instead of triggering sprite clipboard operations.
- Sprite editor: `Ctrl+E` toggles the offset crosshair, and `Ctrl+Q` toggles the fixed X/Y offset anchor preview. Clipboard copy includes the red offset crosshair when the offset crosshair option is enabled.
- Color conversion: `Esc` closes the window. After selecting a source/target color slot, click the preview or palette to pick a color; double-click a slot to open the system color picker.

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
- The default transparent color is `#307070`. PNG import treats exact `#307070` pixels and alpha-transparent pixels as transparent.
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

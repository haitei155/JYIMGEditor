# JYIMGEditor

JYIMGEditor, also known as "金庸群侠传贴图资源编辑器", is a lightweight sprite and texture resource editor for *Jin Yong Qun Xia Zhuan* and its mods. It focuses on the classic image archive pairs used by the game, including `idx/grp`, `wdx/wmp`, `sdx/smp`, and `fdx/fmp`, while preserving per-frame metadata such as width, height, X offset, and Y offset.

The project was created because the older editor sFishedit (SFE) is useful but incomplete for modern batch editing workflows. It lacks convenient batch PNG import/export, and it can be unstable when editing sprites on modern Windows 11 systems. JYIMGEditor is a new Python/Tkinter implementation intended to make sprite inspection, frame alignment, and bulk editing more practical.

[中文说明](README.md)

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
- Browse `idx/grp`-style archives with a thumbnail grid, scrolling, multi-selection, and context menus.
- Set the game `data` directory from the UI and save it back to `config.ini`.
- Edit a single sprite: width, height, X/Y offsets, zoom preview, 1x preview, offset crosshair, previous/next frame.
- Read and write X/Y offsets as signed 16-bit values, allowing negative offsets.
- Pick colors from pixels with left click, paint pixels with right click, and use the configured transparent color.
- Crop a sprite by dragging a selection rectangle, updating dimensions and offsets accordingly.
- Undo and redo in the sprite editor, with disabled buttons when no step is available.
- Multi-color conversion window with source/target color slots, zoom preview, test, restore, undo, redo, and final apply.
- Batch export PNG files with a `manifest.csv` containing `index/file/width/height/xoff/yoff`.
- Batch import PNG files by replacing the whole archive, appending to the end, or inserting after the current selection.
- Export selected sprites and import the first N PNG files from a folder into N selected sprites by filename order.
- Delete multiple selected sprites.
- Batch-adjust relative X/Y offsets for selected sprites, for example `+2`, `2`, or `-2`.
- Batch-resize selected sprites by relative delta or absolute dimensions, with a 3x3 anchor for cropping or padding.
- Copy/paste a single sprite through the system clipboard, and copy/paste a sprite with its X/Y offsets through an internal cache.
- Insert a blank sprite before the current sprite, or append a blank sprite to the end.
- Save with confirmation and automatic `.bak_timestamp` backups for both idx and grp files.
- Prompt before switching archives when there are unsaved changes.
- Child windows support `Esc` to close.
- `main.py` exposes `UI_FONT_SIZE`, `UI_FONT_FAMILY`, and `MAIN_WINDOW_EXTRA_WIDTH` near the top for local UI tuning.

## Author Page

Bilibili: https://space.bilibili.com/16385

Feel free to follow and send private messages for related questions.

## Improvements over sFishedit/SFE

- Batch PNG export and import.
- Metadata-preserving `manifest.csv` workflow.
- Selected-image import/export and batch width/height adjustment.
- Lazy decoding and visible-thumbnail caching for large archives.
- Safer editing workflow with undo/redo, transparent color tools, crop selection, 1x and zoom previews, and offset crosshair preview.
- Multi-color conversion with preview and delayed application.
- Batch relative offset adjustment for selected sprites.
- A modern Windows-friendly implementation intended to avoid the crashes encountered with the old editor on Windows 11.

## Keyboard Shortcuts

- Main window: `Enter` loads or refreshes the current archive, `Ctrl+S` saves, and `Ctrl+A` selects all sprites in the current archive.
- Main window: `Ctrl+C` copies the single selected sprite to the system clipboard, and `Ctrl+V` pastes from the clipboard into the single selected sprite.
- Main window: `Ctrl+N` appends a blank sprite to the end, and `Ctrl+I` inserts a blank sprite before the current selection.
- Sprite editor: `Left/Right` switches to the previous/next sprite, and `Esc` closes the window.
- Sprite editor: `Ctrl+C` copies to the clipboard, `Ctrl+V` pastes from the clipboard, `Ctrl+Z` undoes, and `Ctrl+Shift+Z` redoes.
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
- The default transparent color is `#307070`.
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

import base64
import configparser
import csv
import ctypes
import io
import json
import os
import re
import shutil
import struct
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageGrab


APP_NAME = "金庸群侠传贴图资源编辑器"
APP_VERSION = "v0.5"
AUTHOR = "海底.zip"
BG = "#307070"
APP_USER_MODEL_ID = "haitei155.JYIMGEditor"
FIXED_ANCHOR_MIN_SIDE_MARGIN = 10
MAIN_WINDOW_EXTRA_WIDTH = 24
MAIN_WINDOW_SCREEN_MARGIN = 20
MAIN_WINDOW_MIN_WIDTH = 900
UI_FONT_FAMILY = ""
UI_FONT_SIZE = 10
BILIBILI_URL = "https://space.bilibili.com/16385"
SPRITE_CLIPBOARD_PREFIX = "JYIMGEditorSpriteV1:"
SPRITE_LIST_CLIPBOARD_PREFIX = "JYIMGEditorSpriteListV1:"
EXPORT_SCALES = [1, 2, 4, 8, 16]


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(*parts) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).joinpath(*parts)
    return app_dir().joinpath(*parts)


def u16(data: bytes, pos: int) -> int:
    return data[pos] | (data[pos + 1] << 8)


def s16(data: bytes, pos: int) -> int:
    v = u16(data, pos)
    return v - 65536 if v >= 32768 else v


def p16(v: int) -> bytes:
    return struct.pack("<H", max(0, min(65535, int(v))))


def p16s(v: int) -> bytes:
    v = max(-32768, min(32767, int(v)))
    return struct.pack("<h", v)


def p32(v: int) -> bytes:
    return struct.pack("<I", max(0, int(v)))


def rgb_hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb[:3])


def parse_hex_color_text(text):
    value = (text or "").strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        return None
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


class ToolTip:
    def __init__(self, widget, text, delay=0):
        self.widget = widget
        self.text = text
        self.tip = None
        self.delay = delay
        self.after_id = None
        self.last_event = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Motion>", self.move, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def position(self, event=None):
        if event is not None and hasattr(event, "x_root"):
            return event.x_root + 14, event.y_root + 18
        return self.widget.winfo_rootx() + 24, self.widget.winfo_rooty() + self.widget.winfo_height() + 4

    def show(self, event=None):
        if self.tip or not self.text:
            return
        self.last_event = event
        if self.delay > 0:
            self.cancel_pending()
            self.after_id = self.widget.after(self.delay, lambda: self.show_now(self.last_event))
            return
        self.show_now(event)

    def show_now(self, event=None):
        if self.tip or not self.text:
            return
        x, y = self.position(event)
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(self.tip, text=self.text, background="#ffffe0", relief=tk.SOLID, borderwidth=1)
        label.pack()

    def move(self, event=None):
        self.last_event = event
        if self.delay > 0:
            self.hide()
            self.show(event)
            return
        if self.tip:
            x, y = self.position(event)
            self.tip.wm_geometry(f"+{x}+{y}")

    def cancel_pending(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def hide(self, event=None):
        self.cancel_pending()
        if self.tip:
            self.tip.destroy()
            self.tip = None


def center_window(win):
    win.update_idletasks()
    width = max(1, win.winfo_width())
    height = max(1, win.winfo_height())
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    win.geometry(f"+{x}+{y}")


def focus_window(win, widget=None):
    target = widget or win

    def apply_focus():
        try:
            win.lift()
            win.focus_force()
            target.focus_set()
        except tk.TclError:
            pass

    win.after(0, apply_focus)


def bind_combobox_home_end(combo, on_change=None):
    def apply_index(index):
        values = list(combo.cget("values"))
        if not values:
            return "break"
        combo.current(max(0, min(len(values) - 1, index)))
        if on_change:
            on_change()
        return "break"

    def bind_popdown(event=None):
        try:
            listbox = combo.tk.call("ttk::combobox::PopdownWindow", str(combo)) + ".f.l"
            home_cmd = combo.register(lambda: apply_index(0))
            end_cmd = combo.register(lambda: apply_index(len(list(combo.cget("values"))) - 1))
            combo._jy_combo_nav_cmds = getattr(combo, "_jy_combo_nav_cmds", []) + [home_cmd, end_cmd]
            combo.tk.call("bind", listbox, "<Home>", f"{home_cmd}; break")
            combo.tk.call("bind", listbox, "<End>", f"{end_cmd}; break")
        except tk.TclError:
            pass

    if on_change:
        combo.bind("<<ComboboxSelected>>", lambda event: on_change())
    combo.bind("<Home>", lambda event: apply_index(0))
    combo.bind("<End>", lambda event: apply_index(len(list(combo.cget("values"))) - 1))
    combo.bind("<FocusIn>", bind_popdown, add="+")
    combo.bind("<Button-1>", lambda event: combo.after(50, bind_popdown), add="+")


def set_window_icon(win):
    ico_path = resource_path("assets", "JYIMGEditor.ico")
    icon_path = resource_path("assets", "JYIMGEditor.png")
    try:
        if ico_path.exists():
            win.iconbitmap(default=str(ico_path))
        if icon_path.exists():
            photo = tk.PhotoImage(file=str(icon_path))
            win.iconphoto(True, photo)
            win._jy_icon = photo
    except tk.TclError:
        pass


def set_app_user_model_id():
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


@dataclass
class Sprite:
    width: int
    height: int
    xoff: int
    yoff: int
    pixels: list  # rows of palette indexes, -1 means transparent


def clone_sprite(sprite):
    return Sprite(sprite.width, sprite.height, sprite.xoff, sprite.yoff, [row[:] for row in sprite.pixels])


def blank_sprite():
    return Sprite(1, 1, 0, 0, [[-1]])


def sprite_anchor_margin(sprite):
    return max(
        0,
        int(sprite.xoff),
        int(sprite.yoff),
        int(sprite.width) - 1 - int(sprite.xoff),
        int(sprite.height) - 1 - int(sprite.yoff),
    )


def sprite_anchor_margins(sprite, min_margin=FIXED_ANCHOR_MIN_SIDE_MARGIN):
    min_margin = max(0, int(min_margin))
    return (
        max(min_margin, int(sprite.xoff)),
        max(min_margin, int(sprite.yoff)),
        max(min_margin, int(sprite.width) - 1 - int(sprite.xoff)),
        max(min_margin, int(sprite.height) - 1 - int(sprite.yoff)),
    )


def combined_anchor_margins(sprites, min_margin=0):
    margins = [max(0, int(min_margin))] * 4
    for spr in sprites:
        margins = [max(a, b) for a, b in zip(margins, sprite_anchor_margins(spr, min_margin))]
    return tuple(margins)


def clipboard_sequence_number():
    try:
        return int(ctypes.windll.user32.GetClipboardSequenceNumber())
    except Exception:
        return None


def image_resize_nearest(img, size):
    try:
        resample = Image.Resampling.NEAREST
    except AttributeError:
        resample = Image.NEAREST
    return img.resize(size, resample)


def downscale_import_image(img, scale):
    scale = max(1, int(scale or 1))
    if scale <= 1:
        return img
    w, h = img.size
    return image_resize_nearest(img, (max(1, w // scale), max(1, h // scale)))


def auto_crop_sprite(sprite, palette):
    """Crop transparent edges from sprite, adjusting X/Y offsets.
    Transparent means pixel index < 0 (i.e., the preset transparent color).
    """
    if sprite.width <= 0 or sprite.height <= 0:
        return
    # Find top non-transparent row
    top = 0
    for y in range(sprite.height):
        if any(p >= 0 for p in sprite.pixels[y]):
            top = y
            break
    else:
        # All pixels are transparent — keep 1x1 at center
        return
    # Find bottom non-transparent row
    bottom = sprite.height - 1
    for y in range(sprite.height - 1, -1, -1):
        if any(p >= 0 for p in sprite.pixels[y]):
            bottom = y
            break
    # Find left non-transparent column
    left = 0
    for x in range(sprite.width):
        if any(sprite.pixels[y][x] >= 0 for y in range(sprite.height)):
            left = x
            break
    # Find right non-transparent column
    right = sprite.width - 1
    for x in range(sprite.width - 1, -1, -1):
        if any(sprite.pixels[y][x] >= 0 for y in range(sprite.height)):
            right = x
            break
    if top > bottom or left > right:
        return
    new_w = right - left + 1
    new_h = bottom - top + 1
    if new_w == sprite.width and new_h == sprite.height:
        return
    sprite.pixels = [row[left:right + 1] for row in sprite.pixels[top:bottom + 1]]
    sprite.width = new_w
    sprite.height = new_h
    sprite.xoff -= left
    sprite.yoff -= top


def _color_close(rgb, target, max_dist=8):
    """Check if an RGB tuple is within max_dist (per-channel) of target."""
    return all(abs(rgb[i] - target[i]) <= max_dist for i in range(3))


def pil_to_sprite_alpha_as_bg(img, palette, xoff=0, yoff=0):
    """Convert a PIL RGBA image to a Sprite, treating alpha/BG-near pixels as transparent.

    Pixels with alpha=0 or within tolerance of the preset BG color are treated as
    transparent (index -1).  This handles GIF palette quantization that may shift the
    BG colour slightly.
    """
    img = img.convert("RGBA")
    w, h = img.size
    pixels = []
    tr = palette.transparent_rgb
    for y in range(h):
        row = []
        for x in range(w):
            r, g, b, a = img.getpixel((x, y))
            if a == 0 or _color_close((r, g, b), tr, 10):
                row.append(-1)
            else:
                row.append(palette.nearest((r, g, b)))
        pixels.append(row)
    return Sprite(w, h, xoff, yoff, pixels)


def anchor_offsets(old_w, old_h, new_w, new_h, anchor):
    col = anchor % 3
    row = anchor // 3
    if col == 0:
        old_x = new_x = 0
    elif col == 1:
        old_x = max(0, (old_w - new_w) // 2)
        new_x = max(0, (new_w - old_w) // 2)
    else:
        old_x = max(0, old_w - new_w)
        new_x = max(0, new_w - old_w)
    if row == 0:
        old_y = new_y = 0
    elif row == 1:
        old_y = max(0, (old_h - new_h) // 2)
        new_y = max(0, (new_h - old_h) // 2)
    else:
        old_y = max(0, old_h - new_h)
        new_y = max(0, new_h - old_h)
    return old_x, old_y, new_x, new_y


def resize_sprite(sprite, new_w, new_h, anchor=4):
    new_w, new_h = max(1, int(new_w)), max(1, int(new_h))
    old_x, old_y, new_x, new_y = anchor_offsets(sprite.width, sprite.height, new_w, new_h, anchor)
    new_pixels = [[-1 for _ in range(new_w)] for _ in range(new_h)]
    copy_w = min(sprite.width - old_x, new_w - new_x)
    copy_h = min(sprite.height - old_y, new_h - new_y)
    if copy_w > 0 and copy_h > 0:
        for y in range(copy_h):
            new_pixels[new_y + y][new_x:new_x + copy_w] = sprite.pixels[old_y + y][old_x:old_x + copy_w]
    sprite.pixels = new_pixels
    sprite.width = new_w
    sprite.height = new_h
    sprite.xoff += new_x - old_x
    sprite.yoff += new_y - old_y
    return sprite


class Palette:
    def __init__(self, path: Path | None, transparent=BG):
        self.colors = [(0, 0, 0)] * 256
        if path and path.exists():
            raw = path.read_bytes()
            if len(raw) >= 768:
                scale = 4 if max(raw[:768]) <= 63 else 1
                self.colors = [
                    (
                        min(255, raw[i * 3] * scale),
                        min(255, raw[i * 3 + 1] * scale),
                        min(255, raw[i * 3 + 2] * scale),
                    )
                    for i in range(256)
                ]
        self.transparent_rgb = self.parse_hex(transparent)
        self._cache = {}

    @staticmethod
    def parse_hex(value):
        value = (value or BG).strip().lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def nearest(self, rgb):
        key = tuple(rgb)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        best_i, best_d = 0, 10**18
        for i, c in enumerate(self.colors):
            d = (c[0] - rgb[0]) ** 2 + (c[1] - rgb[1]) ** 2 + (c[2] - rgb[2]) ** 2
            if d < best_d:
                best_i, best_d = i, d
        self._cache[key] = best_i
        return best_i


class JyPicArchive:
    def __init__(self, idx_path: Path, grp_path: Path, palette: Palette):
        self.idx_path = idx_path
        self.grp_path = grp_path
        self.palette = palette
        self.sprites: list[Sprite] = []
        self.raw_entries: list[bytes | None] = []
        self.dirty = False

    def load(self):
        idx = self.idx_path.read_bytes()
        grp = self.grp_path.read_bytes()
        if len(idx) % 4 != 0:
            raise ValueError("idx 文件长度不是 4 的倍数")
        ends = [struct.unpack_from("<I", idx, i)[0] for i in range(0, len(idx), 4)]
        self.sprites.clear()
        self.raw_entries.clear()
        start = 0
        for end in ends:
            if end < start or end > len(grp):
                raise ValueError("idx offset 与 grp 长度不匹配")
            self.raw_entries.append(grp[start:end])
            self.sprites.append(None)
            start = end
        self.dirty = False

    def get_sprite(self, index: int) -> Sprite:
        spr = self.sprites[index]
        if spr is None:
            raw = self.raw_entries[index] or b""
            spr = self.decode_one(raw)
            self.sprites[index] = spr
        return spr

    def set_sprite(self, index: int, sprite: Sprite):
        self.sprites[index] = sprite
        self.raw_entries[index] = None

    def replace_all(self, sprites: list[Sprite]):
        self.sprites = list(sprites)
        self.raw_entries = [None] * len(self.sprites)

    def insert_many(self, index: int, sprites: list[Sprite]):
        self.sprites[index:index] = sprites
        self.raw_entries[index:index] = [None] * len(sprites)

    def append_many(self, sprites: list[Sprite]):
        self.insert_many(len(self.sprites), sprites)

    def delete_indexes(self, indexes):
        dead = set(indexes)
        self.sprites = [s for i, s in enumerate(self.sprites) if i not in dead]
        self.raw_entries = [r for i, r in enumerate(self.raw_entries) if i not in dead]

    def save(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for path in (self.idx_path, self.grp_path):
            if path.exists():
                shutil.copy2(path, path.with_name(path.name + f".bak_{stamp}"))
        offsets, blob = [], bytearray()
        for i, spr in enumerate(self.sprites):
            if spr is None and self.raw_entries[i] is not None:
                blob.extend(self.raw_entries[i])
            else:
                blob.extend(self.encode_one(self.get_sprite(i)))
            offsets.append(len(blob))
        self.idx_path.write_bytes(b"".join(p32(v) for v in offsets))
        self.grp_path.write_bytes(bytes(blob))
        self.dirty = False

    def decode_one(self, data: bytes) -> Sprite:
        if len(data) < 8:
            return Sprite(1, 1, 0, 0, [[-1]])
        w, h, xoff, yoff = u16(data, 0), u16(data, 2), s16(data, 4), s16(data, 6)
        pixels = [[-1 for _ in range(w)] for _ in range(h)]
        pos = 8
        for y in range(h):
            if pos >= len(data):
                break
            row_len = data[pos]
            pos += 1
            row_end = min(len(data), pos + row_len)
            cursor = 0
            while pos + 1 < row_end:
                skip, cnt = data[pos], data[pos + 1]
                pos += 2
                x = cursor + skip
                for i in range(cnt):
                    if pos + i < row_end and 0 <= x + i < w:
                        pixels[y][x + i] = data[pos + i]
                pos += cnt
                cursor = x + cnt
            pos = row_end
        return Sprite(w, h, xoff, yoff, pixels)

    def encode_one(self, spr: Sprite) -> bytes:
        out = bytearray()
        out.extend(p16(spr.width) + p16(spr.height) + p16s(spr.xoff) + p16s(spr.yoff))
        for y in range(spr.height):
            row = bytearray()
            cursor = 0
            x = 0
            while x < spr.width:
                while x < spr.width and spr.pixels[y][x] < 0:
                    x += 1
                if x >= spr.width:
                    break
                start = x
                vals = []
                while x < spr.width and spr.pixels[y][x] >= 0 and len(vals) < 255:
                    vals.append(spr.pixels[y][x] & 0xFF)
                    x += 1
                skip = start - cursor
                if skip > 255:
                    # split long transparent runs with empty cursor jumps
                    while skip > 255:
                        row.extend([255, 0])
                        cursor += 255
                        skip = start - cursor
                row.extend([skip, len(vals)])
                row.extend(vals)
                cursor = start + len(vals)
            if len(row) > 255:
                raise ValueError(f"第 {y} 行编码超过 255 字节，当前图片过宽或碎片过多")
            out.append(len(row))
            out.extend(row)
        return bytes(out)


class ImageTools:
    @staticmethod
    def sprite_to_photo(sprite: Sprite, palette: Palette, zoom=1, show_offset=False, fixed_anchor=False, anchor_margins=None):
        zoom = max(1, int(zoom))
        if fixed_anchor:
            left, top, right, bottom = anchor_margins or sprite_anchor_margins(sprite)
            w = max(1, (left + right + 1) * zoom)
            h = max(1, (top + bottom + 1) * zoom)
            ox = (left - sprite.xoff) * zoom
            oy = (top - sprite.yoff) * zoom
            cx = left * zoom
            cy = top * zoom
        else:
            w, h = max(1, sprite.width * zoom), max(1, sprite.height * zoom)
            ox = oy = 0
            cx, cy = sprite.xoff * zoom, sprite.yoff * zoom
        photo = tk.PhotoImage(width=w, height=h)
        photo.put(BG, to=(0, 0, w, h))
        for y in range(sprite.height):
            runs = []
            last = None
            start = 0
            for x in range(sprite.width):
                idx = sprite.pixels[y][x]
                color = BG if idx < 0 else rgb_hex(palette.colors[idx])
                if color != last:
                    if last is not None:
                        runs.append((start, x, last))
                    start, last = x, color
            if last is not None:
                runs.append((start, sprite.width, last))
            for x1, x2, color in runs:
                photo.put(color, to=(ox + x1 * zoom, oy + y * zoom, ox + x2 * zoom, oy + (y + 1) * zoom))
        if show_offset:
            red = "#ff0000"
            arm = max(8, 8 * zoom)
            thick = max(1, zoom // 3)
            hx1, hy1 = max(0, cx - arm), max(0, cy)
            hx2, hy2 = min(w, cx + arm + 1), min(h, cy + thick)
            vx1, vy1 = max(0, cx), max(0, cy - arm)
            vx2, vy2 = min(w, cx + thick), min(h, cy + arm + 1)
            if hx2 > hx1 and hy2 > hy1:
                photo.put(red, to=(hx1, hy1, hx2, hy2))
            if vx2 > vx1 and vy2 > vy1:
                photo.put(red, to=(vx1, vy1, vx2, vy2))
        return photo

    @staticmethod
    def export_png(path: Path, sprite: Sprite, palette: Palette, show_offset=False, zoom=1, fixed_anchor=False, anchor_margins=None):
        img = ImageTools.sprite_to_pil(sprite, palette, show_offset, zoom, fixed_anchor, anchor_margins)
        img.save(path, "PNG")

    @staticmethod
    def sprite_to_pil(sprite: Sprite, palette: Palette, show_offset=False, zoom=1, fixed_anchor=False, anchor_margins=None):
        zoom = max(1, int(zoom))
        if fixed_anchor:
            left, top, right, bottom = anchor_margins or sprite_anchor_margins(sprite, 0)
            width = max(1, left + right + 1)
            height = max(1, top + bottom + 1)
            ox = left - sprite.xoff
            oy = top - sprite.yoff
            cx, cy = left, top
        else:
            width = max(1, sprite.width)
            height = max(1, sprite.height)
            if show_offset:
                width = max(width, sprite.xoff + 1)
                height = max(height, sprite.yoff + 1)
            ox = oy = 0
            cx, cy = sprite.xoff, sprite.yoff
        img = Image.new("RGB", (width, height), Palette.parse_hex(BG))
        px = img.load()
        for y, row in enumerate(sprite.pixels):
            for x, idx in enumerate(row):
                if idx >= 0:
                    dx, dy = ox + x, oy + y
                    if 0 <= dx < width and 0 <= dy < height:
                        px[dx, dy] = tuple(palette.colors[idx])
        if show_offset:
            red = (255, 0, 0)
            for x in range(max(0, cx - 8), min(width, cx + 9)):
                if 0 <= cy < height:
                    px[x, cy] = red
            for y in range(max(0, cy - 8), min(height, cy + 9)):
                if 0 <= cx < width:
                    px[cx, y] = red
        if zoom > 1:
            img = image_resize_nearest(img, (max(1, width * zoom), max(1, height * zoom)))
        return img

    @staticmethod
    def pil_to_sprite(img, palette: Palette, xoff=0, yoff=0) -> Sprite:
        img = img.convert("RGBA")
        w, h = img.size
        pixels = []
        tr = palette.transparent_rgb
        for y in range(h):
            row = []
            for x in range(w):
                r, g, b, a = img.getpixel((x, y))
                if a == 0 or (r, g, b) == tr:
                    row.append(-1)
                else:
                    row.append(palette.nearest((r, g, b)))
            pixels.append(row)
        return Sprite(w, h, xoff, yoff, pixels)

    @staticmethod
    def copy_sprite_to_clipboard(sprite: Sprite, palette: Palette, show_offset=False):
        img = ImageTools.sprite_to_pil(sprite, palette, show_offset).convert("RGB")
        output = io.BytesIO()
        img.save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_bool
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.restype = ctypes.c_void_p
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.EmptyClipboard.restype = ctypes.c_bool
        user32.CloseClipboard.restype = ctypes.c_bool
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        gmem_moveable = 0x0002
        cf_dib = 8
        hglobal = kernel32.GlobalAlloc(gmem_moveable, len(data))
        if not hglobal:
            raise RuntimeError("无法分配剪贴板内存")
        ptr = kernel32.GlobalLock(hglobal)
        if not ptr:
            kernel32.GlobalFree(hglobal)
            raise RuntimeError("无法锁定剪贴板内存")
        ctypes.memmove(ctypes.c_void_p(ptr), data, len(data))
        kernel32.GlobalUnlock(hglobal)
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(hglobal)
            raise RuntimeError("无法打开剪贴板")
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(cf_dib, hglobal):
                raise RuntimeError("无法写入剪贴板")
            hglobal = None
        finally:
            user32.CloseClipboard()
            if hglobal:
                kernel32.GlobalFree(hglobal)

    @staticmethod
    def sprite_from_clipboard(palette: Palette, xoff=0, yoff=0):
        got = ImageGrab.grabclipboard()
        if isinstance(got, Image.Image):
            return ImageTools.pil_to_sprite(got, palette, xoff, yoff)
        if isinstance(got, list) and got:
            return ImageTools.import_png(Path(got[0]), palette, xoff, yoff)
        raise ValueError("剪贴板中没有可读取的图片")

    @staticmethod
    def import_png(path: Path, palette: Palette, xoff=0, yoff=0) -> Sprite:
        return ImageTools.pil_to_sprite(Image.open(path), palette, xoff, yoff)


class SpriteEditWindow(tk.Toplevel):
    def __init__(self, app, index: int):
        super().__init__(app.root)
        set_window_icon(self)
        self.app = app
        self.index = index
        self.zoom = tk.IntVar(value=self.app.sprite_edit_zoom)
        self.show_offset = tk.BooleanVar(value=self.app.sprite_edit_show_offset)
        self.fixed_anchor = tk.BooleanVar(value=self.app.sprite_edit_fixed_anchor)
        self.selected_color = tk.IntVar(value=self.app.sprite_edit_selected_color)
        self.selected_color_hex = tk.StringVar(value="#000000")
        self.color_text_updating = False
        self.paint_mode = tk.StringVar(value="brush")
        self.undo_stack = []
        self.redo_stack = []
        self.refreshing_fields = False
        self.drag_start = None
        self.drag_rect = None
        self.dragging = False
        self.painting = False
        self.paint_last_point = None
        self.paint_changed = False
        self._pushed_main_undo = False
        self.title(f"贴图编辑 - {index}")
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.build()
        self.bind("<Left>", lambda e: self.prev_sprite())
        self.bind("<Right>", lambda e: self.next_sprite())
        self.bind("<Escape>", lambda e: self.close_window())
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-Z>", lambda e: self.redo())
        self.bind("<Control-Shift-Z>", lambda e: self.redo())
        self.bind("<Control-c>", self.copy_shortcut)
        self.bind("<Control-C>", self.copy_shortcut)
        self.bind("<Control-v>", self.paste_shortcut)
        self.bind("<Control-V>", self.paste_shortcut)
        self.bind("<Control-e>", self.toggle_show_offset)
        self.bind("<Control-E>", self.toggle_show_offset)
        self.bind("<Control-q>", self.toggle_fixed_anchor)
        self.bind("<Control-Q>", self.toggle_fixed_anchor)
        self.refresh()
        center_window(self)
        self.transient(self.app.root)
        focus_window(self, self.canvas)

    @property
    def sprite(self):
        return self.app.archive.get_sprite(self.index)

    def build(self):
        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        self.vars = {}
        top_left = ttk.Frame(left)
        top_left.pack(anchor="w", fill=tk.X)
        fields = ttk.Frame(top_left)
        fields.pack(side=tk.LEFT, anchor="n")
        for label, attr in [("宽度", "width"), ("高度", "height"), ("X偏移", "xoff"), ("Y偏移", "yoff")]:
            ttk.Label(fields, text=label).pack(anchor="w")
            var = tk.StringVar()
            ent = ttk.Entry(fields, textvariable=var, width=8)
            ent.pack(anchor="w", pady=(0, 4))
            ent.bind("<Return>", self.apply_fields_shortcut)
            ent.bind("<KP_Enter>", self.apply_fields_shortcut)
            self.vars[attr] = var
            if attr in ("xoff", "yoff"):
                var.trace_add("write", lambda *args: self.refresh_images_from_fields())
        preview_box = ttk.Frame(top_left)
        preview_box.pack(side=tk.LEFT, anchor="n", padx=(14, 0))
        self.preview_canvas = tk.Canvas(preview_box, bg=BG, width=250, height=180, highlightthickness=1, highlightbackground="#888")
        self.preview_canvas.pack()
        ttk.Button(left, text="确认宽高", command=self.apply_fields).pack(fill=tk.X, pady=3)
        ttk.Checkbutton(left, text="显示偏移", variable=self.show_offset, command=self.on_show_offset_changed).pack(anchor="w")
        ttk.Checkbutton(left, text="以X+Y偏移为固定点", variable=self.fixed_anchor, command=self.on_fixed_anchor_changed).pack(anchor="w")
        ttk.Button(left, text="上一张", command=self.prev_sprite).pack(fill=tk.X, pady=3)
        ttk.Button(left, text="下一张", command=self.next_sprite).pack(fill=tk.X, pady=3)
        ttk.Button(left, text="颜色转换", command=self.color_convert).pack(fill=tk.X, pady=3)
        ttk.Button(left, text="复制到剪贴板", command=self.copy_to_clipboard).pack(fill=tk.X, pady=3)
        ttk.Button(left, text="从剪贴板粘贴", command=self.paste_from_clipboard).pack(fill=tk.X, pady=3)
        ttk.Button(left, text="保存图片", command=self.save_png).pack(fill=tk.X, pady=3)
        ttk.Button(left, text="保存修改", command=self.apply_fields).pack(fill=tk.X, pady=3)
        ttk.Label(left, text="选择颜色").pack(anchor="w", pady=(8, 0))
        color_row = ttk.Frame(left)
        color_row.pack(fill=tk.X, pady=2)
        self.color_preview = tk.Canvas(color_row, width=72, height=24, bg="#000000", highlightthickness=1, highlightbackground="#888")
        self.color_preview.pack(side=tk.LEFT, anchor="n")
        self.color_preview.bind("<Double-Button-1>", self.choose_selected_color)
        mode_box = ttk.Frame(color_row)
        mode_box.pack(side=tk.LEFT, anchor="n", padx=(10, 0))
        ttk.Radiobutton(mode_box, text="画笔", variable=self.paint_mode, value="brush").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_box, text="油漆桶", variable=self.paint_mode, value="bucket").pack(side=tk.LEFT, padx=(6, 0))
        self.color_entry = ttk.Entry(left, textvariable=self.selected_color_hex, width=10)
        self.color_entry.pack(anchor="w", pady=(0, 3))
        self.color_entry.bind("<Return>", self.blur_text_input)
        self.color_entry.bind("<KP_Enter>", self.blur_text_input)
        self.selected_color_hex.trace_add("write", self.on_selected_color_hex_changed)
        color_buttons = ttk.Frame(left)
        color_buttons.pack(fill=tk.X, pady=3)
        select_tr_btn = ttk.Button(color_buttons, text="选择透明色", command=lambda: self.set_selected_color(-1))
        select_tr_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ToolTip(select_tr_btn, "选择透明色为当前颜色")
        set_tr_btn = ttk.Button(color_buttons, text="设置透明色", command=self.replace_selected_with_transparent)
        set_tr_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ToolTip(set_tr_btn, "用透明色替换当前颜色")
        history_buttons = ttk.Frame(left)
        history_buttons.pack(fill=tk.X, pady=(0, 3))
        self.undo_btn = ttk.Button(history_buttons, text="撤销", command=self.undo, state=tk.DISABLED)
        self.undo_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        self.redo_btn = ttk.Button(history_buttons, text="重做", command=self.redo, state=tk.DISABLED)
        self.redo_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.palette_canvas = tk.Canvas(left, width=256, height=128, bg="white", highlightthickness=0)
        self.palette_canvas.pack(anchor="w", pady=4)
        self.palette_canvas.bind("<Button-1>", self.on_palette_click)
        self.draw_palette()

        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=6, pady=6)
        ttk.Label(top, text="放大倍数").pack(side=tk.LEFT)
        zoom_combo = ttk.Combobox(top, textvariable=self.zoom, values=[1, 2, 4, 8, 16], width=5, state="readonly")
        zoom_combo.pack(side=tk.LEFT)
        bind_combobox_home_end(zoom_combo, self.on_zoom_changed)

        self.canvas = tk.Canvas(self, bg="black", width=700, height=560, scrollregion=(0, 0, 100, 100), takefocus=True)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.canvas.bind("<ButtonPress-1>", self.on_image_press)
        self.canvas.bind("<B1-Motion>", self.on_image_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_image_release)
        self.canvas.bind("<ButtonPress-3>", self.on_image_paint_press)
        self.canvas.bind("<B3-Motion>", self.on_image_paint_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_image_paint_release)
        self.canvas.bind("<MouseWheel>", self.on_image_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self.on_image_ctrl_mousewheel)
        self.canvas.bind("<Alt-MouseWheel>", self.on_image_alt_mousewheel)
        self.canvas_tooltip = ToolTip(self.canvas, "左键拾取颜色，右键按当前模式上色，左键拖拽方块裁剪贴图", delay=2000)

    def draw_palette(self):
        cell = 16
        self.palette_canvas.delete("all")
        for i, rgb in enumerate(self.app.palette.colors):
            x = (i % 16) * cell
            y = (i // 16) * (cell // 2)
            self.palette_canvas.create_rectangle(x, y, x + cell, y + cell // 2, fill=rgb_hex(rgb), outline="")

    def set_selected_color(self, idx):
        idx = int(idx)
        self.color_text_updating = True
        if idx < 0:
            self.selected_color.set(-1)
            self.app.sprite_edit_selected_color = -1
            self.selected_color_hex.set(BG)
            self.color_preview.configure(bg=BG)
            self.color_text_updating = False
            return
        idx = max(0, min(255, idx))
        self.selected_color.set(idx)
        self.app.sprite_edit_selected_color = idx
        color = rgb_hex(self.app.palette.colors[idx])
        self.selected_color_hex.set(color)
        self.color_preview.configure(bg=color)
        self.color_text_updating = False

    def color_index_from_rgb(self, rgb):
        return -1 if tuple(rgb) == self.app.palette.transparent_rgb else self.app.palette.nearest(rgb)

    def on_selected_color_hex_changed(self, *args):
        if self.color_text_updating:
            return
        rgb = parse_hex_color_text(self.selected_color_hex.get())
        if rgb is None:
            return
        self.set_selected_color(self.color_index_from_rgb(rgb))

    def choose_selected_color(self, event=None):
        chosen = colorchooser.askcolor(color=self.selected_color_hex.get(), parent=self, title="选择颜色")
        if not chosen or not chosen[0]:
            return "break"
        rgb = tuple(int(v) for v in chosen[0])
        self.set_selected_color(self.color_index_from_rgb(rgb))
        return "break"

    def on_palette_click(self, event):
        self.canvas.focus_set()
        idx = int(event.y // 8) * 16 + int(event.x // 16)
        if 0 <= idx < 256:
            self.set_selected_color(idx)

    def image_point(self, event):
        zoom = max(1, int(self.zoom.get()))
        ox, oy = self.display_origin(zoom)
        x = int((self.canvas.canvasx(event.x) - ox) // zoom)
        y = int((self.canvas.canvasy(event.y) - oy) // zoom)
        return x, y

    def on_zoom_changed(self, event=None):
        self.app.sprite_edit_zoom = max(1, int(self.zoom.get()))
        self.refresh()

    def on_image_mousewheel(self, event):
        if event.delta > 0:
            self.prev_sprite()
        else:
            self.next_sprite()
        return "break"

    def on_image_ctrl_mousewheel(self, event):
        if event.delta > 0:
            self.prev_sprite()
        else:
            self.next_sprite()
        return "break"

    def on_image_alt_mousewheel(self, event):
        values = [1, 2, 4, 8, 16]
        current = int(self.zoom.get())
        try:
            pos = values.index(current)
        except ValueError:
            pos = min(range(len(values)), key=lambda i: abs(values[i] - current))
        if event.delta > 0:
            pos = min(len(values) - 1, pos + 1)
        else:
            pos = max(0, pos - 1)
        if values[pos] != current:
            self.zoom.set(values[pos])
            self.on_zoom_changed()
        return "break"

    def on_show_offset_changed(self, event=None):
        self.app.sprite_edit_show_offset = bool(self.show_offset.get())
        self.refresh_images_from_fields()

    def on_fixed_anchor_changed(self, event=None):
        self.app.sprite_edit_fixed_anchor = bool(self.fixed_anchor.get())
        self.refresh_images_from_fields()

    def display_sprite(self):
        spr = self.sprite
        if not self.show_offset.get():
            return spr
        try:
            return Sprite(spr.width, spr.height, int(self.vars["xoff"].get()), int(self.vars["yoff"].get()), spr.pixels)
        except Exception:
            return spr

    def display_anchor_margins(self, spr=None):
        if not self.fixed_anchor.get():
            return None
        spr = spr or self.display_sprite()
        app_margins = self.app.get_anchor_margins()
        spr_margins = sprite_anchor_margins(spr)
        return tuple(max(a, b) for a, b in zip(app_margins, spr_margins))

    def display_origin(self, zoom=None):
        zoom = max(1, int(zoom or self.zoom.get()))
        spr = self.display_sprite()
        if self.fixed_anchor.get():
            left, top, _, _ = self.display_anchor_margins(spr)
            return (left - spr.xoff) * zoom, (top - spr.yoff) * zoom
        return 0, 0

    def push_undo(self):
        # On first edit, push full state to main undo so Ctrl+Z can revert the editor session
        if not self._pushed_main_undo:
            self._pushed_main_undo = True
            self.app.push_main_undo()
        self.undo_stack.append(clone_sprite(self.sprite))
        if len(self.undo_stack) > 80:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_history_buttons()

    def update_history_buttons(self):
        self.undo_btn.configure(state=tk.NORMAL if self.undo_stack else tk.DISABLED)
        self.redo_btn.configure(state=tk.NORMAL if self.redo_stack else tk.DISABLED)

    def restore_sprite(self, sprite):
        self.app.archive.set_sprite(self.index, clone_sprite(sprite))
        self.app.mark_dirty()
        self.app.invalidate_thumb(self.index)
        self.refresh()
        self.app.draw_grid(clear_cache=False)
        self.update_history_buttons()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(clone_sprite(self.sprite))
        self.restore_sprite(self.undo_stack.pop())

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(clone_sprite(self.sprite))
        self.restore_sprite(self.redo_stack.pop())

    def mark_sprite_changed(self):
        self.app.mark_dirty()
        self.app.archive.raw_entries[self.index] = None
        self.app.invalidate_thumb(self.index)

    def on_image_press(self, event):
        self.canvas.focus_set()
        self.canvas_tooltip.hide()
        self.drag_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y), event.x, event.y)
        self.dragging = False
        if self.drag_rect:
            self.canvas.delete(self.drag_rect)
            self.drag_rect = None

    def on_image_drag(self, event):
        if not self.drag_start:
            return
        sx, sy, root_x, root_y = self.drag_start
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if abs(event.x - root_x) < 4 and abs(event.y - root_y) < 4:
            return
        self.dragging = True
        self.canvas_tooltip.hide()
        if self.drag_rect:
            self.canvas.coords(self.drag_rect, sx, sy, cx, cy)
        else:
            self.drag_rect = self.canvas.create_rectangle(sx, sy, cx, cy, outline="#ff0000", width=1, dash=(4, 2))

    def on_image_release(self, event):
        if self.dragging:
            self.crop_to_drag(event)
        else:
            self.on_image_click(event)
        if self.drag_rect:
            self.canvas.delete(self.drag_rect)
            self.drag_rect = None
        self.drag_start = None
        self.dragging = False

    def on_image_click(self, event):
        self.canvas.focus_set()
        spr = self.sprite
        x, y = self.image_point(event)
        if 0 <= x < spr.width and 0 <= y < spr.height:
            idx = spr.pixels[y][x]
            self.set_selected_color(idx)

    def on_image_paint_press(self, event):
        self.canvas.focus_set()
        self.canvas_tooltip.hide()
        if self.paint_mode.get() == "bucket":
            self.paint_bucket(self.image_point(event))
            return "break"
        self.painting = True
        self.paint_changed = False
        self.paint_last_point = self.image_point(event)
        self.paint_line(self.paint_last_point, self.paint_last_point)
        return "break"

    def on_image_paint_drag(self, event):
        if self.paint_mode.get() == "bucket":
            return "break"
        if not self.painting:
            return "break"
        point = self.image_point(event)
        if self.paint_last_point is None:
            self.paint_last_point = point
        self.paint_line(self.paint_last_point, point)
        self.paint_last_point = point
        return "break"

    def on_image_paint_release(self, event):
        if self.paint_mode.get() == "bucket":
            self.painting = False
            self.paint_last_point = None
            self.paint_changed = False
            return "break"
        if self.painting and self.paint_last_point is not None:
            self.paint_line(self.paint_last_point, self.image_point(event))
        self.painting = False
        self.paint_last_point = None
        self.paint_changed = False
        return "break"

    def paint_line(self, start, end):
        spr = self.sprite
        x1, y1 = start
        x2, y2 = end
        steps = max(abs(x2 - x1), abs(y2 - y1), 1)
        color = int(self.selected_color.get())
        changed = False
        for i in range(steps + 1):
            x = int(round(x1 + (x2 - x1) * i / steps))
            y = int(round(y1 + (y2 - y1) * i / steps))
            if 0 <= x < spr.width and 0 <= y < spr.height and spr.pixels[y][x] != color:
                if not self.paint_changed:
                    self.push_undo()
                    self.paint_changed = True
                spr.pixels[y][x] = color
                changed = True
        if changed:
            self.mark_sprite_changed()
            self.refresh()
        return changed

    def paint_bucket(self, point):
        spr = self.sprite
        x, y = point
        if not (0 <= x < spr.width and 0 <= y < spr.height):
            return False
        target = spr.pixels[y][x]
        color = int(self.selected_color.get())
        if target == color:
            return False
        self.push_undo()
        stack = [(x, y)]
        while stack:
            px, py = stack.pop()
            if not (0 <= px < spr.width and 0 <= py < spr.height):
                continue
            if spr.pixels[py][px] != target:
                continue
            spr.pixels[py][px] = color
            stack.extend(((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)))
        self.mark_sprite_changed()
        self.refresh()
        return True

    def crop_to_drag(self, event):
        if not self.drag_start:
            return
        spr = self.sprite
        zoom = max(1, int(self.zoom.get()))
        ox, oy = self.display_origin(zoom)
        sx, sy = self.drag_start[0], self.drag_start[1]
        ex, ey = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        x1 = int((min(sx, ex) - ox) // zoom)
        y1 = int((min(sy, ey) - oy) // zoom)
        x2 = int((max(sx, ex) - ox) // zoom)
        y2 = int((max(sy, ey) - oy) // zoom)
        left = max(0, min(spr.width - 1, x1))
        top = max(0, min(spr.height - 1, y1))
        right = max(0, min(spr.width - 1, x2)) + 1
        bottom = max(0, min(spr.height - 1, y2)) + 1
        if right <= left or bottom <= top:
            return
        if left == 0 and top == 0 and right == spr.width and bottom == spr.height:
            return
        self.push_undo()
        spr.pixels = [row[left:right] for row in spr.pixels[top:bottom]]
        spr.width = right - left
        spr.height = bottom - top
        spr.xoff -= left
        spr.yoff -= top
        self.mark_sprite_changed()
        self.refresh()

    def replace_selected_with_transparent(self):
        idx = int(self.selected_color.get())
        if idx < 0:
            return
        spr = self.sprite
        changed = False
        for y in range(spr.height):
            row = spr.pixels[y]
            if any(color == idx for color in row):
                changed = True
                break
        if changed:
            self.push_undo()
            for y in range(spr.height):
                row = spr.pixels[y]
                for x, color in enumerate(row):
                    if color == idx:
                        row[x] = -1
            self.mark_sprite_changed()
            self.refresh()

    def apply_fields(self, redraw_grid=True):
        spr = self.sprite
        try:
            nw, nh = int(self.vars["width"].get()), int(self.vars["height"].get())
            nx, ny = int(self.vars["xoff"].get()), int(self.vars["yoff"].get())
            changed = (nx, ny, nw, nh) != (spr.xoff, spr.yoff, spr.width, spr.height)
            if changed:
                self.push_undo()
            spr.xoff, spr.yoff = nx, ny
            if nw != spr.width or nh != spr.height:
                new_pixels = [[-1 for _ in range(nw)] for _ in range(nh)]
                for y in range(min(nh, spr.height)):
                    for x in range(min(nw, spr.width)):
                        new_pixels[y][x] = spr.pixels[y][x]
                spr.width, spr.height, spr.pixels = nw, nh, new_pixels
            if changed:
                self.mark_sprite_changed()
            self.refresh()
            if redraw_grid and changed:
                self.app.draw_grid()
        except Exception as e:
            messagebox.showerror("错误", str(e), parent=self)

    def apply_fields_shortcut(self, event=None):
        self.apply_fields()
        self.canvas.focus_set()
        return "break"

    def refresh(self):
        spr = self.sprite
        self.refreshing_fields = True
        try:
            for attr, var in self.vars.items():
                var.set(str(getattr(spr, attr)))
        finally:
            self.refreshing_fields = False
        self.title(f"贴图编辑 - {self.index}")
        self.refresh_images_from_fields()
        self.set_selected_color(self.selected_color.get())

    def refresh_images_from_fields(self):
        if getattr(self, "refreshing_fields", False) or not hasattr(self, "canvas"):
            return
        spr = self.display_sprite()
        margins = self.display_anchor_margins(spr)
        self.preview_photo = ImageTools.sprite_to_photo(spr, self.app.palette, 1, self.show_offset.get(), False)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(4, 4, image=self.preview_photo, anchor="nw")
        self.photo = ImageTools.sprite_to_photo(spr, self.app.palette, self.zoom.get(), self.show_offset.get(), self.fixed_anchor.get(), margins)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.config(scrollregion=(0, 0, self.photo.width(), self.photo.height()))

    def prev_sprite(self):
        self.apply_fields(redraw_grid=False)
        if self.index > 0:
            self.index -= 1
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_history_buttons()
            self.refresh()

    def next_sprite(self):
        self.apply_fields(redraw_grid=False)
        if self.index + 1 < len(self.app.archive.sprites):
            self.index += 1
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_history_buttons()
            self.refresh()

    def save_png(self):
        total = len(self.app.archive.sprites)
        digits = max(2, len(str(total - 1)))
        default = f"{self.app.current_base}_{self.index:0{digits}d}.png"
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".png", initialfile=default, filetypes=[("PNG", "*.png")])
        if path:
            ImageTools.export_png(Path(path), self.sprite, self.app.palette, self.show_offset.get())

    def copy_to_clipboard(self):
        try:
            ImageTools.copy_sprite_to_clipboard(self.sprite, self.app.palette, self.show_offset.get())
        except Exception as e:
            messagebox.showerror("复制失败", str(e), parent=self)

    def paste_from_clipboard(self):
        try:
            spr = self.sprite
            pasted = ImageTools.sprite_from_clipboard(self.app.palette, spr.xoff, spr.yoff)
            self.push_undo()
            spr.width, spr.height, spr.pixels = pasted.width, pasted.height, pasted.pixels
            self.mark_sprite_changed()
            self.refresh()
            self.app.draw_grid(clear_cache=False)
        except Exception as e:
            messagebox.showerror("粘贴失败", str(e), parent=self)

    def copy_shortcut(self, event=None):
        if self.text_input_has_focus():
            return None
        self.copy_to_clipboard()
        return "break"

    def paste_shortcut(self, event=None):
        if self.text_input_has_focus():
            return None
        self.paste_from_clipboard()
        return "break"

    def blur_text_input(self, event=None):
        self.canvas.focus_set()
        return "break"

    def text_input_has_focus(self):
        widget = self.focus_get()
        if not widget:
            return False
        try:
            cls = widget.winfo_class()
        except tk.TclError:
            return False
        return cls in {"Entry", "TEntry", "Text", "Spinbox", "TSpinbox"}

    def toggle_show_offset(self, event=None):
        self.show_offset.set(not self.show_offset.get())
        self.on_show_offset_changed()
        return "break"

    def toggle_fixed_anchor(self, event=None):
        self.fixed_anchor.set(not self.fixed_anchor.get())
        self.on_fixed_anchor_changed()
        return "break"

    def color_convert(self):
        ColorConvertWindow(self.app, self.index, self, self.selected_color.get())

    def close_window(self):
        self.app.sprite_edit_show_offset = bool(self.show_offset.get())
        self.app.sprite_edit_fixed_anchor = bool(self.fixed_anchor.get())
        self.app.draw_grid(clear_cache=False)
        self.destroy()


class ColorConvertWindow(tk.Toplevel):
    ROWS = 10

    def __init__(self, app, index, parent=None, initial_from=None):
        super().__init__(parent or app.root)
        set_window_icon(self)
        self.app = app
        self.index = index
        self.title("颜色转换")
        self.scope = tk.StringVar(value="current")
        black = app.palette.nearest((0, 0, 0))
        first = initial_from if initial_from is not None and initial_from >= 0 else black
        self.from_colors = [black] * self.ROWS
        self.to_colors = [black] * self.ROWS
        self.from_colors[0] = first
        self.active_slot = None
        self.tested = False
        self.undo_stack = []
        self.redo_stack = []
        self.from_swatches = []
        self.to_swatches = []
        self.zoom = tk.IntVar(value=self.app.color_convert_zoom)
        self.current_color_hex = tk.StringVar(value=BG)
        self.color_text_updating = False
        self.base_sprite = clone_sprite(app.archive.get_sprite(index))
        self.preview_sprite = clone_sprite(self.base_sprite)
        self.build()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-z>", self.undo_shortcut)
        self.bind("<Control-Z>", self.redo_shortcut)
        self.bind("<Control-Shift-Z>", self.redo_shortcut)
        self.refresh_swatches()
        self.refresh_preview()
        self.update_history_buttons()
        center_window(self)
        self.transient(parent or app.root)
        focus_window(self, self.preview_canvas)

    def build(self):
        frm = ttk.Frame(self)
        frm.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)
        for i in range(self.ROWS):
            row = ttk.Frame(frm)
            row.pack(anchor="w", pady=2)
            ttk.Label(row, text="选择\n颜色").pack(side=tk.LEFT)
            fc = tk.Canvas(row, width=54, height=26, bg="#000000", highlightthickness=2, highlightbackground="#ddd")
            fc.pack(side=tk.LEFT, padx=(2, 8))
            fc.bind("<Button-1>", lambda e, idx=i: self.toggle_slot(idx, "from"))
            fc.bind("<Double-Button-1>", lambda e, idx=i: self.choose_slot_color(idx, "from"))
            ttk.Label(row, text="替换\n颜色").pack(side=tk.LEFT)
            tc = tk.Canvas(row, width=54, height=26, bg="#000000", highlightthickness=2, highlightbackground="#ddd")
            tc.pack(side=tk.LEFT, padx=(2, 0))
            tc.bind("<Button-1>", lambda e, idx=i: self.toggle_slot(idx, "to"))
            tc.bind("<Double-Button-1>", lambda e, idx=i: self.choose_slot_color(idx, "to"))
            self.from_swatches.append(fc)
            self.to_swatches.append(tc)

        controls = ttk.Frame(frm)
        controls.pack(fill=tk.X, pady=(8, 4))
        ttk.Button(controls, text="确定", command=self.apply).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(controls, text="取消", command=self.destroy).pack(side=tk.LEFT, fill=tk.X, expand=True)
        controls2 = ttk.Frame(frm)
        controls2.pack(fill=tk.X, pady=4)
        ttk.Button(controls2, text="测试", command=self.test).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(controls2, text="复原", command=self.restore_preview).pack(side=tk.LEFT, fill=tk.X, expand=True)
        controls3 = ttk.Frame(frm)
        controls3.pack(fill=tk.X, pady=4)
        self.undo_btn = ttk.Button(controls3, text="撤销", command=self.undo, state=tk.DISABLED)
        self.undo_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.redo_btn = ttk.Button(controls3, text="重做", command=self.redo, state=tk.DISABLED)
        self.redo_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        scope = ttk.LabelFrame(frm, text="转换范围")
        scope.pack(fill=tk.X, pady=(8, 0))
        ttk.Radiobutton(scope, text="转换所有图片", variable=self.scope, value="all").pack(anchor="w")
        ttk.Radiobutton(scope, text="转换当前图片", variable=self.scope, value="current").pack(anchor="w")
        palette_head = ttk.Frame(frm)
        palette_head.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(palette_head, text="调色盘").pack(side=tk.LEFT)
        ttk.Label(palette_head, text="当前颜色").pack(side=tk.LEFT, padx=(18, 4))
        current_entry = ttk.Entry(palette_head, textvariable=self.current_color_hex, width=10)
        current_entry.pack(side=tk.LEFT)
        self.current_color_hex.trace_add("write", self.on_current_color_hex_changed)
        self.palette_canvas = tk.Canvas(frm, width=256, height=144, bg="white", highlightthickness=0)
        self.palette_canvas.pack(anchor="w", pady=4)
        self.palette_canvas.bind("<Button-1>", self.on_palette_click)
        self.draw_palette()

        right = ttk.Frame(self)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=8)
        zoom_row = ttk.Frame(right)
        zoom_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(zoom_row, text="放大倍数").pack(side=tk.LEFT)
        zoom_combo = ttk.Combobox(zoom_row, textvariable=self.zoom, values=[1, 2, 4, 8, 16], width=5, state="readonly")
        zoom_combo.pack(side=tk.LEFT, padx=4)
        bind_combobox_home_end(zoom_combo, self.on_zoom_changed)
        self.preview_canvas = tk.Canvas(right, width=520, height=620, bg=BG, scrollregion=(0, 0, 100, 100))
        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preview_canvas.bind("<Button-1>", self.on_preview_click)
        ToolTip(self.preview_canvas, "点击预览图颜色填入当前框选色块", delay=2000)

    def snapshot(self):
        return (self.from_colors[:], self.to_colors[:], self.active_slot, self.tested)

    def restore_snapshot(self, state):
        self.from_colors, self.to_colors, self.active_slot, self.tested = state[0][:], state[1][:], state[2], state[3]
        self.preview_sprite = self.converted_sprite() if self.tested else clone_sprite(self.base_sprite)
        self.refresh_swatches()
        self.refresh_preview()
        self.update_history_buttons()

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        if len(self.undo_stack) > 80:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_history_buttons()

    def update_history_buttons(self):
        self.undo_btn.configure(state=tk.NORMAL if self.undo_stack else tk.DISABLED)
        self.redo_btn.configure(state=tk.NORMAL if self.redo_stack else tk.DISABLED)

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self.snapshot())
        self.restore_snapshot(self.undo_stack.pop())

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self.snapshot())
        self.restore_snapshot(self.redo_stack.pop())

    def undo_shortcut(self, event=None):
        self.undo()
        return "break"

    def redo_shortcut(self, event=None):
        self.redo()
        return "break"

    def toggle_slot(self, row, side):
        slot = (row, side)
        if self.active_slot == slot:
            self.active_slot = None
        else:
            self.active_slot = slot
            colors = self.from_colors if side == "from" else self.to_colors
            self.update_current_color_text(colors[row])
        self.refresh_swatches()

    def color_bg(self, color_idx):
        return BG if color_idx < 0 else rgb_hex(self.app.palette.colors[color_idx])

    def update_current_color_text(self, color_idx):
        self.color_text_updating = True
        self.current_color_hex.set(self.color_bg(color_idx))
        self.color_text_updating = False

    def color_index_from_rgb(self, rgb):
        return -1 if tuple(rgb) == self.app.palette.transparent_rgb else self.app.palette.nearest(rgb)

    def on_current_color_hex_changed(self, *args):
        if self.color_text_updating:
            return
        rgb = parse_hex_color_text(self.current_color_hex.get())
        if rgb is None:
            return
        self.set_active_color(self.color_index_from_rgb(rgb))

    def set_active_color(self, color_idx):
        color_idx = int(color_idx)
        self.update_current_color_text(color_idx)
        if self.active_slot is None:
            return
        row, side = self.active_slot
        current = self.from_colors[row] if side == "from" else self.to_colors[row]
        if current == color_idx:
            return
        self.push_undo()
        if side == "from":
            self.from_colors[row] = color_idx
        else:
            self.to_colors[row] = color_idx
        if self.tested:
            self.preview_sprite = self.converted_sprite()
        self.refresh_swatches()
        self.refresh_preview()

    def choose_slot_color(self, row, side):
        self.active_slot = (row, side)
        self.refresh_swatches()
        current = self.from_colors[row] if side == "from" else self.to_colors[row]
        chosen = colorchooser.askcolor(color=self.color_bg(current), parent=self, title="选择颜色")
        if not chosen or not chosen[1]:
            return
        rgb = tuple(int(v) for v in chosen[0])
        color_idx = -1 if rgb == self.app.palette.transparent_rgb else self.app.palette.nearest(rgb)
        self.set_active_color(color_idx)

    def draw_palette(self):
        self.palette_canvas.delete("all")
        self.palette_canvas.create_rectangle(0, 0, 64, 16, fill=BG, outline="#333")
        self.palette_canvas.create_text(70, 8, text="透明色", anchor="w")
        cell = 16
        y0 = 16
        for i, rgb in enumerate(self.app.palette.colors):
            x = (i % 16) * cell
            y = y0 + (i // 16) * (cell // 2)
            self.palette_canvas.create_rectangle(x, y, x + cell, y + cell // 2, fill=rgb_hex(rgb), outline="")

    def on_palette_click(self, event):
        if event.y < 16:
            self.set_active_color(-1)
            return
        idx = int((event.y - 16) // 8) * 16 + int(event.x // 16)
        if 0 <= idx < 256:
            self.set_active_color(idx)

    def on_preview_click(self, event):
        spr = self.preview_sprite
        zoom = max(1, int(self.zoom.get()))
        x = int(self.preview_canvas.canvasx(event.x) // zoom)
        y = int(self.preview_canvas.canvasy(event.y) // zoom)
        if 0 <= x < spr.width and 0 <= y < spr.height:
            idx = spr.pixels[y][x]
            self.set_active_color(idx)
        else:
            self.set_active_color(-1)

    def on_zoom_changed(self, event=None):
        self.app.color_convert_zoom = max(1, int(self.zoom.get()))
        self.refresh_preview()

    def refresh_swatches(self):
        for i in range(self.ROWS):
            for side, canvases, colors in [("from", self.from_swatches, self.from_colors), ("to", self.to_swatches, self.to_colors)]:
                canvas = canvases[i]
                canvas.configure(bg=self.color_bg(colors[i]))
                canvas.configure(highlightbackground="#ff0000" if self.active_slot == (i, side) else "#ddd")

    def mappings(self):
        return {src: dst for src, dst in zip(self.from_colors, self.to_colors) if src != dst}

    def converted_sprite(self):
        mapping = self.mappings()
        spr = clone_sprite(self.base_sprite)
        if not mapping:
            return spr
        for y, row in enumerate(spr.pixels):
            spr.pixels[y] = [mapping.get(p, p) for p in row]
        return spr

    def refresh_preview(self):
        self.preview_photo = ImageTools.sprite_to_photo(self.preview_sprite, self.app.palette, self.zoom.get(), False)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, image=self.preview_photo, anchor="nw")
        self.preview_canvas.config(scrollregion=(0, 0, self.preview_photo.width(), self.preview_photo.height()))

    def test(self):
        self.push_undo()
        self.tested = True
        self.preview_sprite = self.converted_sprite()
        self.refresh_preview()

    def restore_preview(self):
        if not self.tested:
            return
        self.push_undo()
        self.tested = False
        self.preview_sprite = clone_sprite(self.base_sprite)
        self.refresh_preview()

    def apply(self):
        mapping = self.mappings()
        if not mapping:
            self.destroy()
            return
        self.app.push_main_undo()
        indexes = range(len(self.app.archive.sprites)) if self.scope.get() == "all" else [self.index]
        for i in indexes:
            spr = self.app.archive.get_sprite(i)
            for y in range(spr.height):
                spr.pixels[y] = [mapping.get(p, p) for p in spr.pixels[y]]
            self.app.archive.raw_entries[i] = None
            self.app.invalidate_thumb(i)
        self.app.mark_dirty()
        self.app.draw_grid()
        self.destroy()


class ImportDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("批量导入")
        self.mode = tk.StringVar(value="replace")
        ttk.Radiobutton(master, text="覆盖全文件", variable=self.mode, value="replace").pack(anchor="w")
        ttk.Radiobutton(master, text="追加到最后", variable=self.mode, value="append").pack(anchor="w")
        ttk.Radiobutton(master, text="插入到当前选中贴图后", variable=self.mode, value="insert").pack(anchor="w")
        return master

    def apply(self):
        self.result = self.mode.get()


class ExportSelectedDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("导出PNG选项")
        self.scale = tk.IntVar(value=1)
        self.layout = tk.StringVar(value="single")
        ttk.Label(master, text="导出倍数").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        scale_combo = ttk.Combobox(master, textvariable=self.scale, values=EXPORT_SCALES, width=6, state="readonly")
        scale_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        bind_combobox_home_end(scale_combo)
        ttk.Label(master, text="导出形式").grid(row=1, column=0, sticky="nw", padx=4, pady=4)
        box = ttk.Frame(master)
        box.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Radiobutton(box, text="逐张PNG", variable=self.layout, value="single").pack(anchor="w")
        ttk.Radiobutton(box, text="4拼1", variable=self.layout, value="grid4").pack(anchor="w")
        ttk.Radiobutton(box, text="9拼1", variable=self.layout, value="grid9").pack(anchor="w")
        ttk.Radiobutton(box, text="16拼1", variable=self.layout, value="grid16").pack(anchor="w")
        ttk.Label(master, text="拼图模式按 X+Y 偏移固定点导出，无额外边缘 padding。").grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        return scale_combo

    def apply(self):
        self.result = {"scale": int(self.scale.get()), "layout": self.layout.get()}


class ImportSelectedDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("导入PNG选项")
        self.scale = tk.StringVar(value="自动")
        self.mode = tk.StringVar(value="as_is")
        ttk.Label(master, text="源图倍数").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        scale_combo = ttk.Combobox(master, textvariable=self.scale, values=["自动"] + [str(v) for v in EXPORT_SCALES], width=8, state="readonly")
        scale_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        bind_combobox_home_end(scale_combo)
        ttk.Label(master, text="自动会优先读取 manifest.csv，其次读取文件名里的 _s2/_s4/_s8/_s16。").grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
        ttk.Label(master, text="导入模式").grid(row=2, column=0, sticky="nw", padx=4, pady=4)
        box = ttk.Frame(master)
        box.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Radiobutton(box, text="原样（补方向边缘，每张一样大）", variable=self.mode, value="as_is").pack(anchor="w")
        ttk.Radiobutton(box, text="自动裁剪边缘", variable=self.mode, value="auto_crop").pack(anchor="w")
        ttk.Label(master, text="自动裁剪会切除透明边缘并校正X/Y偏移。").grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
        return scale_combo

    def apply(self):
        value = self.scale.get()
        self.result = {"scale": None if value == "自动" else int(value), "mode": self.mode.get()}


class GifExportDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("导出GIF选项")
        self.scale = tk.IntVar(value=1)
        self.transparent = tk.BooleanVar(value=False)
        ttk.Label(master, text="导出倍数").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        scale_combo = ttk.Combobox(master, textvariable=self.scale, values=EXPORT_SCALES, width=6, state="readonly")
        scale_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        bind_combobox_home_end(scale_combo)
        ttk.Checkbutton(master, text="导出为透明背景色", variable=self.transparent).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        ttk.Label(master, text="勾选后将 #307070 替换为 Alpha 透明通道。").grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
        return scale_combo

    def apply(self):
        self.result = {"scale": int(self.scale.get()), "transparent": bool(self.transparent.get())}


class GifImportDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("从GIF导入选项")
        self.mode = tk.StringVar(value="as_is")
        ttk.Label(master, text="导入模式").grid(row=0, column=0, sticky="nw", padx=4, pady=4)
        box = ttk.Frame(master)
        box.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Radiobutton(box, text="原样（补方向边缘，每张一样大）", variable=self.mode, value="as_is").pack(anchor="w")
        ttk.Radiobutton(box, text="自动裁剪边缘", variable=self.mode, value="auto_crop").pack(anchor="w")
        ttk.Label(master, text="原样模式保持导出时的边缘距离；自动裁剪会切除透明边缘并校正X/Y偏移。").grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        return master

    def apply(self):
        self.result = {"mode": self.mode.get()}


class OffsetDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("批量调整偏移")
        self.dx = tk.StringVar(value="")
        self.dy = tk.StringVar(value="")
        ttk.Label(master, text="X 相对调整").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        first_entry = ttk.Entry(master, textvariable=self.dx, width=10)
        first_entry.grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(master, text="Y 相对调整").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(master, textvariable=self.dy, width=10).grid(row=1, column=1, padx=4, pady=4)
        ttk.Label(master, text="可输入 +1、1 或 -1").grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        return first_entry

    def apply(self):
        self.result = (int(self.dx.get() or "0"), int(self.dy.get() or "0"))


class ResizeDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("批量修改宽度/高度")
        self.width_var = tk.StringVar(value="")
        self.height_var = tk.StringVar(value="")
        self.absolute_var = tk.BooleanVar(value=False)
        self.anchor_var = tk.IntVar(value=4)
        ttk.Label(master, text="宽度").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        first_entry = ttk.Entry(master, textvariable=self.width_var, width=10)
        first_entry.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(master, text="高度").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        height_entry = ttk.Entry(master, textvariable=self.height_var, width=10)
        height_entry.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Checkbutton(master, text="直接覆盖宽高（不勾选为相对增减）", variable=self.absolute_var).grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        ttk.Label(master, text="定位").grid(row=3, column=0, sticky="nw", padx=4, pady=4)
        grid = ttk.Frame(master)
        grid.grid(row=3, column=1, sticky="w", padx=4, pady=4)
        labels = ["↖", "↑", "↗", "←", "●", "→", "↙", "↓", "↘"]
        anchor_widgets = [first_entry, height_entry, master, self]
        for i, text in enumerate(labels):
            btn = ttk.Radiobutton(grid, text=text, value=i, variable=self.anchor_var, width=3)
            btn.grid(row=i // 3, column=i % 3, padx=1, pady=1)
            anchor_widgets.append(btn)
        ttk.Label(master, text="空值保持原值；相对模式支持 +1、1、-1").grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        ttk.Label(master, text="宽度/高度修改时会自动保持贴图相对X/Y偏移").grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 0))

        for widget in anchor_widgets:
            widget.bind("<Up>", lambda e: self.select_anchor(1))
            widget.bind("<Down>", lambda e: self.select_anchor(7))
            widget.bind("<Left>", lambda e: self.select_anchor(3))
            widget.bind("<Right>", lambda e: self.select_anchor(5))
        return first_entry

    def select_anchor(self, value):
        self.anchor_var.set(value)
        return "break"

    def apply(self):
        self.result = {
            "width": self.width_var.get().strip(),
            "height": self.height_var.get().strip(),
            "absolute": self.absolute_var.get(),
            "anchor": int(self.anchor_var.get()),
        }


class App:
    def __init__(self):
        set_app_user_model_id()
        self.root = tk.Tk()
        set_window_icon(self.root)
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.builtin_grid_cell_w = 170
        self.builtin_grid_cell_h = 90
        self.cfg_path = app_dir() / "config.ini"
        self.config = configparser.ConfigParser(interpolation=None)
        self.config.optionxform = str
        self.config.read(self.cfg_path, encoding="utf-8")
        self.default_grid_cell_w = self.config_int("View", "UnitWidthBase", self.builtin_grid_cell_w, minimum=1)
        self.default_grid_cell_h = self.config_int("View", "UnitHeightBase", self.builtin_grid_cell_h, minimum=1)
        self.cell_w = self.default_grid_cell_w
        self.cell_h = self.default_grid_cell_h
        self.per_row_values = self.config_int_list("View", "PerRowValues", list(range(4, 36)), minimum=1)
        self.unit_width_deltas = self.config_int_list("View", "UnitWidthDeltas", [-60,-55,-50,-45,-40,-35,-30,-25,-20,-15,-10,-5,0,5,10,15,20,25,30,35,40,45,50])
        self.unit_height_deltas = self.config_int_list("View", "UnitHeightDeltas", [-20,-15,-10,-5,0,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85,90])
        self.initial_per_row = self.config_int("View", "PerRow", 10, minimum=1)
        self.initial_grid_cell_w = self.config_grid_cell_value("UnitWidth", "UnitWidthDelta", self.default_grid_cell_w)
        self.initial_grid_cell_h = self.config_grid_cell_value("UnitHeight", "UnitHeightDelta", self.default_grid_cell_h)
        self.per_row_values = self.with_value(self.per_row_values, self.initial_per_row)
        self.unit_width_values = self.grid_cell_values(self.default_grid_cell_w, self.unit_width_deltas, self.initial_grid_cell_w)
        self.unit_height_values = self.grid_cell_values(self.default_grid_cell_h, self.unit_height_deltas, self.initial_grid_cell_h)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        # Restore saved window geometry, or fall back to cell-based calculation on first launch
        saved_width = self.config_int("View", "WindowWidth", 0, minimum=0)
        saved_height = self.config_int("View", "WindowHeight", 0, minimum=0)
        if saved_width > 0 and saved_height > 0:
            width = max(MAIN_WINDOW_MIN_WIDTH, saved_width)
            height = max(200, saved_height)
        else:
            width = min(
                max(MAIN_WINDOW_MIN_WIDTH, self.initial_grid_cell_w * self.initial_per_row + MAIN_WINDOW_EXTRA_WIDTH),
                max(MAIN_WINDOW_MIN_WIDTH, screen_w - MAIN_WINDOW_SCREEN_MARGIN),
            )
            height = min(920, max(780, screen_h - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.configure_fonts()
        self.gamepath = self.resolve_initial_gamepath()
        self.palette = Palette(self.gamepath / self.config.get("Run", "Palette", fallback="mmap.col"), self.config.get("Run", "TransparentColor", fallback=BG))
        self.files = self.load_file_entries()
        self.archive: JyPicArchive | None = None
        self.current_base = "pic"
        self.selection = set()
        self.last_selected_index = None
        self.sprite_clipboard = None
        self.image_clipboard = None
        self.image_clipboard_sequence = None
        self.anchor_margin_cache = None
        self.thumb_refs = []
        self.thumb_cache = {}
        self.per_row = tk.IntVar(value=self.initial_per_row)
        self.grid_cell_w = tk.IntVar(value=self.initial_grid_cell_w)
        self.grid_cell_h = tk.IntVar(value=self.initial_grid_cell_h)
        self.sprite_edit_zoom = 4
        self.color_convert_zoom = 4
        self.sprite_edit_show_offset = False
        self.sprite_edit_fixed_anchor = False
        self.sprite_edit_selected_color = 0
        self.file_choice = tk.StringVar()
        self.file_combo_digit_buffer = ""
        self.file_combo_digit_after = None
        self.image_digit_buffer = ""
        self.image_digit_after = None
        self.main_undo_stack = []
        self.main_redo_stack = []
        self.idx_var = tk.StringVar()
        self.grp_var = tk.StringVar()
        self.path_var = tk.StringVar(value=str(self.gamepath))
        self.build_ui()
        self.root.bind("<Control-s>", lambda e: self.save_archive())
        self.root.bind("<Control-a>", self.select_all)
        self.root.bind("<Control-A>", self.select_all)
        self.root.bind("<Control-c>", self.copy_shortcut)
        self.root.bind("<Control-C>", self.copy_shortcut)
        self.root.bind("<Control-Shift-C>", self.copy_with_offset_shortcut)
        self.root.bind("<Control-Shift-c>", self.copy_with_offset_shortcut)
        self.root.bind("<Control-v>", self.paste_shortcut)
        self.root.bind("<Control-V>", self.paste_shortcut)
        self.root.bind("<Control-Shift-V>", self.paste_with_offset_shortcut)
        self.root.bind("<Control-Shift-v>", self.paste_with_offset_shortcut)
        self.root.bind("<Control-n>", self.append_blank_shortcut)
        self.root.bind("<Control-N>", self.append_blank_shortcut)
        self.root.bind("<Control-i>", self.insert_blank_shortcut)
        self.root.bind("<Control-I>", self.insert_blank_shortcut)
        self.root.bind("<Delete>", self.delete_shortcut)
        self.root.bind("<Control-z>", self.main_undo)
        self.root.bind("<Control-Z>", self.main_redo)
        self.root.bind("<Control-Shift-Z>", self.main_redo)
        self.root.bind("<F1>", self.edit_shortcut)
        self.root.bind("<F2>", self.batch_offset_shortcut)
        self.root.bind("<F3>", self.batch_resize_shortcut)
        self.root.bind("<F4>", self.color_convert_shortcut)
        self.root.bind("<Alt-Key-1>", self.edit_shortcut)
        self.root.bind("<Alt-Key-2>", self.batch_offset_shortcut)
        self.root.bind("<Alt-Key-3>", self.batch_resize_shortcut)
        self.root.bind("<Alt-Key-4>", self.color_convert_shortcut)
        self.root.bind("<Home>", self.select_first_shortcut)
        self.root.bind("<End>", self.select_last_shortcut)
        self.root.bind("<Insert>", self.insert_before_first_shortcut)
        self.root.bind("<Control-Insert>", self.append_blank_shortcut)
        self.root.bind("<Control-t>", self.flip_horizontal_shortcut)
        self.root.bind("<Control-T>", self.flip_horizontal_shortcut)
        self.root.bind("<Control-End>", self.copy_to_end_shortcut)
        self.root.bind("<Control-r>", self.reverse_shortcut)
        self.root.bind("<Control-R>", self.reverse_shortcut)
        self.root.bind("<Control-g>", self.gif_export_shortcut)
        self.root.bind("<Control-G>", self.gif_export_shortcut)
        self.root.bind("<Control-Shift-G>", self.gif_import_shortcut)
        self.root.bind("<Control-Shift-g>", self.gif_import_shortcut)
        for digit in "0123456789":
            self.root.bind(str(digit), lambda e, d=digit: self.on_image_digit(d))
            self.root.bind(f"<KP_{digit}>", lambda e, d=digit: self.on_image_digit(d))
        self.root.bind("<Up>", lambda e: self.move_selection_by_key(-max(1, int(self.per_row.get())), e))
        self.root.bind("<Down>", lambda e: self.move_selection_by_key(max(1, int(self.per_row.get())), e))
        self.root.bind("<Left>", lambda e: self.move_selection_by_key(-1, e))
        self.root.bind("<Right>", lambda e: self.move_selection_by_key(1, e))
        self.root.bind("<Prior>", lambda e: self.page_move(-1))
        self.root.bind("<Next>", lambda e: self.page_move(1))
        self.root.bind("<Shift-Home>", lambda e: self.select_to_edge(0, e))
        self.root.bind("<Shift-End>", lambda e: self.select_to_edge(-1, e))
        self.root.bind("<Return>", lambda e: self.load_archive())
        self.root.bind("<Configure>", self._on_window_configure)
        self._geometry_save_after = None
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def configure_fonts(self):
        font_names = (
            "TkDefaultFont",
            "TkTextFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
        )
        for name in font_names:
            try:
                font = tkfont.nametofont(name)
                cfg = {"size": UI_FONT_SIZE}
                if UI_FONT_FAMILY:
                    cfg["family"] = UI_FONT_FAMILY
                font.configure(**cfg)
            except tk.TclError:
                pass
        style = ttk.Style(self.root)
        default_font = tkfont.nametofont("TkDefaultFont")
        style.configure(".", font=default_font)
        style.configure("Treeview", font=default_font)
        style.configure("Treeview.Heading", font=tkfont.nametofont("TkHeadingFont"))

    def config_int(self, section, option, default, minimum=None):
        try:
            value = self.config.get(section, option, fallback=str(default)).strip()
            result = int(value)
        except Exception:
            result = int(default)
        if minimum is not None:
            result = max(int(minimum), result)
        return result

    def config_int_list(self, section, option, default, minimum=None):
        raw = self.config.get(section, option, fallback="").strip()
        values = []
        if raw:
            for part in raw.replace("，", ",").split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    value = int(part)
                except ValueError:
                    continue
                if minimum is not None:
                    value = max(int(minimum), value)
                if value not in values:
                    values.append(value)
        return values or list(default)

    def with_value(self, values, value):
        value = int(value)
        if value not in values:
            values = list(values) + [value]
        return sorted(values)

    def config_grid_cell_value(self, legacy_option, delta_option, base):
        if self.config.has_option("View", delta_option):
            return max(1, int(base) + self.config_int("View", delta_option, 0))
        raw = self.config.get("View", legacy_option, fallback=f"{base}+0").strip().replace(" ", "")
        try:
            for pos in range(1, len(raw)):
                if raw[pos] in "+-":
                    return max(1, int(raw[:pos]) + int(raw[pos:]))
            return max(1, int(raw))
        except Exception:
            return int(base)

    def grid_cell_config_text(self, value, base):
        delta = int(value) - int(base)
        return f"{base}{delta:+d}"

    def config_int_list_text(self, values):
        return ",".join(str(int(v)) for v in values)

    def write_config(self):
        sections_written = set()
        lines = []

        def add_plain_section(section):
            if not self.config.has_section(section):
                return
            sections_written.add(section)
            lines.append(f"[{section}]")
            for key, value in self.config.items(section):
                lines.append(f"{key}={value}")
            lines.append("")

        add_plain_section("Run")
        if self.config.has_section("View"):
            sections_written.add("View")
            lines.extend([
                "[View]",
                "; 每行贴图启动默认值，也会在界面修改后保存为当前选择值",
                f"PerRow={self.config.get('View', 'PerRow', fallback='10')}",
                "; 每行贴图下拉菜单可选范围",
                f"PerRowValues={self.config.get('View', 'PerRowValues', fallback=self.config_int_list_text(list(range(4, 36))))}",
                "; 单元宽度/高度的基准值",
                f"UnitWidthBase={self.config.get('View', 'UnitWidthBase', fallback=str(self.builtin_grid_cell_w))}",
                f"UnitHeightBase={self.config.get('View', 'UnitHeightBase', fallback=str(self.builtin_grid_cell_h))}",
                "; 单元宽度/高度当前相对基准值的偏移，界面修改后保存这里",
                f"UnitWidthDelta={self.config.get('View', 'UnitWidthDelta', fallback='0')}",
                f"UnitHeightDelta={self.config.get('View', 'UnitHeightDelta', fallback='0')}",
                "; 单元宽度/高度下拉菜单可选的相对偏移范围",
                f"UnitWidthDeltas={self.config.get('View', 'UnitWidthDeltas', fallback=self.config_int_list_text([-30,-25,-20,-15,-10,-5,0,5,10,15,20,25,30]))}",
                f"UnitHeightDeltas={self.config.get('View', 'UnitHeightDeltas', fallback=self.config_int_list_text([-10,-5,0,5,10,15,20,25,30,35,40,45,50,55,60]))}",
                "; 主窗口宽/高，关闭时自动保存，下次启动恢复（独立于单元宽度）",
                f"WindowWidth={self.config.get('View', 'WindowWidth', fallback='0')}",
                f"WindowHeight={self.config.get('View', 'WindowHeight', fallback='0')}",
                "",
            ])
        add_plain_section("File")
        for section in self.config.sections():
            if section not in sections_written:
                add_plain_section(section)
        with self.cfg_path.open("w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines).rstrip() + "\n")

    def resolve_initial_gamepath(self):
        raw = self.config.get("Run", "Gamepath", fallback="../data")
        candidates = []
        p = Path(raw)
        if p.is_absolute():
            candidates.append(p)
        else:
            candidates.append((app_dir() / p).resolve())
            candidates.append((app_dir().parent / p).resolve())
        candidates.extend([
            app_dir() / "data",
            app_dir().parent / "data",
            app_dir().parent.parent / "data",
            Path.cwd() / "data",
        ])
        for c in candidates:
            if (c / "mmap.col").exists() or (c / "wdx").exists() or (c / "hdgrp.idx").exists():
                return c.resolve()
        return candidates[0].resolve()

    def write_config_gamepath(self):
        if not self.config.has_section("Run"):
            self.config.add_section("Run")
        self.config.set("Run", "Gamepath", str(self.gamepath))
        if not self.config.has_option("Run", "Palette"):
            self.config.set("Run", "Palette", "mmap.col")
        if not self.config.has_option("Run", "TransparentColor"):
            self.config.set("Run", "TransparentColor", BG)
        self.write_config()

    def write_view_config(self):
        if not self.config.has_section("View"):
            self.config.add_section("View")
        self.config.set("View", "PerRow", str(max(1, int(self.per_row.get()))))
        self.config.set("View", "PerRowValues", self.config_int_list_text(self.per_row_values))
        self.config.set("View", "UnitWidthBase", str(int(self.default_grid_cell_w)))
        self.config.set("View", "UnitHeightBase", str(int(self.default_grid_cell_h)))
        self.config.set("View", "UnitWidthDelta", str(int(self.grid_cell_w.get()) - int(self.default_grid_cell_w)))
        self.config.set("View", "UnitHeightDelta", str(int(self.grid_cell_h.get()) - int(self.default_grid_cell_h)))
        self.config.set("View", "UnitWidthDeltas", self.config_int_list_text(self.unit_width_deltas))
        self.config.set("View", "UnitHeightDeltas", self.config_int_list_text(self.unit_height_deltas))
        self.config.remove_option("View", "UnitWidth")
        self.config.remove_option("View", "UnitHeight")
        self.write_config()

    def set_data_path(self):
        messagebox.showinfo("设置路径", "请选择游戏目录下的 data 文件夹。")
        path = filedialog.askdirectory(title="请选择游戏 data 文件夹", initialdir=str(self.gamepath if self.gamepath.exists() else app_dir()))
        if not path:
            return
        p = Path(path).resolve()
        if p.name.lower() != "data":
            if not messagebox.askyesno("确认路径", "选择的文件夹名称不是 data。仍然使用这个文件夹吗？"):
                return
        if not ((p / "mmap.col").exists() or (p / "wdx").exists() or (p / "hdgrp.idx").exists()):
            if not messagebox.askyesno("确认路径", "该目录下没有发现常见贴图文件。仍然保存为游戏 data 路径吗？"):
                return
        self.gamepath = p
        self.path_var.set(str(self.gamepath))
        self.palette = Palette(self.gamepath / self.config.get("Run", "Palette", fallback="mmap.col"), self.config.get("Run", "TransparentColor", fallback=BG))
        self.write_config_gamepath()
        messagebox.showinfo("完成", f"已更新 config.ini：\n{self.gamepath}")

    def open_data_dir(self):
        try:
            if not self.gamepath.exists():
                raise FileNotFoundError(str(self.gamepath))
            os.startfile(self.gamepath)
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    def load_file_entries(self):
        sec = self.config["File"] if self.config.has_section("File") else {}
        n = int(sec.get("FileNumber", "0"))
        rows = []
        for i in range(n):
            raw = sec.get(f"File{i}", "")
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) >= 3:
                rows.append((parts[0], parts[1], parts[2]))
        fight = sec.get("FightName", "")
        if fight:
            parts = [p.strip() for p in fight.split(",")]
            if len(parts) >= 3:
                for i in range(int(sec.get("FightNum", "0"))):
                    rows.append((parts[0].replace("***", f"{i:03d}"), parts[1].replace("***", f"{i:03d}"), f"{parts[2]}{i:03d}"))
        return rows

    def grid_cell_values(self, base, deltas, current=None):
        values = []
        for delta in deltas:
            value = max(1, base + delta)
            if value not in values:
                values.append(value)
        if current is not None and int(current) not in values:
            values.append(int(current))
        return values

    def grid_cell_size(self):
        return max(1, int(self.grid_cell_w.get())), max(1, int(self.grid_cell_h.get()))

    def on_grid_cell_size_changed(self, event=None):
        self.write_view_config()
        self.draw_grid(clear_cache=False)

    def on_per_row_changed(self, event=None):
        self.write_view_config()
        self.draw_grid(clear_cache=False)

    def build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(top, text="设置data路径", command=self.set_data_path).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(top, textvariable=self.path_var, width=42, anchor="w").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="打开data目录", command=self.open_data_dir).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(top, text="单元宽度").pack(side=tk.LEFT)
        cell_w_combo = ttk.Combobox(top, textvariable=self.grid_cell_w, values=self.unit_width_values, width=5, state="readonly")
        cell_w_combo.pack(side=tk.LEFT, padx=4)
        bind_combobox_home_end(cell_w_combo, self.on_grid_cell_size_changed)
        ttk.Label(top, text="单元高度").pack(side=tk.LEFT)
        cell_h_combo = ttk.Combobox(top, textvariable=self.grid_cell_h, values=self.unit_height_values, width=4, state="readonly")
        cell_h_combo.pack(side=tk.LEFT, padx=4)
        bind_combobox_home_end(cell_h_combo, self.on_grid_cell_size_changed)
        ttk.Label(top, text="每行贴图").pack(side=tk.LEFT)
        per_combo = ttk.Combobox(top, textvariable=self.per_row, values=self.per_row_values, width=4, state="readonly")
        per_combo.pack(side=tk.LEFT, padx=4)
        bind_combobox_home_end(per_combo, self.on_per_row_changed)
        self.combo = ttk.Combobox(top, textvariable=self.file_choice, values=[f"{a},{b},{c}" for a, b, c in self.files], width=30)
        self.combo.pack(side=tk.LEFT, padx=6)
        bind_combobox_home_end(self.combo, self.fill_selected_file)
        self.bind_file_combo_digit_nav()
        ttk.Label(top, text="IDX").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.idx_var, width=13).pack(side=tk.LEFT, padx=3)
        ttk.Label(top, text="GRP").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.grp_var, width=13).pack(side=tk.LEFT, padx=3)
        ttk.Button(top, text="贴图查看", width=10, command=self.load_archive).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="保存", width=6,  command=self.save_archive).pack(side=tk.LEFT)
        ttk.Button(top, text="关于", width=6,  command=self.about).pack(side=tk.RIGHT)

        wrap = ttk.Frame(self.root)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(wrap, bg=BG, takefocus=True)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.on_yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.on_xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Double-Button-1>", self.on_double)
        self.canvas.bind("<Button-3>", self.popup)
        self.canvas.bind("<Configure>", lambda e: self.draw_grid(clear_cache=False))
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.menu = tk.Menu(self.root, tearoff=0)
        for label, cmd in [
            ("编辑贴图", self.edit_selected),
            ("颜色转换", self.color_convert_selected),
            ("批量调整X/Y偏移", self.batch_adjust_offset),
            ("批量修改宽度/高度", self.batch_resize_selected),
            ("选中贴图导出PNG", self.export_selected),
            ("选中贴图导入PNG(带偏移)", self.import_selected_with_offset),
            ("选中贴图导入PNG(无偏移)", self.import_selected_without_offset),
            ("导出为GIF动画", self.export_selected_gif),
            ("从GIF动画导入", self.import_from_gif),
            ("删除选中贴图", self.delete_selected),
        ]:
            self.menu.add_command(label=label, command=cmd)
        self.menu.add_separator()
        for label, cmd in [
            ("复制到剪贴板", self.copy_single_to_clipboard),
            ("复制到剪贴板(带偏移十字)", self.copy_single_to_clipboard_with_offset),
            ("从剪贴板粘贴", self.paste_single_from_clipboard),
            ("复制贴图(带偏移)", self.copy_sprite_with_offset),
            ("粘贴贴图(带偏移)", self.paste_sprite_with_offset),
            ("插入空白贴图(当前贴图前)", self.insert_blank_before),
            ("添加空白贴图到最后", self.append_blank_sprite),
            ("水平翻转", self.flip_selected_horizontal),
            ("复制并插入到最后", self.copy_selected_to_end),
            ("选中图片倒序排列", self.reverse_selected_in_place),
            ("选中贴图向前移位", self.shift_selected_forward),
            ("选中贴图向后移位", self.shift_selected_backward),
        ]:
            self.menu.add_command(label=label, command=cmd)
        self.menu.add_separator()
        self.menu.add_command(label="撤销", command=self.main_undo)
        self.menu.add_command(label="重做", command=self.main_redo)
        self.menu.add_command(label="保存文件", command=self.save_archive)

    def fill_selected_file(self):
        idx = self.combo.current()
        if idx >= 0:
            a, b, _ = self.files[idx]
            self.idx_var.set(a)
            self.grp_var.set(b)

    def bind_file_combo_digit_nav(self):
        def bind_popdown(event=None):
            try:
                listbox = self.combo.tk.call("ttk::combobox::PopdownWindow", str(self.combo)) + ".f.l"
                if not hasattr(self.combo, "_jy_file_digit_cmd"):
                    self.combo._jy_file_digit_cmd = self.combo.register(self.on_file_combo_digit)
                    self.combo._jy_file_commit_cmd = self.combo.register(self.commit_file_combo_selection)
                cmd = self.combo._jy_file_digit_cmd
                commit_cmd = self.combo._jy_file_commit_cmd
                for digit in "0123456789":
                    self.combo.tk.call("bind", listbox, f"<KeyPress-{digit}>", f"{cmd} {digit}; break")
                    self.combo.tk.call("bind", listbox, f"<KP_{digit}>", f"{cmd} {digit}; break")
                self.combo.tk.call("bind", listbox, "<Return>", f"{commit_cmd}; break")
            except tk.TclError:
                pass

        for digit in "0123456789":
            self.combo.bind(f"<KeyPress-{digit}>", lambda event, d=digit: self.on_file_combo_digit(d))
            self.combo.bind(f"<KP_{digit}>", lambda event, d=digit: self.on_file_combo_digit(d))
        self.combo.bind("<Return>", lambda event: self.commit_file_combo_selection())
        self.combo.bind("<FocusIn>", bind_popdown, add="+")
        self.combo.bind("<Button-1>", lambda event: self.combo.after(50, bind_popdown), add="+")

    def clear_file_combo_digit_buffer(self):
        self.file_combo_digit_buffer = ""
        self.file_combo_digit_after = None

    def on_file_combo_digit(self, digit):
        if not str(digit).isdigit():
            return "break"
        if self.file_combo_digit_after is not None:
            self.root.after_cancel(self.file_combo_digit_after)
            self.file_combo_digit_after = None
        if len(self.file_combo_digit_buffer) >= 3:
            self.file_combo_digit_buffer = ""
        self.file_combo_digit_buffer += str(digit)
        self.file_combo_digit_after = self.root.after(700, self.clear_file_combo_digit_buffer)
        idx = self.find_fight_file_index(int(self.file_combo_digit_buffer))
        if idx is not None:
            self.combo.current(idx)
            self.select_file_combo_popdown_index(idx)
            self.fill_selected_file()
            try:
                self.combo.icursor(tk.END)
            except tk.TclError:
                pass
        return "break"

    def select_file_combo_popdown_index(self, idx):
        try:
            listbox = self.combo.tk.call("ttk::combobox::PopdownWindow", str(self.combo)) + ".f.l"
            self.combo.tk.call(listbox, "selection", "clear", 0, "end")
            self.combo.tk.call(listbox, "selection", "set", idx)
            self.combo.tk.call(listbox, "activate", idx)
            self.combo.tk.call(listbox, "see", idx)
        except tk.TclError:
            pass

    def commit_file_combo_selection(self):
        self.fill_selected_file()
        self.clear_file_combo_digit_buffer()
        try:
            popdown = self.combo.tk.call("ttk::combobox::PopdownWindow", str(self.combo))
            is_posted = bool(int(self.combo.tk.call("winfo", "ismapped", popdown)))
        except tk.TclError:
            is_posted = False
        if is_posted:
            try:
                self.combo.tk.call("ttk::combobox::Unpost", str(self.combo))
            except tk.TclError:
                pass
        else:
            self.load_archive()
            try:
                self.canvas.focus_set()
            except tk.TclError:
                pass
        return "break"

    def find_fight_file_index(self, number):
        target_idx = f"fdx{int(number):03d}"
        target_grp = f"fmp{int(number):03d}"
        for i, (idx_name, grp_name, _label) in enumerate(self.files):
            if Path(idx_name).stem.lower() == target_idx and Path(grp_name).stem.lower() == target_grp:
                return i
        return None

    def resolve(self, name):
        p = Path(name)
        return p if p.is_absolute() else self.gamepath / p

    def load_archive(self):
        try:
            if not self.confirm_archive_switch():
                return
            idx_path = self.resolve(self.idx_var.get())
            grp_path = self.resolve(self.grp_var.get())
            if not idx_path.exists() or not grp_path.exists():
                raise FileNotFoundError(f"找不到贴图文件。\n当前data路径：{self.gamepath}\nIDX：{idx_path}\nGRP：{grp_path}\n\n请点击“设置data路径”，选择游戏目录下的data文件夹。")
            self.archive = JyPicArchive(idx_path, grp_path, self.palette)
            self.archive.load()
            self.current_base = Path(self.grp_var.get()).stem
            self.selection.clear()
            self.last_selected_index = None
            self.anchor_margin_cache = None
            self.canvas.yview_moveto(0)
            self.canvas.focus_set()
            self.draw_grid(clear_cache=True)
        except Exception as e:
            messagebox.showerror("读取失败", str(e))

    def confirm_archive_switch(self):
        if not self.archive or not self.archive.dirty:
            return True
        name = f"{self.archive.idx_path.name}/{self.archive.grp_path.name}"
        ans = messagebox.askyesnocancel("未保存", f"{name} 未保存，是否保存？\n选择“否”会丢失未保存进度。")
        if ans is None:
            return False
        if ans:
            return self.save_archive(confirm=False)
        return True

    def mark_dirty(self):
        if self.archive:
            self.archive.dirty = True
            self.anchor_margin_cache = None

    def invalidate_thumb(self, index=None):
        if index is None:
            self.thumb_cache.clear()
        else:
            self.thumb_cache.pop(index, None)

    def get_anchor_margins(self):
        if not self.archive:
            return (FIXED_ANCHOR_MIN_SIDE_MARGIN,) * 4
        if self.anchor_margin_cache is not None:
            return self.anchor_margin_cache
        margins = [FIXED_ANCHOR_MIN_SIDE_MARGIN] * 4
        for i, spr in enumerate(self.archive.sprites):
            if spr is not None:
                margins = [max(a, b) for a, b in zip(margins, sprite_anchor_margins(spr))]
                continue
            raw = self.archive.raw_entries[i] or b""
            if len(raw) >= 8:
                w, h, xoff, yoff = u16(raw, 0), u16(raw, 2), s16(raw, 4), s16(raw, 6)
                margins = [max(a, b) for a, b in zip(margins, sprite_anchor_margins(Sprite(w, h, xoff, yoff, [])))]
            else:
                margins = [max(a, b) for a, b in zip(margins, sprite_anchor_margins(blank_sprite()))]
        self.anchor_margin_cache = tuple(margins)
        return self.anchor_margin_cache

    def save_archive(self, confirm=True):
        if not self.archive:
            return True
        if confirm and not messagebox.askyesno("确认保存", "保存会覆盖 idx/grp，并自动生成备份文件。确定保存？"):
            return False
        try:
            self.archive.save()
            messagebox.showinfo("完成", "保存完成，已生成备份。")
            return True
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return False

    def on_yview(self, *args):
        self.canvas.yview(*args)
        self.draw_grid(clear_cache=False)

    def on_xview(self, *args):
        self.canvas.xview(*args)
        self.draw_grid(clear_cache=False)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.draw_grid(clear_cache=False)
        return "break"

    def thumb_photo(self, index):
        photo = self.thumb_cache.get(index)
        if photo is None:
            spr = self.archive.get_sprite(index)
            photo = ImageTools.sprite_to_photo(spr, self.palette, 1, False)
            self.thumb_cache[index] = photo
        return photo

    def draw_grid(self, clear_cache=False):
        self.canvas.delete("all")
        self.thumb_refs.clear()
        if not self.archive:
            return
        if clear_cache:
            self.invalidate_thumb()
        per = max(1, int(self.per_row.get()))
        cell_w, cell_h = self.grid_cell_size()
        box_w, box_h = max(1, cell_w - 8), max(1, cell_h - 8)
        total = len(self.archive.sprites)
        rows = (total + per - 1) // per
        self.canvas.config(scrollregion=(0, 0, per * cell_w, max(1, rows) * cell_h))
        top = max(0, self.canvas.canvasy(0))
        height = max(1, self.canvas.winfo_height())
        bottom = self.canvas.canvasy(height)
        first_row = max(0, int(top // cell_h) - 1)
        last_row = min(max(0, rows - 1), int(bottom // cell_h) + 1)
        for row in range(first_row, last_row + 1):
            start = row * per
            stop = min(total, start + per)
            for i in range(start, stop):
                col = i % per
                x, y = col * cell_w + 10, row * cell_h + 10
                photo = self.thumb_photo(i)
                self.thumb_refs.append(photo)
                self.canvas.create_text(x, y, text=str(i), fill="yellow", anchor="nw", font=("Arial", 11, "bold"))
                self.canvas.create_image(x + 22, y + 18, image=photo, anchor="nw")
                if i in self.selection:
                    self.canvas.create_rectangle(x, y, x + box_w, y + box_h, outline="red", width=2)

    def index_at(self, event):
        per = max(1, int(self.per_row.get()))
        cell_w, cell_h = self.grid_cell_size()
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        idx = int(y // cell_h) * per + int(x // cell_w)
        if self.archive and 0 <= idx < len(self.archive.sprites):
            return idx
        return None

    def on_click(self, event):
        self.canvas.focus_set()
        idx = self.index_at(event)
        if idx is None:
            return
        old_selection = set(self.selection)
        if event.state & 0x0001 and self.last_selected_index is not None:
            a, b = sorted((self.last_selected_index, idx))
            self.selection.update(range(a, b + 1))
        elif event.state & 0x0004:
            if idx in self.selection:
                self.selection.remove(idx)
            else:
                self.selection.add(idx)
            self.last_selected_index = idx
        else:
            self.selection = {idx}
            self.last_selected_index = idx
        if self.selection != old_selection:
            self.draw_grid(clear_cache=False)

    def select_all(self, event=None):
        if not self.archive:
            return "break"
        self.selection = set(range(len(self.archive.sprites)))
        self.last_selected_index = len(self.archive.sprites) - 1 if self.archive.sprites else None
        self.draw_grid(clear_cache=False)
        return "break"

    def copy_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.copy_single_to_clipboard()
        return "break"

    def paste_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.paste_single_from_clipboard()
        return "break"

    def copy_with_offset_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.copy_sprite_with_offset()
        return "break"

    def paste_with_offset_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.paste_sprite_with_offset()
        return "break"

    def append_blank_shortcut(self, event=None):
        self.append_blank_sprite()
        return "break"

    def insert_blank_shortcut(self, event=None):
        self.insert_blank_before()
        return "break"

    def delete_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.delete_selected()
        return "break"

    def edit_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.edit_selected()
        return "break"

    def batch_offset_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.batch_adjust_offset()
        return "break"

    def batch_resize_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.batch_resize_selected()
        return "break"

    def color_convert_shortcut(self, event=None):
        if self.main_shortcut_blocked():
            return None
        self.color_convert_selected()
        return "break"

    def select_first_shortcut(self, event=None):
        """Home — jump to first image, single selection."""
        if self.main_shortcut_blocked() or not self.archive or not self.archive.sprites:
            return None
        self.selection = {0}
        self.last_selected_index = 0
        self.ensure_index_visible(0)
        self.draw_grid(clear_cache=False)
        return "break"

    def select_last_shortcut(self, event=None):
        """End — jump to last image, single selection."""
        if self.main_shortcut_blocked() or not self.archive or not self.archive.sprites:
            return None
        last = len(self.archive.sprites) - 1
        self.selection = {last}
        self.last_selected_index = last
        self.ensure_index_visible(last)
        self.draw_grid(clear_cache=False)
        return "break"

    def insert_before_first_shortcut(self, event=None):
        """Insert — insert blank sprite before first selected (works with multi-selection)."""
        if not self.archive or not self.selection:
            return None
        self.push_main_undo()
        idx = min(self.selection)
        self.archive.insert_many(idx, [blank_sprite()])
        self.selection = {idx}
        self.last_selected_index = idx
        self.mark_dirty()
        self.draw_grid(clear_cache=True)
        return "break"

    def flip_horizontal_shortcut(self, event=None):
        """Ctrl+T — flip selected horizontally."""
        if self.main_shortcut_blocked():
            return None
        self.flip_selected_horizontal()
        return "break"

    def copy_to_end_shortcut(self, event=None):
        """Ctrl+End — copy selected to end."""
        if self.main_shortcut_blocked():
            return None
        self.copy_selected_to_end()
        return "break"

    def reverse_shortcut(self, event=None):
        """Ctrl+R — reverse selected in place."""
        if self.main_shortcut_blocked():
            return None
        self.reverse_selected_in_place()
        return "break"

    def gif_export_shortcut(self, event=None):
        """Ctrl+G — export selected as GIF animation."""
        if self.main_shortcut_blocked():
            return None
        self.export_selected_gif()
        return "break"

    def gif_import_shortcut(self, event=None):
        """Ctrl+Shift+G — import GIF animation into selected."""
        if self.main_shortcut_blocked():
            return None
        self.import_from_gif()
        return "break"

    def on_image_digit(self, digit):
        """Digit-based index navigation: press consecutive digits to select image by index number."""
        if self.main_shortcut_blocked() or not self.archive:
            return "break"
        if not str(digit).isdigit():
            return "break"
        if self.image_digit_after is not None:
            self.root.after_cancel(self.image_digit_after)
            self.image_digit_after = None
        if len(self.image_digit_buffer) >= 4:
            self.image_digit_buffer = ""
        self.image_digit_buffer += str(digit)
        self.image_digit_after = self.root.after(700, self._clear_image_digit_buffer)
        try:
            target = int(self.image_digit_buffer)
        except ValueError:
            return "break"
        total = len(self.archive.sprites)
        if target < 0 or target >= total:
            return "break"
        old_selection = set(self.selection)
        self.selection = {target}
        self.last_selected_index = target
        self.ensure_index_visible(target)
        if self.selection != old_selection:
            self.draw_grid(clear_cache=False)
        return "break"

    def _clear_image_digit_buffer(self):
        self.image_digit_buffer = ""
        self.image_digit_after = None

    def main_shortcut_blocked(self):
        widget = self.root.focus_get()
        if not widget:
            return False
        try:
            cls = widget.winfo_class()
        except tk.TclError:
            return False
        return cls in {"Entry", "TEntry", "TCombobox", "Text", "Spinbox", "TSpinbox"}

    def selection_reference_index(self):
        if not self.archive or not self.archive.sprites:
            return None
        total = len(self.archive.sprites)
        if self.last_selected_index is not None and 0 <= self.last_selected_index < total:
            return self.last_selected_index
        if self.selection:
            return min(max(self.selection), total - 1)
        return None

    def ensure_index_visible(self, idx):
        if not self.archive:
            return
        per = max(1, int(self.per_row.get()))
        cell_w, cell_h = self.grid_cell_size()
        total = len(self.archive.sprites)
        rows = (total + per - 1) // per
        total_w = max(1, per * cell_w)
        total_h = max(1, rows * cell_h)
        self.canvas.config(scrollregion=(0, 0, total_w, total_h))
        col, row = idx % per, idx // per
        x1, y1 = col * cell_w, row * cell_h
        x2, y2 = x1 + cell_w, y1 + cell_h
        view_left, view_top = self.canvas.canvasx(0), self.canvas.canvasy(0)
        view_right = view_left + max(1, self.canvas.winfo_width())
        view_bottom = view_top + max(1, self.canvas.winfo_height())
        if x1 < view_left:
            self.canvas.xview_moveto(x1 / total_w)
        elif x2 > view_right:
            self.canvas.xview_moveto(max(0, (x2 - self.canvas.winfo_width()) / total_w))
        if y1 < view_top:
            self.canvas.yview_moveto(y1 / total_h)
        elif y2 > view_bottom:
            self.canvas.yview_moveto(max(0, (y2 - self.canvas.winfo_height()) / total_h))

    def move_selection_by_key(self, delta, event=None):
        if self.main_shortcut_blocked() or not self.archive or not self.archive.sprites:
            return None
        total = len(self.archive.sprites)
        ref = self.selection_reference_index()
        if ref is None:
            target = 0
        else:
            target = max(0, min(total - 1, ref + int(delta)))
        shift = bool(event and event.state & 0x0001)
        ctrl = bool(event and event.state & 0x0004)
        old_selection = set(self.selection)
        if ref is None:
            self.selection = {target}
        elif shift:
            a, b = sorted((ref, target))
            self.selection.update(range(a, b + 1))
        elif ctrl:
            self.selection.add(target)
        else:
            self.selection = {target}
        self.last_selected_index = target
        self.ensure_index_visible(target)
        if self.selection != old_selection:
            self.draw_grid(clear_cache=False)
        return "break"

    def page_move(self, direction):
        """Page Up / Page Down — scroll by one page of visible rows."""
        if self.main_shortcut_blocked() or not self.archive or not self.archive.sprites:
            return "break"
        cell_w, cell_h = self.grid_cell_size()
        per = max(1, int(self.per_row.get()))
        vis_rows = max(1, self.canvas.winfo_height() // max(1, cell_h) - 1)
        delta = direction * vis_rows * per
        total = len(self.archive.sprites)
        ref = self.selection_reference_index()
        if ref is None:
            target = 0
        else:
            target = max(0, min(total - 1, ref + delta))
        old_selection = set(self.selection)
        self.selection = {target}
        self.last_selected_index = target
        self.ensure_index_visible(target)
        if self.selection != old_selection:
            self.draw_grid(clear_cache=False)
        return "break"

    def select_to_edge(self, edge, event=None):
        if self.main_shortcut_blocked() or not self.archive or not self.archive.sprites:
            return None
        total = len(self.archive.sprites)
        target = 0 if int(edge) == 0 else total - 1
        ref = self.selection_reference_index()
        if ref is None:
            ref = target
        a, b = sorted((ref, target))
        old_selection = set(self.selection)
        self.selection = set(range(a, b + 1))
        self.last_selected_index = target
        self.ensure_index_visible(target)
        if self.selection != old_selection:
            self.draw_grid(clear_cache=False)
        return "break"

    def on_double(self, event):
        idx = self.index_at(event)
        if idx is not None:
            self.selection = {idx}
            self.last_selected_index = idx
            self.edit_selected()

    def popup(self, event):
        self.canvas.focus_set()
        idx = self.index_at(event)
        if idx is not None and idx not in self.selection:
            self.selection = {idx}
            self.last_selected_index = idx
            self.draw_grid(clear_cache=False)
        self.update_menu_state()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            pass

    def _menu_set(self, label, state):
        """Safely configure a menu entry state, ignoring missing labels."""
        try:
            self.menu.entryconfigure(label, state=state)
        except tk.TclError:
            pass

    def update_menu_state(self):
        count = len(self.selection)
        single = count == 1
        has_selection = bool(self.archive and count > 0)
        multiple = bool(self.archive and count > 1)
        for label in ["编辑贴图", "颜色转换"]:
            self._menu_set(label, tk.NORMAL if has_selection else tk.DISABLED)
        for label in ["选中贴图导出PNG", "选中贴图导入PNG(带偏移)", "选中贴图导入PNG(无偏移)", "批量调整X/Y偏移", "批量修改宽度/高度", "删除选中贴图"]:
            self._menu_set(label, tk.NORMAL if has_selection else tk.DISABLED)
        for label in ["水平翻转", "复制并插入到最后"]:
            self._menu_set(label, tk.NORMAL if has_selection else tk.DISABLED)
        self._menu_set("选中图片倒序排列", tk.NORMAL if multiple else tk.DISABLED)
        for label in ["复制到剪贴板", "复制到剪贴板(带偏移十字)", "从剪贴板粘贴", "复制贴图(带偏移)"]:
            self._menu_set(label, tk.NORMAL if has_selection else tk.DISABLED)
        self._menu_set("插入空白贴图(当前贴图前)", tk.NORMAL if has_selection else tk.DISABLED)
        self._menu_set("粘贴贴图(带偏移)", tk.NORMAL if has_selection and self.has_sprite_clipboard() else tk.DISABLED)
        self._menu_set("添加空白贴图到最后", tk.NORMAL if self.archive else tk.DISABLED)
        self._menu_set("导出为GIF动画", tk.NORMAL if has_selection else tk.DISABLED)
        self._menu_set("从GIF动画导入", tk.NORMAL if has_selection else tk.DISABLED)
        self._menu_set("撤销", tk.NORMAL if self.main_undo_stack else tk.DISABLED)
        self._menu_set("重做", tk.NORMAL if self.main_redo_stack else tk.DISABLED)
        self._menu_set("保存文件", tk.NORMAL if self.archive else tk.DISABLED)
        self._menu_set("选中贴图向前移位", tk.NORMAL if self.can_shift_selected(-1) else tk.DISABLED)
        self._menu_set("选中贴图向后移位", tk.NORMAL if self.can_shift_selected(1) else tk.DISABLED)

    def selected_index(self):
        return min(self.selection) if self.selection else 0

    def selected_indices(self):
        return sorted(self.selection)

    def encode_sprite_clipboard_text(self, sprite):
        raw = JyPicArchive.encode_one(self.archive, sprite)
        return SPRITE_CLIPBOARD_PREFIX + base64.b64encode(raw).decode("ascii")

    def encode_sprites_clipboard_text(self, sprites):
        payload = [
            base64.b64encode(JyPicArchive.encode_one(self.archive, spr)).decode("ascii")
            for spr in sprites
        ]
        return SPRITE_LIST_CLIPBOARD_PREFIX + json.dumps(payload, separators=(",", ":"))

    def decode_sprite_clipboard_text(self, text):
        text = (text or "").strip()
        if not text.startswith(SPRITE_CLIPBOARD_PREFIX):
            return None
        try:
            raw = base64.b64decode(text[len(SPRITE_CLIPBOARD_PREFIX):], validate=True)
            return self.archive.decode_one(raw)
        except Exception:
            return None

    def decode_sprites_clipboard_text(self, text):
        text = (text or "").strip()
        if text.startswith(SPRITE_LIST_CLIPBOARD_PREFIX):
            try:
                items = json.loads(text[len(SPRITE_LIST_CLIPBOARD_PREFIX):])
                sprites = []
                for item in items:
                    raw = base64.b64decode(item, validate=True)
                    sprites.append(self.archive.decode_one(raw))
                return sprites
            except Exception:
                return None
        spr = self.decode_sprite_clipboard_text(text)
        return [spr] if spr else None

    def clipboard_sprites_with_offset(self):
        try:
            sprites = self.decode_sprites_clipboard_text(self.root.clipboard_get())
            if sprites:
                return sprites
        except tk.TclError:
            pass
        if self.sprite_clipboard:
            return [clone_sprite(spr) for spr in self.sprite_clipboard]
        return None

    def has_sprite_clipboard(self):
        if self.sprite_clipboard:
            return True
        try:
            return self.decode_sprites_clipboard_text(self.root.clipboard_get()) is not None
        except tk.TclError:
            return False

    def can_shift_selected(self, direction):
        if not self.archive or not self.selection:
            return False
        total = len(self.archive.sprites)
        if direction < 0:
            return any(i > 0 and i - 1 not in self.selection for i in self.selection)
        return any(i + 1 < total and i + 1 not in self.selection for i in self.selection)

    def edit_selected(self):
        if self.archive and self.archive.sprites:
            SpriteEditWindow(self, self.selected_index())

    def color_convert_selected(self):
        if self.archive and self.archive.sprites:
            ColorConvertWindow(self, self.selected_index())

    def parse_scale_from_name(self, path: Path):
        m = re.search(r"(?:^|_)s(1|2|4|8|16)(?:_|\.|$)", path.name, re.IGNORECASE)
        return int(m.group(1)) if m else 1

    def parse_xy_from_name(self, path: Path):
        m = re.search(r"(?:^|_)x(-?\d+)_y(-?\d+)(?:_|\.|$)", path.name, re.IGNORECASE)
        return (int(m.group(1)), int(m.group(2))) if m else None

    def import_pil_as_sprite(self, img, xoff, yoff, scale):
        img = downscale_import_image(img, scale)
        return ImageTools.pil_to_sprite(img, self.palette, xoff, yoff)

    def export_selected(self):
        if not self.archive or not self.selection:
            return
        dlg = ExportSelectedDialog(self.root)
        if not getattr(dlg, "result", None):
            return
        scale = max(1, int(dlg.result["scale"]))
        layout = dlg.result["layout"]
        root = filedialog.askdirectory(title="选择导出文件夹")
        if not root:
            return
        outdir = Path(root) / f"{self.current_base}_selected"
        outdir.mkdir(parents=True, exist_ok=True)
        digits = max(2, len(str(len(self.archive.sprites) - 1)))
        manifest = outdir / "manifest.csv"
        fields = ["index", "file", "width", "height", "xoff", "yoff", "scale", "layout", "page_file", "tile_slot", "cell_width", "cell_height", "cell_xoff", "cell_yoff"]
        selected = [(i, self.archive.get_sprite(i)) for i in self.selected_indices()]
        with manifest.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            if layout == "single":
                for i, spr in selected:
                    name = f"{self.current_base}_{i:0{digits}d}_x{spr.xoff}_y{spr.yoff}_s{scale}.png"
                    ImageTools.export_png(outdir / name, spr, self.palette, False, scale)
                    writer.writerow({
                        "index": i, "file": name, "width": spr.width, "height": spr.height,
                        "xoff": spr.xoff, "yoff": spr.yoff, "scale": scale, "layout": "single",
                        "page_file": "", "tile_slot": "", "cell_width": "", "cell_height": "",
                        "cell_xoff": "", "cell_yoff": "",
                    })
            else:
                per_page = 4 if layout == "grid4" else 9 if layout == "grid9" else 16
                cols = 2 if layout == "grid4" else 3 if layout == "grid9" else 4
                rows = cols
                margins = combined_anchor_margins([spr for _, spr in selected], min_margin=0)
                left, top, right, bottom = margins
                cell_w, cell_h = left + right + 1, top + bottom + 1
                for page_index in range(0, len(selected), per_page):
                    chunk = selected[page_index:page_index + per_page]
                    page_no = page_index // per_page
                    page_name = f"{self.current_base}_{layout}_page{page_no:03d}_x{left}_y{top}_s{scale}.png"
                    page = Image.new("RGB", (cell_w * cols * scale, cell_h * rows * scale), Palette.parse_hex(BG))
                    for slot, (i, spr) in enumerate(chunk):
                        tile = ImageTools.sprite_to_pil(spr, self.palette, False, scale, True, margins)
                        x = (slot % cols) * cell_w * scale
                        y = (slot // cols) * cell_h * scale
                        page.paste(tile, (x, y))
                        writer.writerow({
                            "index": i, "file": f"{page_name}#slot{slot}", "width": spr.width, "height": spr.height,
                            "xoff": spr.xoff, "yoff": spr.yoff, "scale": scale, "layout": layout,
                            "page_file": page_name, "tile_slot": slot, "cell_width": cell_w, "cell_height": cell_h,
                            "cell_xoff": left, "cell_yoff": top,
                        })
                    page.save(outdir / page_name, "PNG")
        messagebox.showinfo("完成", f"已导出 {len(self.selection)} 张贴图到：\n{outdir}")

    def export_selected_gif(self):
        if not self.archive or not self.selection:
            return
        dlg = GifExportDialog(self.root)
        if not getattr(dlg, "result", None):
            return
        scale = max(1, int(dlg.result["scale"]))
        transparent_bg = dlg.result["transparent"]
        targets = self.selected_indices()
        sprites = [self.archive.get_sprite(i) for i in targets]
        margins = combined_anchor_margins(sprites, min_margin=0)
        # The correct X/Y offset for the fixed-anchor padded GIF frame is the
        # anchor-margin (left, top), not any single sprite's raw xoff/yoff.
        gif_xoff = margins[0]
        gif_yoff = margins[1]
        # Build filename: base_x{xoff}_y{yoff}[_s{scale}][_tr].gif
        name_parts = [self.current_base, f"x{gif_xoff}_y{gif_yoff}"]
        if scale > 1:
            name_parts.append(f"s{scale}")
        if transparent_bg:
            name_parts.append("tr")
        initial = "_".join(name_parts) + ".gif"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出为GIF动画",
            defaultextension=".gif",
            initialfile=initial,
            filetypes=[("GIF", "*.gif")],
        )
        if not path:
            return
        frames = []
        for spr in sprites:
            img = ImageTools.sprite_to_pil(spr, self.palette, False, scale, True, margins)
            if transparent_bg:
                img = img.convert("RGBA")
                px = img.load()
                bg_tr = Palette.parse_hex(BG)
                for y in range(img.height):
                    for x in range(img.width):
                        r, g, b, a = px[x, y]
                        if (r, g, b) == bg_tr:
                            px[x, y] = (r, g, b, 0)
                # RGBA — Pillow converts to palette + handles transparency during save
                frames.append(img)
            else:
                # RGB mode: each frame processed independently → no dedup merging
                frames.append(img.convert("RGB"))
        if not frames:
            return
        kwargs = dict(save_all=True, append_images=frames[1:], duration=120, loop=0, disposal=2)
        if transparent_bg:
            kwargs["transparency"] = 0
        frames[0].save(path, **kwargs)
        messagebox.showinfo("完成", f"已导出 GIF：\n{path}")

    def import_from_gif(self):
        """右键菜单 - 从GIF动画导入，支持自动解析缩放倍数和X/Y偏移。"""
        if not self.archive or not self.selection:
            return
        path = filedialog.askopenfilename(
            parent=self.root,
            title="从GIF动画导入",
            filetypes=[("GIF", "*.gif")],
        )
        if not path:
            return
        dlg = GifImportDialog(self.root)
        if not getattr(dlg, "result", None):
            return
        mode = dlg.result["mode"]
        gif_path = Path(path)
        # Parse scale and offsets from filename
        filename_scale = self.parse_scale_from_name(gif_path)
        filename_xy = self.parse_xy_from_name(gif_path)
        # Read GIF frames; expand based on duration to recover merged duplicates.
        # Base duration is 120 ms (matching the export).
        BASE_DURATION = 120
        gif = Image.open(path)
        raw_frames = []  # (frame_image, duration_ms)
        i = 0
        while True:
            try:
                gif.seek(i)
                dur = gif.info.get("duration", BASE_DURATION)
                # Paste onto a fresh RGBA canvas to avoid palette / disposal artefacts
                frame = Image.new("RGBA", gif.size)
                frame.paste(gif)
                raw_frames.append((frame, max(1, int(dur or BASE_DURATION))))
                i += 1
            except EOFError:
                break
        gif.close()
        if not raw_frames:
            messagebox.showerror("导入失败", "GIF文件中没有可读取的帧。", parent=self.root)
            return
        # Expand frames: repeat each raw frame floor(duration / BASE_DURATION) times
        frames = []
        for img, dur in raw_frames:
            repeat = max(1, round(dur / BASE_DURATION))
            for _ in range(repeat):
                frames.append(img.copy())
        # Downscale if needed
        scale = max(1, int(filename_scale or 1))
        if scale > 1:
            frames = [downscale_import_image(f, scale) for f in frames]
        # Convert frames to sprites (alpha → transparent color)
        imported = []
        for img in frames:
            xoff = filename_xy[0] if filename_xy else 0
            yoff = filename_xy[1] if filename_xy else 0
            spr = pil_to_sprite_alpha_as_bg(img, self.palette, xoff, yoff)
            if mode == "auto_crop":
                auto_crop_sprite(spr, self.palette)
            imported.append(spr)
        targets = self.selected_indices()
        self.push_main_undo()
        if len(imported) > len(targets):
            # More GIF frames than selected slots:
            # fill selected slots first, then insert remaining after last selected
            for idx, spr in zip(targets, imported[:len(targets)]):
                old = self.archive.get_sprite(idx)
                if mode == "as_is":
                    # Preserve original X/Y offsets if not parsed from filename
                    if not filename_xy:
                        spr.xoff, spr.yoff = old.xoff, old.yoff
                self.archive.set_sprite(idx, spr)
                self.invalidate_thumb(idx)
            # Insert extra frames after last selected
            extra = imported[len(targets):]
            insert_pos = targets[-1] + 1 if targets else len(self.archive.sprites)
            self.archive.insert_many(insert_pos, extra)
            self.invalidate_thumb()
        elif len(imported) <= len(targets):
            # GIF frames ≤ selected slots: fill first N selected slots
            for idx, spr in zip(targets, imported):
                old = self.archive.get_sprite(idx)
                if mode == "as_is":
                    if not filename_xy:
                        spr.xoff, spr.yoff = old.xoff, old.yoff
                self.archive.set_sprite(idx, spr)
                self.invalidate_thumb(idx)
        self.mark_dirty()
        self.draw_grid(clear_cache=False)
        messagebox.showinfo("完成", f"已从GIF导入 {len(imported)} 帧。\n源：{path}")

    def import_selected_with_offset(self):
        self.import_selected(use_manifest_offset=True)

    def import_selected_without_offset(self):
        self.import_selected(use_manifest_offset=False)

    def import_selected(self, use_manifest_offset=True):
        if not self.archive or not self.selection:
            return
        folder = filedialog.askdirectory(title="选择PNG文件夹")
        if not folder:
            return
        folder = Path(folder)
        dlg = ImportSelectedDialog(self.root)
        if not getattr(dlg, "result", None):
            return
        forced_scale = dlg.result["scale"]
        mode = dlg.result["mode"]
        targets = self.selected_indices()
        imported = []
        man = folder / "manifest.csv"
        try:
            if man.exists():
                page_cache = {}
                with man.open("r", encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f):
                        layout = (row.get("layout") or "single").strip()
                        scale = int(forced_scale or row.get("scale") or 1)
                        if layout in {"grid4", "grid9", "grid16"} and row.get("page_file"):
                            page_path = folder / row["page_file"]
                            if page_path not in page_cache:
                                page_cache[page_path] = Image.open(page_path).convert("RGBA")
                            page = page_cache[page_path]
                            slot = int(row.get("tile_slot") or 0)
                            cols = 2 if layout == "grid4" else 3 if layout == "grid9" else 4
                            cell_w = int(row.get("cell_width") or max(1, page.width // cols))
                            cell_h = int(row.get("cell_height") or max(1, page.height // cols))
                            x = (slot % cols) * cell_w * scale
                            y = (slot // cols) * cell_h * scale
                            img = page.crop((x, y, x + cell_w * scale, y + cell_h * scale))
                            xoff = int(row.get("cell_xoff") or row.get("xoff") or 0)
                            yoff = int(row.get("cell_yoff") or row.get("yoff") or 0)
                        else:
                            file_name = row.get("file") or ""
                            path = folder / file_name
                            img = Image.open(path).convert("RGBA")
                            xoff = int(row.get("xoff") or 0)
                            yoff = int(row.get("yoff") or 0)
                        imported.append((img, xoff, yoff, scale))
            else:
                for path in sorted(folder.glob("*.png"), key=lambda p: p.name.lower()):
                    name = path.name.lower()
                    scale = int(forced_scale or self.parse_scale_from_name(path))
                    xy = self.parse_xy_from_name(path)
                    grid = re.search(r"_grid(4|9|16)_page\d+", name)
                    img = Image.open(path).convert("RGBA")
                    if grid:
                        count = int(grid.group(1))
                        cols = 2 if count == 4 else 3 if count == 9 else 4
                        rows = cols
                        cell_w, cell_h = img.width // cols, img.height // rows
                        xoff, yoff = xy or (None, None)
                        for slot in range(count):
                            x = (slot % cols) * cell_w
                            y = (slot // cols) * cell_h
                            imported.append((img.crop((x, y, x + cell_w, y + cell_h)), xoff, yoff, scale))
                    else:
                        xoff, yoff = xy or (None, None)
                        imported.append((img, xoff, yoff, scale))
        except Exception as e:
            messagebox.showerror("导入失败", f"读取 PNG 文件时出错：\n{e}", parent=self.root)
            return
        to_import = min(len(imported), len(targets))
        if to_import == 0:
            return
        self.push_main_undo()
        for idx, (img, meta_xoff, meta_yoff, scale) in zip(targets[:to_import], imported[:to_import]):
            old = self.archive.get_sprite(idx)
            if use_manifest_offset:
                xoff = old.xoff if meta_xoff is None else meta_xoff
                yoff = old.yoff if meta_yoff is None else meta_yoff
            else:
                xoff, yoff = old.xoff, old.yoff
            spr = self.import_pil_as_sprite(img, xoff, yoff, scale)
            if mode == "auto_crop":
                auto_crop_sprite(spr, self.palette)
            self.archive.set_sprite(idx, spr)
            self.invalidate_thumb(idx)
        self.mark_dirty()
        self.draw_grid(clear_cache=False)

    def batch_resize_selected(self):
        if not self.archive or not self.selection:
            return
        dlg = ResizeDialog(self.root)
        if not getattr(dlg, "result", None):
            return
        result = dlg.result
        if not result["width"] and not result["height"]:
            return
        self.push_main_undo()
        try:
            for i in self.selected_indices():
                spr = self.archive.get_sprite(i)
                if result["absolute"]:
                    new_w = int(result["width"]) if result["width"] else spr.width
                    new_h = int(result["height"]) if result["height"] else spr.height
                else:
                    new_w = spr.width + (int(result["width"]) if result["width"] else 0)
                    new_h = spr.height + (int(result["height"]) if result["height"] else 0)
                resize_sprite(spr, new_w, new_h, result["anchor"])
                self.archive.raw_entries[i] = None
                self.invalidate_thumb(i)
            self.mark_dirty()
            self.draw_grid(clear_cache=False)
        except Exception as e:
            messagebox.showerror("批量修改失败", str(e))

    def copy_single_to_clipboard(self):
        if not self.archive or not self.selection:
            return
        indexes = self.selected_indices()
        self.image_clipboard = [clone_sprite(self.archive.get_sprite(i)) for i in indexes]
        try:
            ImageTools.copy_sprite_to_clipboard(self.image_clipboard[0], self.palette, False)
            self.image_clipboard_sequence = clipboard_sequence_number()
        except Exception as e:
            messagebox.showerror("复制失败", str(e))

    def copy_single_to_clipboard_with_offset(self):
        if not self.archive or not self.selection:
            return
        indexes = self.selected_indices()
        self.image_clipboard = [clone_sprite(self.archive.get_sprite(i)) for i in indexes]
        try:
            ImageTools.copy_sprite_to_clipboard(self.image_clipboard[0], self.palette, True)
            self.image_clipboard_sequence = clipboard_sequence_number()
        except Exception as e:
            messagebox.showerror("复制失败", str(e))

    def paste_single_from_clipboard(self):
        if not self.archive or not self.selection:
            return
        self.push_main_undo()
        try:
            targets = self.selected_indices()
            current_seq = clipboard_sequence_number()
            use_internal = self.image_clipboard and current_seq is not None and current_seq == self.image_clipboard_sequence
            if use_internal:
                sources = [clone_sprite(spr) for spr in self.image_clipboard]
            else:
                old = self.archive.get_sprite(targets[0])
                sources = [ImageTools.sprite_from_clipboard(self.palette, old.xoff, old.yoff)]
            for idx, source in zip(targets, sources):
                old = self.archive.get_sprite(idx)
                pasted = clone_sprite(source)
                pasted.xoff, pasted.yoff = old.xoff, old.yoff
                self.archive.set_sprite(idx, pasted)
                self.invalidate_thumb(idx)
            self.mark_dirty()
            self.draw_grid(clear_cache=False)
        except Exception as e:
            messagebox.showerror("粘贴失败", str(e))

    def copy_sprite_with_offset(self):
        if not self.archive or not self.selection:
            return
        self.sprite_clipboard = [clone_sprite(self.archive.get_sprite(i)) for i in self.selected_indices()]
        try:
            self.root.clipboard_clear()
            if len(self.sprite_clipboard) == 1:
                self.root.clipboard_append(self.encode_sprite_clipboard_text(self.sprite_clipboard[0]))
            else:
                self.root.clipboard_append(self.encode_sprites_clipboard_text(self.sprite_clipboard))
        except tk.TclError as e:
            messagebox.showerror("复制失败", str(e))

    def paste_sprite_with_offset(self):
        if not self.archive or not self.selection:
            return
        self.push_main_undo()
        pasted = self.clipboard_sprites_with_offset()
        if not pasted:
            messagebox.showerror("粘贴失败", "剪贴板中没有可识别的贴图数据。")
            return
        for idx, spr in zip(self.selected_indices(), pasted):
            self.archive.set_sprite(idx, clone_sprite(spr))
            self.invalidate_thumb(idx)
        self.mark_dirty()
        self.draw_grid(clear_cache=False)

    def insert_blank_before(self):
        if not self.archive or not self.selection:
            return
        self.push_main_undo()
        idx = min(self.selection)
        self.archive.insert_many(idx, [blank_sprite()])
        self.selection = {idx}
        self.last_selected_index = idx
        self.mark_dirty()
        self.draw_grid(clear_cache=True)

    def append_blank_sprite(self):
        if not self.archive:
            return
        self.push_main_undo()
        idx = len(self.archive.sprites)
        self.archive.append_many([blank_sprite()])
        self.selection = {idx}
        self.last_selected_index = idx
        self.mark_dirty()
        self.draw_grid(clear_cache=True)

    def flip_selected_horizontal(self):
        if not self.archive or not self.selection:
            return
        self.push_main_undo()
        for idx in self.selected_indices():
            spr = self.archive.get_sprite(idx)
            spr.pixels = [list(reversed(row)) for row in spr.pixels]
            spr.xoff = spr.width - spr.xoff
            self.archive.raw_entries[idx] = None
            self.invalidate_thumb(idx)
        self.mark_dirty()
        self.draw_grid(clear_cache=False)

    def copy_selected_to_end(self):
        self.copy_selected_to_end_impl(reverse=False)

    def copy_selected_to_end_impl(self, reverse=False):
        if not self.archive or not self.selection:
            return
        self.push_main_undo()
        indexes = self.selected_indices()
        if reverse:
            indexes = list(reversed(indexes))
        start = len(self.archive.sprites)
        copies = [clone_sprite(self.archive.get_sprite(i)) for i in indexes]
        self.archive.append_many(copies)
        self.selection = set(range(start, start + len(copies)))
        self.last_selected_index = start + len(copies) - 1 if copies else None
        self.mark_dirty()
        self.draw_grid(clear_cache=True)

    def reverse_selected_in_place(self):
        if not self.archive or len(self.selection) < 2:
            return
        self.push_main_undo()
        indexes = self.selected_indices()
        sprites = [self.archive.sprites[i] for i in indexes]
        raws = [self.archive.raw_entries[i] for i in indexes]
        for idx, spr, raw in zip(indexes, reversed(sprites), reversed(raws)):
            self.archive.sprites[idx] = spr
            self.archive.raw_entries[idx] = raw
            self.invalidate_thumb(idx)
        self.last_selected_index = indexes[-1]
        self.mark_dirty()
        self.draw_grid(clear_cache=False)

    def shift_selected_forward(self):
        self.shift_selected(-1)

    def shift_selected_backward(self):
        self.shift_selected(1)

    def shift_selected(self, direction):
        if not self.archive or not self.can_shift_selected(direction):
            return
        self.push_main_undo()
        selected = set(self.selection)
        order = sorted(selected) if direction < 0 else sorted(selected, reverse=True)
        for idx in order:
            target = idx + direction
            if target < 0 or target >= len(self.archive.sprites) or target in selected:
                continue
            self.archive.sprites[idx], self.archive.sprites[target] = self.archive.sprites[target], self.archive.sprites[idx]
            self.archive.raw_entries[idx], self.archive.raw_entries[target] = self.archive.raw_entries[target], self.archive.raw_entries[idx]
            selected.remove(idx)
            selected.add(target)
        self.selection = selected
        self.last_selected_index = min(selected) if direction < 0 else max(selected)
        self.mark_dirty()
        self.draw_grid(clear_cache=True)

    def batch_adjust_offset(self):
        if not self.archive or not self.selection:
            return
        dlg = OffsetDialog(self.root)
        if not getattr(dlg, "result", None):
            return
        dx, dy = dlg.result
        if dx == 0 and dy == 0:
            return
        self.push_main_undo()
        if dx == 0 and dy == 0:
            return
        for i in self.selection:
            spr = self.archive.get_sprite(i)
            spr.xoff += dx
            spr.yoff += dy
            self.archive.raw_entries[i] = None
            self.invalidate_thumb(i)
        self.mark_dirty()
        self.draw_grid(clear_cache=False)

    def export_all(self):
        if not self.archive:
            return
        root = filedialog.askdirectory(title="选择导出文件夹")
        if not root:
            return
        show_offset = messagebox.askyesno("导出选项", "是否保存显示偏移红色十字？")
        outdir = Path(root) / self.current_base
        outdir.mkdir(parents=True, exist_ok=True)
        digits = max(2, len(str(len(self.archive.sprites) - 1)))
        manifest = outdir / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["index", "file", "width", "height", "xoff", "yoff"])
            for i in range(len(self.archive.sprites)):
                spr = self.archive.get_sprite(i)
                name = f"{self.current_base}_{i:0{digits}d}.png"
                ImageTools.export_png(outdir / name, spr, self.palette, show_offset)
                writer.writerow([i, name, spr.width, spr.height, spr.xoff, spr.yoff])
        messagebox.showinfo("完成", f"已导出到：\n{outdir}")

    def import_folder(self):
        if not self.archive:
            return
        folder = filedialog.askdirectory(title="选择PNG文件夹")
        if not folder:
            return
        dlg = ImportDialog(self.root)
        if not dlg.result:
            return
        folder = Path(folder)
        meta = {}
        man = folder / "manifest.csv"
        if man.exists():
            with man.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    meta[row["file"]] = (int(row.get("xoff", 0)), int(row.get("yoff", 0)))
        sprites = []
        for p in sorted(folder.glob("*.png")):
            xoff, yoff = meta.get(p.name, (0, 0))
            sprites.append(ImageTools.import_png(p, self.palette, xoff, yoff))
        if not sprites:
            return
        if dlg.result == "replace":
            self.archive.replace_all(sprites)
        elif dlg.result == "append":
            self.archive.append_many(sprites)
        else:
            pos = self.selected_index() + 1
            self.archive.insert_many(pos, sprites)
        self.mark_dirty()
        self.draw_grid(clear_cache=True)

    def push_main_undo(self):
        if not self.archive:
            return
        state = (
            [clone_sprite(self.archive.get_sprite(i)) for i in range(len(self.archive.sprites))],
            list(self.archive.raw_entries),
        )
        self.main_undo_stack.append(state)
        if len(self.main_undo_stack) > 50:
            self.main_undo_stack.pop(0)
        self.main_redo_stack.clear()

    def main_undo(self, event=None):
        if self.main_shortcut_blocked():
            return None
        if not self.main_undo_stack or not self.archive:
            return "break"
        # Save current state to redo
        current = (
            [clone_sprite(self.archive.get_sprite(i)) for i in range(len(self.archive.sprites))],
            list(self.archive.raw_entries),
        )
        self.main_redo_stack.append(current)
        if len(self.main_redo_stack) > 50:
            self.main_redo_stack.pop(0)
        # Restore undo state
        sprites, raws = self.main_undo_stack.pop()
        self.archive.sprites = sprites
        self.archive.raw_entries = raws
        self.selection.clear()
        self.last_selected_index = None
        self.anchor_margin_cache = None
        self.mark_dirty()
        self.draw_grid(clear_cache=True)
        return "break"

    def main_redo(self, event=None):
        if self.main_shortcut_blocked():
            return None
        if not self.main_redo_stack or not self.archive:
            return "break"
        current = (
            [clone_sprite(self.archive.get_sprite(i)) for i in range(len(self.archive.sprites))],
            list(self.archive.raw_entries),
        )
        self.main_undo_stack.append(current)
        sprites, raws = self.main_redo_stack.pop()
        self.archive.sprites = sprites
        self.archive.raw_entries = raws
        self.selection.clear()
        self.last_selected_index = None
        self.anchor_margin_cache = None
        self.mark_dirty()
        self.draw_grid(clear_cache=True)
        return "break"

    def delete_selected(self):
        if not self.archive or not self.selection:
            return
        targets = self.selected_indices()
        if not targets:
            return
        if not messagebox.askyesno("确认删除", f"删除 {len(targets)} 张贴图？"):
            return
        self.push_main_undo()
        self.archive.delete_indexes(targets)
        self.selection.clear()
        self.last_selected_index = None
        self.mark_dirty()
        self.draw_grid(clear_cache=True)

    def about(self):
        win = tk.Toplevel(self.root)
        set_window_icon(win)
        win.title("关于")
        win.resizable(False, False)
        win.transient(self.root)
        win.bind("<Escape>", lambda e: win.destroy())
        frm = ttk.Frame(win, padding=14)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text=APP_NAME, font=tkfont.nametofont("TkHeadingFont")).pack(anchor="w", pady=(0, 6))
        ttk.Label(frm, text=f"版本：{APP_VERSION}").pack(anchor="w")
        ttk.Label(frm, text=f"作者：{AUTHOR}").pack(anchor="w", pady=(0, 8))
        link = tk.Label(frm, text=f"B站：{BILIBILI_URL}", fg="#1a5fb4", cursor="hand2")
        link.configure(font=tkfont.nametofont("TkDefaultFont"))
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda e: webbrowser.open(BILIBILI_URL))
        ttk.Label(frm, text="欢迎关注，相关问题可私信提出").pack(anchor="w", pady=(2, 10))
        ttk.Label(frm, text="支持 idx/grp 贴图浏览、编辑、批量导入导出。").pack(anchor="w")
        btn_row = ttk.Frame(frm)
        btn_row.pack(anchor="e", pady=(12, 0))
        ttk.Button(btn_row, text="查看快捷键", command=self.show_shortcuts).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="确定", command=win.destroy).pack(side=tk.LEFT)
        win.update_idletasks()
        x = max(self.root.winfo_rootx(), self.root.winfo_rootx() + 80)
        y = max(self.root.winfo_rooty(), self.root.winfo_rooty() + 80)
        win.geometry(f"+{x}+{y}")
        focus_window(win)

    def show_shortcuts(self):
        """显示快捷键参考窗口，按功能分区以表格形式列出。"""
        win = tk.Toplevel(self.root)
        set_window_icon(win)
        win.title("快捷键参考")
        win.transient(self.root)
        win.bind("<Escape>", lambda e: win.destroy())

        sections = [
            ("主界面", [
                ("Ctrl+S", "保存文件"),
                ("Ctrl+A", "全选所有贴图"),
                ("Ctrl+C", "复制到剪贴板"),
                ("Ctrl+Shift+C", "复制到剪贴板（带偏移十字）"),
                ("Ctrl+V", "从剪贴板粘贴"),
                ("Ctrl+Shift+V", "粘贴贴图（带偏移）"),
                ("Ctrl+N", "添加空白贴图到最后"),
                ("Ctrl+I", "插入空白贴图（当前贴图前）"),
                ("Delete", "删除选中贴图"),
                ("Ctrl+Z", "撤销（右键操作）"),
                ("Ctrl+Shift+Z", "重做（右键操作）"),
                ("F1 / Alt+1", "编辑贴图"),
                ("F2 / Alt+2", "批量调整 X/Y 偏移"),
                ("F3 / Alt+3", "批量修改宽度/高度"),
                ("F4 / Alt+4", "颜色转换"),
                ("Home", "跳到第一张并单独框选"),
                ("End", "跳到最后一张并单独框选"),
                ("Insert", "选中贴图前插入空白贴图"),
                ("Ctrl+Insert", "添加空白贴图到最后"),
                ("Ctrl+T", "选中图片水平翻转"),
                ("Ctrl+End", "选中图片复制并插入到最后"),
                ("Ctrl+R", "选中图片倒序排列"),
                ("Ctrl+G", "选中图片导出 GIF 动画"),
                ("Ctrl+Shift+G", "从 GIF 动画导入到选中贴图"),
                ("0–9（连续按）", "按索引号跳转到指定贴图（0.7s 超时）"),
                ("↑ ↓ ← →", "方向键移动选择"),
                ("Page Up / Page Down", "向上/下翻一整页"),
                ("Shift+↑/↓/←/→", "扩展选择范围"),
                ("Shift+Home / Shift+End", "选择到首尾"),
                ("Enter", "加载并查看贴图文件"),
                ("鼠标滚轮 (画布)", "垂直滚动贴图列表"),
            ]),
            ("编辑贴图", [
                ("Ctrl+Z", "撤销"),
                ("Ctrl+Shift+Z", "重做"),
                ("Ctrl+C", "复制贴图到系统剪贴板"),
                ("Ctrl+V", "从系统剪贴板粘贴"),
                ("Ctrl+E", "切换显示偏移十字"),
                ("Ctrl+Q", "切换以 X+Y 偏移为固定点"),
                ("←", "上一张贴图"),
                ("→", "下一张贴图"),
                ("Esc", "关闭编辑窗口"),
                ("鼠标滚轮", "切换上一张/下一张"),
                ("Ctrl+鼠标滚轮", "切换上一张/下一张"),
                ("Alt+鼠标滚轮", "更改放大倍数"),
                ("左键点击画布", "拾取颜色"),
                ("右键拖拽画布", "按画笔/油漆桶模式上色"),
                ("左键拖拽画布", "裁剪贴图到选框范围"),
                ("双击色块", "自定义选色"),
                ("Enter (宽高/偏移框)", "确认并应用修改"),
            ]),
            ("颜色转换", [
                ("Ctrl+Z", "撤销操作"),
                ("Ctrl+Shift+Z", "重做操作"),
                ("左键点击色块", "选中当前行色块"),
                ("双击色块", "自定义选色"),
                ("左键点击预览图", "拾取预览图颜色"),
                ("Esc", "关闭颜色转换窗口"),
            ]),
            ("批量调整 X/Y 偏移", [
                ("Enter", "确认调整"),
                ("Esc", "关闭对话框"),
            ]),
            ("批量修改宽度/高度", [
                ("↑ ↓ ← →", "切换锚点定位"),
                ("Enter", "确认修改"),
                ("Esc", "关闭对话框"),
            ]),
        ]

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for section_title, rows in sections:
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=section_title)

            tree = ttk.Treeview(tab, columns=("key", "desc"), show="headings", height=min(len(rows), 20))
            tree.heading("key", text="快捷键", anchor="w")
            tree.heading("desc", text="功能说明", anchor="w")
            tree.column("key", width=210, minwidth=160)
            tree.column("desc", width=340, minwidth=200)

            vsb = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)

            tree.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            tab.rowconfigure(0, weight=1)
            tab.columnconfigure(0, weight=1)

            for key_text, desc_text in rows:
                tree.insert("", "end", values=(key_text, desc_text))

        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=(0, 10))
        center_window(win)
        focus_window(win)

    def close(self):
        if self.confirm_archive_switch():
            self._save_window_geometry()
            self.root.destroy()

    def _on_window_configure(self, event=None):
        if event and event.widget is not self.root:
            return
        if self._geometry_save_after is not None:
            self.root.after_cancel(self._geometry_save_after)
        self._geometry_save_after = self.root.after(500, self._save_window_geometry)

    def _save_window_geometry(self):
        self._geometry_save_after = None
        try:
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            if w > 0 and h > 0:
                if not self.config.has_section("View"):
                    self.config.add_section("View")
                self.config.set("View", "WindowWidth", str(w))
                self.config.set("View", "WindowHeight", str(h))
                self.write_config()
        except Exception:
            pass

    def run(self):
        if self.files:
            self.combo.current(0)
            self.fill_selected_file()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()

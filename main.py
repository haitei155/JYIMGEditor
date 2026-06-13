import base64
import configparser
import csv
import ctypes
import io
import os
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
APP_VERSION = "v0.4"
AUTHOR = "海底.zip"
BG = "#307070"
APP_USER_MODEL_ID = "haitei155.JYIMGEditor"
FIXED_ANCHOR_MIN_SIDE_MARGIN = 10
MAIN_WINDOW_EXTRA_WIDTH = 24
MAIN_WINDOW_SCREEN_MARGIN = 20
MAIN_WINDOW_MIN_WIDTH = 1000
UI_FONT_FAMILY = ""
UI_FONT_SIZE = 10
BILIBILI_URL = "https://space.bilibili.com/16385"
SPRITE_CLIPBOARD_PREFIX = "JYIMGEditorSpriteV1:"


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


def sprite_anchor_margins(sprite):
    return (
        max(FIXED_ANCHOR_MIN_SIDE_MARGIN, int(sprite.xoff)),
        max(FIXED_ANCHOR_MIN_SIDE_MARGIN, int(sprite.yoff)),
        max(FIXED_ANCHOR_MIN_SIDE_MARGIN, int(sprite.width) - 1 - int(sprite.xoff)),
        max(FIXED_ANCHOR_MIN_SIDE_MARGIN, int(sprite.height) - 1 - int(sprite.yoff)),
    )


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

    @staticmethod
    def parse_hex(value):
        value = (value or BG).strip().lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def nearest(self, rgb):
        best_i, best_d = 0, 10**18
        for i, c in enumerate(self.colors):
            d = (c[0] - rgb[0]) ** 2 + (c[1] - rgb[1]) ** 2 + (c[2] - rgb[2]) ** 2
            if d < best_d:
                best_i, best_d = i, d
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
    def export_png(path: Path, sprite: Sprite, palette: Palette, show_offset=False):
        photo = ImageTools.sprite_to_photo(sprite, palette, 1, show_offset)
        photo.write(str(path), format="png")

    @staticmethod
    def sprite_to_pil(sprite: Sprite, palette: Palette, show_offset=False):
        width = max(1, sprite.width)
        height = max(1, sprite.height)
        if show_offset:
            width = max(width, sprite.xoff + 1)
            height = max(height, sprite.yoff + 1)
        img = Image.new("RGB", (width, height), Palette.parse_hex(BG))
        px = img.load()
        for y, row in enumerate(sprite.pixels):
            for x, idx in enumerate(row):
                if idx >= 0:
                    px[x, y] = tuple(palette.colors[idx])
        if show_offset:
            cx, cy = sprite.xoff, sprite.yoff
            red = (255, 0, 0)
            for x in range(max(0, cx - 8), min(width, cx + 9)):
                if 0 <= cy < height:
                    px[x, cy] = red
            for y in range(max(0, cy - 8), min(height, cy + 9)):
                if 0 <= cx < width:
                    px[cx, y] = red
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
        self.selected_color = tk.IntVar(value=0)
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
        ToolTip(self.canvas, "左键拾取颜色，右键按当前模式上色，左键拖拽方块裁剪贴图", delay=2000)

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
            self.selected_color_hex.set(BG)
            self.color_preview.configure(bg=BG)
            self.color_text_updating = False
            return
        idx = max(0, min(255, idx))
        self.selected_color.set(idx)
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
        self.builtin_grid_cell_w = 180
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
        self.unit_width_deltas = self.config_int_list("View", "UnitWidthDeltas", [-30,-25,-20,-15,-10,-5,0,5,10,15,20,25,30])
        self.unit_height_deltas = self.config_int_list("View", "UnitHeightDeltas", [-10,-5,0,5,10,15,20,25,30,35,40,45,50,55,60])
        self.initial_per_row = self.config_int("View", "PerRow", 10, minimum=1)
        self.initial_grid_cell_w = self.config_grid_cell_value("UnitWidth", "UnitWidthDelta", self.default_grid_cell_w)
        self.initial_grid_cell_h = self.config_grid_cell_value("UnitHeight", "UnitHeightDelta", self.default_grid_cell_h)
        self.per_row_values = self.with_value(self.per_row_values, self.initial_per_row)
        self.unit_width_values = self.grid_cell_values(self.default_grid_cell_w, self.unit_width_deltas, self.initial_grid_cell_w)
        self.unit_height_values = self.grid_cell_values(self.default_grid_cell_h, self.unit_height_deltas, self.initial_grid_cell_h)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
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
        self.file_choice = tk.StringVar()
        self.file_combo_digit_buffer = ""
        self.file_combo_digit_after = None
        self.idx_var = tk.StringVar()
        self.grp_var = tk.StringVar()
        self.path_var = tk.StringVar(value=str(self.gamepath))
        self.build_ui()
        self.root.bind("<Control-s>", lambda e: self.save_archive())
        self.root.bind("<Control-a>", self.select_all)
        self.root.bind("<Control-A>", self.select_all)
        self.root.bind("<Control-c>", self.copy_shortcut)
        self.root.bind("<Control-C>", self.copy_shortcut)
        self.root.bind("<Control-v>", self.paste_shortcut)
        self.root.bind("<Control-V>", self.paste_shortcut)
        self.root.bind("<Control-n>", self.append_blank_shortcut)
        self.root.bind("<Control-N>", self.append_blank_shortcut)
        self.root.bind("<Control-i>", self.insert_blank_shortcut)
        self.root.bind("<Control-I>", self.insert_blank_shortcut)
        self.root.bind("<Delete>", self.delete_shortcut)
        self.root.bind("1", self.edit_shortcut)
        self.root.bind("<KP_1>", self.edit_shortcut)
        self.root.bind("2", self.batch_offset_shortcut)
        self.root.bind("<KP_2>", self.batch_offset_shortcut)
        self.root.bind("3", self.batch_resize_shortcut)
        self.root.bind("<KP_3>", self.batch_resize_shortcut)
        self.root.bind("4", self.color_convert_shortcut)
        self.root.bind("<KP_4>", self.color_convert_shortcut)
        self.root.bind("<Up>", lambda e: self.move_selection_by_key(-max(1, int(self.per_row.get())), e))
        self.root.bind("<Down>", lambda e: self.move_selection_by_key(max(1, int(self.per_row.get())), e))
        self.root.bind("<Left>", lambda e: self.move_selection_by_key(-1, e))
        self.root.bind("<Right>", lambda e: self.move_selection_by_key(1, e))
        self.root.bind("<Shift-Home>", lambda e: self.select_to_edge(0, e))
        self.root.bind("<Shift-End>", lambda e: self.select_to_edge(-1, e))
        self.root.bind("<Return>", lambda e: self.load_archive())
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
        cell_h_combo = ttk.Combobox(top, textvariable=self.grid_cell_h, values=self.unit_height_values, width=5, state="readonly")
        cell_h_combo.pack(side=tk.LEFT, padx=4)
        bind_combobox_home_end(cell_h_combo, self.on_grid_cell_size_changed)
        ttk.Label(top, text="每行贴图").pack(side=tk.LEFT)
        per_combo = ttk.Combobox(top, textvariable=self.per_row, values=self.per_row_values, width=5, state="readonly")
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
        ttk.Button(top, text="贴图查看", command=self.load_archive).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="保存", command=self.save_archive).pack(side=tk.LEFT)
        ttk.Button(top, text="关于", command=self.about).pack(side=tk.RIGHT)

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
            ("复制并倒序插入到最后", self.copy_selected_reversed_to_end),
            ("选中贴图向前移位", self.shift_selected_forward),
            ("选中贴图向后移位", self.shift_selected_backward),
        ]:
            self.menu.add_command(label=label, command=cmd)
        self.menu.add_separator()
        self.menu.add_command(label="保存图片", command=self.save_archive)

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
        self.copy_single_to_clipboard()
        return "break"

    def paste_shortcut(self, event=None):
        self.paste_single_from_clipboard()
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
        self.menu.tk_popup(event.x_root, event.y_root)

    def update_menu_state(self):
        count = len(self.selection)
        single = count == 1
        has_selection = bool(self.archive and count > 0)
        for label in ["编辑贴图", "颜色转换"]:
            self.menu.entryconfigure(label, state=tk.NORMAL if has_selection else tk.DISABLED)
        for label in ["选中贴图导出PNG", "选中贴图导入PNG(带偏移)", "选中贴图导入PNG(无偏移)", "批量调整X/Y偏移", "批量修改宽度/高度", "删除选中贴图"]:
            self.menu.entryconfigure(label, state=tk.NORMAL if has_selection else tk.DISABLED)
        for label in ["水平翻转", "复制并插入到最后", "复制并倒序插入到最后"]:
            self.menu.entryconfigure(label, state=tk.NORMAL if has_selection else tk.DISABLED)
        for label in ["复制到剪贴板", "复制到剪贴板(带偏移十字)", "从剪贴板粘贴", "复制贴图(带偏移)", "插入空白贴图(当前贴图前)"]:
            self.menu.entryconfigure(label, state=tk.NORMAL if single else tk.DISABLED)
        self.menu.entryconfigure("粘贴贴图(带偏移)", state=tk.NORMAL if single and self.has_sprite_clipboard() else tk.DISABLED)
        self.menu.entryconfigure("添加空白贴图到最后", state=tk.NORMAL if self.archive else tk.DISABLED)
        self.menu.entryconfigure("选中贴图向前移位", state=tk.NORMAL if self.can_shift_selected(-1) else tk.DISABLED)
        self.menu.entryconfigure("选中贴图向后移位", state=tk.NORMAL if self.can_shift_selected(1) else tk.DISABLED)

    def selected_index(self):
        return min(self.selection) if self.selection else 0

    def selected_indices(self):
        return sorted(self.selection)

    def encode_sprite_clipboard_text(self, sprite):
        raw = JyPicArchive.encode_one(self.archive, sprite)
        return SPRITE_CLIPBOARD_PREFIX + base64.b64encode(raw).decode("ascii")

    def decode_sprite_clipboard_text(self, text):
        text = (text or "").strip()
        if not text.startswith(SPRITE_CLIPBOARD_PREFIX):
            return None
        try:
            raw = base64.b64decode(text[len(SPRITE_CLIPBOARD_PREFIX):], validate=True)
            return self.archive.decode_one(raw)
        except Exception:
            return None

    def clipboard_sprite_with_offset(self):
        try:
            spr = self.decode_sprite_clipboard_text(self.root.clipboard_get())
            if spr:
                return spr
        except tk.TclError:
            pass
        if self.sprite_clipboard:
            return clone_sprite(self.sprite_clipboard)
        return None

    def has_sprite_clipboard(self):
        if self.sprite_clipboard:
            return True
        try:
            return self.decode_sprite_clipboard_text(self.root.clipboard_get()) is not None
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

    def export_selected(self):
        if not self.archive or not self.selection:
            return
        root = filedialog.askdirectory(title="选择导出文件夹")
        if not root:
            return
        outdir = Path(root) / f"{self.current_base}_selected"
        outdir.mkdir(parents=True, exist_ok=True)
        digits = max(2, len(str(len(self.archive.sprites) - 1)))
        manifest = outdir / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["index", "file", "width", "height", "xoff", "yoff"])
            for i in self.selected_indices():
                spr = self.archive.get_sprite(i)
                name = f"{self.current_base}_{i:0{digits}d}.png"
                ImageTools.export_png(outdir / name, spr, self.palette, False)
                writer.writerow([i, name, spr.width, spr.height, spr.xoff, spr.yoff])
        messagebox.showinfo("完成", f"已导出 {len(self.selection)} 张贴图到：\n{outdir}")

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
        files = sorted(folder.glob("*.png"), key=lambda p: p.name.lower())
        targets = self.selected_indices()
        if len(files) < len(targets):
            messagebox.showerror("导入失败", f"PNG 数量不足：需要 {len(targets)} 张，实际 {len(files)} 张。")
            return
        meta = {}
        man = folder / "manifest.csv"
        if use_manifest_offset and man.exists():
            with man.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    meta[row["file"]] = (int(row.get("xoff", 0)), int(row.get("yoff", 0)))
        for idx, path in zip(targets, files[:len(targets)]):
            old = self.archive.get_sprite(idx)
            if use_manifest_offset:
                xoff, yoff = meta.get(path.name, (old.xoff, old.yoff))
            else:
                xoff, yoff = old.xoff, old.yoff
            self.archive.set_sprite(idx, ImageTools.import_png(path, self.palette, xoff, yoff))
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
        if not self.archive or len(self.selection) != 1:
            return
        try:
            ImageTools.copy_sprite_to_clipboard(self.archive.get_sprite(self.selected_index()), self.palette, False)
        except Exception as e:
            messagebox.showerror("复制失败", str(e))

    def copy_single_to_clipboard_with_offset(self):
        if not self.archive or len(self.selection) != 1:
            return
        try:
            ImageTools.copy_sprite_to_clipboard(self.archive.get_sprite(self.selected_index()), self.palette, True)
        except Exception as e:
            messagebox.showerror("复制失败", str(e))

    def paste_single_from_clipboard(self):
        if not self.archive or len(self.selection) != 1:
            return
        idx = self.selected_index()
        try:
            old = self.archive.get_sprite(idx)
            pasted = ImageTools.sprite_from_clipboard(self.palette, old.xoff, old.yoff)
            self.archive.set_sprite(idx, pasted)
            self.invalidate_thumb(idx)
            self.mark_dirty()
            self.draw_grid(clear_cache=False)
        except Exception as e:
            messagebox.showerror("粘贴失败", str(e))

    def copy_sprite_with_offset(self):
        if not self.archive or len(self.selection) != 1:
            return
        self.sprite_clipboard = clone_sprite(self.archive.get_sprite(self.selected_index()))
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.encode_sprite_clipboard_text(self.sprite_clipboard))
        except tk.TclError as e:
            messagebox.showerror("复制失败", str(e))

    def paste_sprite_with_offset(self):
        if not self.archive or len(self.selection) != 1:
            return
        pasted = self.clipboard_sprite_with_offset()
        if not pasted:
            messagebox.showerror("粘贴失败", "剪贴板中没有可识别的贴图数据。")
            return
        idx = self.selected_index()
        self.archive.set_sprite(idx, pasted)
        self.invalidate_thumb(idx)
        self.mark_dirty()
        self.draw_grid(clear_cache=False)

    def insert_blank_before(self):
        if not self.archive or len(self.selection) != 1:
            return
        idx = self.selected_index()
        self.archive.insert_many(idx, [blank_sprite()])
        self.selection = {idx}
        self.last_selected_index = idx
        self.mark_dirty()
        self.draw_grid(clear_cache=True)

    def append_blank_sprite(self):
        if not self.archive:
            return
        idx = len(self.archive.sprites)
        self.archive.append_many([blank_sprite()])
        self.selection = {idx}
        self.last_selected_index = idx
        self.mark_dirty()
        self.draw_grid(clear_cache=True)

    def flip_selected_horizontal(self):
        if not self.archive or not self.selection:
            return
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

    def copy_selected_reversed_to_end(self):
        self.copy_selected_to_end_impl(reverse=True)

    def copy_selected_to_end_impl(self, reverse=False):
        if not self.archive or not self.selection:
            return
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

    def shift_selected_forward(self):
        self.shift_selected(-1)

    def shift_selected_backward(self):
        self.shift_selected(1)

    def shift_selected(self, direction):
        if not self.archive or not self.can_shift_selected(direction):
            return
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

    def delete_selected(self):
        if not self.archive or not self.selection:
            return
        targets = self.selected_indices()
        if not targets:
            return
        if not messagebox.askyesno("确认删除", f"删除 {len(targets)} 张贴图？"):
            return
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
        ttk.Button(frm, text="确定", command=win.destroy).pack(anchor="e", pady=(12, 0))
        win.update_idletasks()
        x = max(self.root.winfo_rootx(), self.root.winfo_rootx() + 80)
        y = max(self.root.winfo_rooty(), self.root.winfo_rooty() + 80)
        win.geometry(f"+{x}+{y}")
        focus_window(win)

    def close(self):
        if self.confirm_archive_switch():
            self.root.destroy()

    def run(self):
        if self.files:
            self.combo.current(0)
            self.fill_selected_file()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()

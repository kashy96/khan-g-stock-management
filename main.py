"""KHAN G Stationary - Stock Management ERP.

Run:  python main.py
Default login:  admin / admin123   (change it after first login!)
"""

import csv
import io
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from db import DATE_FMT, Database, load_config

SHOP_NAME = "KHAN G Stationary"
CURRENCY = "Rs"

PERIODS = ["Today", "Yesterday", "This Week", "Last Week",
           "This Month", "Last Month", "This Year", "All Time", "Custom"]

# ------------------------------------------------------------------ theme ----

C = {
    "sidebar":        "#0f172a",
    "sidebar_hover":  "#1e293b",
    "sidebar_active": "#242e45",
    "sidebar_text":   "#94a3b8",
    "sidebar_bright": "#f8fafc",
    "accent":         "#4f46e5",
    "accent_dark":    "#4338ca",
    "accent_press":   "#3730a3",
    "bg":             "#f2f3f6",
    "card":           "#ffffff",
    "border":         "#e3e6ec",
    "shadow":         "#d9dce3",
    "ghost_hover":    "#eef0fb",
    "ghost_press":    "#e1e5f9",
    "text":           "#0f172a",
    "muted":          "#64748b",
    "green":          "#16a34a",
    "green_dark":     "#15803d",
    "red":            "#dc2626",
    "red_dark":       "#b91c1c",
    "amber":          "#d97706",
    "teal":           "#0d9488",
    "blue":           "#2563eb",
    "stripe":         "#f6f8fb",
    "low_row":        "#fdecec",
}

F = {
    "brand":  ("Segoe UI", 17, "bold"),
    "h1":     ("Segoe UI", 15, "bold"),
    "h2":     ("Segoe UI", 11, "bold"),
    "body":   ("Segoe UI", 10),
    "small":  ("Segoe UI", 9),
    "tiny":   ("Segoe UI", 8),
    "stat":   ("Segoe UI", 16, "bold"),
    "nav":    ("Segoe UI", 10, "bold"),
}


def money(value):
    return f"{CURRENCY} {value:,.2f}"


def process_image_file(path):
    """Load a photo file, shrink it and return JPEG bytes for DB storage."""
    img = Image.open(path)
    img = img.convert("RGB")
    img.thumbnail((1000, 1000))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def photo_from_bytes(data, max_w, max_h):
    """PhotoImage from stored image bytes, scaled to fit the preview area."""
    img = Image.open(io.BytesIO(data))
    img.thumbnail((max_w, max_h))
    return ImageTk.PhotoImage(img)


def setup_styles(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=C["bg"], foreground=C["text"], font=F["body"])
    style.configure("TFrame", background=C["bg"])
    style.configure("Card.TFrame", background=C["card"])
    style.configure("TLabel", background=C["bg"], foreground=C["text"])
    style.configure("TEntry", fieldbackground="white", bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"], padding=5)
    style.map("TEntry",
              bordercolor=[("focus", C["accent"])],
              lightcolor=[("focus", C["accent"])],
              darkcolor=[("focus", C["accent"])])
    style.configure("TCombobox", fieldbackground="white", bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"], padding=4,
                    arrowcolor=C["muted"])
    style.map("TCombobox",
              fieldbackground=[("readonly", "white")],
              bordercolor=[("focus", C["accent"])],
              lightcolor=[("focus", C["accent"])],
              darkcolor=[("focus", C["accent"])])
    style.configure("Treeview", background="white", fieldbackground="white",
                    foreground=C["text"], rowheight=30, font=F["body"],
                    borderwidth=0, relief="flat")
    style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                    background="#e8edf3", foreground="#334155",
                    relief="flat", padding=(8, 7))
    style.map("Treeview.Heading", background=[("active", "#dde4ec")])
    style.map("Treeview",
              background=[("selected", "#e0e7ff")],
              foreground=[("selected", C["text"])])
    # Windows 11 style scrollbars: slim, no arrow buttons, just a soft thumb.
    style.configure("Vertical.TScrollbar", background="#c7cbd3",
                    troughcolor=C["bg"], bordercolor=C["bg"],
                    arrowcolor=C["bg"], width=11)
    style.configure("Horizontal.TScrollbar", background="#c7cbd3",
                    troughcolor=C["bg"], bordercolor=C["bg"],
                    arrowcolor=C["bg"], width=11)
    style.map("Vertical.TScrollbar", background=[("active", "#a6acb8")])
    style.map("Horizontal.TScrollbar", background=[("active", "#a6acb8")])
    try:
        style.layout("Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.layout("Horizontal.TScrollbar", [
            ("Horizontal.Scrollbar.trough", {"sticky": "ew", "children": [
                ("Horizontal.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    except tk.TclError:
        pass


# ------------------------------------------------------------- ui helpers ----

def _widget_bg(widget, default=None):
    try:
        return widget["bg"]
    except (tk.TclError, KeyError):
        return default or C["bg"]


def round_rect_points(x0, y0, x1, y1, r):
    """Point list for a smoothed (rounded-corner) canvas polygon."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    return [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]


class RoundedButton(tk.Canvas):
    """A Windows 11 style pill/rounded-rect button, drawn on a Canvas so it
    can have real rounded corners (plain tk.Button can't). Supports the same
    hover/press color feedback as the buttons it replaces, and re-flows
    cleanly when packed with fill='x'."""

    def __init__(self, parent, text, command=None, radius=9, bg=None, fg="white",
                 font=None, padx=16, pady=7, hover=None, press=None, outline=False,
                 backdrop=None):
        super().__init__(parent, bg=backdrop or _widget_bg(parent),
                         highlightthickness=0, bd=0)
        self.command = command
        self.radius = radius
        self.fill = bg or C["accent"]
        self.hover_fill = hover or C["accent_dark"]
        self.press_fill = press or C["accent_press"]
        self.fg = fg
        self.font = font or F["nav"]
        self.outline = outline
        self.enabled = True

        probe = tk.Label(self, text=text, font=self.font)
        probe.update_idletasks()
        self._min_w = probe.winfo_reqwidth() + padx * 2
        self._min_h = probe.winfo_reqheight() + pady * 2
        probe.destroy()
        self.configure(width=self._min_w, height=self._min_h)

        self.shape = self.create_polygon(
            round_rect_points(1, 1, self._min_w - 1, self._min_h - 1, radius),
            smooth=True, fill=self.fill,
            outline=C["border"] if outline else self.fill, width=1)
        self.label = self.create_text(self._min_w / 2, self._min_h / 2, text=text,
                                      fill=fg, font=self.font)

        self.bind("<Configure>", self._reflow)
        self.bind("<Enter>", lambda e: self._paint(self.hover_fill))
        self.bind("<Leave>", lambda e: self._paint(self.fill))
        self.bind("<ButtonPress-1>", lambda e: self._paint(self.press_fill))
        self.bind("<ButtonRelease-1>", self._on_release)
        self.configure(cursor="hand2")

    def _reflow(self, _event=None):
        w = max(self.winfo_width(), self._min_w)
        h = max(self.winfo_height(), self._min_h)
        self.coords(self.shape, *round_rect_points(1, 1, w - 1, h - 1, self.radius))
        self.coords(self.label, w / 2, h / 2)

    def _paint(self, color):
        if not self.enabled:
            return
        self.itemconfig(self.shape, fill=color,
                        outline=C["border"] if self.outline else color)

    def _on_release(self, event):
        if not self.enabled:
            return
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self._paint(self.hover_fill if inside else self.fill)
        if inside and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._paint(self.fill if enabled else C["border"])


def flat_button(parent, text, command, bg=None, fg="white", font=None,
                padx=16, pady=7, hover=None):
    return RoundedButton(parent, text, command, bg=bg, fg=fg, font=font,
                         padx=padx, pady=pady, hover=hover)


def ghost_button(parent, text, command, padx=14, pady=6):
    return RoundedButton(parent, text, command, bg=C["card"], fg=C["accent"],
                         font=F["nav"], padx=padx, pady=pady,
                         hover=C["ghost_hover"], press=C["ghost_press"],
                         outline=True)


class RoundedCard(tk.Canvas):
    """Windows 11 style elevated card: rounded corners + a soft offset shadow.
    Pack/grid children into `.body` (a plain white Frame); the card auto-sizes
    to its content exactly like a Frame would when not stretched by fill/expand."""

    def __init__(self, parent, radius=12, pad=14, accent=None, **kwargs):
        outer_bg = kwargs.pop("bg", None) or _widget_bg(parent)
        super().__init__(parent, bg=outer_bg, highlightthickness=0, bd=0, **kwargs)
        self.radius = radius
        self.accent = accent
        self.body = tk.Frame(self, bg=C["card"])
        leftpad = pad + (9 if accent else 0)
        self.body.pack(fill="both", expand=True,
                       padx=(leftpad, pad + 3), pady=(pad, pad + 4))
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.delete("shape")
        self.create_polygon(round_rect_points(3, 4, w - 1, h - 1, self.radius),
                            smooth=True, fill=C["shadow"], outline="", tags="shape")
        self.create_polygon(round_rect_points(1, 1, w - 3, h - 3, self.radius),
                            smooth=True, fill=C["card"], outline=C["border"],
                            width=1, tags="shape")
        if self.accent:
            self.create_polygon(round_rect_points(1, 7, 6, h - 10, 3),
                                smooth=True, fill=self.accent, outline="",
                                tags="shape")
        self.tag_lower("shape")


def card_frame(parent, **kwargs):
    return RoundedCard(parent, **kwargs)


def rounded_badge(parent, text, size=40, radius=11, bg=None, fg="white", font=None):
    """A small rounded-square tile, used for the 'KG' brand mark."""
    bg = bg or C["accent"]
    c = tk.Canvas(parent, width=size, height=size, bg=_widget_bg(parent),
                 highlightthickness=0, bd=0)
    c.create_polygon(round_rect_points(1, 1, size - 1, size - 1, radius),
                     smooth=True, fill=bg, outline=bg)
    c.create_text(size / 2, size / 2, text=text, fill=fg,
                 font=font or ("Segoe UI", max(int(size * 0.34), 8), "bold"))
    return c


def _resize_tree_columns(tree, wrapper_width):
    """Scale Treeview columns to fit the wrapper, or keep minimum widths + scroll."""
    columns = getattr(tree, "_table_columns", [])
    tree_col = getattr(tree, "_table_tree_col", None)
    available = max(wrapper_width - 40, 60)

    specs = []
    if tree_col:
        specs.append(("#0", tree_col[1]))
    for key, _heading, min_w, _anchor in columns:
        specs.append((key, min_w))

    total_min = sum(w for _col, w in specs)
    if total_min <= 0:
        return

    if available >= total_min:
        scale = available / total_min
        for col_id, min_w in specs:
            tree.column(col_id, width=max(int(min_w * scale), min_w))
    else:
        for col_id, min_w in specs:
            tree.column(col_id, width=min_w)


def bind_table_autoresize(wrapper, tree):
    """Keep table columns sized to the available width as the window changes."""
    def apply():
        width = wrapper.winfo_width()
        if width > 1:
            _resize_tree_columns(tree, width)

    def on_configure(event):
        if event.widget is wrapper:
            apply()

    wrapper.bind("<Configure>", on_configure)
    wrapper.after_idle(apply)


def pack_split_view(body, table_wrap, side_panel=None, panel_padx=(12, 0)):
    """Table + side panel: panel is packed first so it is never clipped."""
    if side_panel is None:
        table_wrap.pack(side="left", fill="both", expand=True)
        return

    def do_pack(right=True, avail_h=None):
        try:
            table_wrap.pack_forget()
        except Exception:
            pass
        try:
            side_panel.pack_forget()
        except Exception:
            pass

        if right:
            side_panel.pack(side="right", fill="y", padx=panel_padx)
            # let table take remaining area
            table_wrap.pack(side="left", fill="both", expand=True)
            try:
                side_panel.configure(height="")
            except Exception:
                pass
        else:
            # when stacked, give the panel a reasonable height and allow vertical scroll
            table_wrap.pack(side="top", fill="both", expand=True)
            h = avail_h or body.winfo_height() or 400
            panel_h = max(220, int(h * 0.45))
            try:
                side_panel.configure(height=panel_h)
            except Exception:
                pass
            side_panel.pack(side="bottom", fill="x", pady=(8, 0))

    # initial layout (right side)
    do_pack(right=True)

    # responsive: move the panel below the table on narrow widths
    def on_config(event):
        width = event.width
        height = event.height
        do_pack(right=(width >= 800), avail_h=height)

    body.bind("<Configure>", on_config)


def side_panel(parent, width=270, padx=16, pady=14):
    """Fixed-width side panel with vertical scroll for tall forms."""
    panel = card_frame(parent, width=width, pad=6)
    panel.pack_propagate(False)

    canvas = tk.Canvas(panel.body, bg=C["card"], highlightthickness=0, bd=0)
    # Use the same ttk scrollbar used by tables so it looks identical
    yscroll = ttk.Scrollbar(panel.body, orient="vertical", command=canvas.yview)

    pad = tk.Frame(canvas, bg=C["card"], padx=padx, pady=pady)
    pad_id = canvas.create_window((0, 0), window=pad, anchor="nw")

    def on_frame_configure(_event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_configure(event):
        canvas.itemconfig(pad_id, width=event.width)

    pad.bind("<Configure>", on_frame_configure)
    canvas.bind("<Configure>", on_canvas_configure)
    canvas.configure(yscrollcommand=yscroll.set)

    canvas.pack(side="left", fill="both", expand=True)
    yscroll.pack(side="right", fill="y")

    # Enable mouse-wheel scrolling when cursor is over the panel (works on Windows)
    def _on_mousewheel_windows(event):
        canvas.yview_scroll(-1 * int(event.delta / 120), "units")

    def _on_mousewheel_other(event):
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")

    def _bind_wheel(_ev=None):
        try:
            canvas.bind_all("<MouseWheel>", _on_mousewheel_windows)
        except Exception:
            pass
        try:
            canvas.bind_all("<Button-4>", _on_mousewheel_other)
            canvas.bind_all("<Button-5>", _on_mousewheel_other)
        except Exception:
            pass

    def _unbind_wheel(_ev=None):
        try:
            canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass
        try:
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
        except Exception:
            pass

    canvas.bind("<Enter>", _bind_wheel)
    canvas.bind("<Leave>", _unbind_wheel)
    pad.bind("<Enter>", _bind_wheel)
    pad.bind("<Leave>", _unbind_wheel)

    # Add a fixed 'scroll to bottom' button so users can reach bottom controls
    def _scroll_to_bottom():
        try:
            canvas.yview_moveto(1.0)
        except Exception:
            pass

    btn = RoundedButton(panel, "▼", _scroll_to_bottom, radius=13, bg=C["card"],
                        fg=C["accent"], hover=C["ghost_hover"],
                        press=C["ghost_press"], outline=True, padx=7, pady=4,
                        backdrop=C["card"])
    btn.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
    # Add an 'up' button to jump to the top of the panel
    def _scroll_to_top():
        try:
            canvas.yview_moveto(0.0)
        except Exception:
            pass

    btn_up = RoundedButton(panel, "▲", _scroll_to_top, radius=13, bg=C["card"],
                           fg=C["accent"], hover=C["ghost_hover"],
                           press=C["ghost_press"], outline=True, padx=7, pady=4,
                           backdrop=C["card"])
    btn_up.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-42)
    return panel, pad


def make_table(parent, columns, tree_col=None, height=None):
    """columns: list of (key, heading, width, anchor). Returns (wrapper, tree).
    tree_col: (heading, width) to enable the hierarchy column #0."""
    wrapper = card_frame(parent, pad=8)
    inner = wrapper.body
    inner.grid_rowconfigure(0, weight=1)
    inner.grid_columnconfigure(0, weight=1)

    show = "tree headings" if tree_col else "headings"
    kwargs = {"height": height} if height else {}
    tree = ttk.Treeview(inner, columns=[c[0] for c in columns], show=show, **kwargs)
    if tree_col:
        tree.heading("#0", text=tree_col[0], anchor="w")
        tree.column("#0", width=tree_col[1], anchor="w", stretch=False)
    for key, heading, width, anchor in columns:
        tree.heading(key, text=heading, anchor=anchor)
        tree.column(key, width=width, anchor=anchor, stretch=False)

    yscroll = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(inner, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")

    tree._table_columns = list(columns)
    tree._table_tree_col = tree_col
    bind_table_autoresize(wrapper, tree)

    tree.tag_configure("stripe", background=C["stripe"])
    tree.tag_configure("low", background=C["low_row"])
    tree.tag_configure("IN", foreground=C["green_dark"])
    tree.tag_configure("OUT", foreground=C["red_dark"])
    tree.tag_configure("parent", font=("Segoe UI", 10, "bold"))
    return wrapper, tree


def stripe_rows(tree):
    for i, item in enumerate(tree.get_children()):
        tags = set(tree.item(item, "tags"))
        if i % 2 and "low" not in tags:
            tags.add("stripe")
            tree.item(item, tags=tuple(tags))


def white_label(parent, text, font=None, fg=None, **kwargs):
    return tk.Label(parent, text=text, bg=C["card"], font=font or F["body"],
                    fg=fg or C["text"], **kwargs)


def section_title(parent, text):
    return tk.Label(parent, text=text.upper(), bg=C["card"], fg=C["muted"],
                    font=("Segoe UI", 8, "bold"))


def form_field(parent, label, row, show=None, width=22):
    tk.Label(parent, text=label, bg=C["card"], fg=C["muted"],
             font=F["small"]).grid(row=row, column=0, sticky="w", pady=(6, 1))
    var = tk.StringVar()
    entry = ttk.Entry(parent, textvariable=var, width=width,
                      show=show or "", font=F["body"])
    entry.grid(row=row + 1, column=0, sticky="ew", pady=(0, 2))
    return var, entry


def password_field(parent, label, row, width=22):
    """Like form_field, but masked with a Windows 11 style SHOW/HIDE toggle
    overlaid on the right edge of the entry."""
    tk.Label(parent, text=label, bg=C["card"], fg=C["muted"],
             font=F["small"]).grid(row=row, column=0, sticky="w", pady=(6, 1))
    var = tk.StringVar()
    entry = ttk.Entry(parent, textvariable=var, show="•", width=width, font=F["body"])
    entry.grid(row=row + 1, column=0, sticky="ew", pady=(0, 2))

    state = {"visible": False}
    toggle = tk.Label(parent, text="SHOW", bg="white", fg=C["muted"],
                      font=("Segoe UI", 8, "bold"), cursor="hand2")
    toggle.place(in_=entry, relx=1.0, rely=0.5, anchor="e", x=-6)

    def set_visible(visible):
        state["visible"] = visible
        entry.config(show="" if visible else "•")
        toggle.config(text="HIDE" if visible else "SHOW",
                      fg=C["accent"] if visible else C["muted"])

    toggle.bind("<Button-1>", lambda e: set_visible(not state["visible"]))
    toggle.bind("<Enter>", lambda e: toggle.config(fg=C["accent"]))
    toggle.bind("<Leave>", lambda e: toggle.config(
        fg=C["accent"] if state["visible"] else C["muted"]))
    return var, entry


def stat_card(parent, title, accent):
    frame = card_frame(parent, radius=10, pad=12, accent=accent)
    tk.Label(frame.body, text=title.upper(), bg=C["card"], fg=C["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w")
    value = tk.Label(frame.body, text="-", bg=C["card"], fg=C["text"], font=F["stat"])
    value.pack(anchor="w")
    return frame, value


# ---------------------------------------------------------------- login ----

def _blend(base, rgb, alpha):
    """Mix an RGB color into a base RGB by alpha (0-1); Tk canvas stipple is
    a no-op on Windows, so soft/translucent glows are faked this way."""
    r, g, b = (int(base[i] * (1 - alpha) + rgb[i] * alpha) for i in range(3))
    return f"#{r:02x}{g:02x}{b:02x}"


class LoginView(tk.Frame):
    BG_RGB = (15, 23, 42)     # matches C["sidebar"] #0f172a
    GLOWS = [  # (relcx, relcy, relmax_radius, rgb) — soft accent glows
        (0.08, 0.16, 0.34, (79, 70, 229)),    # top-left indigo (accent)
        (0.95, 0.90, 0.42, (13, 148, 136)),   # bottom-right teal
        (0.52, -0.05, 0.28, (49, 46, 129)),   # top-center violet
    ]

    def __init__(self, master, db, on_success):
        super().__init__(master, bg=C["sidebar"])
        self.db = db
        self.on_success = on_success

        self.bg_canvas = tk.Canvas(self, bg=C["sidebar"], highlightthickness=0, bd=0)
        self.bg_canvas.pack(fill="both", expand=True)
        self.bg_canvas.bind("<Configure>", self._draw_background)

        outer = card_frame(self, radius=18, pad=30)
        outer.place(relx=0.5, rely=0.46, anchor="center")
        card = outer.body

        rounded_badge(card, "KG", size=56, radius=15,
                     font=("Segoe UI", 19, "bold")).pack(pady=(0, 14))
        tk.Label(card, text=SHOP_NAME, bg=C["card"], fg=C["text"],
                 font=F["brand"]).pack()
        tk.Label(card, text="Stock & Inventory ERP", bg=C["card"],
                 fg=C["muted"], font=F["small"]).pack(pady=(2, 22))

        form = tk.Frame(card, bg=C["card"])
        form.pack(fill="x")
        self.username_var, entry_user = form_field(form, "USERNAME", 0, width=28)
        self.password_var, _ = password_field(form, "PASSWORD", 2, width=28)
        form.columnconfigure(0, weight=1)

        self.error = tk.Label(card, text=" ", bg=C["card"], fg=C["red"],
                              font=F["small"])
        self.error.pack(pady=(8, 2))
        flat_button(card, "Sign In", self.login, padx=30, pady=9).pack(fill="x")

        tk.Label(self, text=f"© {datetime.now().year} {SHOP_NAME}",
                 bg=C["sidebar"], fg="#475569", font=F["tiny"]).place(
            relx=0.5, rely=0.97, anchor="s")

        entry_user.focus_set()
        self.winfo_toplevel().bind("<Return>", lambda e: self.login())

    def _draw_background(self, _event=None):
        """Windows 11 style login backdrop: soft glow blobs + a faint brand
        watermark + a sparse dot texture, all drawn on a Canvas since there
        are no image assets to rely on."""
        c = self.bg_canvas
        c.delete("bg")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 4 or h < 4:
            return

        for rel_cx, rel_cy, rel_r, rgb in self.GLOWS:
            cx, cy = rel_cx * w, rel_cy * h
            r_max = rel_r * max(w, h)
            layers = 6
            for i in range(layers, 0, -1):
                frac = i / layers
                r = r_max * frac
                alpha = 0.05 + 0.09 * (1 - frac)
                color = _blend(self.BG_RGB, rgb, alpha)
                c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color,
                              outline="", tags="bg")

        step = 42
        for gx in range(step // 2, w, step):
            for gy in range(step // 2, h, step):
                c.create_oval(gx, gy, gx + 1.6, gy + 1.6, fill="#1e293b",
                              outline="", tags="bg")

        c.create_text(w * 0.16, h * 0.5, text=SHOP_NAME.upper(), angle=90,
                      anchor="center", font=("Segoe UI", 54, "bold"),
                      fill="#16213e", tags="bg")
        c.tag_lower("bg")

    def login(self):
        user = self.db.verify_user(self.username_var.get().strip(),
                                   self.password_var.get())
        if user:
            self.winfo_toplevel().unbind("<Return>")
            self.on_success(user)
        else:
            self.error.config(text="Invalid username or password.")


# --------------------------------------------------------------- sidebar ----

class SidebarItem(tk.Canvas):
    """A Windows 11 NavigationView style nav row: a rounded highlight pill
    behind the whole row on hover/active, plus a short accent indicator pill
    on the left when active."""

    HEIGHT = 40

    def __init__(self, master, icon, text, command):
        super().__init__(master, bg=C["sidebar"], height=self.HEIGHT,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.active = False
        start = round_rect_points(10, 3, 215, self.HEIGHT - 3, 9)
        self.shape = self.create_polygon(start, smooth=True, tags="shape")
        self.dot = self.create_polygon(
            round_rect_points(10, self.HEIGHT / 2 - 8, 14, self.HEIGHT / 2 + 8, 2),
            smooth=True, tags="dot")
        self.label = self.create_text(34, self.HEIGHT / 2, anchor="w",
                                      text=f"{icon}   {text}", font=F["nav"])

        self.bind("<Configure>", self._layout)
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._paint(hover=True))
        self.bind("<Leave>", lambda e: self._paint(hover=False))
        self._layout()
        self._paint()

    def _layout(self, _event=None):
        w = self.winfo_width() or 225
        h = self.winfo_height() or self.HEIGHT
        self.coords(self.shape, *round_rect_points(10, 3, w - 10, h - 3, 9))
        self.coords(self.dot, *round_rect_points(10, h / 2 - 8, 14, h / 2 + 8, 2))
        self.coords(self.label, 34, h / 2)

    def set_active(self, active):
        self.active = active
        self._paint()

    def _paint(self, hover=False):
        if self.active:
            shape, fg, dot = C["sidebar_active"], C["sidebar_bright"], C["accent"]
        elif hover:
            shape, fg, dot = C["sidebar_hover"], C["sidebar_bright"], C["sidebar_hover"]
        else:
            shape, fg, dot = C["sidebar"], C["sidebar_text"], C["sidebar"]
        self.itemconfig(self.shape, fill=shape, outline=shape)
        self.itemconfig(self.dot, fill=dot, outline=dot)
        self.itemconfig(self.label, fill=fg)


class Sidebar(tk.Frame):
    def __init__(self, master, items, on_select, user, on_logout):
        super().__init__(master, bg=C["sidebar"], width=225)
        self.pack_propagate(False)
        self.on_select = on_select
        self.items = {}

        brand = tk.Frame(self, bg=C["sidebar"])
        brand.pack(fill="x", pady=(22, 6), padx=18)
        rounded_badge(brand, "KG", size=36, radius=10,
                     font=("Segoe UI", 12, "bold")).pack(side="left")
        text = tk.Frame(brand, bg=C["sidebar"])
        text.pack(side="left", padx=10)
        tk.Label(text, text="KHAN G", bg=C["sidebar"], fg="white",
                 font=("Segoe UI", 13, "bold"), anchor="w").pack(anchor="w")
        tk.Label(text, text="Stationary ERP", bg=C["sidebar"], fg=C["sidebar_text"],
                 font=F["tiny"], anchor="w").pack(anchor="w")

        tk.Frame(self, bg="#1e293b", height=1).pack(fill="x", pady=(14, 10), padx=14)

        for key, icon, label in items:
            item = SidebarItem(self, icon, label, lambda k=key: self.on_select(k))
            item.pack(fill="x")
            self.items[key] = item

        bottom = tk.Frame(self, bg=C["sidebar"])
        bottom.pack(side="bottom", fill="x", pady=14, padx=14)
        tk.Frame(bottom, bg="#1e293b", height=1).pack(fill="x", pady=(0, 10))
        tk.Label(bottom, text=user["full_name"] or user["username"],
                 bg=C["sidebar"], fg="white", font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(anchor="w")
        tk.Label(bottom, text=user["role"].upper(), bg=C["sidebar"],
                 fg=C["accent"] if user["role"] == "admin" else C["teal"],
                 font=("Segoe UI", 7, "bold"), anchor="w").pack(anchor="w")
        logout = tk.Label(bottom, text="↩  Logout", bg=C["sidebar"],
                          fg=C["sidebar_text"], font=F["small"], cursor="hand2",
                          anchor="w")
        logout.pack(anchor="w", pady=(8, 0))
        logout.bind("<Button-1>", lambda e: on_logout())
        logout.bind("<Enter>", lambda e: logout.config(fg="white"))
        logout.bind("<Leave>", lambda e: logout.config(fg=C["sidebar_text"]))

    def set_active(self, key):
        for k, item in self.items.items():
            item.set_active(k == key)


# ------------------------------------------------------------- dashboard ----

class DashboardPage(tk.Frame):
    def __init__(self, master, db):
        super().__init__(master, bg=C["bg"])
        self.db = db

        toolbar = tk.Frame(self, bg=C["bg"])
        toolbar.pack(fill="x", padx=18, pady=(16, 0))
        ghost_button(toolbar, "⤓  Backup Database", self.backup).pack(side="right")

        cards = tk.Frame(self, bg=C["bg"])
        cards.pack(fill="x", padx=18, pady=(18, 6))
        self.values = {}
        specs = [
            ("product_count", "Products", C["accent"]),
            ("variant_count", "Variants", C["blue"]),
            ("stock_units", "Stock Units", C["teal"]),
            ("stock_value", "Stock Value (cost)", C["amber"]),
            ("today_sales", "Today's Sales", C["green"]),
            ("today_profit", "Today's Profit", C["red"]),
        ]
        for i, (key, title, accent) in enumerate(specs):
            frame, value = stat_card(cards, title, accent)
            frame.grid(row=i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
            self.values[key] = value
        for col in range(3):
            cards.columnconfigure(col, weight=1)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=(6, 18))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        tk.Label(body, text="⚠  Low stock alerts", bg=C["bg"], fg=C["text"],
                 font=F["h2"]).grid(row=0, column=0, sticky="w", pady=(4, 6))
        low_wrap, self.low_tree = make_table(body, [
            ("product", "Product", 190, "w"), ("variant", "Variant", 110, "w"),
            ("location", "Location", 110, "w"), ("qty", "In Stock", 70, "center"),
            ("level", "Alert Level", 80, "center")])
        low_wrap.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        tk.Label(body, text="★  Top sellers (this month)", bg=C["bg"],
                 fg=C["text"], font=F["h2"]).grid(row=0, column=1, sticky="w",
                                                  pady=(4, 6))
        top_wrap, self.top_tree = make_table(body, [
            ("item", "Product / Variant", 230, "w"),
            ("sold", "Sold", 70, "center"), ("revenue", "Revenue", 110, "e")])
        top_wrap.grid(row=1, column=1, sticky="nsew")

    def refresh(self):
        stats = self.db.dashboard_stats()
        self.values["product_count"].config(text=f"{stats['product_count']:,}")
        self.values["variant_count"].config(text=f"{stats['variant_count']:,}")
        self.values["stock_units"].config(text=f"{stats['stock_units']:,}")
        self.values["stock_value"].config(text=money(stats["stock_value"]))
        self.values["today_sales"].config(text=money(stats["today"]["revenue"]))
        self.values["today_profit"].config(text=money(stats["today"]["profit"]))

        self.low_tree.delete(*self.low_tree.get_children())
        for product, variant, location, qty, level in stats["low_stock"]:
            self.low_tree.insert("", "end", tags=("low",), values=(
                product, variant, location or "-", qty, level))

        self.top_tree.delete(*self.top_tree.get_children())
        for product, variant, sold, revenue in stats["top_sellers"]:
            self.top_tree.insert("", "end", values=(
                f"{product} — {variant}", sold, money(revenue)))
        stripe_rows(self.top_tree)

    def backup(self):
        if self.db.engine != "sqlite":
            messagebox.showinfo(
                SHOP_NAME,
                "This shop is using the shared network database (MySQL).\n\n"
                "Back it up on the main PC with:\n"
                "mysqldump -u khang -p khan_g_stock > backup.sql\n\n"
                "See README.md for details.")
            return
        default = f"KHANG_backup_{datetime.now():%Y-%m-%d_%H%M}.db"
        path = filedialog.asksaveasfilename(
            defaultextension=".db", initialfile=default,
            filetypes=[("Database backup", "*.db")])
        if not path:
            return
        try:
            self.db.backup_sqlite(path)
        except Exception as exc:
            messagebox.showerror(SHOP_NAME, f"Backup failed:\n{exc}")
            return
        messagebox.showinfo(SHOP_NAME, f"Backup saved to:\n{path}\n\n"
                                       "Copy this file to a USB drive or cloud "
                                       "folder to keep it safe.")


# -------------------------------------------------------------- products ----

class ProductsPage(tk.Frame):
    def __init__(self, master, db, user, on_data_changed):
        super().__init__(master, bg=C["bg"])
        self.db = db
        self.user = user
        self.is_admin = user["role"] == "admin"
        self.on_data_changed = on_data_changed
        self.selected_product_id = None
        self.selected_variant_id = None

        toolbar = tk.Frame(self, bg=C["bg"])
        toolbar.pack(fill="x", padx=18, pady=(16, 8))
        toolbar.columnconfigure(1, weight=1)

        search_row = tk.Frame(toolbar, bg=C["bg"])
        search_row.pack(fill="x")
        tk.Label(search_row, text="Search:", bg=C["bg"],
                 fg=C["muted"], font=F["body"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(search_row, textvariable=self.search_var).pack(
            side="left", fill="x", expand=True, padx=8)
        tk.Label(search_row, text="(name, category, variant or location)",
                 bg=C["bg"], fg=C["muted"], font=F["tiny"]).pack(side="left")
        if self.is_admin:
            flat_button(toolbar, "＋  New Product", self.clear_forms).pack(
                anchor="e", pady=(6, 0))

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        if self.is_admin:
            columns = [("category", "Category", 110, "w"),
                       ("location", "Location", 100, "w"),
                       ("cost", "Cost", 90, "e"), ("price", "Sale Price", 90, "e"),
                       ("qty", "In Stock", 70, "center"),
                       ("value", "Stock Value", 105, "e")]
        else:
            columns = [("category", "Category", 130, "w"),
                       ("location", "Location", 120, "w"),
                       ("price", "Sale Price", 100, "e"),
                       ("qty", "In Stock", 80, "center")]
        table_wrap, self.tree = make_table(body, columns,
                                           tree_col=("Product / Variant", 260))
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        panel = None
        if self.is_admin:
            panel = self._build_side_panel(body)
        pack_split_view(body, table_wrap, panel)

    # -- admin editor panel ---------------------------------------------------

    def _build_side_panel(self, body):
        panel, pad = side_panel(body, width=270)

        section_title(pad, "Product").pack(anchor="w")
        pform = tk.Frame(pad, bg=C["card"])
        pform.pack(fill="x")
        pform.columnconfigure(0, weight=1)
        self.p_name, _ = form_field(pform, "Product name", 0)
        self.p_category, _ = form_field(pform, "Category", 2)

        prow = tk.Frame(pad, bg=C["card"])
        prow.pack(fill="x", pady=(8, 2))
        flat_button(prow, "Add Product", self.add_product, padx=10, pady=5,
                    font=F["small"]).pack(side="left")
        ghost_button(prow, "Save", self.save_product, padx=10, pady=4).pack(
            side="left", padx=4)
        ghost_button(prow, "Delete", self.delete_product, padx=10, pady=4).pack(
            side="left")

        tk.Frame(pad, bg=C["border"], height=1).pack(fill="x", pady=12)

        section_title(pad, "Variant  (color / size / type)").pack(anchor="w")
        vform = tk.Frame(pad, bg=C["card"])
        vform.pack(fill="x")
        vform.columnconfigure(0, weight=1)
        self.v_name, _ = form_field(vform, "Variant name (e.g. Blue, Large)", 0)
        self.v_cost, _ = form_field(vform, f"Cost ({CURRENCY})", 2)
        self.v_price, _ = form_field(vform, f"Sale price ({CURRENCY})", 4)
        self.v_qty, self.v_qty_entry = form_field(vform, "Opening quantity", 6)
        tk.Label(vform, text="Location (shelf / rack)", bg=C["card"],
                 fg=C["muted"], font=F["small"]).grid(row=8, column=0,
                                                      sticky="w", pady=(6, 1))
        self.v_location = tk.StringVar(value="(none)")
        self.v_location_combo = ttk.Combobox(vform, textvariable=self.v_location,
                                             state="readonly")
        self.v_location_combo.grid(row=9, column=0, sticky="ew", pady=(0, 2))
        self.v_low, _ = form_field(vform, "Low-stock alert level", 10)

        vrow = tk.Frame(pad, bg=C["card"])
        vrow.pack(fill="x", pady=(8, 2))
        flat_button(vrow, "Add Variant", self.add_variant, bg=C["teal"],
                    hover="#0f766e", padx=10, pady=5, font=F["small"]).pack(side="left")
        ghost_button(vrow, "Save", self.save_variant, padx=10, pady=4).pack(
            side="left", padx=4)
        ghost_button(vrow, "Delete", self.delete_variant, padx=10, pady=4).pack(
            side="left")

        tk.Label(pad, text="Select a product row to add variants to it.\n"
                           "Opening quantity applies only when adding.\n"
                           "Use Stock In / Out for later stock changes.\n"
                           "Create shelf/rack options in the Locations page.",
                 bg=C["card"], fg=C["muted"], font=F["tiny"],
                 justify="left").pack(anchor="w", pady=(12, 0))
        return panel

    # -- data <-> ui -----------------------------------------------------------

    def _reload_locations(self):
        self.location_ids = {}
        names = []
        for loc_id, name, *_rest in self.db.list_locations():
            self.location_ids[name] = loc_id
            names.append(name)
        self.v_location_combo["values"] = ["(none)"] + names
        if self.v_location.get() not in self.v_location_combo["values"]:
            self.v_location.set("(none)")

    def _selected_location_id(self):
        return self.location_ids.get(self.v_location.get())

    def refresh(self):
        if self.is_admin:
            self._reload_locations()
        open_ids = {iid for iid in self.tree.get_children()
                    if self.tree.item(iid, "open")}
        self.tree.delete(*self.tree.get_children())
        rows = self.db.products_with_variants(self.search_var.get())
        products = {}
        for row in rows:
            p_id, p_name, category = row[0], row[1], row[2]
            products.setdefault(p_id, {"name": p_name, "category": category,
                                       "variants": []})
            if row[3] is not None:
                products[p_id]["variants"].append(row[3:])

        searching = bool(self.search_var.get().strip())
        for p_id, info in products.items():
            total_qty = sum(v[4] for v in info["variants"])
            total_value = sum(v[4] * v[2] for v in info["variants"])
            n = len(info["variants"])
            if self.is_admin:
                values = (info["category"], "", "", "", total_qty,
                          f"{total_value:,.2f}")
            else:
                values = (info["category"], "", "", total_qty)
            parent = self.tree.insert(
                "", "end", iid=f"p{p_id}", text=f"{info['name']}  ({n})",
                values=values, open=(searching or f"p{p_id}" in open_ids),
                tags=("parent",))
            for v_id, v_name, cost, price, qty, location, low in info["variants"]:
                tags = ("low",) if qty <= low else ()
                if self.is_admin:
                    vals = ("", location or "-", f"{cost:,.2f}", f"{price:,.2f}",
                            qty, f"{qty * cost:,.2f}")
                else:
                    vals = ("", location or "-", f"{price:,.2f}", qty)
                self.tree.insert(parent, "end", iid=f"v{v_id}",
                                 text=f"    ● {v_name}", values=vals, tags=tags)

    def on_select(self, _event=None):
        if not self.is_admin:
            return
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        if iid.startswith("p"):
            self.selected_product_id = int(iid[1:])
            self.selected_variant_id = None
            product = self.db.get_product(self.selected_product_id)
            if product:
                self.p_name.set(product[1])
                self.p_category.set(product[2])
            self._clear_variant_form()
        else:
            self.selected_variant_id = int(iid[1:])
            variant = self.db.get_variant(self.selected_variant_id)
            if variant:
                self.selected_product_id = variant[1]
                self.p_name.set(variant[2])
                product = self.db.get_product(variant[1])
                self.p_category.set(product[2] if product else "")
                self.v_name.set(variant[3])
                self.v_cost.set(f"{variant[4]:g}")
                self.v_price.set(f"{variant[5]:g}")
                self.v_qty.set(str(variant[6]))
                self.v_qty_entry.config(state="disabled")
                self.v_location.set(variant[8] or "(none)")
                self.v_low.set(str(variant[9]))

    def _clear_variant_form(self):
        self.selected_variant_id = None
        self.v_qty_entry.config(state="normal")
        self.v_name.set("")
        self.v_cost.set("")
        self.v_price.set("")
        self.v_qty.set("0")
        self.v_location.set("(none)")
        self.v_low.set("5")

    def clear_forms(self):
        self.selected_product_id = None
        self.p_name.set("")
        self.p_category.set("")
        self._clear_variant_form()
        for item in self.tree.selection():
            self.tree.selection_remove(item)

    def _read_variant_form(self, with_qty):
        try:
            cost = float(self.v_cost.get() or 0)
            price = float(self.v_price.get() or 0)
            low = int(self.v_low.get() or 5)
            qty = int(self.v_qty.get() or 0) if with_qty else 0
        except ValueError:
            messagebox.showwarning(SHOP_NAME, "Cost, price and quantities must be numbers.")
            return None
        if cost < 0 or price < 0 or qty < 0 or low < 0:
            messagebox.showwarning(SHOP_NAME, "Values cannot be negative.")
            return None
        return cost, price, qty, low

    # -- product actions --------------------------------------------------------

    def add_product(self):
        name = self.p_name.get().strip()
        if not name:
            messagebox.showwarning(SHOP_NAME, "Product name is required.")
            return
        data = self._read_variant_form(with_qty=True)
        if not data:
            return
        cost, price, qty, low = data
        try:
            product_id = self.db.add_product(name, self.p_category.get())
        except Exception:
            messagebox.showerror(SHOP_NAME,
                                 f"Could not add product. '{name}' may already exist.")
            return
        self.db.add_variant(product_id, self.v_name.get() or "Standard",
                            cost, price, qty, self._selected_location_id(), low,
                            self.user["id"])
        self.clear_forms()
        self._after_change()

    def save_product(self):
        if not self.selected_product_id:
            messagebox.showinfo(SHOP_NAME, "Select a product in the list first.")
            return
        name = self.p_name.get().strip()
        if not name:
            messagebox.showwarning(SHOP_NAME, "Product name is required.")
            return
        self.db.update_product(self.selected_product_id, name, self.p_category.get())
        self._after_change()

    def delete_product(self):
        if not self.selected_product_id:
            messagebox.showinfo(SHOP_NAME, "Select a product in the list first.")
            return
        product = self.db.get_product(self.selected_product_id)
        if product and messagebox.askyesno(
                SHOP_NAME, f"Delete '{product[1]}', ALL its variants and their "
                           "stock history?\nThis cannot be undone."):
            self.db.delete_product(self.selected_product_id)
            self.clear_forms()
            self._after_change()

    # -- variant actions ---------------------------------------------------------

    def add_variant(self):
        if not self.selected_product_id:
            messagebox.showinfo(SHOP_NAME,
                                "Select the product to add this variant to.")
            return
        data = self._read_variant_form(with_qty=True)
        if not data:
            return
        cost, price, qty, low = data
        try:
            self.db.add_variant(self.selected_product_id,
                                self.v_name.get() or "Standard", cost, price, qty,
                                self._selected_location_id(), low, self.user["id"])
        except Exception:
            messagebox.showerror(SHOP_NAME,
                                 "Could not add variant. That variant name may "
                                 "already exist for this product.")
            return
        self._clear_variant_form()
        self._after_change()

    def save_variant(self):
        if not self.selected_variant_id:
            messagebox.showinfo(SHOP_NAME, "Select a variant row in the list first.")
            return
        data = self._read_variant_form(with_qty=False)
        if not data:
            return
        cost, price, _qty, low = data
        try:
            self.db.update_variant(self.selected_variant_id,
                                   self.v_name.get() or "Standard", cost, price,
                                   self._selected_location_id(), low)
        except Exception:
            messagebox.showerror(SHOP_NAME,
                                 "Could not save. That variant name may already "
                                 "exist for this product.")
            return
        self._after_change()

    def delete_variant(self):
        if not self.selected_variant_id:
            messagebox.showinfo(SHOP_NAME, "Select a variant row in the list first.")
            return
        variant = self.db.get_variant(self.selected_variant_id)
        if variant and messagebox.askyesno(
                SHOP_NAME, f"Delete variant '{variant[2]} — {variant[3]}' "
                           "and its stock history?"):
            self.db.delete_variant(self.selected_variant_id)
            self._clear_variant_form()
            self._after_change()

    def _after_change(self):
        self.refresh()
        self.on_data_changed()


# ------------------------------------------------------------------ stock ----

class StockPage(tk.Frame):
    def __init__(self, master, db, user):
        super().__init__(master, bg=C["bg"])
        self.db = db
        self.user = user
        self.variants = []

        panel = card_frame(self)
        panel.pack(fill="x", padx=18, pady=(16, 10))
        pad = panel.body

        section_title(pad, "Record stock movement").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        tk.Label(pad, text="Filter", bg=C["card"], fg=C["muted"],
                 font=F["small"]).grid(row=1, column=0, sticky="w")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *a: self.reload_variants())
        ttk.Entry(pad, textvariable=self.filter_var, width=18).grid(
            row=2, column=0, sticky="ew", padx=(0, 12))

        tk.Label(pad, text="Quantity", bg=C["card"], fg=C["muted"],
                 font=F["small"]).grid(row=1, column=1, sticky="w")
        self.qty_var = tk.StringVar()
        ttk.Entry(pad, textvariable=self.qty_var, width=8).grid(
            row=2, column=1, sticky="w", padx=(0, 12))

        tk.Label(pad, text="Product — Variant", bg=C["card"], fg=C["muted"],
                 font=F["small"]).grid(row=3, column=0, columnspan=4, sticky="w",
                                       pady=(8, 0))
        self.variant_var = tk.StringVar()
        self.variant_combo = ttk.Combobox(pad, textvariable=self.variant_var,
                                          state="readonly")
        self.variant_combo.grid(row=4, column=0, columnspan=4, sticky="ew",
                                pady=(0, 4))
        self.variant_combo.bind("<<ComboboxSelected>>", self.show_stock)

        tk.Label(pad, text="Note (optional)", bg=C["card"], fg=C["muted"],
                 font=F["small"]).grid(row=5, column=0, sticky="w", pady=(4, 0))
        self.note_var = tk.StringVar()
        ttk.Entry(pad, textvariable=self.note_var).grid(
            row=6, column=0, columnspan=4, sticky="ew")

        self.stock_label = tk.Label(pad, text="Stock: –   Location: –",
                                    bg="#eef2ff", fg=C["accent"],
                                    font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        self.stock_label.grid(row=7, column=0, columnspan=4, sticky="w", pady=(8, 0))

        btns = tk.Frame(pad, bg=C["card"])
        btns.grid(row=8, column=0, columnspan=4, sticky="w", pady=(12, 0))
        flat_button(btns, "▲  STOCK IN", lambda: self.record("IN"),
                    bg=C["green"], hover=C["green_dark"]).pack(side="left")
        flat_button(btns, "▼  STOCK OUT / SALE", lambda: self.record("OUT"),
                    bg=C["red"], hover=C["red_dark"]).pack(side="left", padx=8)

        pad.columnconfigure(0, weight=1)

        tk.Label(self, text="Recent transactions", bg=C["bg"], fg=C["text"],
                 font=F["h2"]).pack(anchor="w", padx=18, pady=(6, 6))
        table_wrap, self.tree = make_table(self, [
            ("date", "Date / Time", 135, "w"), ("product", "Product", 160, "w"),
            ("variant", "Variant", 90, "w"), ("location", "Location", 90, "w"),
            ("type", "Type", 55, "center"), ("qty", "Qty", 55, "center"),
            ("price", "Unit Price", 85, "e"), ("amount", "Amount", 95, "e"),
            ("user", "By", 75, "center"), ("note", "Note", 140, "w")])
        table_wrap.pack(fill="both", expand=True, padx=18, pady=(0, 16))

    def reload_variants(self):
        self.variants = self.db.list_variants(self.filter_var.get())
        self.variant_combo["values"] = [
            f"{p} — {v}   [{loc or 'no location'}]   stock: {qty}"
            for _id, p, v, qty, loc, *_ in self.variants]
        self.variant_var.set("")
        self.stock_label.config(text="Stock: –   Location: –")

    def selected_variant(self):
        idx = self.variant_combo.current()
        if idx < 0 or idx >= len(self.variants):
            return None
        return self.variants[idx]

    def show_stock(self, _event=None):
        variant = self.selected_variant()
        if variant:
            fresh = self.db.get_variant(variant[0])
            self.stock_label.config(
                text=f"Stock: {fresh[6]}   Location: {fresh[8] or '–'}")

    def record(self, ttype):
        variant = self.selected_variant()
        if not variant:
            messagebox.showinfo(SHOP_NAME, "Select a product variant first.")
            return
        try:
            qty = int(self.qty_var.get())
        except ValueError:
            messagebox.showwarning(SHOP_NAME, "Enter a whole-number quantity.")
            return
        error = self.db.record_txn(variant[0], self.user["id"], ttype, qty,
                                   self.note_var.get())
        if error:
            messagebox.showwarning(SHOP_NAME, error)
            return
        self.qty_var.set("")
        self.note_var.set("")
        self.refresh(keep_selection=True)

    def refresh(self, keep_selection=False):
        selected = self.variant_combo.current() if keep_selection else -1
        self.reload_variants()
        if keep_selection and 0 <= selected < len(self.variants):
            self.variant_combo.current(selected)
            self.show_stock()
        self.tree.delete(*self.tree.get_children())
        for (date, product, variant, location, ttype, qty, price, amount,
             user, note) in self.db.recent_txns():
            self.tree.insert("", "end", tags=(ttype,), values=(
                date, product, variant, location or "-", ttype, qty,
                f"{price:,.2f}", f"{amount:,.2f}", user, note))


# -------------------------------------------------------------- locations ----

class LocationsPage(tk.Frame):
    UNASSIGNED = "__none__"
    PREVIEW_W, PREVIEW_H = 360, 220

    def __init__(self, master, db, user):
        super().__init__(master, bg=C["bg"])
        self.db = db
        self.is_admin = user["role"] == "admin"
        self.selected = None          # location id, UNASSIGNED, or None
        self.pending_image = None     # new image bytes waiting for Add/Save
        self.photo = None             # keep a reference or tk drops the image

        toolbar = tk.Frame(self, bg=C["bg"])
        toolbar.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(toolbar, text="Find item or location:", bg=C["bg"],
                 fg=C["muted"], font=F["body"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(toolbar, textvariable=self.search_var, width=30).pack(
            side="left", padx=8)
        tk.Label(toolbar, text="Assign items to locations in the Products page.",
                 bg=C["bg"], fg=C["muted"], font=F["tiny"]).pack(side="right")

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        # -- right: details of the selected location (packed first so it keeps space)
        right = card_frame(body)
        right.pack(side="right", fill="both", expand=True)
        pad = right.body

        self.loc_title = white_label(pad, "Select a location", font=F["h1"])
        self.loc_title.pack(anchor="w")
        self.loc_note = white_label(pad, "", font=F["small"], fg=C["muted"])
        self.loc_note.pack(anchor="w", pady=(0, 8))

        self.img_label = tk.Label(pad, text="", bg="#f1f5f9", fg=C["muted"],
                                  font=F["small"], height=2)
        self.img_label.pack(fill="x", pady=(0, 10))

        columns = [("product", "Product", 180, "w"),
                   ("variant", "Variant", 110, "w"),
                   ("qty", "In Stock", 70, "center"),
                   ("price", "Sale Price", 90, "e")]
        if self.is_admin:
            columns.append(("value", "Stock Value", 100, "e"))
        items_wrap, self.items_tree = make_table(pad, columns)
        items_wrap.pack(fill="both", expand=True)

        # -- left: list of locations (+ admin editor) --------------------------
        left = tk.Frame(body, bg=C["bg"], width=300)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        list_wrap, self.loc_tree = make_table(left, [
            ("name", "Location", 120, "w"), ("items", "Items", 50, "center"),
            ("units", "Units", 55, "center"), ("photo", "Photo", 45, "center")])
        self.loc_tree.bind("<<TreeviewSelect>>", self.on_select)

        if self.is_admin:
            self._build_editor(left)
        list_wrap.pack(side="top", fill="both", expand=True)

    # -- admin editor ------------------------------------------------------------

    def _build_editor(self, left):
        panel, pad = side_panel(left, width=280, padx=14, pady=12)
        panel.configure(height=280)
        # packed before the location list (side="bottom") so it always keeps
        # its space and its buttons are never clipped off the bottom of the window
        panel.pack(side="bottom", fill="x", pady=(10, 0))

        section_title(pad, "Location details").pack(anchor="w")
        form = tk.Frame(pad, bg=C["card"])
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)
        self.e_name, _ = form_field(form, "Name (e.g. Shelf A1, Rack 3)", 0)
        self.e_note, _ = form_field(form, "Note (optional)", 2)

        img_row = tk.Frame(pad, bg=C["card"])
        img_row.pack(fill="x", pady=(8, 0))
        ghost_button(img_row, "📷  Choose Photo…", self.choose_image,
                     padx=8, pady=4).pack(side="left")
        self.img_status = tk.Label(img_row, text="", bg=C["card"], fg=C["muted"],
                                   font=F["tiny"], anchor="w")
        self.img_status.pack(side="left", padx=8)

        btns = tk.Frame(pad, bg=C["card"])
        btns.pack(fill="x", pady=(10, 0))
        flat_button(btns, "＋ Add", self.add_location, padx=10, pady=5,
                    font=F["small"]).pack(side="left")
        ghost_button(btns, "Save", self.save_location, padx=10, pady=4).pack(
            side="left", padx=4)
        ghost_button(btns, "Delete", self.delete_location, padx=10, pady=4).pack(
            side="left")
        ghost_button(btns, "Clear", self.clear_editor, padx=10, pady=4).pack(
            side="left", padx=4)

    def choose_image(self):
        if not HAS_PIL:
            messagebox.showwarning(
                SHOP_NAME, "Image support needs the Pillow library.\n"
                           "Open a command prompt and run:  pip install pillow")
            return
        path = filedialog.askopenfilename(filetypes=[
            ("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"),
            ("All files", "*.*")])
        if not path:
            return
        try:
            self.pending_image = process_image_file(path)
        except Exception:
            messagebox.showerror(SHOP_NAME, "Could not read that image file.")
            return
        self.img_status.config(
            text="Photo selected — press Add or Save to store it.")

    def clear_editor(self):
        self.selected = None
        self.pending_image = None
        self.e_name.set("")
        self.e_note.set("")
        self.img_status.config(text="")
        for item in self.loc_tree.selection():
            self.loc_tree.selection_remove(item)

    def add_location(self):
        name = self.e_name.get().strip()
        if not name:
            messagebox.showwarning(SHOP_NAME, "Location name is required.")
            return
        try:
            self.db.add_location(name, self.e_note.get(), self.pending_image)
        except Exception:
            messagebox.showerror(SHOP_NAME,
                                 f"Could not add location. '{name}' may already exist.")
            return
        self.clear_editor()
        self.refresh()

    def save_location(self):
        if not isinstance(self.selected, int):
            messagebox.showinfo(SHOP_NAME, "Select a location in the list first.")
            return
        name = self.e_name.get().strip()
        if not name:
            messagebox.showwarning(SHOP_NAME, "Location name is required.")
            return
        try:
            self.db.update_location(self.selected, name, self.e_note.get(),
                                    image=self.pending_image,
                                    replace_image=self.pending_image is not None)
        except Exception:
            messagebox.showerror(SHOP_NAME,
                                 f"Could not save. '{name}' may already exist.")
            return
        self.pending_image = None
        self.img_status.config(text="")
        self.refresh()

    def delete_location(self):
        if not isinstance(self.selected, int):
            messagebox.showinfo(SHOP_NAME, "Select a location in the list first.")
            return
        location = self.db.get_location(self.selected)
        if location and messagebox.askyesno(
                SHOP_NAME, f"Delete location '{location[1]}'?\nItems there are "
                           "kept and become '(no location)'."):
            self.db.delete_location(self.selected)
            self.clear_editor()
            self.refresh()

    # -- list / details ------------------------------------------------------------

    def refresh(self):
        search = self.search_var.get().strip()
        match_ids = self.db.search_location_ids(search) if search else None

        self.loc_tree.delete(*self.loc_tree.get_children())
        for loc_id, name, note, items, units, has_image in self.db.list_locations():
            if search and search.lower() not in name.lower() \
                    and loc_id not in (match_ids or ()):
                continue
            self.loc_tree.insert("", "end", iid=str(loc_id), values=(
                name, items, units, "🖼" if has_image else "—"))
        count, units = self.db.unassigned_summary()
        if count and (not search or None in (match_ids or ())):
            self.loc_tree.insert("", "end", iid=self.UNASSIGNED, values=(
                "(no location)", count, units, "—"))
        stripe_rows(self.loc_tree)

        if self.selected is not None:
            iid = (self.UNASSIGNED if self.selected == self.UNASSIGNED
                   else str(self.selected))
            if self.loc_tree.exists(iid):
                self.loc_tree.selection_set(iid)
            else:
                self.selected = None
        self._show_details()

    def on_select(self, _event=None):
        selection = self.loc_tree.selection()
        if not selection:
            return
        iid = selection[0]
        self.selected = self.UNASSIGNED if iid == self.UNASSIGNED else int(iid)
        self.pending_image = None
        if self.is_admin:
            self.img_status.config(text="")
            if isinstance(self.selected, int):
                location = self.db.get_location(self.selected)
                if location:
                    self.e_name.set(location[1])
                    self.e_note.set(location[2])
            else:
                self.e_name.set("")
                self.e_note.set("")
        self._show_details()

    def _show_details(self):
        self.items_tree.delete(*self.items_tree.get_children())
        self.photo = None

        if self.selected is None:
            self.loc_title.config(text="Select a location")
            self.loc_note.config(text="Click a location on the left to see its "
                                      "photo and everything stored there.")
            self.img_label.config(image="", text="", height=2)
            return

        if self.selected == self.UNASSIGNED:
            name, note, image = "(no location)", \
                "Items that have not been assigned a shelf/rack yet.", None
        else:
            location = self.db.get_location(self.selected)
            if not location:
                return
            name, note, image = location[1], location[2], location[3]

        self.loc_title.config(text=f"⚑  {name}")
        self.loc_note.config(text=note or "")

        if image and HAS_PIL:
            try:
                self.photo = photo_from_bytes(image, self.PREVIEW_W, self.PREVIEW_H)
                self.img_label.config(image=self.photo, text="", height=0)
            except Exception:
                self.img_label.config(image="", text="(photo could not be shown)",
                                      height=2)
        elif image and not HAS_PIL:
            self.img_label.config(image="", height=2,
                                  text="(photo stored — install Pillow to view: "
                                       "pip install pillow)")
        else:
            self.img_label.config(image="", text="No photo for this location yet."
                                  if self.is_admin else "No photo available.",
                                  height=2)

        loc_id = None if self.selected == self.UNASSIGNED else self.selected
        for product, variant, qty, price, cost, low in self.db.location_items(loc_id):
            tags = ("low",) if qty <= low else ()
            values = [product, variant, qty, f"{price:,.2f}"]
            if self.is_admin:
                values.append(f"{qty * cost:,.2f}")
            self.items_tree.insert("", "end", values=values, tags=tags)
        stripe_rows(self.items_tree)


# ---------------------------------------------------------------- reports ----

class ReportsPage(tk.Frame):
    GROUPINGS = ["By Product", "By Variant", "By Day", "All Transactions"]

    def __init__(self, master, db):
        super().__init__(master, bg=C["bg"])
        self.db = db
        self.current_rows = []
        self.current_headers = []

        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=18, pady=(16, 8))

        row1 = tk.Frame(bar, bg=C["bg"])
        row1.pack(fill="x")
        tk.Label(row1, text="Period:", bg=C["bg"], fg=C["muted"]).pack(side="left")
        self.period_var = tk.StringVar(value="Today")
        period_combo = ttk.Combobox(row1, textvariable=self.period_var,
                                    values=PERIODS, state="readonly", width=12)
        period_combo.pack(side="left", padx=6)
        period_combo.bind("<<ComboboxSelected>>", lambda e: self.toggle_custom())

        self.custom_frame = tk.Frame(row1, bg=C["bg"])
        tk.Label(self.custom_frame, text="From:", bg=C["bg"],
                 fg=C["muted"]).pack(side="left")
        self.from_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(self.custom_frame, textvariable=self.from_var, width=11).pack(
            side="left", padx=4)
        tk.Label(self.custom_frame, text="To:", bg=C["bg"],
                 fg=C["muted"]).pack(side="left")
        self.to_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(self.custom_frame, textvariable=self.to_var, width=11).pack(
            side="left", padx=4)

        row2 = tk.Frame(bar, bg=C["bg"])
        row2.pack(fill="x", pady=(8, 0))
        tk.Label(row2, text="View:", bg=C["bg"], fg=C["muted"]).pack(side="left")
        self.group_var = tk.StringVar(value="By Product")
        ttk.Combobox(row2, textvariable=self.group_var, values=self.GROUPINGS,
                     state="readonly", width=16).pack(side="left", padx=6)

        flat_button(row2, "Generate", self.generate, padx=14, pady=5).pack(
            side="left", padx=10)
        ghost_button(row2, "⤓  Export CSV", self.export_csv).pack(side="left")

        cards = tk.Frame(self, bg=C["bg"])
        cards.pack(fill="x", padx=12, pady=(4, 8))
        self.summary_values = {}
        for i, (key, title, accent) in enumerate([
                ("stock_in", "Stock In (units)", C["blue"]),
                ("items_sold", "Items Sold", C["teal"]),
                ("revenue", "Sales Revenue", C["accent"]),
                ("cost", "Cost of Goods", C["amber"]),
                ("profit", "Profit", C["green"])]):
            frame, value = stat_card(cards, title, accent)
            frame.grid(row=0, column=i, sticky="nsew", padx=6)
            cards.columnconfigure(i, weight=1)
            self.summary_values[key] = value

        self.table_area = tk.Frame(self, bg=C["bg"])
        self.table_area.pack(fill="both", expand=True, padx=18, pady=(4, 4))
        self.table_wrap = None
        self.tree = None

        self.range_label = tk.Label(self, text="", bg=C["bg"], fg=C["muted"],
                                    font=F["small"])
        self.range_label.pack(anchor="w", padx=18, pady=(0, 12))

    def toggle_custom(self):
        if self.period_var.get() == "Custom":
            self.custom_frame.pack(side="left", padx=6)
        else:
            self.custom_frame.pack_forget()

    def get_range(self):
        if self.period_var.get() == "Custom":
            try:
                start = datetime.strptime(self.from_var.get().strip(), "%Y-%m-%d")
                end = datetime.strptime(self.to_var.get().strip(),
                                        "%Y-%m-%d") + timedelta(days=1)
            except ValueError:
                messagebox.showwarning(SHOP_NAME, "Enter dates as YYYY-MM-DD.")
                return None
            return start, end
        return self.db.period_range(self.period_var.get())

    def refresh(self):
        self.generate()

    def generate(self):
        rng = self.get_range()
        if not rng:
            return
        start, end = rng
        start_s, end_s = start.strftime(DATE_FMT), end.strftime(DATE_FMT)

        summary = self.db.report_summary(start_s, end_s)
        self.summary_values["stock_in"].config(text=f"{summary['stock_in']:,}")
        self.summary_values["items_sold"].config(text=f"{summary['items_sold']:,}")
        self.summary_values["revenue"].config(text=money(summary["revenue"]))
        self.summary_values["cost"].config(text=money(summary["cost"]))
        self.summary_values["profit"].config(text=money(summary["profit"]))

        grouping = self.group_var.get()
        if grouping == "By Product":
            headers = [("name", "Product", 230, "w"), ("in", "Stock In", 80, "center"),
                       ("sold", "Sold", 80, "center"), ("revenue", "Revenue", 110, "e"),
                       ("profit", "Profit", 110, "e"),
                       ("stock", "Current Stock", 100, "center")]
            rows = [(r[0], r[1], r[2], f"{r[3]:,.2f}", f"{r[4]:,.2f}", r[5])
                    for r in self.db.report_by_product(start_s, end_s)]
        elif grouping == "By Variant":
            headers = [("name", "Product", 180, "w"), ("variant", "Variant", 100, "w"),
                       ("location", "Location", 90, "w"),
                       ("in", "Stock In", 70, "center"), ("sold", "Sold", 70, "center"),
                       ("revenue", "Revenue", 100, "e"), ("profit", "Profit", 100, "e"),
                       ("stock", "Current Stock", 95, "center")]
            rows = [(r[0], r[1], r[2] or "-", r[3], r[4], f"{r[5]:,.2f}",
                     f"{r[6]:,.2f}", r[7])
                    for r in self.db.report_by_variant(start_s, end_s)]
        elif grouping == "By Day":
            headers = [("day", "Date", 110, "w"), ("in", "Stock In", 85, "center"),
                       ("sold", "Sold", 85, "center"), ("revenue", "Revenue", 115, "e"),
                       ("profit", "Profit", 115, "e")]
            rows = [(r[0], r[1], r[2], f"{r[3]:,.2f}", f"{r[4]:,.2f}")
                    for r in self.db.report_by_day(start_s, end_s)]
        else:
            headers = [("date", "Date / Time", 130, "w"), ("product", "Product", 150, "w"),
                       ("variant", "Variant", 85, "w"), ("type", "Type", 50, "center"),
                       ("qty", "Qty", 50, "center"), ("cost", "Unit Cost", 75, "e"),
                       ("price", "Unit Price", 75, "e"), ("amount", "Amount", 90, "e"),
                       ("profit", "Profit", 85, "e"), ("user", "By", 65, "center"),
                       ("note", "Note", 120, "w")]
            rows = [(r[0], r[1], r[2], r[3], r[4], f"{r[5]:,.2f}", f"{r[6]:,.2f}",
                     f"{r[7]:,.2f}", f"{r[8]:,.2f}", r[9], r[10])
                    for r in self.db.report_transactions(start_s, end_s)]

        if self.table_wrap:
            self.table_wrap.destroy()
        self.table_wrap, self.tree = make_table(self.table_area, headers)
        self.table_wrap.pack(fill="both", expand=True)
        for row in rows:
            tags = ()
            if grouping == "All Transactions":
                tags = (row[3],)
            self.tree.insert("", "end", values=row, tags=tags)
        stripe_rows(self.tree)

        self.current_headers = [h[1] for h in headers]
        self.current_rows = rows
        self.range_label.config(
            text=f"Report period: {start:%d %b %Y} to {end - timedelta(days=1):%d %b %Y}"
                 f"    |    {len(rows)} rows    |    Generated {datetime.now():%d %b %Y %H:%M}")

    def export_csv(self):
        if not self.current_rows:
            messagebox.showinfo(SHOP_NAME, "Generate a report first (it has no rows).")
            return
        default = (f"KHANG_report_{self.period_var.get().replace(' ', '_')}"
                   f"_{datetime.now():%Y%m%d}.csv")
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=default,
            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([SHOP_NAME + " - Stock Report"])
            writer.writerow([self.range_label.cget("text")])
            writer.writerow([])
            writer.writerow(self.current_headers)
            writer.writerows(self.current_rows)
        messagebox.showinfo(SHOP_NAME, f"Report saved to:\n{path}")


# ------------------------------------------------------------------ users ----

class UsersPage(tk.Frame):
    def __init__(self, master, db, current_user):
        super().__init__(master, bg=C["bg"])
        self.db = db
        self.current_user = current_user

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=18, pady=16)

        table_wrap, self.tree = make_table(body, [
            ("id", "ID", 50, "center"), ("username", "Username", 130, "w"),
            ("full_name", "Full Name", 190, "w"), ("role", "Role", 80, "center"),
            ("created", "Created", 150, "w")])

        panel, pad = side_panel(body, width=260)

        section_title(pad, "Add user / actions").pack(anchor="w")
        form = tk.Frame(pad, bg=C["card"])
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)
        self.u_username, _ = form_field(form, "Username", 0)
        self.u_fullname, _ = form_field(form, "Full name", 2)
        self.u_password, _ = form_field(form, "Password", 4, show="*")

        tk.Label(form, text="Role", bg=C["card"], fg=C["muted"],
                 font=F["small"]).grid(row=6, column=0, sticky="w", pady=(6, 1))
        self.role_var = tk.StringVar(value="staff")
        ttk.Combobox(form, textvariable=self.role_var, values=["staff", "admin"],
                     state="readonly").grid(row=7, column=0, sticky="ew")

        flat_button(pad, "＋  Add User", self.add, padx=10, pady=6).pack(
            fill="x", pady=(14, 4))
        ghost_button(pad, "Reset Password of Selected",
                     self.reset_password).pack(fill="x", pady=4)
        ghost_button(pad, "Delete Selected User", self.delete).pack(fill="x", pady=4)

        tk.Label(pad, text="Staff can: stock in/out, view products\n"
                           "and locations.\nStaff cannot: see cost or profit,\n"
                           "edit products, view reports,\nmanage users.",
                 bg=C["card"], fg=C["muted"], font=F["tiny"],
                 justify="left").pack(anchor="w", pady=(14, 0))

        pack_split_view(body, table_wrap, panel)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for row in self.db.list_users():
            self.tree.insert("", "end", values=row)
        stripe_rows(self.tree)

    def selected_user(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(SHOP_NAME, "Select a user from the list first.")
            return None
        values = self.tree.item(selection[0])["values"]
        return {"id": values[0], "username": values[1], "role": values[3]}

    def add(self):
        username = self.u_username.get().strip()
        password = self.u_password.get()
        if not username or not password:
            messagebox.showwarning(SHOP_NAME, "Username and password are required.")
            return
        if len(password) < 4:
            messagebox.showwarning(SHOP_NAME, "Password must be at least 4 characters.")
            return
        try:
            self.db.add_user(username, password, self.u_fullname.get(),
                             self.role_var.get())
        except Exception:
            messagebox.showerror(SHOP_NAME,
                                 f"Could not add user. Username '{username}' may already exist.")
            return
        self.u_username.set("")
        self.u_fullname.set("")
        self.u_password.set("")
        self.refresh()

    def reset_password(self):
        user = self.selected_user()
        if not user:
            return
        password = self.u_password.get()
        if len(password) < 4:
            messagebox.showwarning(
                SHOP_NAME,
                "Type the new password (4+ characters) in the Password box first.")
            return
        self.db.reset_password(user["id"], password)
        self.u_password.set("")
        messagebox.showinfo(SHOP_NAME, f"Password updated for '{user['username']}'.")

    def delete(self):
        user = self.selected_user()
        if not user:
            return
        if user["id"] == self.current_user["id"]:
            messagebox.showwarning(SHOP_NAME,
                                   "You cannot delete the account you are logged in with.")
            return
        if user["role"] == "admin" and self.db.count_admins() <= 1:
            messagebox.showwarning(SHOP_NAME, "Cannot delete the last admin account.")
            return
        if messagebox.askyesno(SHOP_NAME, f"Delete user '{user['username']}'?"):
            self.db.delete_user(user["id"])
            self.refresh()


# -------------------------------------------------------------------- app ----

PAGE_DEFS = {
    "dashboard": ("⌂", "Dashboard"),
    "products":  ("▦", "Products"),
    "stock":     ("⇅", "Stock In / Out"),
    "locations": ("⚑", "Locations"),
    "reports":   ("▤", "Reports"),
    "users":     ("☺", "Users"),
}

PAGE_TITLES = {
    "dashboard": "Dashboard",
    "products":  "Products & Variants",
    "stock":     "Stock In / Out",
    "locations": "Locations — where everything is",
    "reports":   "Reports",
    "users":     "User Management",
}


class App:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.user = None
        self.pages = {}
        self.current_page = None

        root.title(f"{SHOP_NAME} — Stock & Inventory ERP")
        root.geometry("1280x760")
        root.minsize(1024, 640)
        root.configure(bg=C["bg"])
        setup_styles(root)
        self.show_login()

    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def show_login(self):
        self.clear()
        LoginView(self.root, self.db, self.on_login).pack(fill="both", expand=True)

    def on_login(self, user):
        self.user = user
        self.clear()
        self.build_shell()

    def build_shell(self):
        is_admin = self.user["role"] == "admin"
        keys = (["dashboard", "products", "stock", "locations", "reports", "users"]
                if is_admin else ["products", "stock", "locations"])

        items = [(key, *PAGE_DEFS[key]) for key in keys]
        self.sidebar = Sidebar(self.root, items, self.show_page, self.user,
                               self.show_login)
        self.sidebar.pack(side="left", fill="y")

        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)

        topbar = tk.Frame(main, bg=C["card"], height=52,
                          highlightthickness=1, highlightbackground=C["border"])
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        self.title_label = tk.Label(topbar, text="", bg=C["card"], fg=C["text"],
                                    font=F["h1"], padx=20)
        self.title_label.pack(side="left")
        tk.Label(topbar, text=datetime.now().strftime("%A, %d %B %Y"),
                 bg=C["card"], fg=C["muted"], font=F["small"],
                 padx=20).pack(side="right")

        content = tk.Frame(main, bg=C["bg"])
        content.pack(fill="both", expand=True)

        self.pages = {}
        for key in keys:
            if key == "dashboard":
                page = DashboardPage(content, self.db)
            elif key == "products":
                page = ProductsPage(content, self.db, self.user,
                                    on_data_changed=self.refresh_others)
            elif key == "stock":
                page = StockPage(content, self.db, self.user)
            elif key == "locations":
                page = LocationsPage(content, self.db, self.user)
            elif key == "reports":
                page = ReportsPage(content, self.db)
            else:
                page = UsersPage(content, self.db, self.user)
            self.pages[key] = page

        self.show_page(keys[0])

    def show_page(self, key):
        if self.current_page:
            self.pages[self.current_page].pack_forget()
        self.current_page = key
        page = self.pages[key]
        page.pack(fill="both", expand=True)
        if hasattr(page, "refresh"):
            page.refresh()
        self.sidebar.set_active(key)
        self.title_label.config(text=PAGE_TITLES[key])

    def refresh_others(self):
        for key, page in self.pages.items():
            if key != self.current_page and hasattr(page, "refresh"):
                page.refresh()


def main():
    config = load_config()
    try:
        db = Database(config)
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            SHOP_NAME,
            "Could not connect to the database.\n\n"
            f"Engine: {config.get('engine')}\nError: {exc}\n\n"
            "Check config.json (and that the MySQL server on the main PC "
            "is running, if using the network setup).")
        return
    root = tk.Tk()
    try:
        root.state("zoomed")
    except tk.TclError:
        pass
    App(root, db)
    root.mainloop()
    db.close()


if __name__ == "__main__":
    main()

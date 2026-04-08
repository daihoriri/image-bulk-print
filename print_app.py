import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

try:
    from PIL import Image, ImageTk, ImageWin
    import win32print
    import win32ui
    import win32con
    WINDOWS = True
except ImportError:
    WINDOWS = False

SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif')
MARGIN_MM = 5
PREVIEW_SIZE = (400, 566)

DMORIENT_PORTRAIT  = 1
DMORIENT_LANDSCAPE = 2

THUMB_W = 120
THUMB_H = 100


# ─────────────────────────── スクロール可能フレーム共通基底 ──────────────────────
class _ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(self, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=sb.set)

        self._inner = ttk.Frame(self._canvas)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas_cfg)
        self._canvas.bind("<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", self._on_wheel))
        self._canvas.bind("<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

    def _on_canvas_cfg(self, event):
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _on_wheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ─────────────────────────────── チェックボックスリスト ──────────────────────────
class CheckboxList(_ScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self._items: list[tuple[str, tk.BooleanVar]] = []

    def set_items(self, items: list[tuple[str, tk.BooleanVar]]):
        """shared items リストをセットして描画"""
        self._items = items
        self._rebuild()

    def _rebuild(self):
        for w in self._inner.winfo_children():
            w.destroy()
        for path, var in self._items:
            fname = os.path.basename(path)
            cb = ttk.Checkbutton(self._inner, text=f"  {fname}", variable=var)
            cb.pack(anchor="w", padx=6, pady=2, fill="x")

    # ── 共通インターフェース ──────────────────────────────────────────────────
    def get_selected(self)  -> list[str]: return [p for p, v in self._items if v.get()]
    def select_all(self):
        for _, v in self._items: v.set(True)
    def deselect_all(self):
        for _, v in self._items: v.set(False)
    def count_total(self)    -> int: return len(self._items)
    def count_selected(self) -> int: return sum(1 for _, v in self._items if v.get())


# ─────────────────────────────────── サムネイルビュー ────────────────────────────
class ThumbnailView(_ScrollableFrame):
    COL_MIN_W = THUMB_W + 28   # 1セルの最小幅

    def __init__(self, parent):
        super().__init__(parent)
        self._items: list[tuple[str, tk.BooleanVar]] = []
        self._tk_images: list = []
        self._cell_updaters: list = []   # (var, update_fn) ペア

    def _on_canvas_cfg(self, event):
        self._canvas.itemconfig(self._win_id, width=event.width)
        self._rebuild()

    def set_items(self, items: list[tuple[str, tk.BooleanVar]]):
        self._items = items
        self._rebuild()

    def _rebuild(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._tk_images.clear()
        self._cell_updaters.clear()

        if not self._items:
            return

        cw = self._canvas.winfo_width() or 600
        cols = max(1, cw // self.COL_MIN_W)
        for c in range(cols):
            self._inner.columnconfigure(c, weight=1)

        for i, (path, var) in enumerate(self._items):
            r, c = divmod(i, cols)
            cell, updater = self._make_cell(path, var)
            cell.grid(row=r, column=c, padx=6, pady=6, sticky="n")
            self._cell_updaters.append((var, updater))

    def _make_cell(self, path: str, var: tk.BooleanVar):
        outer = tk.Frame(self._inner)

        # サムネイル読み込み
        try:
            img = Image.open(path)
            img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
        except Exception:
            tk_img = None
        self._tk_images.append(tk_img)

        # 画像枠（選択状態をボーダーで表現）
        border_frame = tk.Frame(
            outer,
            width=THUMB_W + 6,
            height=THUMB_H + 6,
            highlightthickness=3,
            highlightbackground="#cccccc",
        )
        border_frame.pack_propagate(False)
        border_frame.pack()

        img_label = tk.Label(border_frame, image=tk_img, bg="#f5f5f5", cursor="hand2")
        img_label.pack(expand=True, fill="both")

        # ファイル名（短縮）
        fname = os.path.basename(path)
        short = fname if len(fname) <= 16 else fname[:14] + "…"

        # チェックボックス
        cb = ttk.Checkbutton(outer, text=short, variable=var)
        cb.pack(pady=(2, 0))

        # ボーダー色を選択状態と同期
        def update_border(v=var, bf=border_frame, il=img_label, cb_=cb):
            if v.get():
                bf.configure(highlightbackground="#1a7fd4")
                il.configure(bg="#daeeff")
            else:
                bf.configure(highlightbackground="#cccccc")
                il.configure(bg="#f5f5f5")

        update_border()

        def toggle(event=None, v=var, upd=update_border):
            v.set(not v.get())
            upd()

        img_label.bind("<Button-1>", toggle)

        # チェックボックス操作後もボーダーを更新
        cb.configure(command=update_border)

        return outer, update_border

    def _refresh_all_borders(self):
        for var, updater in self._cell_updaters:
            updater()

    # ── 共通インターフェース ──────────────────────────────────────────────────
    def get_selected(self)  -> list[str]: return [p for p, v in self._items if v.get()]
    def select_all(self):
        for _, v in self._items: v.set(True)
        self._refresh_all_borders()
    def deselect_all(self):
        for _, v in self._items: v.set(False)
        self._refresh_all_borders()
    def count_total(self)    -> int: return len(self._items)
    def count_selected(self) -> int: return sum(1 for _, v in self._items if v.get())


# ───────────────────────────────────── プレビュー ─────────────────────────────
class PreviewWindow:
    def __init__(self, parent, image_files: list[str]):
        self.image_files = image_files
        self.index = 0
        self.win = tk.Toplevel(parent)
        self.win.title("印刷プレビュー")
        self.win.resizable(False, False)
        self.win.grab_set()
        self._build_ui()
        self._show(0)

    def _build_ui(self):
        cf = ttk.Frame(self.win, relief="sunken", borderwidth=1)
        cf.grid(row=0, column=0, padx=15, pady=(15, 6))
        self.canvas = tk.Canvas(cf, width=PREVIEW_SIZE[0], height=PREVIEW_SIZE[1], bg="white")
        self.canvas.pack()

        self.page_label = ttk.Label(self.win, text="")
        self.page_label.grid(row=1, column=0, pady=(0, 6))

        nav = ttk.Frame(self.win)
        nav.grid(row=2, column=0, pady=(0, 12))
        ttk.Button(nav, text="◀ 前の画像", command=self._prev,         width=14).pack(side="left", padx=6)
        ttk.Button(nav, text="次の画像 ▶", command=self._next,         width=14).pack(side="left", padx=6)
        ttk.Button(nav, text="閉じる",     command=self.win.destroy,   width=10).pack(side="left", padx=6)

    def _show(self, idx: int):
        self.index = idx
        path = self.image_files[idx]
        img = Image.open(path).convert("RGB")
        is_landscape = img.width > img.height

        cw, ch = (PREVIEW_SIZE[1], PREVIEW_SIZE[0]) if is_landscape else PREVIEW_SIZE
        self.canvas.config(width=cw, height=ch)

        margin = 9
        avail_w, avail_h = cw - 2 * margin, ch - 2 * margin
        ratio = img.width / img.height
        area_ratio = avail_w / avail_h
        if ratio > area_ratio:
            w, h = avail_w, int(avail_w / ratio)
        else:
            h, w = avail_h, int(avail_h * ratio)

        img = img.resize((w, h), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(img)
        x0 = margin + (avail_w - w) // 2
        y0 = margin + (avail_h - h) // 2

        self.canvas.delete("all")
        self.canvas.create_image(x0, y0, anchor="nw", image=self._tk_img)

        orient_str = "横向き (A4ランドスケープ)" if is_landscape else "縦向き (A4ポートレート)"
        fname = os.path.basename(path)
        self.page_label.config(
            text=f"{idx + 1} / {len(self.image_files)}  —  {fname}  [{orient_str}]"
        )
        self.win.title(f"プレビュー [{idx + 1}/{len(self.image_files)}]")

    def _prev(self):
        if self.index > 0: self._show(self.index - 1)

    def _next(self):
        if self.index < len(self.image_files) - 1: self._show(self.index + 1)


# ─────────────────────────────────── メインアプリ ────────────────────────────
class ImageBulkPrinter:
    def __init__(self, root):
        self.root = root
        self.root.title("画像一括印刷")
        self.root.geometry("740x600")
        self.root.resizable(True, True)

        self.image_folder    = tk.StringVar()
        self._shared_items: list[tuple[str, tk.BooleanVar]] = []  # 共有データ
        self.selected_printer = tk.StringVar()
        self.devmode = None
        self._view_mode = "list"   # "list" or "thumb"

        if WINDOWS:
            try: self.selected_printer.set(win32print.GetDefaultPrinter())
            except Exception: pass

        self._setup_ui()
        self._refresh_printers()

    # ─────────────────────────────────────────────────────────────── UI ──
    def _setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # フォルダ選択
        ff = ttk.LabelFrame(self.root, text="印刷フォルダ", padding=10)
        ff.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ff.columnconfigure(1, weight=1)
        ttk.Button(ff, text="フォルダを選択", command=self._select_folder).grid(row=0, column=0, padx=(0, 10))
        ttk.Entry(ff, textvariable=self.image_folder, state="readonly").grid(row=0, column=1, sticky="ew")

        # プリンター設定
        pf = ttk.LabelFrame(self.root, text="プリンター設定", padding=10)
        pf.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        pf.columnconfigure(1, weight=1)
        ttk.Label(pf, text="プリンター:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.printer_combo = ttk.Combobox(
            pf, textvariable=self.selected_printer, state="readonly", width=42)
        self.printer_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        bf2 = ttk.Frame(pf)
        bf2.grid(row=0, column=2)
        ttk.Button(bf2, text="更新",          command=self._refresh_printers, width=6).pack(side="left", padx=2)
        ttk.Button(bf2, text="印刷プロパティ", command=self._show_properties).pack(side="left", padx=2)

        # 画像リスト
        lf = ttk.LabelFrame(self.root, text="印刷対象の画像", padding=10)
        lf.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(1, weight=1)

        # ── ツールバー（全選択 / 全解除 / 表示切替） ──────────────────────────
        toolbar = ttk.Frame(lf)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        ttk.Button(toolbar, text="全選択", command=self._select_all,   width=8).pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="全解除", command=self._deselect_all, width=8).pack(side="left", padx=(0, 12))

        self.sel_label = ttk.Label(toolbar, text="")
        self.sel_label.pack(side="left")

        # 表示切替ボタン（右寄せ）
        view_frame = ttk.Frame(toolbar)
        view_frame.pack(side="right")
        self._btn_list  = ttk.Button(view_frame, text="☰ リスト",     command=lambda: self._set_view("list"),  width=12)
        self._btn_thumb = ttk.Button(view_frame, text="⊞ サムネイル", command=lambda: self._set_view("thumb"), width=12)
        self._btn_list.pack(side="left", padx=2)
        self._btn_thumb.pack(side="left", padx=2)

        # ── 2つのビュー（同じ場所に重ねて配置） ────────────────────────────────
        self.cb_list    = CheckboxList(lf)
        self.thumb_view = ThumbnailView(lf)

        self.cb_list.grid(row=1, column=0, sticky="nsew")
        self.thumb_view.grid(row=1, column=0, sticky="nsew")
        self.thumb_view.grid_remove()   # 初期はリスト表示

        self._update_view_buttons()

        # ボタン
        btn_frame = ttk.Frame(self.root)
        btn_frame.grid(row=3, column=0, pady=12)
        ttk.Button(btn_frame, text="プレビュー確認", command=self._open_preview, width=18).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="一括印刷",       command=self._print_all,    width=14).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="PDF出力",        command=self._export_pdf,   width=12).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="終了",           command=self.root.quit,     width=10).pack(side="left", padx=8)

        self._update_sel_label()

    def _update_sel_label(self):
        view = self.cb_list if self._view_mode == "list" else self.thumb_view
        self.sel_label.config(text=f"{view.count_selected()} / {view.count_total()} 枚 選択中")
        self.root.after(300, self._update_sel_label)

    # ────────────────────────────────────────────── 表示切替 ──
    def _set_view(self, mode: str):
        if mode == self._view_mode:
            return
        self._view_mode = mode
        if mode == "list":
            self.thumb_view.grid_remove()
            self.cb_list.grid()
        else:
            self.cb_list.grid_remove()
            self.thumb_view.set_items(self._shared_items)
            self.thumb_view.grid()
        self._update_view_buttons()

    def _update_view_buttons(self):
        if self._view_mode == "list":
            self._btn_list.state(["pressed"])
            self._btn_thumb.state(["!pressed"])
        else:
            self._btn_list.state(["!pressed"])
            self._btn_thumb.state(["pressed"])

    # ─────────────────────────────────────── フォルダ・リスト ──
    def _select_folder(self):
        folder = filedialog.askdirectory(title="印刷する画像フォルダを選択")
        if folder:
            self.image_folder.set(folder)
            self._load_image_list(folder)

    def _load_image_list(self, folder: str):
        self._shared_items = []
        try:
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(SUPPORTED_EXTENSIONS):
                    path = os.path.join(folder, f)
                    self._shared_items.append((path, tk.BooleanVar(value=True)))
        except Exception as e:
            messagebox.showerror("エラー", f"フォルダの読み込みに失敗しました:\n{e}")

        self.cb_list.set_items(self._shared_items)
        if self._view_mode == "thumb":
            self.thumb_view.set_items(self._shared_items)

    def _current_view(self):
        return self.cb_list if self._view_mode == "list" else self.thumb_view

    def _select_all(self):
        self._current_view().select_all()

    def _deselect_all(self):
        self._current_view().deselect_all()

    # ────────────────────────────────────── プリンター設定 ──
    def _refresh_printers(self):
        if not WINDOWS: return
        try:
            printers = [p[2] for p in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
            self.printer_combo["values"] = printers
            if printers and self.selected_printer.get() not in printers:
                self.selected_printer.set(printers[0])
        except Exception as e:
            messagebox.showerror("エラー", f"プリンター一覧の取得に失敗しました:\n{e}")

    def _show_properties(self):
        if not WINDOWS:
            messagebox.showinfo("情報", "この機能は Windows 環境でのみ使用できます。")
            return
        name = self.selected_printer.get()
        if not name:
            messagebox.showwarning("警告", "プリンターを選択してください。"); return
        try:
            h = win32print.OpenPrinter(name)
            try:
                dm = win32print.GetPrinter(h, 2)["pDevMode"]
                result = win32print.DocumentProperties(
                    self.root.winfo_id(), h, name, dm, dm,
                    win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER | win32con.DM_IN_PROMPT)
                if result == 1: self.devmode = dm
            finally:
                win32print.ClosePrinter(h)
        except Exception as e:
            messagebox.showerror("エラー", f"プロパティの表示に失敗しました:\n{e}")

    # ──────────────────────────────────────────── プレビュー ──
    def _open_preview(self):
        selected = self._current_view().get_selected()
        if not selected:
            messagebox.showwarning("警告", "画像が選択されていません。"); return
        PreviewWindow(self.root, selected)

    # ───────────────────────────────────────────────── 印刷 ──
    def _set_printer_orientation(self, printer_name: str, orientation: int):
        try:
            h = win32print.OpenPrinter(printer_name)
            try:
                info = win32print.GetPrinter(h, 2)
                dm = info["pDevMode"]
                dm.Orientation = orientation
                win32print.DocumentProperties(
                    0, h, printer_name, dm, dm,
                    win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER)
                info["pDevMode"] = dm
                win32print.SetPrinter(h, 2, info, 0)
            finally:
                win32print.ClosePrinter(h)
        except Exception:
            pass

    def _print_image(self, image_path: str, printer_name: str):
        img = Image.open(image_path).convert("RGB")
        is_landscape = img.width > img.height

        self._set_printer_orientation(
            printer_name,
            DMORIENT_LANDSCAPE if is_landscape else DMORIENT_PORTRAIT
        )

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)

        pw = hdc.GetDeviceCaps(win32con.HORZRES)
        ph = hdc.GetDeviceCaps(win32con.VERTRES)
        dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)
        mx = int(dpi_x * MARGIN_MM / 25.4)
        my = int(dpi_y * MARGIN_MM / 25.4)
        avail_w, avail_h = pw - 2 * mx, ph - 2 * my

        ratio = img.width / img.height
        area_ratio = avail_w / avail_h
        if ratio > area_ratio:
            new_w, new_h = avail_w, int(avail_w / ratio)
        else:
            new_h, new_w = avail_h, int(avail_h * ratio)

        img = img.resize((new_w, new_h), Image.LANCZOS)
        x0 = mx + (avail_w - new_w) // 2
        y0 = my + (avail_h - new_h) // 2

        dib = ImageWin.Dib(img)
        hdc.StartDoc(os.path.basename(image_path))
        hdc.StartPage()
        dib.draw(hdc.GetHandleOutput(), (x0, y0, x0 + new_w, y0 + new_h))
        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()

    def _print_all(self):
        targets = self._current_view().get_selected()
        if not targets:
            messagebox.showwarning("警告", "印刷する画像が選択されていません。"); return

        printer_name = self.selected_printer.get()
        if not printer_name:
            messagebox.showwarning("警告", "プリンターを選択してください。"); return

        if not messagebox.askyesno(
            "印刷確認",
            f"{len(targets)} 枚の画像を印刷します。\n"
            f"プリンター: {printer_name}\n\n"
            f"（縦横は画像に合わせて自動判定します）\n\nよろしいですか？"
        ): return

        prog = tk.Toplevel(self.root)
        prog.title("印刷中...")
        prog.geometry("440x130")
        prog.resizable(False, False)
        prog.grab_set()
        ttk.Label(prog, text="印刷しています。しばらくお待ちください...").pack(pady=(12, 4))
        bar = ttk.Progressbar(prog, maximum=len(targets), mode="determinate")
        bar.pack(fill="x", padx=20, pady=4)
        status = ttk.Label(prog, text="")
        status.pack()

        errors = []
        for i, path in enumerate(targets):
            fname = os.path.basename(path)
            status.config(text=f"{fname}  ({i + 1} / {len(targets)})")
            prog.update()
            try:
                self._print_image(path, printer_name)
            except Exception as e:
                errors.append(f"{fname}: {e}")
            bar["value"] = i + 1
            prog.update()

        prog.destroy()
        if errors:
            messagebox.showerror("印刷エラー", "以下の画像で印刷に失敗しました:\n\n" + "\n".join(errors))
        else:
            messagebox.showinfo("完了", f"{len(targets)} 枚の印刷が完了しました。")

    # ──────────────────────────────────────────────── PDF出力 ──
    def _export_pdf(self):
        targets = self._current_view().get_selected()
        if not targets:
            messagebox.showwarning("警告", "画像が選択されていません。"); return

        # 保存先を選択
        save_path = filedialog.asksaveasfilename(
            title="PDFの保存先を選択",
            defaultextension=".pdf",
            filetypes=[("PDF ファイル", "*.pdf")],
            initialfile="output.pdf",
        )
        if not save_path:
            return

        # A4サイズ（ポイント単位: 1pt = 1/72inch）
        A4_W_PT = 595.27
        A4_H_PT = 841.89
        MARGIN_PT = MARGIN_MM / 25.4 * 72  # 5mm → pt

        prog = tk.Toplevel(self.root)
        prog.title("PDF出力中...")
        prog.geometry("440x130")
        prog.resizable(False, False)
        prog.grab_set()
        ttk.Label(prog, text="PDFを作成しています...").pack(pady=(12, 4))
        bar = ttk.Progressbar(prog, maximum=len(targets), mode="determinate")
        bar.pack(fill="x", padx=20, pady=4)
        status = ttk.Label(prog, text="")
        status.pack()

        errors = []
        pdf_pages: list[Image.Image] = []

        for i, path in enumerate(targets):
            fname = os.path.basename(path)
            status.config(text=f"{fname}  ({i + 1} / {len(targets)})")
            prog.update()
            try:
                img = Image.open(path).convert("RGB")
                is_landscape = img.width > img.height

                # ページサイズ（向き自動）
                if is_landscape:
                    page_w, page_h = A4_H_PT, A4_W_PT   # 横
                else:
                    page_w, page_h = A4_W_PT, A4_H_PT   # 縦

                avail_w = page_w - 2 * MARGIN_PT
                avail_h = page_h - 2 * MARGIN_PT

                ratio = img.width / img.height
                area_ratio = avail_w / avail_h
                if ratio > area_ratio:
                    new_w_pt, new_h_pt = avail_w, avail_w / ratio
                else:
                    new_h_pt, new_w_pt = avail_h, avail_h * ratio

                # pt → px（PDF解像度 150dpi）
                DPI = 150
                PT_TO_PX = DPI / 72
                new_w_px = max(1, int(new_w_pt * PT_TO_PX))
                new_h_px = max(1, int(new_h_pt * PT_TO_PX))
                page_w_px = int(page_w * PT_TO_PX)
                page_h_px = int(page_h * PT_TO_PX)
                margin_px = int(MARGIN_PT * PT_TO_PX)

                img_resized = img.resize((new_w_px, new_h_px), Image.LANCZOS)

                # 白紙ページに中央配置
                page_img = Image.new("RGB", (page_w_px, page_h_px), "white")
                x0 = margin_px + (int(avail_w * PT_TO_PX) - new_w_px) // 2
                y0 = margin_px + (int(avail_h * PT_TO_PX) - new_h_px) // 2
                page_img.paste(img_resized, (x0, y0))
                pdf_pages.append(page_img)

            except Exception as e:
                errors.append(f"{fname}: {e}")
            bar["value"] = i + 1
            prog.update()

        prog.destroy()

        if not pdf_pages:
            messagebox.showerror("エラー", "PDFを作成できる画像がありませんでした。")
            return

        try:
            pdf_pages[0].save(
                save_path,
                format="PDF",
                save_all=True,
                append_images=pdf_pages[1:],
                resolution=150,
            )
        except Exception as e:
            messagebox.showerror("エラー", f"PDF保存に失敗しました:\n{e}")
            return

        if errors:
            messagebox.showwarning(
                "PDF出力完了（一部エラー）",
                f"PDFを保存しました。\n{save_path}\n\n"
                f"以下の画像は取り込めませんでした:\n" + "\n".join(errors),
            )
        else:
            messagebox.showinfo(
                "PDF出力完了",
                f"{len(pdf_pages)} ページのPDFを保存しました。\n\n{save_path}",
            )


# ──────────────────────────────────────────────────────────────── main ──
def main():
    root = tk.Tk()
    ImageBulkPrinter(root)
    root.mainloop()


if __name__ == "__main__":
    main()

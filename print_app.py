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
PREVIEW_SIZE = (400, 566)   # A4縦比率

DMORIENT_PORTRAIT  = 1
DMORIENT_LANDSCAPE = 2


# ───────────────────────────── チェックボックスリスト ──────────────────────────
class CheckboxList(ttk.Frame):
    """スクロール可能なチェックボックスリスト"""

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

        self._inner.bind("<Configure>", self._on_frame_cfg)
        self._canvas.bind("<Configure>", self._on_canvas_cfg)
        self._canvas.bind("<MouseWheel>", self._on_wheel)
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all("<MouseWheel>", self._on_wheel))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

        self._items: list[tuple[str, tk.BooleanVar]] = []   # (path, var)

    def _on_frame_cfg(self, _):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_cfg(self, event):
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _on_wheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── 公開メソッド ──────────────────────────────────────────────────────────
    def set_items(self, image_files: list[str]):
        for w in self._inner.winfo_children():
            w.destroy()
        self._items.clear()

        for path in image_files:
            var = tk.BooleanVar(value=True)
            fname = os.path.basename(path)
            cb = ttk.Checkbutton(self._inner, text=f"  {fname}", variable=var)
            cb.pack(anchor="w", padx=6, pady=2, fill="x")
            self._items.append((path, var))

    def get_selected(self) -> list[str]:
        return [p for p, v in self._items if v.get()]

    def select_all(self):
        for _, v in self._items:
            v.set(True)

    def deselect_all(self):
        for _, v in self._items:
            v.set(False)

    def count_total(self) -> int:
        return len(self._items)

    def count_selected(self) -> int:
        return sum(1 for _, v in self._items if v.get())


# ───────────────────────────────── プレビュー ─────────────────────────────────
class PreviewWindow:
    """A4レイアウトで画像をプレビューするウィンドウ（前後ナビ付き）"""

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
        cf.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 6))

        self.canvas = tk.Canvas(cf, width=PREVIEW_SIZE[0], height=PREVIEW_SIZE[1], bg="white")
        self.canvas.pack()

        self.page_label = ttk.Label(self.win, text="")
        self.page_label.grid(row=1, column=0, columnspan=3, pady=(0, 6))

        nav = ttk.Frame(self.win)
        nav.grid(row=2, column=0, columnspan=3, pady=(0, 12))
        ttk.Button(nav, text="◀ 前の画像", command=self._prev, width=14).pack(side="left", padx=6)
        ttk.Button(nav, text="次の画像 ▶", command=self._next, width=14).pack(side="left", padx=6)
        ttk.Button(nav, text="閉じる",     command=self.win.destroy, width=10).pack(side="left", padx=6)

    def _show(self, idx: int):
        self.index = idx
        path = self.image_files[idx]
        img = Image.open(path).convert("RGB")
        is_landscape = img.width > img.height

        # プレビューキャンバスサイズを向きに合わせる
        if is_landscape:
            cw, ch = PREVIEW_SIZE[1], PREVIEW_SIZE[0]  # 横長
        else:
            cw, ch = PREVIEW_SIZE[0], PREVIEW_SIZE[1]  # 縦長

        self.canvas.config(width=cw, height=ch)

        margin = 9
        avail_w = cw - 2 * margin
        avail_h = ch - 2 * margin

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
        if self.index > 0:
            self._show(self.index - 1)

    def _next(self):
        if self.index < len(self.image_files) - 1:
            self._show(self.index + 1)


# ─────────────────────────────── メインアプリ ─────────────────────────────────
class ImageBulkPrinter:
    def __init__(self, root):
        self.root = root
        self.root.title("画像一括印刷")
        self.root.geometry("740x580")
        self.root.resizable(True, True)

        self.image_folder   = tk.StringVar()
        self.image_files: list[str] = []
        self.selected_printer = tk.StringVar()
        self.devmode = None

        if WINDOWS:
            try:
                self.selected_printer.set(win32print.GetDefaultPrinter())
            except Exception:
                pass

        self._setup_ui()
        self._refresh_printers()

    # ───────────────────────────────────────────────────────────────── UI ──
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
            pf, textvariable=self.selected_printer, state="readonly", width=42
        )
        self.printer_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        bf = ttk.Frame(pf)
        bf.grid(row=0, column=2)
        ttk.Button(bf, text="更新",         command=self._refresh_printers, width=6).pack(side="left", padx=2)
        ttk.Button(bf, text="印刷プロパティ", command=self._show_properties).pack(side="left", padx=2)

        # 画像リスト
        lf = ttk.LabelFrame(self.root, text="印刷対象の画像", padding=10)
        lf.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(1, weight=1)

        # 全選択 / 全解除
        sel_frame = ttk.Frame(lf)
        sel_frame.grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Button(sel_frame, text="全選択", command=self._select_all,   width=8).pack(side="left", padx=(0, 4))
        ttk.Button(sel_frame, text="全解除", command=self._deselect_all, width=8).pack(side="left")
        self.sel_label = ttk.Label(sel_frame, text="")
        self.sel_label.pack(side="left", padx=10)

        self.cb_list = CheckboxList(lf)
        self.cb_list.grid(row=1, column=0, sticky="nsew")
        self.cb_list._items  # ensure exists

        # チェック変更のたびにカウント更新（定期ポーリング）
        self._update_sel_label()

        # ボタン
        btn_frame = ttk.Frame(self.root)
        btn_frame.grid(row=3, column=0, pady=12)
        ttk.Button(btn_frame, text="プレビュー確認", command=self._open_preview, width=18).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="一括印刷",       command=self._print_all,    width=14).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="終了",           command=self.root.quit,     width=10).pack(side="left", padx=8)

    def _update_sel_label(self):
        total    = self.cb_list.count_total()
        selected = self.cb_list.count_selected()
        self.sel_label.config(text=f"{selected} / {total} 枚 選択中")
        self.root.after(300, self._update_sel_label)

    # ─────────────────────────────────────────────── フォルダ・リスト ──
    def _select_folder(self):
        folder = filedialog.askdirectory(title="印刷する画像フォルダを選択")
        if folder:
            self.image_folder.set(folder)
            self._load_image_list(folder)

    def _load_image_list(self, folder: str):
        self.image_files = []
        try:
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(SUPPORTED_EXTENSIONS):
                    self.image_files.append(os.path.join(folder, f))
        except Exception as e:
            messagebox.showerror("エラー", f"フォルダの読み込みに失敗しました:\n{e}")
        self.cb_list.set_items(self.image_files)

    def _select_all(self):
        self.cb_list.select_all()

    def _deselect_all(self):
        self.cb_list.deselect_all()

    # ──────────────────────────────────────────────── プリンター設定 ──
    def _refresh_printers(self):
        if not WINDOWS:
            return
        try:
            printers = [
                p[2]
                for p in win32print.EnumPrinters(
                    win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                )
            ]
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
            messagebox.showwarning("警告", "プリンターを選択してください。")
            return
        try:
            h = win32print.OpenPrinter(name)
            try:
                dm = win32print.GetPrinter(h, 2)["pDevMode"]
                result = win32print.DocumentProperties(
                    self.root.winfo_id(), h, name, dm, dm,
                    win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER | win32con.DM_IN_PROMPT,
                )
                if result == 1:
                    self.devmode = dm
            finally:
                win32print.ClosePrinter(h)
        except Exception as e:
            messagebox.showerror("エラー", f"プロパティの表示に失敗しました:\n{e}")

    # ───────────────────────────────────────────────────── プレビュー ──
    def _open_preview(self):
        selected = self.cb_list.get_selected()
        if not selected:
            messagebox.showwarning("警告", "画像が選択されていません。")
            return
        PreviewWindow(self.root, selected)

    # ───────────────────────────────────────────────────────── 印刷 ──
    def _set_printer_orientation(self, printer_name: str, orientation: int):
        """プリンターの向きを変更する（DMORIENT_PORTRAIT=1 / DMORIENT_LANDSCAPE=2）"""
        try:
            h = win32print.OpenPrinter(printer_name)
            try:
                info = win32print.GetPrinter(h, 2)
                dm = info["pDevMode"]
                dm.Orientation = orientation
                win32print.DocumentProperties(
                    0, h, printer_name, dm, dm,
                    win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER,
                )
                info["pDevMode"] = dm
                win32print.SetPrinter(h, 2, info, 0)
            finally:
                win32print.ClosePrinter(h)
        except Exception:
            pass  # 変更できなくてもフォールバックとして続行

    def _print_image(self, image_path: str, printer_name: str):
        """1枚の画像を向き自動判定してA4に印刷する"""
        img = Image.open(image_path).convert("RGB")
        is_landscape = img.width > img.height

        # 向きを設定
        orientation = DMORIENT_LANDSCAPE if is_landscape else DMORIENT_PORTRAIT
        self._set_printer_orientation(printer_name, orientation)

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)

        # 印刷可能領域
        printable_w = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_h = hdc.GetDeviceCaps(win32con.VERTRES)

        dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)
        mx = int(dpi_x * MARGIN_MM / 25.4)
        my = int(dpi_y * MARGIN_MM / 25.4)

        avail_w = printable_w - 2 * mx
        avail_h = printable_h - 2 * my

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
        targets = self.cb_list.get_selected()
        if not targets:
            messagebox.showwarning("警告", "印刷する画像が選択されていません。")
            return

        printer_name = self.selected_printer.get()
        if not printer_name:
            messagebox.showwarning("警告", "プリンターを選択してください。")
            return

        if not messagebox.askyesno(
            "印刷確認",
            f"{len(targets)} 枚の画像を印刷します。\n"
            f"プリンター: {printer_name}\n\n"
            f"（縦横は画像に合わせて自動判定します）\n\nよろしいですか？",
        ):
            return

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


# ─────────────────────────────────────────────────────────────────── main ──
def main():
    root = tk.Tk()
    ImageBulkPrinter(root)
    root.mainloop()


if __name__ == "__main__":
    main()

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
MARGIN_MM = 5       # 印刷余白 5mm
PREVIEW_SIZE = (400, 566)   # A4縦比率のプレビューサイズ（px）


class PreviewWindow:
    """選択した画像をA4縦レイアウトでプレビュー表示するウィンドウ"""

    def __init__(self, parent, image_files: list):
        self.image_files = image_files
        self.index = 0

        self.win = tk.Toplevel(parent)
        self.win.title("印刷プレビュー")
        self.win.resizable(False, False)
        self.win.grab_set()

        self._build_ui()
        self._show(0)

    def _build_ui(self):
        # キャンバス（A4縦比率 400×566）
        canvas_frame = ttk.Frame(self.win, relief="sunken", borderwidth=1)
        canvas_frame.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 8))

        self.canvas = tk.Canvas(
            canvas_frame,
            width=PREVIEW_SIZE[0],
            height=PREVIEW_SIZE[1],
            bg="white"
        )
        self.canvas.pack()

        # ページ情報
        self.page_label = ttk.Label(self.win, text="")
        self.page_label.grid(row=1, column=0, columnspan=3, pady=(0, 6))

        # ナビゲーションボタン
        nav_frame = ttk.Frame(self.win)
        nav_frame.grid(row=2, column=0, columnspan=3, pady=(0, 10))

        ttk.Button(nav_frame, text="◀ 前の画像", command=self._prev, width=14).pack(
            side="left", padx=6
        )
        ttk.Button(nav_frame, text="次の画像 ▶", command=self._next, width=14).pack(
            side="left", padx=6
        )
        ttk.Button(nav_frame, text="閉じる", command=self.win.destroy, width=10).pack(
            side="left", padx=6
        )

    def _show(self, idx: int):
        self.index = idx
        path = self.image_files[idx]

        # A4プレビューに収まるようリサイズ（余白5mm相当＝プレビュー上約9px）
        margin = 9
        avail_w = PREVIEW_SIZE[0] - 2 * margin
        avail_h = PREVIEW_SIZE[1] - 2 * margin

        img = Image.open(path).convert("RGB")
        ratio = img.width / img.height
        area_ratio = avail_w / avail_h

        if ratio > area_ratio:
            w = avail_w
            h = int(avail_w / ratio)
        else:
            h = avail_h
            w = int(avail_h * ratio)

        img = img.resize((w, h), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(img)  # 参照保持

        x0 = margin + (avail_w - w) // 2
        y0 = margin + (avail_h - h) // 2

        self.canvas.delete("all")
        self.canvas.create_image(x0, y0, anchor="nw", image=self._tk_img)

        # ページ番号 + ファイル名
        fname = os.path.basename(path)
        self.page_label.config(
            text=f"{idx + 1} / {len(self.image_files)}  —  {fname}"
        )
        self.win.title(f"印刷プレビュー  [{idx + 1}/{len(self.image_files)}]  {fname}")

    def _prev(self):
        if self.index > 0:
            self._show(self.index - 1)

    def _next(self):
        if self.index < len(self.image_files) - 1:
            self._show(self.index + 1)


class ImageBulkPrinter:
    def __init__(self, root):
        self.root = root
        self.root.title("画像一括印刷")
        self.root.geometry("720x560")
        self.root.resizable(True, True)

        self.image_folder = tk.StringVar()
        self.image_files = []
        self.selected_printer = tk.StringVar()
        self.devmode = None

        if WINDOWS:
            try:
                self.selected_printer.set(win32print.GetDefaultPrinter())
            except Exception:
                pass

        self._setup_ui()
        self._refresh_printers()

    # ------------------------------------------------------------------ UI --
    def _setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # フォルダ選択
        folder_frame = ttk.LabelFrame(self.root, text="印刷フォルダ", padding=10)
        folder_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        folder_frame.columnconfigure(1, weight=1)

        ttk.Button(folder_frame, text="フォルダを選択", command=self._select_folder).grid(
            row=0, column=0, padx=(0, 10)
        )
        ttk.Entry(folder_frame, textvariable=self.image_folder, state="readonly").grid(
            row=0, column=1, sticky="ew"
        )

        # プリンター設定
        printer_frame = ttk.LabelFrame(self.root, text="プリンター設定", padding=10)
        printer_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        printer_frame.columnconfigure(1, weight=1)

        ttk.Label(printer_frame, text="プリンター:").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.printer_combo = ttk.Combobox(
            printer_frame, textvariable=self.selected_printer, state="readonly", width=42
        )
        self.printer_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        btn_frame = ttk.Frame(printer_frame)
        btn_frame.grid(row=0, column=2)
        ttk.Button(btn_frame, text="更新", command=self._refresh_printers, width=6).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="印刷プロパティ", command=self._show_properties).pack(
            side="left", padx=2
        )

        # 画像リスト
        list_frame = ttk.LabelFrame(self.root, text="印刷対象の画像", padding=10)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        list_inner = ttk.Frame(list_frame)
        list_inner.grid(row=0, column=0, sticky="nsew")
        list_inner.columnconfigure(0, weight=1)
        list_inner.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_inner, selectmode="extended", font=("Meiryo", 10))
        self.listbox.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(list_inner, orient="vertical", command=self.listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=sb.set)

        self.count_label = ttk.Label(list_frame, text="0 枚の画像")
        self.count_label.grid(row=1, column=0, sticky="w", pady=(5, 0))

        # ボタン群
        print_frame = ttk.Frame(self.root)
        print_frame.grid(row=3, column=0, pady=12)

        ttk.Button(
            print_frame, text="プレビュー確認", command=self._open_preview, width=18
        ).pack(side="left", padx=8)
        ttk.Button(
            print_frame, text="一括印刷", command=self._print_all, width=14
        ).pack(side="left", padx=8)
        ttk.Button(
            print_frame, text="終了", command=self.root.quit, width=10
        ).pack(side="left", padx=8)

    # --------------------------------------------------------- Folder/List --
    def _select_folder(self):
        folder = filedialog.askdirectory(title="印刷する画像フォルダを選択")
        if folder:
            self.image_folder.set(folder)
            self._load_image_list(folder)

    def _load_image_list(self, folder):
        self.listbox.delete(0, tk.END)
        self.image_files = []
        try:
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(SUPPORTED_EXTENSIONS):
                    self.image_files.append(os.path.join(folder, f))
                    self.listbox.insert(tk.END, f"  {f}")
        except Exception as e:
            messagebox.showerror("エラー", f"フォルダの読み込みに失敗しました:\n{e}")
        self.count_label.config(text=f"{len(self.image_files)} 枚の画像")

    # ------------------------------------------------------- Printer setup --
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
            current = self.selected_printer.get()
            if printers and current not in printers:
                self.selected_printer.set(printers[0])
        except Exception as e:
            messagebox.showerror("エラー", f"プリンター一覧の取得に失敗しました:\n{e}")

    def _show_properties(self):
        if not WINDOWS:
            messagebox.showinfo("情報", "この機能は Windows 環境でのみ使用できます。")
            return
        printer_name = self.selected_printer.get()
        if not printer_name:
            messagebox.showwarning("警告", "プリンターを選択してください。")
            return
        try:
            handle = win32print.OpenPrinter(printer_name)
            try:
                dm = win32print.GetPrinter(handle, 2)["pDevMode"]
                result = win32print.DocumentProperties(
                    self.root.winfo_id(),
                    handle,
                    printer_name,
                    dm,
                    dm,
                    win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER | win32con.DM_IN_PROMPT,
                )
                if result == 1:
                    self.devmode = dm
            finally:
                win32print.ClosePrinter(handle)
        except Exception as e:
            messagebox.showerror("エラー", f"プロパティの表示に失敗しました:\n{e}")

    # ------------------------------------------------------------ Preview --
    def _open_preview(self):
        if not self.image_files:
            messagebox.showwarning("警告", "画像がありません。\nフォルダを選択してください。")
            return
        PreviewWindow(self.root, self.image_files)

    # ------------------------------------------------------------ Printing --
    def _print_image_a4(self, image_path: str, printer_name: str):
        """1枚の画像をA4縦・中央配置で印刷する"""
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)

        printable_w = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_h = hdc.GetDeviceCaps(win32con.VERTRES)

        dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)
        margin_x = int(dpi_x * MARGIN_MM / 25.4)
        margin_y = int(dpi_y * MARGIN_MM / 25.4)

        avail_w = printable_w - 2 * margin_x
        avail_h = printable_h - 2 * margin_y

        img = Image.open(image_path).convert("RGB")
        ratio = img.width / img.height
        area_ratio = avail_w / avail_h

        if ratio > area_ratio:
            new_w = avail_w
            new_h = int(avail_w / ratio)
        else:
            new_h = avail_h
            new_w = int(avail_h * ratio)

        img = img.resize((new_w, new_h), Image.LANCZOS)

        x0 = margin_x + (avail_w - new_w) // 2
        y0 = margin_y + (avail_h - new_h) // 2

        dib = ImageWin.Dib(img)
        hdc.StartDoc(os.path.basename(image_path))
        hdc.StartPage()
        dib.draw(hdc.GetHandleOutput(), (x0, y0, x0 + new_w, y0 + new_h))
        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()

    def _print_all(self):
        if not self.image_files:
            messagebox.showwarning("警告", "印刷する画像がありません。\nフォルダを選択してください。")
            return

        printer_name = self.selected_printer.get()
        if not printer_name:
            messagebox.showwarning("警告", "プリンターを選択してください。")
            return

        if not messagebox.askyesno(
            "印刷確認",
            f"{len(self.image_files)} 枚の画像を印刷します。\n\nプリンター: {printer_name}\n\nよろしいですか？",
        ):
            return

        prog_win = tk.Toplevel(self.root)
        prog_win.title("印刷中...")
        prog_win.geometry("420x130")
        prog_win.resizable(False, False)
        prog_win.grab_set()

        ttk.Label(prog_win, text="印刷しています。しばらくお待ちください...").pack(pady=(12, 4))
        bar = ttk.Progressbar(prog_win, maximum=len(self.image_files), mode="determinate")
        bar.pack(fill="x", padx=20, pady=4)
        status = ttk.Label(prog_win, text="")
        status.pack()

        errors = []
        for i, path in enumerate(self.image_files):
            fname = os.path.basename(path)
            status.config(text=f"{fname}  ({i + 1} / {len(self.image_files)})")
            prog_win.update()
            try:
                self._print_image_a4(path, printer_name)
            except Exception as e:
                errors.append(f"{fname}: {e}")
            bar["value"] = i + 1
            prog_win.update()

        prog_win.destroy()

        if errors:
            messagebox.showerror(
                "印刷エラー",
                "以下の画像で印刷に失敗しました:\n\n" + "\n".join(errors),
            )
        else:
            messagebox.showinfo("完了", f"{len(self.image_files)} 枚の印刷が完了しました。")


# ------------------------------------------------------------------- main --
def main():
    root = tk.Tk()
    ImageBulkPrinter(root)
    root.mainloop()


if __name__ == "__main__":
    main()

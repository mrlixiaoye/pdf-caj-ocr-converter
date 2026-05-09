#!/usr/bin/env python3
"""
PDF / CAJ 批量 OCR 转换器  ·  赛博风格
支持：图片PDF / CAJ → 可搜索文字PDF
依赖：brew install tesseract tesseract-lang mupdf-tools
      pip3 install ocrmypdf
用法：python3 pdf_ocr_batch.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import time
import queue
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 赛博配色表 ──────────────────────────────────────────────────────────────
BG_DEEP  = "#060b14"   # 最深背景
BG_DARK  = "#0d1625"   # 面板背景
BG_MID   = "#111c2e"   # 稍亮面板
CYAN     = "#00d9ff"   # 主色（青蓝光）
PINK     = "#ff2d78"   # 副色（品红光）
GREEN_N  = "#00e676"   # 成功绿光
RED_N    = "#ff3d5a"   # 错误红光
AMBER_N  = "#ffc107"   # 进行中琥珀光
TEXT_BR  = "#cdd9f0"   # 主文本
TEXT_MED = "#7ea8cc"   # 中文本
TEXT_DIM = "#3d5a80"   # 暗文本
BORDER   = "#1a3350"   # 边框

COPYRIGHT = "©  该软件版权归 mrlixiaoye 所有，不得商业化"

LANGS = {
    "中文简体":   "chi_sim+eng",
    "中文繁体":   "chi_tra+eng",
    "英文":       "eng",
    "中英文混合": "chi_sim+chi_tra+eng",
    "日文":       "jpn+eng",
}

STATUS_TAG = {
    "等待中":   "wait",
    "CAJ→PDF": "run",
    "OCR中":   "run",
    "完成":     "ok",
    "失败":     "err",
}

SUPPORTED_EXTS = {".pdf", ".caj"}
BUSY_STATUSES  = {"CAJ→PDF", "OCR中"}

INSTALL_CMD_OCR = """\
# 1. 安装 Homebrew（已安装可跳过）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装 Tesseract OCR 引擎（含中文语言包）
brew install tesseract tesseract-lang

# 3. 安装 Python OCR 库
pip3 install ocrmypdf"""

INSTALL_CMD_CAJ = """\
# caj2pdf 不在 PyPI，需要 git clone 到本地：
git clone https://github.com/caj2pdf/caj2pdf.git ~/caj2pdf

# 完成后重新点击转换即可（程序会自动找到 ~/caj2pdf/caj2pdf）"""


# ── 文件条目 ────────────────────────────────────────────────────────────────

class FileItem:
    __slots__ = ("path", "name", "size", "fmt", "status", "error", "elapsed")

    def __init__(self, path: str):
        self.path    = path
        self.name    = os.path.basename(path)
        self.size    = os.path.getsize(path) if os.path.exists(path) else 0
        self.fmt     = os.path.splitext(path)[1].upper().lstrip(".")
        self.status  = "等待中"
        self.error   = ""
        self.elapsed = 0.0

    @property
    def size_str(self) -> str:
        mb = self.size / 1_048_576
        return f"{mb:.1f} MB" if mb >= 1 else f"{self.size / 1024:.1f} KB"

    @property
    def elapsed_str(self) -> str:
        if not self.elapsed:
            return "—"
        m, s = divmod(int(self.elapsed), 60)
        return f"{m}m{s:02d}s" if m else f"{s}s"


# ── 主应用 ──────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF / CAJ 批量 OCR 转换器")
        self.geometry("1060x690")
        self.minsize(820, 540)
        self.configure(bg=BG_DEEP)

        self.files: list     = []
        self.out_dir         = tk.StringVar()
        self.lang_var        = tk.StringVar(value="中文简体")
        self.workers_var     = tk.IntVar(value=2)
        self.force_var       = tk.BooleanVar(value=False)
        self.status_var      = tk.StringVar(value="就绪 — 请添加 PDF 或 CAJ 文件")
        self.prog_var        = tk.DoubleVar(value=0)
        self.running         = False
        self._q: queue.Queue = queue.Queue()

        self._setup_style()
        self._build_ui()
        self._poll()

    # ── 样式 ───────────────────────────────────────────────────────────────

    def _setup_style(self):
        st = ttk.Style()
        st.theme_use("clam")

        # Treeview 深色主题
        st.configure("Treeview",
                     background=BG_DARK,
                     foreground=TEXT_MED,
                     fieldbackground=BG_DARK,
                     rowheight=28,
                     font=("Courier", 10),
                     borderwidth=0,
                     relief="flat")
        st.configure("Treeview.Heading",
                     background=BG_MID,
                     foreground=CYAN,
                     font=("Courier", 10, "bold"),
                     relief="flat",
                     padding=6)
        st.map("Treeview",
               background=[("selected", "#1a3350")],
               foreground=[("selected", CYAN)])

        # 进度条
        st.configure("cyber.Horizontal.TProgressbar",
                     background=CYAN,
                     troughcolor=BG_MID,
                     bordercolor=BORDER,
                     lightcolor=CYAN,
                     darkcolor="#0099bb",
                     thickness=12)

        # Combobox
        st.configure("TCombobox",
                     fieldbackground=BG_MID,
                     background=BG_MID,
                     foreground=TEXT_BR,
                     arrowcolor=CYAN,
                     bordercolor=BORDER,
                     selectbackground=BORDER,
                     selectforeground=CYAN,
                     insertcolor=CYAN)
        st.map("TCombobox",
               fieldbackground=[("readonly", BG_MID)],
               foreground=[("readonly", TEXT_BR)])

        # Spinbox
        st.configure("TSpinbox",
                     fieldbackground=BG_MID,
                     background=BG_MID,
                     foreground=TEXT_BR,
                     arrowcolor=CYAN,
                     bordercolor=BORDER,
                     insertcolor=CYAN)

        # Scrollbar
        st.configure("Vertical.TScrollbar",
                     background=BG_MID,
                     troughcolor=BG_DARK,
                     arrowcolor=CYAN,
                     bordercolor=BORDER,
                     relief="flat")
        st.map("Vertical.TScrollbar",
               background=[("active", BORDER)])

        # Checkbutton
        st.configure("TCheckbutton",
                     background=BG_MID,
                     foreground=TEXT_MED,
                     font=("Helvetica", 11))
        st.map("TCheckbutton",
               background=[("active", BG_MID)],
               foreground=[("active", CYAN)])

    # ── 辅助：赛博风按钮工厂 ────────────────────────────────────────────────

    @staticmethod
    def _cyber_btn(parent, text, command, color=None, **kw):
        c = color or CYAN
        return tk.Button(
            parent, text=text, command=command,
            font=("Courier", 10),
            bg=BG_MID, fg=c,
            activebackground=BORDER, activeforeground=c,
            relief=tk.FLAT, padx=10, pady=4,
            cursor="hand2",
            highlightbackground=BORDER, highlightthickness=1,
            **kw)

    # ── 界面构建 ────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── 顶部标题栏 ──────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG_DEEP, height=62)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Frame(hdr, bg=PINK, width=4).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr,
                 text="  ◈  PDF / CAJ  批量 OCR 转换器",
                 font=("Courier", 18, "bold"), fg=CYAN, bg=BG_DEEP,
                 ).pack(side=tk.LEFT, padx=(8, 0), pady=10)
        tk.Label(hdr,
                 text="[ 图片PDF & CAJ → 可搜索文字PDF  ·  支持 100+ 文件批量处理 ]",
                 font=("Courier", 10), fg=TEXT_DIM, bg=BG_DEEP,
                 ).pack(side=tk.LEFT, padx=14)

        # ── 顶部青色分隔线 ──────────────────────────────────────────────────
        tk.Frame(self, bg=CYAN, height=1).pack(fill=tk.X)

        # ── 工具栏 ──────────────────────────────────────────────────────────
        tb = tk.Frame(self, bg=BG_DARK, padx=10, pady=7)
        tb.pack(fill=tk.X)

        for text, cmd, color in [
            ("[+] 添加文件",    self.add_files,    CYAN),
            ("[⊞] 添加文件夹",  self.add_folder,   CYAN),
            ("[×] 删除选中",   self.remove_sel,   PINK),
            ("[✖] 清空列表",   self.clear_all,    PINK),
            ("[↺] 重置失败",   self.reset_failed, AMBER_N),
        ]:
            self._cyber_btn(tb, text, cmd, color=color).pack(side=tk.LEFT, padx=3)

        self.count_lbl = tk.Label(
            tb, text="◆  共 0 个文件",
            font=("Courier", 10), fg=TEXT_DIM, bg=BG_DARK)
        self.count_lbl.pack(side=tk.LEFT, padx=14)

        # ── 暗色分隔线 ──────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X)

        # ── 文件列表表格 ────────────────────────────────────────────────────
        tbl = tk.Frame(self, bg=BG_DEEP)
        tbl.pack(fill=tk.BOTH, expand=True)

        cols    = ("#",  "格式", "文件名", "大小", "状态", "用时", "备注")
        widths  = [ 42,    52,    348,      80,     90,     68,     210]
        anchors = ["c",   "c",   "w",      "c",    "c",    "c",    "w" ]

        self.tree = ttk.Treeview(tbl, columns=cols, show="headings",
                                  selectmode="extended")
        for col, w, a in zip(cols, widths, anchors):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor=a, minwidth=30)

        self.tree.tag_configure("wait", foreground=TEXT_DIM,  background=BG_DARK)
        self.tree.tag_configure("run",  foreground=AMBER_N,   background="#1a1200")
        self.tree.tag_configure("ok",   foreground=GREEN_N,   background="#001a0d")
        self.tree.tag_configure("err",  foreground=RED_N,     background="#1a0008")

        sb = ttk.Scrollbar(tbl, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── 品红分隔线 ──────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X)

        # ── 选项行 ──────────────────────────────────────────────────────────
        opt = tk.Frame(self, bg=BG_MID, padx=10, pady=8)
        opt.pack(fill=tk.X)

        tk.Label(opt, text="输出目录：", font=("Courier", 10),
                 fg=TEXT_MED, bg=BG_MID).pack(side=tk.LEFT)
        tk.Entry(opt, textvariable=self.out_dir, width=36,
                 font=("Courier", 10),
                 bg=BG_DARK, fg=TEXT_BR, insertbackground=CYAN,
                 relief=tk.FLAT, bd=0,
                 highlightbackground=BORDER, highlightthickness=1,
                 ).pack(side=tk.LEFT, padx=(0, 4), ipady=3)
        self._cyber_btn(opt, "选择", self.pick_dir, color=CYAN,
                        ).pack(side=tk.LEFT, padx=(0, 16))

        tk.Label(opt, text="语言：", font=("Courier", 10),
                 fg=TEXT_MED, bg=BG_MID).pack(side=tk.LEFT)
        ttk.Combobox(opt, textvariable=self.lang_var,
                     values=list(LANGS.keys()),
                     width=13, state="readonly",
                     font=("Courier", 10),
                     ).pack(side=tk.LEFT, padx=(0, 16))

        tk.Label(opt, text="并行数：", font=("Courier", 10),
                 fg=TEXT_MED, bg=BG_MID).pack(side=tk.LEFT)
        ttk.Spinbox(opt, from_=1, to=8, textvariable=self.workers_var,
                    width=3, font=("Courier", 10),
                    ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(opt, text="个", font=("Courier", 10),
                 fg=TEXT_MED, bg=BG_MID).pack(side=tk.LEFT, padx=(0, 16))

        ttk.Checkbutton(opt,
                        text="强制重新 OCR（已有文字层的 PDF 也重新识别）",
                        variable=self.force_var,
                        ).pack(side=tk.LEFT)

        # ── 品红分隔线 ──────────────────────────────────────────────────────
        tk.Frame(self, bg=PINK, height=1).pack(fill=tk.X)

        # ── 底部操作栏 ──────────────────────────────────────────────────────
        bot = tk.Frame(self, bg=BG_DEEP, padx=10, pady=9)
        bot.pack(fill=tk.X, side=tk.BOTTOM)

        self.start_btn = tk.Button(
            bot, text="▶  开始批量转换",
            font=("Courier", 13, "bold"),
            bg="#002a15", fg=GREEN_N,
            activebackground="#003d1f", activeforeground=GREEN_N,
            relief=tk.FLAT, padx=20, pady=7, cursor="hand2",
            highlightbackground=GREEN_N, highlightthickness=1,
            command=self.start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_btn = tk.Button(
            bot, text="■  停止",
            font=("Courier", 12, "bold"),
            bg="#2a0010", fg=RED_N,
            activebackground="#3d0018", activeforeground=RED_N,
            relief=tk.FLAT, padx=14, pady=7, cursor="hand2",
            highlightbackground=RED_N, highlightthickness=1,
            state=tk.DISABLED, command=self.stop)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 16))

        self.prog = ttk.Progressbar(
            bot, variable=self.prog_var,
            maximum=100, length=300,
            style="cyber.Horizontal.TProgressbar")
        self.prog.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(bot, textvariable=self.status_var,
                 font=("Courier", 10),
                 bg=BG_DEEP, fg=TEXT_MED).pack(side=tk.LEFT)

        # 版权声明（右对齐）
        tk.Label(bot, text=COPYRIGHT,
                 font=("Helvetica", 9), fg=TEXT_DIM, bg=BG_DEEP,
                 ).pack(side=tk.RIGHT, padx=8)

    # ── 文件管理 ────────────────────────────────────────────────────────────

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择文件（PDF / CAJ，可多选，Cmd+A 全选）",
            filetypes=[
                ("支持的格式", "*.pdf *.caj"),
                ("PDF 文件",   "*.pdf"),
                ("CAJ 文件",   "*.caj"),
                ("所有文件",   "*.*"),
            ])
        existing = {f.path for f in self.files}
        added = 0
        for p in paths:
            if p not in existing:
                self.files.append(FileItem(p))
                added += 1
        if added:
            self.status_var.set(f"已添加 {added} 个文件")
        self._refresh()

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹（自动递归查找全部 PDF / CAJ）")
        if not folder:
            return
        existing = {f.path for f in self.files}
        added = 0
        for root, _, names in os.walk(folder):
            for fn in sorted(names):
                if os.path.splitext(fn)[1].lower() in SUPPORTED_EXTS:
                    p = os.path.join(root, fn)
                    if p not in existing:
                        self.files.append(FileItem(p))
                        added += 1
        self.status_var.set(f"从文件夹添加了 {added} 个文件（PDF / CAJ）")
        self._refresh()

    def remove_sel(self):
        sel = self.tree.selection()
        if not sel:
            return
        idxs = sorted(
            [int(self.tree.item(i, "values")[0]) - 1 for i in sel],
            reverse=True)
        for idx in idxs:
            if 0 <= idx < len(self.files) and self.files[idx].status not in BUSY_STATUSES:
                self.files.pop(idx)
        self._refresh()

    def clear_all(self):
        busy = [f for f in self.files if f.status in BUSY_STATUSES]
        if busy and not messagebox.askyesno("确认", f"有 {len(busy)} 个文件正在转换，确认清空？"):
            return
        self.files = busy
        self._refresh()

    def reset_failed(self):
        n = 0
        for f in self.files:
            if f.status == "失败":
                f.status  = "等待中"
                f.error   = ""
                f.elapsed = 0.0
                n += 1
        self.status_var.set(f"已重置 {n} 个失败文件，可重新转换")
        self._refresh()

    def pick_dir(self):
        d = filedialog.askdirectory(title="选择输出文件夹")
        if d:
            self.out_dir.set(d)

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(self.files, 1):
            tag = STATUS_TAG.get(f.status, "wait")
            self.tree.insert("", "end",
                             values=(i, f.fmt, f.name, f.size_str,
                                     f.status, f.elapsed_str, f.error),
                             tags=(tag,))
        total = len(self.files)
        ok    = sum(1 for f in self.files if f.status == "完成")
        fail  = sum(1 for f in self.files if f.status == "失败")
        run   = sum(1 for f in self.files if f.status in BUSY_STATUSES)
        if total:
            self.count_lbl.configure(
                text=f"◆  共 {total} 个文件  ✓{ok}  ✗{fail}  ⏳{run}")
        else:
            self.count_lbl.configure(text="◆  共 0 个文件")

    # ── 转换流程 ────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        try:
            import ocrmypdf  # noqa: F401
        except ImportError:
            self._show_install("ocr")
            return

        out = self.out_dir.get().strip()
        if not self.files:
            messagebox.showwarning("提示", "请先添加 PDF 或 CAJ 文件")
            return
        if not out:
            messagebox.showwarning("提示", "请先选择输出文件夹")
            return

        pending = [f for f in self.files if f.status in ("等待中", "失败")]
        if not pending:
            messagebox.showinfo("提示", "没有待处理文件，可点击「重置失败」后重试")
            return

        os.makedirs(out, exist_ok=True)
        self.running = True
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.prog_var.set(0)

        lang    = LANGS.get(self.lang_var.get(), "chi_sim+eng")
        workers = self.workers_var.get()
        force   = self.force_var.get()

        threading.Thread(
            target=self._batch_worker,
            args=(pending, out, lang, workers, force),
            daemon=True).start()

    def stop(self):
        self.running = False
        self.status_var.set("正在停止（等待当前任务完成后停止）…")

    def _batch_worker(self, pending: list, out: str, lang: str, workers: int, force: bool):
        total = len(pending)
        done  = 0

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {}
            for f in pending:
                if not self.running:
                    break
                out_path = self._resolve_out_path(f, out)
                futures[ex.submit(self._ocr_one, f, out_path, lang, force)] = f

            for fut in as_completed(futures):
                done += 1
                self._q.put(("prog", done / total * 100, done, total))

        self._q.put(("done",))

    def _resolve_out_path(self, item: FileItem, out_dir: str) -> str:
        stem = os.path.splitext(item.name)[0]
        base = os.path.join(out_dir, f"{stem}_OCR.pdf")
        if not os.path.exists(base):
            return base
        i = 2
        while True:
            p = os.path.join(out_dir, f"{stem}_OCR_{i}.pdf")
            if not os.path.exists(p):
                return p
            i += 1

    # ── 核心 OCR 工作线程 ───────────────────────────────────────────────────

    def _ocr_one(self, item: FileItem, out_path: str, lang: str, force: bool):
        import ocrmypdf

        start    = time.time()
        tmp_file = None
        is_caj   = item.path.lower().endswith(".caj")

        try:
            input_path = item.path

            # ── 第一步：CAJ → 临时 PDF ──────────────────────────────────────
            if is_caj:
                if self._is_pdf_bytes(item.path):
                    force = True
                else:
                    item.status = "CAJ→PDF"
                    self._q.put(("refresh",))

                    fd, tmp_file = tempfile.mkstemp(suffix=".pdf")
                    os.close(fd)
                    self._convert_caj(item.path, tmp_file)
                    input_path = tmp_file
                    force = True

            # ── 第二步：OCR 识别 ────────────────────────────────────────────
            item.status = "OCR中"
            self._q.put(("refresh",))

            kwargs: dict = dict(
                language=lang,
                output_type="pdf",
                progress_bar=False,
                rotate_pages=True,
            )
            if force:
                kwargs["force_ocr"] = True
            else:
                kwargs["skip_text"] = True

            ocrmypdf.ocr(input_path, out_path, **kwargs)
            item.status = "完成"
            item.error  = ""

        except RuntimeError as e:
            item.status = "失败"
            item.error  = str(e)[:120]
            if "caj2pdf" in str(e):
                self.after(0, lambda: self._show_install("caj"))
        except Exception as e:
            item.status = "失败"
            item.error  = str(e)[:120]
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except Exception:
                    pass
            item.elapsed = time.time() - start

        self._q.put(("refresh",))

    @staticmethod
    def _is_pdf_bytes(path: str) -> bool:
        """通过文件头魔数判断是否为 PDF（部分 .caj 文件实为 PDF）。"""
        try:
            with open(path, "rb") as fh:
                return fh.read(5) == b"%PDF-"
        except Exception:
            return False

    @staticmethod
    def _convert_caj(caj_path: str, out_pdf: str) -> None:
        """将 CAJ 转为 PDF。按顺序尝试三个引擎，有一个成功即返回。"""
        import sys

        errors: dict = {}

        # ── 引擎 1：caj2pdf 命令（极少数情况下全局可用）──────────────────
        exe = shutil.which("caj2pdf")
        if exe:
            r = subprocess.run([exe, "convert", caj_path, "-o", out_pdf],
                               capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                return
            errors["caj2pdf(cmd)"] = (r.stderr or r.stdout or "未知").strip()

        # ── 引擎 2：~/caj2pdf/caj2pdf（git clone 安装方式）──────────────
        script_candidates = [
            os.path.expanduser("~/caj2pdf/caj2pdf"),
            os.path.expanduser("~/Downloads/caj2pdf/caj2pdf"),
        ]
        for script in script_candidates:
            if os.path.isfile(script):
                r = subprocess.run(
                    [sys.executable, script, "convert", caj_path, "-o", out_pdf],
                    capture_output=True, text=True, timeout=300)
                if r.returncode == 0:
                    return
                errors["caj2pdf(script)"] = (r.stderr or r.stdout or "未知").strip()
                break
        else:
            errors["caj2pdf(script)"] = "未找到 ~/caj2pdf/caj2pdf"

        # ── 引擎 3：mutool convert（mupdf-tools 已安装，兜底）────────────
        mutool = shutil.which("mutool")
        if mutool:
            r = subprocess.run([mutool, "convert", "-o", out_pdf, caj_path],
                               capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                return
            errors["mutool"] = (r.stderr or r.stdout or "未知").strip()
        else:
            errors["mutool"] = "未安装"

        # ── 全部失败 ──────────────────────────────────────────────────────
        detail = "\n".join(f"  {k}: {v}" for k, v in errors.items())
        raise RuntimeError(
            f"CAJ 转换失败（所有引擎均无法处理）：\n{detail}\n\n"
            f"请先执行：\n"
            f"git clone https://github.com/caj2pdf/caj2pdf.git ~/caj2pdf"
        )

    # ── UI 轮询（主线程）───────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                msg = self._q.get_nowait()
                if msg[0] == "refresh":
                    self._refresh()
                elif msg[0] == "prog":
                    _, pct, done, total = msg
                    self.prog_var.set(pct)
                    ok   = sum(1 for f in self.files if f.status == "完成")
                    fail = sum(1 for f in self.files if f.status == "失败")
                    self.status_var.set(f"进度 {done}/{total}  ✓{ok}  ✗{fail}")
                    self._refresh()
                elif msg[0] == "done":
                    self.running = False
                    self.start_btn.configure(state=tk.NORMAL)
                    self.stop_btn.configure(state=tk.DISABLED)
                    self.prog_var.set(100)
                    self._refresh()
                    ok   = sum(1 for f in self.files if f.status == "完成")
                    fail = sum(1 for f in self.files if f.status == "失败")
                    self.status_var.set(f"全部完成  ✓{ok}  ✗{fail}")
                    body = f"批量转换完成！\n\n✓ 成功：{ok} 个\n✗ 失败：{fail} 个"
                    if fail:
                        body += "\n\n失败项可点击「重置失败」后重试"
                    messagebox.showinfo("完成", body)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # ── 安装指引弹窗（赛博风） ─────────────────────────────────────────────

    def _show_install(self, mode: str = "ocr"):
        w = tk.Toplevel(self)
        w.configure(bg=BG_DEEP)
        w.grab_set()

        if mode == "ocr":
            w.title("⚙ 需要安装 OCR 依赖")
            w.geometry("640x380")
            title    = "[  ⚙  ]  首次使用：安装 OCR 依赖"
            subtitle = "请打开 Terminal（终端）运行以下命令，安装后重启程序"
            cmd_txt  = INSTALL_CMD_OCR
        else:
            w.title("⚙ 需要安装 CAJ 转换依赖")
            w.geometry("640x310")
            title    = "[  ⚙  ]  CAJ 转换：安装 caj2pdf"
            subtitle = "请打开 Terminal（终端）运行以下命令，安装后重新点击转换"
            cmd_txt  = INSTALL_CMD_CAJ

        tk.Frame(w, bg=CYAN, height=2).pack(fill=tk.X)
        tk.Label(w, text=title,
                 font=("Courier", 14, "bold"), fg=CYAN, bg=BG_DEEP,
                 ).pack(pady=(14, 4))
        tk.Label(w, text=subtitle,
                 font=("Helvetica", 11), bg=BG_DEEP, fg=TEXT_MED,
                 ).pack()

        t = tk.Text(w, font=("Courier", 10),
                    bg=BG_DARK, fg=GREEN_N, padx=12, pady=10,
                    relief=tk.FLAT, bd=0, wrap=tk.NONE,
                    insertbackground=CYAN)
        t.pack(fill=tk.X, padx=16, pady=10)
        t.insert("1.0", cmd_txt)
        t.configure(state=tk.DISABLED)

        def copy_cmd():
            w.clipboard_clear()
            w.clipboard_append(cmd_txt)
            messagebox.showinfo("已复制", "命令已复制到剪贴板", parent=w)

        row = tk.Frame(w, bg=BG_DEEP)
        row.pack(pady=6)
        tk.Button(row, text="[ 📋 ] 复制命令", command=copy_cmd,
                  bg=BG_MID, fg=CYAN, relief=tk.FLAT,
                  padx=16, pady=5, font=("Courier", 11), cursor="hand2",
                  highlightbackground=CYAN, highlightthickness=1,
                  ).pack(side=tk.LEFT, padx=6)
        tk.Button(row, text="[ ✕ ] 关闭", command=w.destroy,
                  bg=BG_MID, fg=TEXT_MED, relief=tk.FLAT,
                  padx=16, pady=5, font=("Courier", 11), cursor="hand2",
                  highlightbackground=BORDER, highlightthickness=1,
                  ).pack(side=tk.LEFT, padx=6)

        tk.Frame(w, bg=PINK, height=2).pack(fill=tk.X, side=tk.BOTTOM)


if __name__ == "__main__":
    app = App()
    app.mainloop()

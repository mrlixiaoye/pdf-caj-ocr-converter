# PDF / CAJ 批量 OCR 转换器
### PDF / CAJ Batch OCR Converter

> 将图片型 PDF 和知网 CAJ 文件批量转换为可搜索、可复制的文字 PDF  
> Convert image-based PDFs and CNKI CAJ files into fully searchable, selectable text PDFs — in bulk.

---

## ⬇️ 直接下载 · Direct Download

**[👉 点击此处下载 pdf_ocr_batch.py](https://raw.githubusercontent.com/mrlixiaoye/pdf-caj-ocr-converter/main/pdf_ocr_batch.py)**

下载后在终端运行 `python3 pdf_ocr_batch.py` 即可启动，macOS 用户也可双击 `PDF_OCR_转换器.app`。  
After downloading, run `python3 pdf_ocr_batch.py` in terminal. macOS users can also double-click `PDF_OCR_转换器.app`.

---

## 截图 · Screenshot

![PDF / CAJ 批量 OCR 转换器界面](screenshot.png)

---

## ✨ 功能特性 · Features

| 功能 | Feature |
|------|---------|
| 图片型 PDF → 可搜索文字 PDF | Image PDF → Searchable text PDF |
| 知网 CAJ 格式直接转换 | Direct CNKI CAJ → PDF conversion |
| 批量处理 100+ 文件 | Batch process 100+ files at once |
| 多语言 OCR（中简、中繁、英文、日文） | Multi-language OCR (ZH-S / ZH-T / EN / JA) |
| 多线程并行加速 | Multi-threaded parallel processing |
| 赛博风格图形界面 | Cyberpunk-style GUI |
| 文件夹递归扫描 | Recursive folder scanning |
| 失败自动提示，一键重试 | Auto error prompts, one-click retry |
| macOS 一键启动 .app | macOS one-click `.app` launcher |

---

## 🖥️ 环境要求 · Requirements

- macOS 12+（推荐）/ Windows / Linux
- Python 3.9+

---

## 🚀 安装 · Installation

### 1. 系统依赖 · System dependencies

```bash
# 安装 Homebrew（macOS，已安装可跳过）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Tesseract OCR 引擎（含中文语言包）
brew install tesseract tesseract-lang mupdf-tools
```

### 2. Python 依赖 · Python dependencies

```bash
pip3 install ocrmypdf
```

### 3. CAJ 支持（可选）· CAJ support (optional)

仅在需要转换知网 `.caj` 文件时安装 / Only needed for CNKI `.caj` files:

```bash
git clone https://github.com/caj2pdf/caj2pdf.git ~/caj2pdf
pip3 install imagesize PyPDF2
```

---

## 📖 使用方法 · Usage

```bash
python3 pdf_ocr_batch.py
```

1. **[+] 添加文件** 或 **[⊞] 添加文件夹** 导入 PDF / CAJ 文件  
   Click **[+] Add Files** or **[⊞] Add Folder**
2. 选择 **输出目录** · Choose an **Output Directory**
3. 选择 **识别语言** · Select **OCR Language**
4. 点击 **▶ 开始批量转换** · Click **▶ Start Batch Convert**

---

## 🔧 CAJ 三引擎转换 · 3-Engine CAJ Pipeline

| 优先级 | 引擎 | 说明 |
|--------|------|------|
| 1 | `caj2pdf`（全局命令） | 如已全局安装 |
| 2 | `~/caj2pdf/caj2pdf`（本地克隆） | `git clone` 方式安装 |
| 3 | `mutool`（mupdf-tools） | 备用引擎 |

---

## 📋 版权声明 · License

**该软件版权归 mrlixiaoye 所有，不得商业化。**  
**Copyright © mrlixiaoye. All rights reserved. Commercial use is prohibited.**

本项目供个人学习和研究使用，欢迎免费下载。  
For personal learning and research only. Free to download and use.

---

## 💬 问题反馈 · Issues

如遇问题，欢迎在 [Issues](https://github.com/mrlixiaoye/pdf-caj-ocr-converter/issues) 页面提交反馈。  
For bug reports or feature requests, please open an [Issue](https://github.com/mrlixiaoye/pdf-caj-ocr-converter/issues).

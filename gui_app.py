from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from contextlib import redirect_stderr, redirect_stdout
import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import re
import unicodedata
import traceback

from PIL import Image, ImageTk


CURRENT_DIR = Path(__file__).resolve().parent
MODULE_BASE = CURRENT_DIR
MODULE_CANDIDATES = [CURRENT_DIR, CURRENT_DIR / "search_man"]

for candidate in MODULE_CANDIDATES:
    if (candidate / "extract_ads.py").exists():
        resolved = str(candidate)
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
        MODULE_BASE = candidate
        break

import extract_ads  # type: ignore
import extract_seo  # type: ignore
import transcribe_website  # type: ignore


APP_TITLE = "SearchMan Desktop"
DEFAULT_MODE = "ads"
DEFAULT_GEMINI_MODEL = "models/gemini-2.5-flash"
PIPELINE_SCRIPT_PATH = MODULE_BASE / "run_full_pipeline.py"
PROGRESS_INTERVAL_SECONDS = 5


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    lowered = normalized.lower()
    slug = re.sub(r"[^0-9a-zA-Z一-龥ぁ-んァ-ヶー_]+", "_", lowered).strip("_")
    return slug or "default"


class TextRedirector:
    def __init__(self, widget: tk.Text):
        self.widget = widget

    def write(self, message: str) -> None:
        if not message:
            return
        self.widget.after(0, self._append, message)

    def flush(self) -> None:  # pragma: no cover
        pass

    def _append(self, message: str) -> None:
        self.widget.configure(state="normal")
        self.widget.insert("end", message)
        self.widget.see("end")
        self.widget.configure(state="disabled")


class SearchManApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("720x560")
        self.minsize(560, 480)

        self.mode_var = tk.StringVar(value=DEFAULT_MODE)
        self.keyword_var = tk.StringVar()
        self.seo_limit_var = tk.StringVar(value=str(extract_seo.RESULT_LIMIT))

        self.conversion_var = tk.StringVar()
        self.pipeline_input_mode = tk.StringVar(value="single")
        self.single_url_var = tk.StringVar()
        self.url_file_var = tk.StringVar()
        self.slice_height_var = tk.StringVar(value=str(transcribe_website.SLICE_HEIGHT_DEFAULT))
        self.overlap_var = tk.StringVar(value=str(transcribe_website.SLICE_OVERLAP_DEFAULT))
        self.use_seo_var = tk.BooleanVar(value=False)
        self.use_ads_var = tk.BooleanVar(value=False)
        self.skip_gemini_var = tk.BooleanVar(value=False)
        self.skip_summary_var = tk.BooleanVar(value=False)
        self.gemini_model_var = tk.StringVar(value=DEFAULT_GEMINI_MODEL)
        self.summary_output_var = tk.StringVar()

        self._running = False
        self._worker: threading.Thread | None = None
        self._progress_after_id: str | None = None
        self._progress_elapsed_seconds = 0
        self._progress_label = ""
        self._pipeline_result_paths: dict[str, list[str]] = {
            "transcripts": [],
            "analysis_results": [],
        }
        self._result_image: ImageTk.PhotoImage | None = None
        self._last_pipeline_config: dict[str, object] | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)
        self.container = container

        mode_label = ttk.Label(container, text="モード")
        mode_label.grid(row=0, column=0, sticky="w")

        mode_frame = ttk.Frame(container)
        mode_frame.grid(row=0, column=1, sticky="w")

        ttk.Radiobutton(
            mode_frame,
            text="Search Ads (スポンサー広告)",
            value="ads",
            variable=self.mode_var,
            command=self._on_mode_change,
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frame,
            text="Search SEO (オーガニック上位)",
            value="seo",
            variable=self.mode_var,
            command=self._on_mode_change,
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frame,
            text="フルパイプライン (分析まで)",
            value="pipeline",
            variable=self.mode_var,
            command=self._on_mode_change,
        ).pack(anchor="w")

        self.keyword_label = ttk.Label(container, text="検索キーワード")
        self.keyword_label.grid(row=1, column=0, sticky="w", pady=(12, 0))

        self.keyword_entry = ttk.Entry(container, textvariable=self.keyword_var, width=48)
        self.keyword_entry.grid(row=1, column=1, sticky="we", pady=(12, 0))
        self.keyword_entry.focus_set()

        self.limit_label = ttk.Label(container, text="SEO件数 (1以上の整数)")
        self.limit_entry = ttk.Entry(container, textvariable=self.seo_limit_var, width=12)

        self.conversion_label = ttk.Label(container, text="コンバージョン目標")
        self.conversion_entry = ttk.Entry(container, textvariable=self.conversion_var, width=48)

        self.input_mode_label = ttk.Label(container, text="URL入力方法")
        self.input_mode_frame = ttk.Frame(container)
        ttk.Radiobutton(
            self.input_mode_frame,
            text="単一URLを入力",
            value="single",
            variable=self.pipeline_input_mode,
            command=self._on_pipeline_input_mode_change,
        ).pack(anchor="w")
        ttk.Radiobutton(
            self.input_mode_frame,
            text="URL一覧ファイルを指定",
            value="list",
            variable=self.pipeline_input_mode,
            command=self._on_pipeline_input_mode_change,
        ).pack(anchor="w")

        self.single_url_label = ttk.Label(container, text="URL")
        self.single_url_entry = ttk.Entry(container, textvariable=self.single_url_var, width=60)

        self.url_file_label = ttk.Label(container, text="URLリストファイル")
        self.url_file_frame = ttk.Frame(container)
        self.url_file_entry = ttk.Entry(self.url_file_frame, textvariable=self.url_file_var, width=44)
        self.url_file_entry.pack(side="left", fill="x", expand=True)
        self.url_file_button = ttk.Button(self.url_file_frame, text="参照...", command=self._browse_url_file)
        self.url_file_button.pack(side="left", padx=(6, 0))

        self.slice_label = ttk.Label(container, text="スクリーンショット設定")
        self.slice_frame = ttk.Frame(container)
        ttk.Label(self.slice_frame, text="高さ(px)").pack(side="left")
        self.slice_height_entry = ttk.Entry(self.slice_frame, textvariable=self.slice_height_var, width=8)
        self.slice_height_entry.pack(side="left", padx=(4, 12))
        ttk.Label(self.slice_frame, text="重なり(px)").pack(side="left")
        self.overlap_entry = ttk.Entry(self.slice_frame, textvariable=self.overlap_var, width=8)
        self.overlap_entry.pack(side="left", padx=(4, 0))

        self.options_label = ttk.Label(container, text="オプション")
        self.options_frame = ttk.Frame(container)
        self.use_seo_check = ttk.Checkbutton(
            self.options_frame,
            text="SEO上位サイトも分析に追加",
            variable=self.use_seo_var,
            command=self._on_use_seo_toggle,
        )
        self.use_seo_check.pack(anchor="w")
        self.use_ads_check = ttk.Checkbutton(
            self.options_frame,
            text="スポンサー広告URLも分析に追加",
            variable=self.use_ads_var,
        )
        self.use_ads_check.pack(anchor="w")
        self.skip_gemini_check = ttk.Checkbutton(
            self.options_frame,
            text="Gemini分析をスキップ",
            variable=self.skip_gemini_var,
            command=self._on_skip_gemini_toggle,
        )
        self.skip_gemini_check.pack(anchor="w")
        self.skip_summary_check = ttk.Checkbutton(
            self.options_frame,
            text="統合レポート生成をスキップ",
            variable=self.skip_summary_var,
            command=self._on_skip_summary_toggle,
        )
        self.skip_summary_check.pack(anchor="w")

        self.gemini_model_label = ttk.Label(container, text="GeminiモデルID")
        self.gemini_model_entry = ttk.Entry(container, textvariable=self.gemini_model_var, width=48)

        self.summary_output_label = ttk.Label(container, text="統合レポート出力先 (任意)")
        self.summary_output_frame = ttk.Frame(container)
        self.summary_output_entry = ttk.Entry(self.summary_output_frame, textvariable=self.summary_output_var, width=44)
        self.summary_output_entry.pack(side="left", fill="x", expand=True)
        self.summary_output_button = ttk.Button(
            self.summary_output_frame,
            text="参照...",
            command=self._browse_summary_output,
        )
        self.summary_output_button.pack(side="left", padx=(6, 0))

        self.button_frame = ttk.Frame(container)
        self.button_frame.grid(row=11, column=0, columnspan=2, pady=(18, 12), sticky="we")
        self.run_button = ttk.Button(self.button_frame, text="実行", command=self.start_task)
        self.run_button.pack(side="left")
        self.stop_button = ttk.Button(
            self.button_frame,
            text="キャンセル",
            command=self.cancel_task,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(12, 0))

        status_frame = ttk.Frame(container)
        status_frame.grid(row=12, column=0, columnspan=2, sticky="we")
        ttk.Label(status_frame, text="ステータス").pack(side="left")
        self.status_var = tk.StringVar(value="待機中")
        self.status_value_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_value_label.pack(side="left", padx=(6, 0))

        self.notebook = ttk.Notebook(container)
        self.notebook.grid(row=13, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
        self.log_tab = ttk.Frame(self.notebook)
        self.result_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.log_tab, text="ログ")
        self.notebook.add(self.result_tab, text="結果")

        self.log_widget = tk.Text(self.log_tab, wrap="word", state="disabled")
        self.log_widget.pack(side="left", fill="both", expand=True)
        log_scrollbar = ttk.Scrollbar(self.log_tab, orient="vertical", command=self.log_widget.yview)
        self.log_widget.configure(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side="right", fill="y")

        self.result_summary_var = tk.StringVar(value="まだ結果はありません。")
        ttk.Label(
            self.result_tab,
            textvariable=self.result_summary_var,
            wraplength=560,
        ).pack(anchor="w", padx=8, pady=(8, 6))

        analysis_frame = ttk.LabelFrame(self.result_tab, text="Gemini分析結果")
        analysis_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.analysis_text = tk.Text(analysis_frame, wrap="word", state="disabled")
        self.analysis_text.pack(side="left", fill="both", expand=True)
        analysis_scrollbar = ttk.Scrollbar(analysis_frame, orient="vertical", command=self.analysis_text.yview)
        self.analysis_text.configure(yscrollcommand=analysis_scrollbar.set)
        analysis_scrollbar.pack(side="right", fill="y")

        screenshot_frame = ttk.LabelFrame(self.result_tab, text="スクリーンショット (縮小表示)")
        screenshot_frame.pack(fill="both", expand=False, padx=8, pady=(0, 8))
        self.image_label = ttk.Label(screenshot_frame, text="スクリーンショットはまだありません。", anchor="center")
        self.image_label.pack(fill="both", expand=True)

        container.columnconfigure(1, weight=1)
        container.rowconfigure(13, weight=1)

        self.pipeline_layout = {
            self.conversion_label: {"row": 3, "column": 0, "sticky": "w", "pady": (12, 0)},
            self.conversion_entry: {"row": 3, "column": 1, "sticky": "we", "pady": (12, 0)},
            self.input_mode_label: {"row": 4, "column": 0, "sticky": "w", "pady": (12, 0)},
            self.input_mode_frame: {"row": 4, "column": 1, "sticky": "w", "pady": (12, 0)},
            self.single_url_label: {"row": 5, "column": 0, "sticky": "w", "pady": (12, 0)},
            self.single_url_entry: {"row": 5, "column": 1, "sticky": "we", "pady": (12, 0)},
            self.url_file_label: {"row": 6, "column": 0, "sticky": "w", "pady": (12, 0)},
            self.url_file_frame: {"row": 6, "column": 1, "sticky": "we", "pady": (12, 0)},
            self.slice_label: {"row": 7, "column": 0, "sticky": "w", "pady": (12, 0)},
            self.slice_frame: {"row": 7, "column": 1, "sticky": "w", "pady": (12, 0)},
            self.options_label: {"row": 8, "column": 0, "sticky": "w", "pady": (12, 0)},
            self.options_frame: {"row": 8, "column": 1, "sticky": "we", "pady": (12, 0)},
            self.gemini_model_label: {"row": 9, "column": 0, "sticky": "w", "pady": (12, 0)},
            self.gemini_model_entry: {"row": 9, "column": 1, "sticky": "we", "pady": (12, 0)},
            self.summary_output_label: {"row": 10, "column": 0, "sticky": "w", "pady": (12, 0)},
            self.summary_output_frame: {"row": 10, "column": 1, "sticky": "we", "pady": (12, 0)},
        }

        self._hide_pipeline_options()
        self._toggle_seo_limit_visibility(False)
        self._on_mode_change()
        self._clear_result_display()

    def _start_progress_indicator(self, label: str) -> None:
        if self._progress_after_id:
            return
        self._progress_label = label
        self._progress_elapsed_seconds = 0
        self._append_log(f"… {label}を開始しました。ログは順次表示されます。\n")
        self._progress_after_id = self.after(PROGRESS_INTERVAL_SECONDS * 1000, self._progress_tick)

    def _progress_tick(self) -> None:
        if not self._running:
            self._stop_progress_indicator()
            return
        self._progress_elapsed_seconds += PROGRESS_INTERVAL_SECONDS
        minutes, seconds = divmod(self._progress_elapsed_seconds, 60)
        timestamp = f"{minutes:02d}:{seconds:02d}"
        self._append_log(f"… {self._progress_label}継続中 ({timestamp})\n")
        self._progress_after_id = self.after(PROGRESS_INTERVAL_SECONDS * 1000, self._progress_tick)

    def _stop_progress_indicator(self) -> None:
        if self._progress_after_id:
            self.after_cancel(self._progress_after_id)
            self._progress_after_id = None
        self._progress_elapsed_seconds = 0
        self._progress_label = ""

    def _update_status(self, text: str) -> None:
        self.status_var.set(text)

    def _clear_result_display(self) -> None:
        if hasattr(self, "analysis_text"):
            self.analysis_text.configure(state="normal")
            self.analysis_text.delete("1.0", "end")
            self.analysis_text.insert("1.0", "結果はまだありません。")
            self.analysis_text.configure(state="disabled")
        if hasattr(self, "image_label"):
            self.image_label.configure(image="", text="スクリーンショットはまだありません。")
        self._result_image = None

    def start_task(self) -> None:
        if self._running:
            return

        keyword = self.keyword_var.get().strip()
        if not keyword:
            messagebox.showwarning(APP_TITLE, "検索キーワードを入力してください。")
            return

        mode = self.mode_var.get()
        task_config: dict[str, object] | None

        if mode == "ads":
            task_config = {"mode": "ads", "keyword": keyword}
        elif mode == "seo":
            seo_limit = self._parse_int(self.seo_limit_var.get(), "SEO件数", minimum=1)
            if seo_limit is None:
                return
            task_config = {"mode": "seo", "keyword": keyword, "seo_limit": seo_limit}
        else:
            task_config = self._collect_pipeline_config(keyword)
            if task_config is None:
                return

        self._update_status("処理を準備しています…")
        self._set_running(True)
        self._append_log("========================================\n")

        if mode == "ads":
            self._append_log("モード: Ads抽出\n")
            self._append_log(f"キーワード: {keyword}\n")
            self._update_status("スポンサー広告を抽出しています…")
        elif mode == "seo":
            self._append_log("モード: SEO抽出\n")
            self._append_log(f"キーワード: {keyword}\n")
            self._append_log(f"取得件数: {task_config['seo_limit']}\n")
            self._update_status("SEO検索結果を収集中…")
        else:
            cfg = task_config
            self._append_log("モード: フルパイプライン\n")
            self._append_log(f"キーワード: {keyword}\n")
            self._append_log(f"コンバージョン目標: {cfg['conversion_goal']}\n")
            if cfg["input_mode"] == "single":
                url_value = cfg.get("url")
                self._append_log(f"URL: {url_value or '（指定なし）'}\n")
            else:
                url_list_value = cfg.get("url_list")
                self._append_log(f"URLリスト: {url_list_value or '（指定なし）'}\n")
            seo_info = "有効" if cfg["use_seo"] else "無効"
            if cfg["use_seo"]:
                seo_info += f" (最大{cfg['seo_limit']}件)"
            self._append_log(f"SEO抽出: {seo_info}\n")
            ads_info = "有効" if cfg["use_ads"] else "無効"
            self._append_log(f"広告URL追加: {ads_info}\n")
            gemini_info = "スキップ" if cfg["skip_gemini"] else cfg["gemini_model"]
            self._append_log(f"Gemini: {gemini_info}\n")
            self._append_log(f"統合レポート: {'生成しない' if cfg['skip_summary'] else '生成する'}\n")
            self._clear_result_display()
            self.result_summary_var.set("処理中の結果を準備しています…")
            self._start_progress_indicator("フルパイプライン処理")
            self._update_status("フルパイプライン処理を開始しました…")

        self._append_log("処理を開始します...\n\n")

        self._worker = threading.Thread(target=self._execute_task, args=(task_config,), daemon=True)
        self._worker.start()

    def cancel_task(self) -> None:
        if not self._running:
            return
        messagebox.showinfo(
            APP_TITLE,
            "現在の処理はPlaywright実行中のため強制停止できません。\nブラウザを閉じて処理終了をお待ちください。",
        )

    def _execute_task(self, config: dict[str, object]) -> None:
        logger = TextRedirector(self.log_widget)
        mode = config["mode"]

        try:
            if mode == "pipeline":
                success = self._run_full_pipeline_task(config, logger)
                if success:
                    self.after(0, lambda: messagebox.showinfo(APP_TITLE, "処理が完了しました。"))
                    self.after(0, lambda: self._update_status("完了しました。"))
                else:
                    self.after(0, lambda: messagebox.showerror(APP_TITLE, "エラーが発生しました。ログを確認してください。"))
                    self.after(0, lambda: self._update_status("エラーが発生しました。"))
            else:
                with redirect_stdout(logger), redirect_stderr(logger):
                    keyword = config["keyword"]
                    keyword_slug = slugify(keyword)
                    if mode == "ads":
                        print("▶ スポンサー広告抽出を開始します。")
                        ads_results = extract_ads.extract_sponsored_ads(keyword=keyword)
                        markdown_path = extract_ads.save_to_markdown(ads_results, keyword)
                        print("\n📁 出力ファイル:")
                        print(f"  - {markdown_path}")
                    else:
                        limit = config["seo_limit"]
                        print(f"▶ オーガニック検索結果を上位{limit}件抽出します。")
                        seo_results = extract_seo.extract_organic_results(
                            keyword=keyword,
                            limit=limit,
                            keyword_slug=keyword_slug,
                        )
                        markdown_path = extract_seo.save_to_markdown(
                            seo_results,
                            keyword=keyword,
                            keyword_slug=keyword_slug,
                        )
                        output_dir = Path(markdown_path).parent
                        screenshot_path = output_dir / "search_result_seo.png"
                        print("\n📁 出力ファイル:")
                        print(f"  - {markdown_path}")
                        if screenshot_path.exists():
                            print(f"  - {screenshot_path}")
                    print("\n✅ 処理が完了しました。")
                    self.after(0, lambda: messagebox.showinfo(APP_TITLE, "処理が完了しました。"))
                    self.after(0, lambda: self._update_status("完了しました。"))
        except Exception:
            error_text = traceback.format_exc()
            logger.write("\n❌ エラーが発生しました。\n")
            logger.write(error_text)
            self.after(0, lambda: messagebox.showerror(APP_TITLE, "エラーが発生しました。ログを確認してください。"))
            self.after(0, lambda: self._update_status("エラーが発生しました。"))
        finally:
            self.after(0, lambda: self._set_running(False))

    def _run_full_pipeline_task(self, config: dict[str, object], logger: TextRedirector) -> bool:
        if not PIPELINE_SCRIPT_PATH.exists():
            logger.write("❌ run_full_pipeline.py が見つかりません。\n")
            return False

        self._last_pipeline_config = dict(config)
        self._pipeline_result_paths = {"transcripts": [], "analysis_results": []}
        temp_url_file_path: Path | None = None

        manual_text = ""
        if config["input_mode"] == "single":
            url_value = config.get("url")
            if url_value:
                manual_text = f"{url_value}\n"
        else:
            url_list_value = config.get("url_list")
            if url_list_value:
                try:
                    manual_text = Path(str(url_list_value)).read_text(encoding="utf-8")
                except Exception as error:
                    logger.write(f"⚠️ URL一覧ファイルの読み込みに失敗しました: {error}\n")
                    manual_text = ""

        ads_url_count = 0
        if config["use_ads"]:
            self.after(0, lambda: self._update_status("スポンサー広告を抽出しています…"))
            logger.write("▶ スポンサー広告からURLを抽出します。\n")
            ads_results = []
            markdown_path: Path | None = None
            try:
                with redirect_stdout(logger), redirect_stderr(logger):
                    ads_results = extract_ads.extract_sponsored_ads(keyword=config["keyword"])
                    markdown_path = extract_ads.save_to_markdown(ads_results, config["keyword"])
            except Exception as error:
                logger.write(f"⚠️ 広告抽出に失敗しました: {error}\n")
            else:
                if markdown_path:
                    logger.write(f"  - 広告レポート: {markdown_path}\n")
                seen_urls: set[str] = set()
                ad_urls: list[str] = []
                for ad in ads_results:
                    url = (ad.get("url") or "").strip()
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        ad_urls.append(url)
                ads_url_count = len(ad_urls)
                logger.write(f"  - 追加URL数: {ads_url_count}\n")
                if ad_urls:
                    combined_text = manual_text
                    if combined_text and not combined_text.endswith("\n"):
                        combined_text += "\n"
                    combined_text += "\n".join(ad_urls) + "\n"
                    try:
                        temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
                        temp_file.write(combined_text)
                        temp_file.flush()
                        temp_file.close()
                        temp_url_file_path = Path(temp_file.name)
                        config["temp_url_file"] = temp_url_file_path
                        logger.write(f"  - URL追加用一時ファイル: {temp_url_file_path}\n")
                    except Exception as error:
                        logger.write(f"⚠️ 広告URLの一時ファイル作成に失敗しました: {error}\n")
                else:
                    logger.write("  - 追加可能な広告URLはありませんでした。\n")

        config["ads_url_count"] = ads_url_count

        url_list_for_command = config.get("temp_url_file") or config.get("url_list")
        url_single_for_command = None
        if config["input_mode"] == "single":
            url_single_for_command = config.get("url")

        if url_list_for_command:
            url_arg = ["--url-list", str(url_list_for_command)]
        elif url_single_for_command:
            url_arg = ["--url", str(url_single_for_command)]
        else:
            url_arg = []

        if not url_arg and not config["use_seo"]:
            logger.write("❌ 処理対象となるURLがありません。広告抽出でもURLが見つかりませんでした。\n")
            if temp_url_file_path and temp_url_file_path.exists():
                try:
                    temp_url_file_path.unlink()
                except OSError:
                    pass
            self.after(0, lambda: self.result_summary_var.set("処理対象URLがありませんでした。"))
            return False

        command: list[str] = [
            sys.executable,
            str(PIPELINE_SCRIPT_PATH),
            "--keyword",
            str(config["keyword"]),
            "--conversion-goal",
            str(config["conversion_goal"]),
            "--slice-height",
            str(config["slice_height"]),
            "--overlap",
            str(config["overlap"]),
            "--gemini-model",
            str(config["gemini_model"]),
        ]

        if url_arg:
            command.extend(url_arg)

        if config["use_seo"]:
            command.append("--use-seo")
            command.extend(["--seo-limit", str(config["seo_limit"])])

        if config["skip_gemini"]:
            command.append("--skip-gemini")

        if config["skip_summary"]:
            command.append("--skip-summary")

        summary_output = str(config.get("summary_output") or "").strip()
        if summary_output:
            command.extend(["--summary-output", summary_output])

        logger.write("▶ フルパイプライン処理を開始します。\n")
        logger.write(f"  - 実行ディレクトリ: {MODULE_BASE}\n")
        logger.write("  - 実行コマンド: " + " ".join(command) + "\n\n")

        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        self.after(0, lambda: self._update_status("URLを解析中…"))

        try:
            process = subprocess.Popen(
                command,
                cwd=str(MODULE_BASE),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
        except Exception:
            logger.write("❌ サブプロセスの起動に失敗しました。\n")
            logger.write(traceback.format_exc())
            if temp_url_file_path and temp_url_file_path.exists():
                try:
                    temp_url_file_path.unlink()
                except OSError:
                    pass
            return False

        try:
            assert process.stdout is not None
            with process.stdout:
                for line in process.stdout:
                    logger.write(line)
                    self._process_pipeline_stdout_line(line)

            return_code = process.wait()
            if return_code == 0:
                ads_count = config.get("ads_url_count", 0)
                if ads_count:
                    logger.write(f"\n✅ 広告経由で追加したURL数: {ads_count}\n")
                logger.write("\n✅ フルパイプライン処理が完了しました。\n")
                self.after(0, self._display_pipeline_results)
                return True

            logger.write(f"\n❌ フルパイプライン処理が異常終了しました (exit code {return_code}).\n")
            self.after(0, lambda: self.result_summary_var.set("今回の実行はエラーで終了しました。ログを確認してください。"))
            return False
        finally:
            temp_path = config.get("temp_url_file")
            if isinstance(temp_path, Path):
                cleanup_target = temp_path
            elif temp_path:
                cleanup_target = Path(str(temp_path))
            else:
                cleanup_target = temp_url_file_path
            if cleanup_target and cleanup_target.exists():
                try:
                    cleanup_target.unlink()
                except OSError:
                    pass

    def _process_pipeline_stdout_line(self, line: str) -> None:
        stripped = line.strip()
        if not stripped:
            return

        normalized = stripped.lstrip("-•").strip()

        if "の処理を開始します" in stripped:
            message = normalized
            self.after(0, lambda msg=message: self._update_status(msg))
        elif "Gemini によるマーケティング分析が完了しました" in stripped:
            self.after(0, lambda: self._update_status("Gemini分析が完了しました。"))
        elif "Gemini による分析に失敗しました" in stripped:
            self.after(0, lambda: self._update_status("Gemini分析でエラーが発生しました。"))
        elif "文字起こしとプロンプト生成が完了しました" in stripped:
            self.after(0, lambda: self._update_status("文字起こしとプロンプト生成が完了しました。"))

        if normalized.startswith("文字起こし Markdown:"):
            path = normalized.split(":", 1)[1].strip()
            if path and path not in self._pipeline_result_paths["transcripts"]:
                self._pipeline_result_paths["transcripts"].append(path)
        elif normalized.startswith("Gemini 分析結果:"):
            path = normalized.split(":", 1)[1].strip()
            if path and "生成されていません" not in path:
                if path not in self._pipeline_result_paths["analysis_results"]:
                    self._pipeline_result_paths["analysis_results"].append(path)

    def _display_pipeline_results(self) -> None:
        transcripts = [Path(p) for p in self._pipeline_result_paths.get("transcripts", []) if p]
        analysis_paths = [Path(p) for p in self._pipeline_result_paths.get("analysis_results", []) if p]

        transcripts = [p for p in transcripts if p.exists()]
        analysis_paths = [p for p in analysis_paths if p.exists()]

        run_dir: Path | None = None
        if analysis_paths:
            run_dir = analysis_paths[-1].parent
        elif transcripts:
            run_dir = transcripts[-1].parent

        if run_dir is None:
            self.result_summary_var.set("今回の実行で表示可能な結果が見つかりませんでした。")
        else:
            summary_parts = [f"最新の出力ディレクトリ: {run_dir}"]
            if transcripts:
                summary_parts.append(f"文字起こし: {len(transcripts)}件")
            if analysis_paths:
                summary_parts.append(f"Gemini分析: {len(analysis_paths)}件")
            elif self._last_pipeline_config and self._last_pipeline_config.get("skip_gemini"):
                summary_parts.append("Gemini分析: スキップ設定")
            self.result_summary_var.set(" / ".join(summary_parts))

        if analysis_paths:
            latest_analysis = analysis_paths[-1]
            try:
                content = latest_analysis.read_text(encoding="utf-8")
            except Exception as error:
                content = f"analysis_result_gemini.md を読み込めませんでした: {error}"
        else:
            if self._last_pipeline_config and self._last_pipeline_config.get("skip_gemini"):
                content = "今回の実行ではGemini分析をスキップしました。"
            else:
                content = "Geminiの分析結果が見つかりませんでした。"

        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("1.0", content)
        self.analysis_text.configure(state="disabled")

        screenshot_path: Path | None = None
        if run_dir is not None:
            candidate = run_dir / "full_page.png"
            if candidate.exists():
                screenshot_path = candidate
            else:
                png_candidates = sorted(run_dir.glob("*.png"))
                if png_candidates:
                    screenshot_path = png_candidates[0]

        if screenshot_path and screenshot_path.exists():
            try:
                with Image.open(screenshot_path) as img:
                    max_size = (560, 560)
                    img.thumbnail(max_size, Image.LANCZOS)
                    self._result_image = ImageTk.PhotoImage(img)
            except Exception as error:
                self._result_image = None
                self.image_label.configure(image="", text=f"スクリーンショットを読み込めませんでした: {error}")
            else:
                self.image_label.configure(image=self._result_image, text="")
        else:
            self._result_image = None
            self.image_label.configure(image="", text="スクリーンショットが見つかりませんでした。")

        self.notebook.select(self.result_tab)

    def _collect_pipeline_config(self, keyword: str) -> dict[str, object] | None:
        conversion_goal = self.conversion_var.get().strip()
        if not conversion_goal:
            messagebox.showerror(APP_TITLE, "コンバージョン目標を入力してください。")
            return None

        input_mode = self.pipeline_input_mode.get()
        config: dict[str, object] = {
            "mode": "pipeline",
            "keyword": keyword,
            "conversion_goal": conversion_goal,
            "input_mode": input_mode,
            "use_seo": self.use_seo_var.get(),
            "use_ads": self.use_ads_var.get(),
            "skip_gemini": self.skip_gemini_var.get(),
            "skip_summary": self.skip_summary_var.get(),
        }

        if input_mode == "single":
            url = self.single_url_var.get().strip()
            if url:
                config["url"] = url
            elif not (config["use_seo"] or config["use_ads"]):
                messagebox.showerror(APP_TITLE, "URLを入力するか、SEO/Adsの自動取得を有効にしてください。")
                return None
        else:
            path_str = self.url_file_var.get().strip()
            if path_str:
                path = Path(path_str).expanduser()
                if not path.exists():
                    messagebox.showerror(APP_TITLE, f"指定したファイルが見つかりません: {path}")
                    return None
                config["url_list"] = str(path)
            elif not (config["use_seo"] or config["use_ads"]):
                messagebox.showerror(APP_TITLE, "URL一覧ファイルを指定するか、SEO/Adsの自動取得を有効にしてください。")
                return None

        slice_height = self._parse_int(self.slice_height_var.get(), "スクリーンショット高さ", minimum=1)
        if slice_height is None:
            return None
        overlap = self._parse_int(self.overlap_var.get(), "スクリーンショット重なり", minimum=0)
        if overlap is None:
            return None

        config["slice_height"] = slice_height
        config["overlap"] = overlap

        if config["use_seo"]:
            seo_limit = self._parse_int(self.seo_limit_var.get(), "SEO件数", minimum=1)
            if seo_limit is None:
                return None
            config["seo_limit"] = seo_limit

        gemini_model = self.gemini_model_var.get().strip()
        if not config["skip_gemini"] and not gemini_model:
            messagebox.showerror(APP_TITLE, "GeminiモデルIDを入力してください。")
            return None
        config["gemini_model"] = gemini_model or DEFAULT_GEMINI_MODEL

        summary_output = self.summary_output_var.get().strip()
        if summary_output:
            config["summary_output"] = str(Path(summary_output).expanduser())

        return config

    def _parse_int(self, value: str, label: str, minimum: int) -> int | None:
        try:
            number = int(value)
        except ValueError:
            messagebox.showerror(APP_TITLE, f"{label}には整数を入力してください。")
            return None
        if number < minimum:
            messagebox.showerror(APP_TITLE, f"{label}には{minimum}以上の値を入力してください。")
            return None
        return number

    def _set_running(self, running: bool) -> None:
        self._running = running
        state = "disabled" if running else "normal"
        self.run_button.configure(state=state)
        self.stop_button.configure(state="normal" if running else "disabled")
        if not running:
            self._stop_progress_indicator()

    def _toggle_seo_limit_visibility(self, show: bool) -> None:
        if show:
            self.limit_label.grid(row=2, column=0, sticky="w", pady=(12, 0))
            self.limit_entry.grid(row=2, column=1, sticky="w", pady=(12, 0))
            self.limit_entry.configure(state="normal")
        else:
            self.limit_label.grid_remove()
            self.limit_entry.grid_remove()

    def _show_pipeline_options(self) -> None:
        for widget, options in self.pipeline_layout.items():
            widget.grid(**options)

    def _hide_pipeline_options(self) -> None:
        for widget in self.pipeline_layout:
            widget.grid_remove()

    def _on_mode_change(self) -> None:
        mode = self.mode_var.get()
        if mode == "ads":
            self._hide_pipeline_options()
            self._toggle_seo_limit_visibility(False)
        elif mode == "seo":
            self._hide_pipeline_options()
            self._toggle_seo_limit_visibility(True)
        else:
            self._show_pipeline_options()
            self._toggle_seo_limit_visibility(self.use_seo_var.get())
            self._on_pipeline_input_mode_change()
            self._on_skip_gemini_toggle()
            self._on_skip_summary_toggle()

    def _on_pipeline_input_mode_change(self) -> None:
        single = self.pipeline_input_mode.get() == "single"
        state_single = "normal" if single else "disabled"
        state_list = "disabled" if single else "normal"
        self.single_url_entry.configure(state=state_single)
        self.url_file_entry.configure(state=state_list)
        self.url_file_button.configure(state=state_list)

    def _on_use_seo_toggle(self) -> None:
        if self.mode_var.get() == "pipeline":
            self._toggle_seo_limit_visibility(self.use_seo_var.get())

    def _on_skip_gemini_toggle(self) -> None:
        state = "disabled" if self.skip_gemini_var.get() else "normal"
        self.gemini_model_entry.configure(state=state)

    def _on_skip_summary_toggle(self) -> None:
        state = "disabled" if self.skip_summary_var.get() else "normal"
        self.summary_output_entry.configure(state=state)
        self.summary_output_button.configure(state=state)

    def _browse_url_file(self) -> None:
        path = filedialog.askopenfilename(
            title="URL一覧ファイルを選択",
            filetypes=[("テキストファイル", "*.txt *.md *.csv"), ("すべてのファイル", "*.*")],
        )
        if path:
            self.url_file_var.set(path)

    def _browse_summary_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="統合レポートの保存先を選択",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("テキストファイル", "*.txt"), ("すべてのファイル", "*.*")],
        )
        if path:
            self.summary_output_var.set(path)

    def _append_log(self, message: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message)
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")


def main() -> None:
    app = SearchManApp()
    app.mainloop()


if __name__ == "__main__":
    main()

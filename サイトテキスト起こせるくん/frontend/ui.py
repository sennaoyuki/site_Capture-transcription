"""TkinterベースのシンプルなGUI実装。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List

from backend.config import AppConfig
from backend.processor import TranscriptionProcessor


class Application(tk.Tk):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.title("サイトテキスト起こせるくん")
        self.geometry("820x620")
        self.config = config
        self.processor = TranscriptionProcessor(config)
        self.queue: queue.Queue = queue.Queue()
        self.urls: List[str] = []
        self._build_widgets()
        self._poll_queue()

    def _build_widgets(self) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # URL入力
        input_frame = ttk.LabelFrame(main_frame, text="URL入力")
        input_frame.pack(fill=tk.X, pady=5)

        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(input_frame, textvariable=self.url_var)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5), pady=8)

        add_button = ttk.Button(input_frame, text="追加", command=self._add_url)
        add_button.pack(side=tk.LEFT, padx=(0, 5))

        file_button = ttk.Button(input_frame, text="ファイル読込", command=self._load_file)
        file_button.pack(side=tk.LEFT)

        # URLリスト
        list_frame = ttk.LabelFrame(main_frame, text="処理対象URL")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.url_listbox = tk.Listbox(list_frame, height=8)
        self.url_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.url_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.url_listbox.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(list_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        remove_button = ttk.Button(button_frame, text="選択削除", command=self._remove_selected)
        remove_button.pack(side=tk.LEFT, padx=5)
        clear_button = ttk.Button(button_frame, text="全削除", command=self._clear_list)
        clear_button.pack(side=tk.LEFT)

        # 実行ボタンと進捗
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)

        self.start_button = ttk.Button(action_frame, text="処理開始", command=self._start_processing)
        self.start_button.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(action_frame, length=300)
        self.progress.pack(side=tk.LEFT, padx=(15, 0))

        # ログ表示
        log_frame = ttk.LabelFrame(main_frame, text="ログ")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, state=tk.DISABLED, height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _add_url(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            return
        self.urls.append(url)
        self.url_listbox.insert(tk.END, url)
        self.url_var.set("")

    def _load_file(self) -> None:
        path = filedialog.askopenfilename(
            title="URLリストを選択",
            filetypes=[("テキストファイル", "*.txt"), ("CSV", "*.csv"), ("すべてのファイル", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fp:
                lines = [line.strip() for line in fp if line.strip()]
        except OSError as exc:
            messagebox.showerror("読み込みエラー", f"ファイルを読み込めませんでした: {exc}")
            return
        for line in lines:
            self.urls.append(line)
            self.url_listbox.insert(tk.END, line)

    def _remove_selected(self) -> None:
        selection = list(self.url_listbox.curselection())
        if not selection:
            return
        for index in reversed(selection):
            self.url_listbox.delete(index)
            self.urls.pop(index)

    def _clear_list(self) -> None:
        self.url_listbox.delete(0, tk.END)
        self.urls.clear()

    def _start_processing(self) -> None:
        if not self.urls:
            messagebox.showinfo("情報", "URLを追加してください")
            return
        self.start_button.config(state=tk.DISABLED)
        self.progress.config(maximum=len(self.urls) * 2, value=0)
        worker = threading.Thread(target=self._process_worker, daemon=True)
        worker.start()

    def _process_worker(self) -> None:
        def progress_callback(message: str) -> None:
            self.queue.put(("progress", message))

        try:
            results = self.processor.process(self.urls, on_progress=progress_callback)
            self.queue.put(("done", results))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.queue.get_nowait()
                self._handle_queue_item(item)
        except queue.Empty:
            pass
        finally:
            self.after(200, self._poll_queue)

    def _handle_queue_item(self, item) -> None:
        kind = item[0]
        if kind == "progress":
            message = item[1]
            self._append_log(message)
            current = self.progress.cget("value")
            self.progress.config(value=current + 1)
        elif kind == "done":
            results = item[1]
            self._append_log("すべての処理が完了しました")
            for result in results:
                self._append_log(f"{result.url} -> {result.text_output}")
            self.start_button.config(state=tk.NORMAL)
        elif kind == "error":
            message = item[1]
            self._append_log(f"エラー: {message}")
            messagebox.showerror("エラー", message)
            self.start_button.config(state=tk.NORMAL)

    def _append_log(self, message: str) -> None:
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)


def run_app(config: AppConfig) -> None:
    app = Application(config)
    app.mainloop()

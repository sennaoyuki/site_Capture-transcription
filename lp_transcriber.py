"""
LP文字起こしGUIアプリケーション
オンライン上のLP URLまたはローカルに保存したHTMLを対象にスクリーンショット取得と文字起こしを実行します。
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from PIL import Image, ImageTk
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_AVAILABLE = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    TKDND_AVAILABLE = False
import threading
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

# transcribe_websiteモジュールをインポート
sys.path.insert(0, str(Path(__file__).resolve().parent / "search_man copy"))
import transcribe_website


class LPTranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("✨ LP文字起こしツール")
        self.root.geometry("950x750")
        self.root.minsize(700, 500)

        self.dnd_enabled = False
        self._dnd_warning: Optional[str] = None
        
        # モダンなカラースキーム（グラデーションとニュートラルトーン）
        self.colors = {
            'bg': '#F8F9FA',
            'bg_secondary': '#FFFFFF',
            'card_bg': '#FFFFFF',
            'primary': '#5B7FFF',
            'primary_hover': '#4C6FE8',
            'primary_light': '#E8EEFF',
            'success': '#10B981',
            'success_light': '#D1FAE5',
            'warning': '#F59E0B',
            'error': '#EF4444',
            'text': '#1A1A1A',
            'text_secondary': '#6B7280',
            'text_light': '#9CA3AF',
            'border': '#E5E7EB',
            'border_focus': '#5B7FFF',
            'shadow': 'rgba(0, 0, 0, 0.08)',
            'shadow_hover': 'rgba(0, 0, 0, 0.12)'
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # モダンなスタイル設定
        style = ttk.Style()
        style.theme_use('clam')
        
        # タイトルスタイル
        style.configure('Title.TLabel',
                       font=('Helvetica Neue', 32, 'bold'),
                       foreground=self.colors['text'],
                       background=self.colors['bg'])
        
        # カードスタイル
        style.configure('Card.TFrame',
                       background=self.colors['card_bg'],
                       relief='flat')
        
        # ラベルスタイル
        style.configure('TLabel',
                       background=self.colors['card_bg'],
                       foreground=self.colors['text'],
                       font=('SF Pro Text', 11))
        
        # エントリースタイル
        style.configure('TEntry',
                       fieldbackground='white',
                       borderwidth=1,
                       relief='solid')
        
        # プライマリボタン
        style.configure('Primary.TButton',
                       font=('SF Pro Text', 12, 'bold'),
                       background=self.colors['primary'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       padding=(20, 10))
        style.map('Primary.TButton',
                 background=[('active', self.colors['primary_hover'])])
        
        # 通常ボタン
        style.configure('TButton',
                       font=('SF Pro Text', 11),
                       borderwidth=1,
                       relief='flat',
                       padding=(12, 6))
        
        # プログレスバー
        style.configure('TProgressbar',
                       background=self.colors['primary'],
                       troughcolor=self.colors['border'],
                       borderwidth=0,
                       thickness=8)

        self.input_mode_var = tk.StringVar(value="url")
        self.local_path_var = tk.StringVar()
        
        # メインコンテナ（シンプルな構造に変更）
        main_frame = tk.Frame(root, bg=self.colors['bg'])
        main_frame.pack(fill="both", expand=True, padx=40, pady=32)
        
        # ヘッダー
        header_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        header_frame.pack(fill="x", pady=(0, 40))
        
        title_label = ttk.Label(
            header_frame,
            text="✨ LP文字起こしツール",
            style='Title.TLabel'
        )
        title_label.pack(anchor="w")
        
        subtitle = tk.Label(
            header_frame,
            text="URLやローカルHTMLから簡単に文字起こし",
            font=('Helvetica Neue', 14),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg']
        )
        subtitle.pack(anchor="w", pady=(5, 0))
        
        # カード1: 入力設定
        input_card = self._create_card(main_frame, "📝 入力設定")
        
        # モード選択
        mode_frame = tk.Frame(input_card, bg=self.colors['card_bg'])
        mode_frame.pack(fill="x", pady=(0, 15))
        
        mode_label = tk.Label(
            mode_frame,
            text="入力タイプ",
            font=('SF Pro Text', 11, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['card_bg']
        )
        mode_label.pack(anchor="w", pady=(0, 8))
        
        radio_frame = tk.Frame(mode_frame, bg=self.colors['card_bg'])
        radio_frame.pack(anchor="w")
        
        self.url_radio = tk.Radiobutton(
            radio_frame,
            text="🌐 URL",
            value="url",
            variable=self.input_mode_var,
            command=self.on_input_mode_change,
            font=('SF Pro Text', 11),
            bg=self.colors['card_bg'],
            fg=self.colors['text'],
            selectcolor=self.colors['card_bg'],
            activebackground=self.colors['card_bg'],
            bd=0,
            highlightthickness=0
        )
        self.url_radio.pack(side="left", padx=(0, 20))
        
        self.local_radio = tk.Radiobutton(
            radio_frame,
            text="📁 ローカルHTML",
            value="local",
            variable=self.input_mode_var,
            command=self.on_input_mode_change,
            font=('SF Pro Text', 11),
            bg=self.colors['card_bg'],
            fg=self.colors['text'],
            selectcolor=self.colors['card_bg'],
            activebackground=self.colors['card_bg'],
            bd=0,
            highlightthickness=0
        )
        self.local_radio.pack(side="left")
        
        # URL入力
        url_input_frame = tk.Frame(input_card, bg=self.colors['card_bg'])
        url_input_frame.pack(fill="x", pady=(0, 15))
        
        url_label = tk.Label(
            url_input_frame,
            text="URL",
            font=('SF Pro Text', 11, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['card_bg']
        )
        url_label.pack(anchor="w", pady=(0, 6))
        
        self.url_entry = tk.Entry(
            url_input_frame,
            font=('Helvetica Neue', 13),
            bg='white',
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            highlightthickness=2,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['border_focus']
        )
        self.url_entry.pack(fill="x", ipady=10)
        placeholder = "https://example.com"
        if TKDND_AVAILABLE:
            placeholder += " または ドラッグ&ドロップ"
        self.url_placeholder = placeholder
        self.url_entry.insert(0, self.url_placeholder)
        self.url_entry.config(fg=self.colors['text_light'])
        self.url_entry.bind('<FocusIn>', self.on_url_focus_in)
        self.url_entry.bind('<FocusOut>', self.on_url_focus_out)
        
        # ローカルHTML入力
        local_input_frame = tk.Frame(input_card, bg=self.colors['card_bg'])
        local_input_frame.pack(fill="x", pady=(0, 15))
        
        local_label = tk.Label(
            local_input_frame,
            text="HTMLファイル",
            font=('SF Pro Text', 11, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['card_bg']
        )
        local_label.pack(anchor="w", pady=(0, 6))
        
        local_entry_frame = tk.Frame(local_input_frame, bg=self.colors['card_bg'])
        local_entry_frame.pack(fill="x")
        
        self.local_path_entry = tk.Entry(
            local_entry_frame,
            textvariable=self.local_path_var,
            font=('Helvetica Neue', 13),
            bg='white',
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            highlightthickness=2,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['border_focus']
        )
        self.local_path_entry.pack(side="left", fill="x", expand=True, ipady=10)
        
        self.local_browse_button = tk.Button(
            local_entry_frame,
            text="📂 参照",
            command=self.browse_local_html,
            font=('SF Pro Text', 11),
            bg=self.colors['card_bg'],
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            padx=15,
            pady=8,
            cursor='hand2'
        )
        self.local_browse_button.pack(side="left", padx=(10, 0))

        if TKDND_AVAILABLE and DND_FILES is not None:
            try:
                self.url_entry.drop_target_register(DND_FILES)
                self.url_entry.dnd_bind('<<Drop>>', self.on_drop_url)
                self.local_path_entry.drop_target_register(DND_FILES)
                self.local_path_entry.dnd_bind('<<Drop>>', self.on_drop_file)
                self.dnd_enabled = True
            except tk.TclError:
                self.dnd_enabled = False
                self._dnd_warning = "⚠️ ドラッグ&ドロップ機能を初期化できませんでした。tkdnd ライブラリが見つからない可能性があります。"
        else:
            self._dnd_warning = "ℹ️ ドラッグ&ドロップ機能は現在無効です。必要な場合は tkinterdnd2 / tkdnd をインストールしてください。"

        if not self.dnd_enabled and "ドラッグ" in self.url_placeholder:
            self.url_placeholder = "https://example.com"
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, self.url_placeholder)
            self.url_entry.config(fg=self.colors['text_light'])
        
        # 実行ボタン
        self.process_button = tk.Button(
            input_card,
            text="🚀 文字起こし実行",
            command=self.start_processing,
            font=('Helvetica Neue', 14, 'bold'),
            bg=self.colors['primary'],
            fg='white',
            relief='flat',
            bd=0,
            padx=30,
            pady=14,
            cursor='hand2',
            activebackground=self.colors['primary_hover']
        )
        self.process_button.pack(fill="x", pady=(8, 0))
        
        # ホバーエフェクトを追加
        def on_enter(e):
            self.process_button['background'] = self.colors['primary_hover']
        
        def on_leave(e):
            self.process_button['background'] = self.colors['primary']
        
        self.process_button.bind("<Enter>", on_enter)
        self.process_button.bind("<Leave>", on_leave)
        
        # カード2: 進行状況
        progress_card = self._create_card(main_frame, "⏳ 進行状況")
        
        self.progress_bar = ttk.Progressbar(
            progress_card,
            mode='indeterminate',
            style='TProgressbar'
        )
        self.progress_bar.pack(fill="x", pady=(0, 10))
        
        self.status_label = tk.Label(
            progress_card,
            text="待機中...",
            font=('SF Pro Text', 11),
            fg=self.colors['text_light'],
            bg=self.colors['card_bg'],
            anchor="w"
        )
        self.status_label.pack(fill="x")
        
        # カード3: スクリーンショットプレビュー
        screenshot_card = self._create_card(main_frame, "📸 スクリーンショット")
        
        self.screenshot_label = tk.Label(
            screenshot_card,
            text="スクリーンショットはここに表示されます",
            font=('SF Pro Text', 11),
            fg=self.colors['text_light'],
            bg=self.colors['card_bg'],
            relief='flat'
        )
        self.screenshot_label.pack(fill="both", expand=True, pady=20)
        
        # カード4: ログ
        log_card = self._create_card(main_frame, "📊 ログ")
        
        self.log_text = scrolledtext.ScrolledText(
            log_card,
            font=('Menlo', 10),
            bg='#F9FAFB',
            fg=self.colors['text'],
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief='flat',
            padx=10,
            pady=10,
            height=8
        )
        self.log_text.pack(fill="both", expand=True)

        if self._dnd_warning:
            self.log_message(self._dnd_warning)
        
        # カード5: 文字起こし結果
        result_card = self._create_card(main_frame, "📄 文字起こし結果")
        
        result_inner = tk.Frame(result_card, bg=self.colors['card_bg'])
        result_inner.pack(fill="both", expand=True)
        
        self.transcript_text = scrolledtext.ScrolledText(
            result_inner,
            font=('SF Pro Text', 11),
            bg='#F9FAFB',
            fg=self.colors['text'],
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief='flat',
            padx=10,
            pady=10,
            height=10
        )
        self.transcript_text.pack(fill="both", expand=True)
        
        self.copy_button = tk.Button(
            result_inner,
            text="📋 クリップボードにコピー",
            command=self.copy_transcript,
            font=('SF Pro Text', 11),
            bg='white',
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            padx=20,
            pady=8,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.copy_button.pack(pady=(10, 0))
        
        # カード6: 出力先
        output_card = self._create_card(main_frame, "💾 出力先")
        
        self.result_path_label = tk.Label(
            output_card,
            text="処理完了後に表示されます",
            font=('Menlo', 10),
            fg=self.colors['text_light'],
            bg=self.colors['card_bg'],
            anchor="w"
        )
        self.result_path_label.pack(fill="x", pady=(0, 10))
        
        self.open_folder_button = tk.Button(
            output_card,
            text="📂 フォルダを開く",
            command=self.open_result_folder,
            font=('SF Pro Text', 11),
            bg='white',
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            padx=20,
            pady=8,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.open_folder_button.pack()

        self.result_dir = None
        self.latest_transcript = ""

        # OCR準備チェック
        self.log_message("🎉 アプリケーション起動")
        self.check_ocr_ready()
        self.on_input_mode_change()
    
    def _create_card(self, parent, title):
        """カードウィジェットを作成し、コンテンツフレームを返す"""
        # カードのコンテナ（シャドウとラウンドコーナー）
        card_frame = tk.Frame(
            parent,
            bg=self.colors['card_bg'],
            relief='flat',
            bd=0
        )
        card_frame.pack(fill="x", pady=(0, 16))
        
        # 内側のカード（シャドウ効果をシミュレート）
        inner_card = tk.Frame(
            card_frame,
            bg=self.colors['card_bg'],
            relief='solid',
            bd=1,
            highlightthickness=1,
            highlightbackground=self.colors['border']
        )
        inner_card.pack(fill="both", expand=True, padx=1, pady=1)
        
        if title:
            title_label = tk.Label(
                inner_card,
                text=title,
                font=('Helvetica Neue', 16, 'bold'),
                fg=self.colors['text'],
                bg=self.colors['card_bg']
            )
            title_label.pack(anchor="w", padx=24, pady=(20, 12))
        
        # コンテンツ用のフレーム
        content_frame = tk.Frame(inner_card, bg=self.colors['card_bg'])
        content_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        
        return content_frame

    def on_url_focus_in(self, event):
        """URLエントリのフォーカスイン時のプレースホルダー処理"""
        if self.url_entry.get() == self.url_placeholder:
            self.url_entry.delete(0, tk.END)
            self.url_entry.config(fg=self.colors['text'])

    def on_url_focus_out(self, event):
        """URLエントリのフォーカスアウト時のプレースホルダー処理"""
        if not self.url_entry.get().strip():
            self.url_entry.insert(0, self.url_placeholder)
            self.url_entry.config(fg=self.colors['text_light'])
    
    def on_drop_url(self, event):
        """URL/ファイルのドロップ処理"""
        dropped = event.data.strip('{}')
        
        # ファイルの場合
        if dropped.startswith('/') or dropped.startswith('file://'):
            file_path = dropped.replace('file://', '')
            self.input_mode_var.set("local")
            self.local_path_var.set(file_path)
            self.on_input_mode_change()
        # URLの場合
        elif dropped.startswith(('http://', 'https://')):
            self.input_mode_var.set("url")
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, dropped)
            self.url_entry.config(foreground=self.colors['text'])
            self.on_input_mode_change()
        else:
            # テキストとして扱う
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, dropped)
            self.url_entry.config(foreground=self.colors['text'])
    
    def on_drop_file(self, event):
        """ファイルのドロップ処理（ローカルHTMLフィールド用）"""
        file_path = event.data.strip('{}').replace('file://', '')
        self.local_path_var.set(file_path)
    
    def copy_transcript(self):
        """文字起こし結果をクリップボードにコピー"""
        if self.latest_transcript:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.latest_transcript)
            self.status_label.config(text="クリップボードにコピーしました！")
            self.log_message("📋 文字起こし結果をクリップボードにコピーしました")
        else:
            messagebox.showinfo("情報", "コピーする内容がありません")
        
    def log_message(self, message):
        """ログエリアにメッセージを追加"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def check_ocr_ready(self):
        """OCR機能の利用可能性をチェック"""
        if not transcribe_website.GEMINI_AVAILABLE:
            self.log_message("⚠️ Gemini OCRが利用できません")
            if not transcribe_website.GENAI_LIB_AVAILABLE:
                self.log_message("   google-generativeai ライブラリが必要です")
            if not transcribe_website.GOOGLE_API_KEY:
                self.log_message("   GOOGLE_API_KEY 環境変数が未設定です")
        else:
            self.log_message("✅ Gemini OCR利用可能")

    def on_input_mode_change(self):
        """入力モードごとにフィールドの有効/無効を切り替える"""
        mode = self.input_mode_var.get()
        if mode == "url":
            self.url_entry.config(state=tk.NORMAL)
            self.local_path_entry.config(state=tk.DISABLED)
            self.local_browse_button.config(state=tk.DISABLED)
        else:
            self.url_entry.config(state=tk.DISABLED)
            self.local_path_entry.config(state=tk.NORMAL)
            self.local_browse_button.config(state=tk.NORMAL)

    def browse_local_html(self):
        """ローカルHTMLファイル（またはindex.htmlがあるディレクトリ）を選択"""
        initial_path = self.local_path_var.get().strip()
        initial_dir = None
        if initial_path:
            candidate = Path(initial_path).expanduser()
            if candidate.is_dir():
                initial_dir = candidate
            elif candidate.parent.exists():
                initial_dir = candidate.parent

        file_path = filedialog.askopenfilename(
            title="ローカルHTMLを選択",
            initialdir=str(initial_dir) if initial_dir else None,
            filetypes=(("HTML", "*.html *.htm"), ("すべてのファイル", "*.*")),
        )
        if file_path:
            self.local_path_var.set(file_path)

    def start_processing(self):
        """処理を開始"""
        mode = self.input_mode_var.get()

        if mode == "url":
            url = self.url_entry.get().strip()

            # プレースホルダーチェック
            if not url or url == "https://example.com または ドラッグ&ドロップ":
                messagebox.showwarning("入力エラー", "URLを入力してください")
                return

            if not url.startswith(("http://", "https://")):
                messagebox.showwarning(
                    "入力エラー",
                    "有効なURLを入力してください\n\n例:\nhttps://example.com"
                )
                return

            task_params = ("url", url)
            log_target = url
        else:
            local_path = self.local_path_var.get().strip()
            if not local_path:
                messagebox.showwarning(
                    "入力エラー",
                    "ローカルHTMLのパスを指定してください\n\n「参照...」ボタンまたはドラッグ&ドロップで指定できます"
                )
                return

            candidate = Path(local_path).expanduser()
            if not candidate.exists():
                messagebox.showerror(
                    "ファイルエラー",
                    f"指定されたパスが見つかりません:\n\n{candidate}\n\n正しいパスを指定してください"
                )
                return
            
            if not candidate.is_file() or not candidate.suffix.lower() in ['.html', '.htm']:
                messagebox.showwarning(
                    "ファイルエラー",
                    f"HTMLファイル(.html, .htm)を指定してください\n\n指定されたファイル: {candidate.name}"
                )
                return

            task_params = ("local", candidate)
            log_target = str(candidate)

        # UIを無効化
        self.process_button.config(state=tk.DISABLED)
        self.url_entry.config(state=tk.DISABLED)
        self.local_path_entry.config(state=tk.DISABLED)
        self.local_browse_button.config(state=tk.DISABLED)
        self.open_folder_button.config(state=tk.DISABLED)

        # プログレスバー開始
        self.progress_bar.start(10)
        self.status_label.config(text="処理中...")
        
        # ログクリア
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        self.latest_transcript = ""
        self.update_transcript_display("")

        self.log_message(f"処理開始: {log_target}")

        # 別スレッドで処理を実行
        thread = threading.Thread(target=self.process_input, args=task_params)
        thread.daemon = True
        thread.start()

    def process_input(self, mode, value):
        """入力タイプに応じて処理を実行（別スレッド）"""
        try:
            self.log_message("📄 ページを読み込み中...")

            if mode == "local":
                result = transcribe_website.transcribe_local_html(
                    html_path=value,
                    slice_height=transcribe_website.SLICE_HEIGHT_DEFAULT,
                    overlap=transcribe_website.SLICE_OVERLAP_DEFAULT,
                    keyword_slug=None
                )
            else:
                result = transcribe_website.transcribe_website(
                    url=value,
                    slice_height=transcribe_website.SLICE_HEIGHT_DEFAULT,
                    overlap=transcribe_website.SLICE_OVERLAP_DEFAULT,
                    keyword_slug=None
                )

            self.log_message("📸 スクリーンショット取得完了")
            self.log_message(f"🔍 OCRセグメント数: {len(result['segments'])}")

            # Markdownとテキストファイルを保存
            md_path = transcribe_website.save_markdown(result)
            txt_path = transcribe_website.save_plain_text(result)
            
            self.log_message("💾 結果を保存中...")
            
            # 分割画像をクリーンアップ
            transcribe_website.cleanup_segment_images(result)
            
            # 最新リンクを更新
            transcribe_website.update_latest_symlink(
                result["run_dir"],
                output_root=result.get("output_root")
            )
            
            self.result_dir = result["run_dir"]
            transcript_body = result.get("combined_text") or result.get("visible_text") or ""
            self.latest_transcript = transcript_body

            # 完了メッセージ
            self.root.after(0, self.processing_complete, result, md_path, txt_path)
            
        except Exception as e:
            error_msg = f"エラーが発生しました: {str(e)}"
            self.root.after(0, self.processing_error, error_msg)
    
    def processing_complete(self, result, md_path, txt_path):
        """処理完了時の処理（メインスレッド）"""
        self.progress_bar.stop()
        self.status_label.config(text="完了！")
        
        self.log_message("=" * 50)
        self.log_message("✅ 処理完了！")
        self.log_message(f"📁 出力フォルダ: {result['run_dir']}")
        self.log_message(f"📄 Markdown: {md_path.name}")
        self.log_message(f"📄 テキスト: {txt_path.name}")
        self.log_message(f"📸 スクリーンショット: {result['screenshot'].name}")
        
        # スクリーンショットをプレビュー表示
        self.display_screenshot(result['screenshot'])

        if result.get('source_type') == 'local_html' and result.get('source_path'):
            self.log_message(f"📂 ローカルHTML: {result['source_path']}")

        if result.get('combined_text'):
            text_preview = result['combined_text'][:200]
            self.log_message(f"\n文字起こしプレビュー:\n{text_preview}...")

        self.update_transcript_display(self.latest_transcript)
        
        # コピーボタンを有効化
        self.copy_button.config(state=tk.NORMAL)

        # 結果パス表示
        self.result_path_label.config(text=str(result['run_dir']))
        self.open_folder_button.config(state=tk.NORMAL)

        # UIを再有効化
        self.process_button.config(state=tk.NORMAL)
        self.url_entry.config(state=tk.NORMAL)
        self.on_input_mode_change()

        messagebox.showinfo(
            "完了",
            f"文字起こしが完了しました！\n\n出力先:\n{result['run_dir']}"
        )
    
    def processing_error(self, error_msg):
        """エラー時の処理（メインスレッド）"""
        self.progress_bar.stop()
        self.status_label.config(text="エラー発生")
        
        self.log_message(f"❌ {error_msg}")
        
        # UIを再有効化
        self.process_button.config(state=tk.NORMAL)
        self.url_entry.config(state=tk.NORMAL)
        self.on_input_mode_change()

        # より詳細なエラーメッセージ
        error_details = error_msg
        if "Connection" in error_msg or "connection" in error_msg:
            error_details += "\n\nネットワーク接続を確認してください"
        elif "Permission" in error_msg or "permission" in error_msg:
            error_details += "\n\nファイルのアクセス権限を確認してください"

        messagebox.showerror("エラー", error_details)

    def update_transcript_display(self, text):
        """文字起こし結果をテキストエリアに表示"""
        self.transcript_text.config(state=tk.NORMAL)
        self.transcript_text.delete(1.0, tk.END)
        if text:
            self.transcript_text.insert(tk.END, text)
        self.transcript_text.config(state=tk.DISABLED)
    
    def open_result_folder(self):
        """結果フォルダを開く"""
        if self.result_dir and self.result_dir.exists():
            import subprocess
            import platform
            
            system = platform.system()
            try:
                if system == "Darwin":  # macOS
                    subprocess.run(["open", str(self.result_dir)])
                elif system == "Windows":
                    subprocess.run(["explorer", str(self.result_dir)])
                else:  # Linux
                    subprocess.run(["xdg-open", str(self.result_dir)])
            except Exception as e:
                messagebox.showerror("エラー", f"フォルダを開けませんでした: {e}")
    
    def display_screenshot(self, screenshot_path):
        """スクリーンショットを表示"""
        try:
            img = Image.open(screenshot_path)
            
            # 表示サイズを計算（最大幅800px、高さは比率を維持）
            max_width = 800
            width, height = img.size
            if width > max_width:
                ratio = max_width / width
                new_width = max_width
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # PIL ImageをTkinter PhotoImageに変換
            photo = ImageTk.PhotoImage(img)
            
            # ラベルに画像を設定（参照を保持しないとガベージコレクションされる）
            self.screenshot_label.config(image=photo, text="")
            self.screenshot_label.image = photo
            
            self.log_message("✅ スクリーンショットを表示しました")
        except Exception as e:
            self.log_message(f"⚠️ スクリーンショット表示エラー: {e}")


def main():
    global TKDND_AVAILABLE

    root = None
    if TKDND_AVAILABLE and TkinterDnD is not None:
        try:
            root = TkinterDnD.Tk()
        except Exception:
            TKDND_AVAILABLE = False
            print("警告: ドラッグ&ドロップ機能が利用できません。tkinterdnd2/tkdnd のインストールを推奨します。")

    if root is None:
        root = tk.Tk()

    app = LPTranscriberApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

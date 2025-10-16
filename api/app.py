"""
LP文字起こしウェブアプリ - FastAPI Backend
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
import sys
import os
from pathlib import Path
import uuid
import json
import shutil
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# transcribe_websiteモジュールをインポート
import transcribe_website

from TD作成くん.td_builder.config import AppConfig as TDAppConfig
from TD作成くん.td_builder.pipeline import build_td_report
from TD作成くん.td_builder.models import InputSpec
from TD作成くん.td_builder.serp import SerpProviderError

app = FastAPI(title="LP Transcriber API", version="1.0.0")

# CORS設定（Nuxt.jsからのリクエストを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://capture-transcription.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 処理状態を管理するグローバル辞書
processing_status: Dict[str, Dict[str, Any]] = {}

def add_log(job_id: str, message: str):
    """ログメッセージを追加"""
    if job_id in processing_status:
        if "logs" not in processing_status[job_id]:
            processing_status[job_id]["logs"] = []
        processing_status[job_id]["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })

# 一時ファイル保存ディレクトリ
TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# ThreadPoolExecutor for running sync code
executor = ThreadPoolExecutor(max_workers=3)


class TranscribeURLRequest(BaseModel):
    url: HttpUrl


class TDRequest(BaseModel):
    target: str
    keyword: str
    site_info: Optional[str] = None


class StatusResponse(BaseModel):
    job_id: str
    status: str
    message: str
    progress: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """API情報を返す"""
    return {
        "name": "LP Transcriber API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "transcribe_url": "/api/transcribe/url",
            "transcribe_upload": "/api/transcribe/upload",
            "status": "/api/status/{job_id}",
            "download": "/api/download/{job_id}/{file_type}",
            "build_td": "/api/td/build"
        }
    }


@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {
        "status": "healthy",
        "gemini_available": transcribe_website.GEMINI_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/transcribe/url")
async def transcribe_url(request: TranscribeURLRequest):
    """URLから文字起こしを実行"""
    job_id = str(uuid.uuid4())

    processing_status[job_id] = {
        "status": "processing",
        "message": "処理を開始しました",
        "progress": 0,
        "created_at": datetime.now().isoformat()
    }

    # バックグラウンドで処理を実行（ThreadPoolExecutorで同期関数を実行）
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(loop.run_in_executor(executor, process_url_transcription, job_id, str(request.url)))

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "処理を開始しました"
    }


@app.post("/api/transcribe/upload")
async def transcribe_upload(file: UploadFile = File(...)):
    """アップロードされたHTMLファイルから文字起こしを実行"""
    if not file.filename.endswith(('.html', '.htm')):
        raise HTTPException(status_code=400, detail="HTMLファイル(.html, .htm)のみ対応しています")

    job_id = str(uuid.uuid4())

    # 一時ファイルとして保存
    temp_file_path = TEMP_DIR / f"{job_id}_{file.filename}"
    try:
        with temp_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ファイル保存エラー: {str(e)}")

    processing_status[job_id] = {
        "status": "processing",
        "message": "処理を開始しました",
        "progress": 0,
        "created_at": datetime.now().isoformat()
    }

    # バックグラウンドで処理を実行（ThreadPoolExecutorで同期関数を実行）
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(loop.run_in_executor(executor, process_local_transcription, job_id, temp_file_path))

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "処理を開始しました"
    }


@app.post("/api/td/build")
async def build_td_endpoint(request: TDRequest):
    """TD生成パイプラインを実行"""
    loop = asyncio.get_event_loop()
    spec = InputSpec(target=request.target, keyword=request.keyword, site_info=request.site_info)
    config = TDAppConfig()
    try:
        report = await loop.run_in_executor(executor, _run_td_pipeline, spec, config)
    except SerpProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"TD生成に失敗しました: {exc}") from exc
    return _serialize_td_report(report)


def _run_td_pipeline(spec: InputSpec, config: TDAppConfig):
    """同期的にTDレポートを生成するヘルパー"""
    return build_td_report(spec, config)


def _serialize_td_report(report):
    """TDレポートをJSONシリアライズ可能な辞書へ変換"""
    return {
        "keyword": report.keyword,
        "target": report.target,
        "intent": {
            "primary": report.intent.primary_intent,
            "evidence": report.intent.supporting_evidence,
        },
        "ads": [
            {
                "position": ad.position,
                "title": ad.title,
                "description": ad.description,
                "link": ad.link,
                "display_link": ad.display_link,
                "summary": _serialize_page_summary(ad.site_summary),
            }
            for ad in report.ads
        ],
        "seo_insights": [
            {
                "position": insight.position,
                "title": insight.title,
                "summary": insight.summary,
                "key_topics": insight.key_topics,
            }
            for insight in report.seo_insights
        ],
        "appeal_axes": [
            {"name": axis.name, "score": axis.score, "evidence": axis.evidence}
            for axis in report.appeal_axes
        ],
        "proposals": [
            {
                "title": proposal.title,
                "description": proposal.description,
                "cta": proposal.cta,
                "rationale": proposal.rationale,
            }
            for proposal in report.proposals
        ],
    }


def _serialize_page_summary(summary):
    if summary is None:
        return None
    return {
        "url": summary.url,
        "title": summary.title,
        "meta_description": summary.meta_description,
        "headings": summary.headings,
        "key_points": summary.key_points,
    }


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """処理状態を取得"""
    if job_id not in processing_status:
        raise HTTPException(status_code=404, detail="Job ID が見つかりません")

    return processing_status[job_id]


@app.get("/api/download/{job_id}/{file_type}")
async def download_file(job_id: str, file_type: str):
    """結果ファイルをダウンロード"""
    if job_id not in processing_status:
        raise HTTPException(status_code=404, detail="Job ID が見つかりません")

    status = processing_status[job_id]
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="処理が完了していません")

    result = status.get("result")
    if not result:
        raise HTTPException(status_code=500, detail="結果が見つかりません")

    # ファイルタイプに応じてパスを取得
    if file_type == "markdown":
        file_path = Path(result["markdown_path"])
    elif file_type == "text":
        file_path = Path(result["text_path"])
    elif file_type == "screenshot":
        file_path = Path(result["screenshot_path"])
    else:
        raise HTTPException(status_code=400, detail="無効なファイルタイプです")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream"
    )


def process_url_transcription(job_id: str, url: str):
    """URLの文字起こし処理（バックグラウンド）- 同期関数"""
    try:
        add_log(job_id, f"処理開始: URL={url}")
        processing_status[job_id]["message"] = "ページを読み込み中..."
        processing_status[job_id]["progress"] = 10

        add_log(job_id, "Playwrightでブラウザを起動中...")
        result = transcribe_website.transcribe_website(
            url=url,
            slice_height=transcribe_website.SLICE_HEIGHT_DEFAULT,
            overlap=transcribe_website.SLICE_OVERLAP_DEFAULT,
            keyword_slug=None
        )

        add_log(job_id, f"スクリーンショット取得完了: {len(result['segments'])} セグメント")
        processing_status[job_id]["message"] = "スクリーンショット取得完了"
        processing_status[job_id]["progress"] = 50

        # Markdownとテキストファイルを保存
        add_log(job_id, "Markdownファイルを保存中...")
        md_path = transcribe_website.save_markdown(result)
        add_log(job_id, "テキストファイルを保存中...")
        txt_path = transcribe_website.save_plain_text(result)

        processing_status[job_id]["message"] = "結果を保存中..."
        processing_status[job_id]["progress"] = 80

        # 分割画像をクリーンアップ（無効化）
        # transcribe_website.cleanup_segment_images(result)

        # 最新リンクを更新
        transcribe_website.update_latest_symlink(
            result["run_dir"],
            output_root=result.get("output_root")
        )

        # 各セグメントの文字起こし結果を抽出
        segments_data = []
        for seg in result["segments"]:
            segments_data.append({
                "index": seg.get("index", 0),
                "text": seg.get("clean_text", ""),
                "top": seg.get("top", 0),
                "bottom": seg.get("bottom", 0)
            })

        add_log(job_id, "処理完了")
        processing_status[job_id]["status"] = "completed"
        processing_status[job_id]["message"] = "処理完了！"
        processing_status[job_id]["progress"] = 100
        processing_status[job_id]["result"] = {
            "transcript": result.get("combined_text") or result.get("visible_text") or "",
            "segments": segments_data,  # セグメントごとの文字起こし
            "markdown_path": str(md_path),
            "text_path": str(txt_path),
            "screenshot_path": str(result["screenshot"]),
            "run_dir": str(result["run_dir"]),
            "segments_count": len(result["segments"]),
            "source_url": url
        }

    except Exception as e:
        add_log(job_id, f"エラー発生: {str(e)}")
        processing_status[job_id]["status"] = "error"
        processing_status[job_id]["message"] = "エラーが発生しました"
        processing_status[job_id]["error"] = str(e)


def process_local_transcription(job_id: str, html_path: Path):
    """ローカルHTMLの文字起こし処理（バックグラウンド）- 同期関数"""
    try:
        add_log(job_id, f"処理開始: HTMLファイル={html_path}")
        processing_status[job_id]["message"] = "HTMLファイルを読み込み中..."
        processing_status[job_id]["progress"] = 10

        add_log(job_id, "Playwrightでブラウザを起動中...")
        result = transcribe_website.transcribe_local_html(
            html_path=html_path,
            slice_height=transcribe_website.SLICE_HEIGHT_DEFAULT,
            overlap=transcribe_website.SLICE_OVERLAP_DEFAULT,
            keyword_slug=None
        )

        add_log(job_id, f"スクリーンショット取得完了: {len(result['segments'])} セグメント")
        processing_status[job_id]["message"] = "スクリーンショット取得完了"
        processing_status[job_id]["progress"] = 50

        # Markdownとテキストファイルを保存
        add_log(job_id, "Markdownファイルを保存中...")
        md_path = transcribe_website.save_markdown(result)
        add_log(job_id, "テキストファイルを保存中...")
        txt_path = transcribe_website.save_plain_text(result)

        processing_status[job_id]["message"] = "結果を保存中..."
        processing_status[job_id]["progress"] = 80

        # 分割画像をクリーンアップ（無効化）
        # transcribe_website.cleanup_segment_images(result)

        # 最新リンクを更新
        transcribe_website.update_latest_symlink(
            result["run_dir"],
            output_root=result.get("output_root")
        )

        # 各セグメントの文字起こし結果を抽出
        segments_data = []
        for seg in result["segments"]:
            segments_data.append({
                "index": seg.get("index", 0),
                "text": seg.get("clean_text", ""),
                "top": seg.get("top", 0),
                "bottom": seg.get("bottom", 0)
            })

        add_log(job_id, "処理完了")
        processing_status[job_id]["status"] = "completed"
        processing_status[job_id]["message"] = "処理完了！"
        processing_status[job_id]["progress"] = 100
        processing_status[job_id]["result"] = {
            "transcript": result.get("combined_text") or result.get("visible_text") or "",
            "segments": segments_data,  # セグメントごとの文字起こし
            "markdown_path": str(md_path),
            "text_path": str(txt_path),
            "screenshot_path": str(result["screenshot"]),
            "run_dir": str(result["run_dir"]),
            "segments_count": len(result["segments"]),
            "source_path": str(html_path)
        }

        # 一時ファイルを削除
        if html_path.exists():
            html_path.unlink()

    except Exception as e:
        add_log(job_id, f"エラー発生: {str(e)}")
        processing_status[job_id]["status"] = "error"
        processing_status[job_id]["message"] = "エラーが発生しました"
        processing_status[job_id]["error"] = str(e)

        # エラー時も一時ファイルを削除
        if html_path.exists():
            html_path.unlink()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""论文 PDF 下载缓存服务"""

import os
import logging
import httpx
from fastapi.responses import StreamingResponse
from fastapi import HTTPException

logger = logging.getLogger(__name__)

PDF_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "papers_pdf")


def _safe_doi(doi: str) -> str:
    """将 DOI 转为安全目录/文件名"""
    return doi.replace("/", "_").replace("\\", "_")


def _ensure_pdf_dir(doi: str = ""):
    """确保 PDF 缓存目录存在"""
    if doi:
        os.makedirs(os.path.join(PDF_CACHE_DIR, _safe_doi(doi)), exist_ok=True)
    else:
        os.makedirs(PDF_CACHE_DIR, exist_ok=True)


def get_pdf_path(doi: str) -> str:
    """获取 PDF 缓存路径（papers_pdf/{safe_doi}/paper.pdf）"""
    return os.path.join(PDF_CACHE_DIR, _safe_doi(doi), "paper.pdf")


def is_pdf_cached(doi: str) -> bool:
    """检查 PDF 是否已缓存"""
    return os.path.exists(get_pdf_path(doi))


def download_and_cache_pdf(pdf_url: str, doi: str) -> str:
    """下载 PDF 并缓存到本地"""
    _ensure_pdf_dir(doi)
    pdf_path = get_pdf_path(doi)

    if os.path.exists(pdf_path):
        logger.info(f"✅ PDF 已缓存: {doi}")
        return pdf_path

    logger.info(f"⬇️ 开始下载 PDF: {pdf_url}")
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(pdf_url)
            response.raise_for_status()
            with open(pdf_path, "wb") as f:
                f.write(response.content)

        file_size = os.path.getsize(pdf_path)
        logger.info(f"✅ PDF 下载完成: {doi} ({file_size / 1024:.1f} KB)")
        return pdf_path

    except httpx.HTTPError as e:
        logger.error(f"❌ PDF 下载失败: {e}")
        raise HTTPException(status_code=502, detail=f"PDF 下载失败: {str(e)}")


def serve_pdf(doi: str) -> StreamingResponse:
    """流式返回 PDF 文件"""
    pdf_path = get_pdf_path(doi)

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF 未缓存")

    def iter_file():
        with open(pdf_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{doi.replace('/', '_')}.pdf",
            "Cache-Control": "public, max-age=86400"
        }
    )

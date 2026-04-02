"""MinerU PDF 转 Markdown 服务（云端 v4 API + 本地双模式）"""

import io
import json
import logging
import os
import re
import zipfile

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://mineru.net"

# 统一论文资源目录（和 PDF 同级）
PAPERS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "papers_pdf")


def _safe_doi(doi: str) -> str:
    """将 DOI 转为安全目录名"""
    return doi.replace("/", "_").replace("\\", "_")


def get_image_path(doi: str, image_name: str) -> str:
    """获取某篇论文的指定图片路径（papers_pdf/{doi}/images/{name}）"""
    return os.path.join(PAPERS_ROOT, _safe_doi(doi), "images", image_name)


def get_images_dir(doi: str) -> str:
    """获取某篇论文的图片目录（papers_pdf/{doi}/images/）"""
    return os.path.join(PAPERS_ROOT, _safe_doi(doi), "images")


def _get_mineru_config() -> dict:
    """从数据库获取 MinerU 配置"""
    from services.mysql_service import load_config_from_db
    config = load_config_from_db("mineru_config")
    if config:
        return config
    return {"mode": "cloud", "api_key": "", "endpoint": "http://localhost:18000"}


def convert_pdf_cloud(pdf_url: str, api_key: str, language: str = "en") -> dict:
    """云端模式：使用 v4 单文件 URL API 提交转换任务

    Args:
        pdf_url: PDF 文件的公网可访问 URL
        api_key: MinerU API Key
        language: 文档语言，默认 en

    Returns:
        {"task_id": "...", "status": "submitted"}
    """
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{BASE_URL}/api/v4/extract/task",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": pdf_url,
                    "model_version": "vlm",
                    "is_ocr": True,
                    "enable_formula": True,
                    "enable_table": True,
                    "language": language,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                error_msg = data.get("msg", "提交任务失败")
                logger.error(f"❌ MinerU 提交失败: {error_msg}")
                return {"status": "failed", "error": error_msg}

            task_id = data["data"]["task_id"]
            logger.info(f"✅ MinerU 任务已提交: {task_id}")
            return {"task_id": task_id, "status": "submitted"}

    except Exception as e:
        logger.error(f"❌ MinerU 云端转换失败: {e}")
        raise


def convert_pdf_cloud_batch(pdf_path: str, api_key: str, language: str = "en") -> dict:
    """云端模式（批量上传）：用于没有公网 URL 的本地 PDF 文件

    流程：获取上传 URL → 上传文件 → 提交解析任务

    Args:
        pdf_path: 本地 PDF 文件路径
        api_key: MinerU API Key
        language: 文档语言

    Returns:
        {"task_id": "...", "status": "submitted"}
    """
    filename = os.path.basename(pdf_path)

    try:
        with httpx.Client(timeout=60.0) as client:
            # 1. 获取上传地址
            resp = client.post(
                f"{BASE_URL}/api/v4/file-urls/batch",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"file_names": [filename]},
            )
            resp.raise_for_status()
            batch_data = resp.json()

            batch_id = batch_data["data"]["batch_id"]
            upload_url = batch_data["data"]["file_urls"][0]["upload_url"]
            file_url = batch_data["data"]["file_urls"][0]["url"]

            # 2. 上传 PDF
            with open(pdf_path, "rb") as f:
                upload_resp = client.put(
                    upload_url,
                    content=f.read(),
                    headers={"Content-Type": "application/pdf"},
                )
                upload_resp.raise_for_status()

            # 3. 提交解析任务
            parse_resp = client.post(
                f"{BASE_URL}/api/v4/task-urls/batch",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"batch_id": batch_id, "file_urls": [file_url]},
            )
            parse_resp.raise_for_status()

            task_data = parse_resp.json()
            task_id = task_data["data"]["task_id"]
            logger.info(f"✅ MinerU 批量上传任务已提交: {task_id}")
            return {"task_id": task_id, "status": "submitted"}

    except Exception as e:
        logger.error(f"❌ MinerU 批量上传转换失败: {e}")
        raise


def poll_cloud_status(task_id: str, api_key: str) -> dict:
    """轮询云端任务状态

    Returns:
        任务状态数据，包含 state 字段 (pending/running/done/failed)
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{BASE_URL}/api/v4/extract/task/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"❌ 查询 MinerU 任务状态失败: {e}")
        raise


def download_cloud_result(task_id: str, api_key: str, doi: str = "") -> dict:
    """下载云端转换结果（从 zip 中提取 full.md 和图片）

    Args:
        task_id: MinerU 任务 ID
        api_key: MinerU API Key
        doi: 论文 DOI，用于保存图片到对应目录

    Returns:
        {"status": "completed", "markdown": "...", "images": [...]}
    """
    try:
        with httpx.Client(timeout=120.0) as client:
            # 查询任务状态获取下载链接
            resp = client.get(
                f"{BASE_URL}/api/v4/extract/task/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()["data"]

            zip_url = data.get("full_zip_url")
            if not zip_url:
                return {"status": "failed", "error": "未找到结果下载链接"}

            # 下载 zip
            zip_resp = client.get(zip_url)
            zip_resp.raise_for_status()

            zip_buffer = io.BytesIO(zip_resp.content)
            markdown_content = ""
            image_list = []

            # 准备图片目录
            img_dir = ""
            if doi:
                img_dir = get_images_dir(doi)
                os.makedirs(img_dir, exist_ok=True)

            with zipfile.ZipFile(zip_buffer, "r") as zf:
                for name in zf.namelist():
                    basename = os.path.basename(name)
                    if basename.endswith("full.md"):
                        markdown_content = zf.read(name).decode("utf-8")
                    elif doi and img_dir and basename and not name.startswith("."):
                        # 保存图片文件（jpg/png/gif/svg/webp 等）
                        ext = os.path.splitext(basename)[1].lower()
                        if ext in (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp"):
                            img_path = os.path.join(img_dir, basename)
                            with open(img_path, "wb") as img_f:
                                img_f.write(zf.read(name))
                            image_list.append(basename)

            if not markdown_content:
                return {"status": "failed", "error": "zip 中未找到 full.md"}

            # 重写 markdown 中的图片路径为 API 路径
            if doi and image_list:
                api_prefix = f"/api/papers/{doi}/markdown/images"
                # 匹配 ![alt](images/xxx.jpg) 或 ![alt](xxx.jpg)
                markdown_content = re.sub(
                    r'!\[([^\]]*)\]\((?:images/)?([^)]+)\)',
                    rf'![\1]({api_prefix}/\2)',
                    markdown_content
                )

            logger.info(f"✅ MinerU 结果下载完成，Markdown 长度: {len(markdown_content)}，图片: {len(image_list)}")
            return {
                "status": "completed",
                "markdown": markdown_content,
                "images": image_list,
            }

    except Exception as e:
        logger.error(f"❌ 下载 MinerU 结果失败: {e}")
        raise


def convert_pdf_local(pdf_path: str, endpoint: str) -> dict:
    """本地模式：直接调用本地 mineru-api"""
    try:
        with httpx.Client(timeout=300.0) as client:
            with open(pdf_path, "rb") as f:
                resp = client.post(
                    f"{endpoint}/file_parse",
                    files={"file": ("paper.pdf", f, "application/pdf")},
                    data={"parse_type": "auto"},
                )
                resp.raise_for_status()

            result = resp.json()
            return {
                "status": "completed",
                "markdown": result.get("markdown", ""),
                "images": result.get("images", []),
            }

    except Exception as e:
        logger.error(f"❌ MinerU 本地转换失败: {e}")
        raise

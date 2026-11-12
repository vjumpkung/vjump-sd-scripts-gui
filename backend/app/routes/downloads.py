"""Download job API routes (catalog-only)."""

from fastapi import APIRouter, Request

from ..schemas.downloads import DownloadRequest
from ..services.downloads import DownloadManager, catalog_payload

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


def _manager(request: Request) -> DownloadManager:
    return request.app.state.downloads


@router.get("/catalog")
async def read_catalog(request: Request) -> list[dict]:
    return catalog_payload(request.app.state.settings)


@router.post("", status_code=202)
async def start_download(payload: DownloadRequest, request: Request) -> dict:
    return _manager(request).start(payload.model_id).to_response()


@router.get("")
async def list_downloads(request: Request) -> list[dict]:
    return [job.to_response() for job in _manager(request).list_jobs()]


@router.get("/{job_id}")
async def read_download(job_id: str, request: Request) -> dict:
    return _manager(request).get(job_id).to_response()


@router.post("/{job_id}/cancel")
async def cancel_download(job_id: str, request: Request) -> dict:
    job = await _manager(request).cancel(job_id)
    return job.to_response()

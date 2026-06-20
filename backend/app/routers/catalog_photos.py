import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import CatalogItem, CatalogItemPhoto, User
from app.schemas import (
    CatalogPhotoOut,
    PhotoConfirmRequest,
    PhotoPresignRequest,
    PhotoPresignResponse,
)
from app.storage import build_app_download_url, generate_upload_url, object_exists

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog-photos"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILENAME_LENGTH = 180


def _build_storage_key(catalog_item_id: int, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if not suffix:
        suffix = ".bin"
    unique = uuid.uuid4().hex
    return f"catalog/{catalog_item_id}/{unique}{suffix}"


@router.post("/{catalog_item_id}/photos/presign", response_model=PhotoPresignResponse)
def presign_catalog_photo_upload(
    catalog_item_id: int,
    payload: PhotoPresignRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = db.query(CatalogItem).filter(CatalogItem.id == catalog_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    if payload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported content type")
    if not payload.filename or len(payload.filename) > MAX_FILENAME_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid filename")

    storage_key = _build_storage_key(catalog_item_id, payload.filename)
    upload_url = generate_upload_url(storage_key=storage_key, content_type=payload.content_type)
    return PhotoPresignResponse(upload_url=upload_url, storage_key=storage_key)


@router.post("/{catalog_item_id}/photos/confirm", response_model=CatalogPhotoOut, status_code=status.HTTP_201_CREATED)
def confirm_catalog_photo_upload(
    catalog_item_id: int,
    payload: PhotoConfirmRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = db.query(CatalogItem).filter(CatalogItem.id == catalog_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    if payload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported content type")
    if not payload.storage_key.startswith(f"catalog/{catalog_item_id}/"):
        raise HTTPException(status_code=400, detail="Storage key does not match catalog item")
    if not object_exists(payload.storage_key):
        raise HTTPException(status_code=400, detail="Uploaded object not found in storage")

    if payload.is_cover:
        db.query(CatalogItemPhoto).filter(CatalogItemPhoto.catalog_item_id == catalog_item_id).update(
            {"is_cover": False}
        )

    photo = CatalogItemPhoto(
        catalog_item_id=catalog_item_id,
        storage_key=payload.storage_key,
        content_type=payload.content_type,
        sort_order=payload.sort_order,
        is_cover=payload.is_cover,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)

    result = CatalogPhotoOut.model_validate(photo)
    result.file_url = build_app_download_url(photo.storage_key)
    return result


@router.get("/{catalog_item_id}/photos", response_model=list[CatalogPhotoOut])
def list_catalog_item_photos(catalog_item_id: int, db: Session = Depends(get_db)):
    photos = (
        db.query(CatalogItemPhoto)
        .filter(CatalogItemPhoto.catalog_item_id == catalog_item_id)
        .order_by(CatalogItemPhoto.is_cover.desc(), CatalogItemPhoto.sort_order.asc(), CatalogItemPhoto.id.asc())
        .all()
    )
    result: list[CatalogPhotoOut] = []
    for photo in photos:
        item = CatalogPhotoOut.model_validate(photo)
        item.file_url = build_app_download_url(photo.storage_key)
        result.append(item)
    return result


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog_photo(photo_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    photo = db.query(CatalogItemPhoto).filter(CatalogItemPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    db.delete(photo)
    db.commit()
    return None


@router.patch("/photos/{photo_id}/cover", response_model=CatalogPhotoOut)
def set_cover_catalog_photo(photo_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    photo = db.query(CatalogItemPhoto).filter(CatalogItemPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    db.query(CatalogItemPhoto).filter(CatalogItemPhoto.catalog_item_id == photo.catalog_item_id).update(
        {"is_cover": False}
    )
    photo.is_cover = True
    db.commit()
    db.refresh(photo)

    result = CatalogPhotoOut.model_validate(photo)
    result.file_url = build_app_download_url(photo.storage_key)
    return result

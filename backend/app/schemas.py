from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.models import ListingStatus, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.seller


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=80)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    name: str
    role: UserRole

    class Config:
        from_attributes = True


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    brand: str
    model: str
    year: int = Field(ge=1950, le=2100)
    mileage: int = Field(ge=0)
    price: Decimal = Field(gt=0)
    city: str
    description: str = Field(min_length=10)
    status: ListingStatus = ListingStatus.draft


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    brand: str | None = None
    model: str | None = None
    year: int | None = Field(default=None, ge=1950, le=2100)
    mileage: int | None = Field(default=None, ge=0)
    price: Decimal | None = Field(default=None, gt=0)
    city: str | None = None
    description: str | None = Field(default=None, min_length=10)
    status: ListingStatus | None = None


class ListingOut(BaseModel):
    id: int
    seller_id: int
    title: str
    brand: str
    model: str
    year: int
    mileage: int
    price: Decimal
    city: str
    description: str
    status: ListingStatus
    created_at: datetime

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserRoleUpdateRequest(BaseModel):
    role: UserRole


class PhotoPresignRequest(BaseModel):
    filename: str
    content_type: str


class PhotoPresignResponse(BaseModel):
    upload_url: str
    storage_key: str


class PhotoConfirmRequest(BaseModel):
    storage_key: str
    content_type: str
    sort_order: int = 0
    is_cover: bool = False


class CatalogPhotoOut(BaseModel):
    id: int
    catalog_item_id: int
    storage_key: str
    content_type: str
    sort_order: int
    is_cover: bool
    created_at: datetime
    file_url: str | None = None

    class Config:
        from_attributes = True

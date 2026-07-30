from app.listing_photos import (
    listing_photo_candidate_urls,
    pick_listing_cover_url,
    resolve_listing_gallery_urls,
    resolve_listing_gallery_urls_map,
)
from app.models import CarListing


def _listing(**kwargs) -> CarListing:
    return CarListing(title="Test", brand="Nissan", model="Qashqai", year=2022, mileage=1, price=1, city="Minsk", description="x", **kwargs)


def test_listing_photo_candidate_urls_reads_variants_dict():
    listing = _listing(
        cover_photo_url="https://avcdn.av.by/advertbig/dead.avif",
        raw_photos=[
            {
                "id": 1,
                "main": True,
                "variants": {
                    "big": "https://avcdn.av.by/advertbig/dead.avif",
                    "medium": "https://avcdn.av.by/advertbig/alive.jpg",
                },
            },
            {
                "id": 2,
                "variants": {"big": "https://avcdn.av.by/advertbig/backup.jpg"},
            },
        ],
    )
    urls = listing_photo_candidate_urls(listing)
    assert urls[0] == "https://avcdn.av.by/advertbig/dead.avif"
    assert "https://avcdn.av.by/advertbig/alive.jpg" in urls
    assert "https://avcdn.av.by/advertbig/backup.jpg" in urls


def test_pick_listing_cover_url_skips_dead_remote(monkeypatch):
    listing = _listing(
        cover_photo_url="https://avcdn.av.by/advertbig/dead.avif",
        raw_photos=[
            {
                "main": True,
                "variants": {
                    "big": "https://avcdn.av.by/advertbig/dead.avif",
                    "medium": "https://avcdn.av.by/advertbig/alive.jpg",
                },
            }
        ],
    )

    def fake_available(url: str) -> bool:
        return url.endswith("alive.jpg")

    monkeypatch.setattr("app.listing_photos.remote_avby_image_available", fake_available)
    cover = pick_listing_cover_url(listing)
    assert cover == "/media/remote?url=https%3A%2F%2Favcdn.av.by%2Fadvertbig%2Falive.jpg"


def test_resolve_listing_gallery_urls_proxies_one_url_per_photo():
    listing = _listing(
        cover_photo_url="https://avcdn.av.by/advertbig/cover.avif",
        raw_photos=[
            {
                "variants": {
                    "big": "https://avcdn.av.by/advertbig/cover.avif",
                    "medium": "https://avcdn.av.by/advertbig/cover-medium.avif",
                },
            },
            {"variants": {"big": "https://avcdn.av.by/advertbig/second.avif"}},
        ],
    )
    gallery = resolve_listing_gallery_urls(listing)
    assert gallery == [
        "/media/remote?url=https%3A%2F%2Favcdn.av.by%2Fadvertbig%2Fcover.avif",
        "/media/remote?url=https%3A%2F%2Favcdn.av.by%2Fadvertbig%2Fsecond.avif",
    ]


def test_resolve_listing_gallery_urls_map_limits_photos_per_listing():
    listings = [
        _listing(
            id=1,
            cover_photo_url="https://avcdn.av.by/advertbig/1.avif",
            raw_photos=[{"variants": {"big": f"https://avcdn.av.by/advertbig/{index}.avif"}} for index in range(1, 8)],
        ),
        _listing(id=2, cover_photo_url=None, raw_photos=[]),
    ]
    gallery_map = resolve_listing_gallery_urls_map(listings, limit=5)
    assert len(gallery_map[1]) == 5
    assert 2 not in gallery_map

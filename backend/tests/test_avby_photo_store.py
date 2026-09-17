from app.avby_photo_store import is_avby_s3_media_url, store_avby_listing_photos


def test_is_avby_s3_media_url():
    assert is_avby_s3_media_url("/media/autoplius?key=avby%2F123%2F000.jpg")
    assert not is_avby_s3_media_url("https://avcdn.av.by/advertbig/x.jpg")
    assert not is_avby_s3_media_url(None)


def test_store_avby_listing_photos_uploads_and_returns_proxy_urls(monkeypatch):
    uploaded: list[tuple[str, bytes, str]] = []

    monkeypatch.setattr("app.avby_photo_store.autoplius_object_exists", lambda key: False)
    monkeypatch.setattr(
        "app.avby_photo_store.put_autoplius_object",
        lambda key, body, content_type: uploaded.append((key, body, content_type)),
    )
    monkeypatch.setattr(
        "app.avby_photo_store._download_image",
        lambda url, timeout=25: (b"img-bytes", "image/jpeg"),
    )

    cover, raw = store_avby_listing_photos(
        42,
        "https://avcdn.av.by/advertbig/cover.jpg",
        [
            {
                "main": True,
                "variants": {
                    "big": "https://avcdn.av.by/advertbig/cover.jpg",
                    "medium": "https://avcdn.av.by/advertbig/cover-m.jpg",
                },
            },
            {"variants": {"big": "https://avcdn.av.by/advertbig/second.jpg"}},
        ],
    )

    assert cover == "/media/autoplius?key=avby%2F42%2F000.jpg"
    assert raw == [
        {"url": "/media/autoplius?key=avby%2F42%2F000.jpg", "main": True},
        {"url": "/media/autoplius?key=avby%2F42%2F001.jpg", "main": False},
    ]
    assert [item[0] for item in uploaded] == ["avby/42/000.jpg", "avby/42/001.jpg"]


def test_store_avby_listing_photos_skips_when_already_in_s3(monkeypatch):
    def fail_download(*_args, **_kwargs):
        raise AssertionError("should not download")

    monkeypatch.setattr("app.avby_photo_store._download_image", fail_download)
    cover = "/media/autoplius?key=avby%2F7%2F000.jpg"
    raw = [{"url": cover, "main": True}]
    out_cover, out_raw = store_avby_listing_photos(7, cover, raw)
    assert out_cover == cover
    assert out_raw == raw


def test_store_avby_listing_photos_falls_back_when_s3_missing(monkeypatch):
    monkeypatch.setattr(
        "app.avby_photo_store.autoplius_object_exists",
        lambda key: (_ for _ in ()).throw(RuntimeError("no creds")),
    )
    monkeypatch.setattr(
        "app.avby_photo_store._download_image",
        lambda url, timeout=25: (b"img", "image/jpeg"),
    )
    cover = "https://avcdn.av.by/advertbig/cover.jpg"
    out_cover, out_raw = store_avby_listing_photos(9, cover, None)
    assert out_cover == cover
    assert out_raw is None

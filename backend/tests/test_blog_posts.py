from types import SimpleNamespace
from unittest.mock import MagicMock

from app.blog_posts import _SEED_BLOG_POSTS, blog_slugify, ensure_seed_blog_posts


def test_blog_slugify_cyrillic():
    assert blog_slugify("Как привезти авто") == "kak-privezti-avto"


def test_blog_slugify_fallback():
    assert blog_slugify("!!!") == "post"


def test_seed_blog_posts_include_about_us():
    about = next(item for item in _SEED_BLOG_POSTS if item["slug"] == "kto-my-i-chem-zanimaemsya")
    assert "160" in about["title"] or "160" in about["body"] or "160" in about["excerpt"]
    assert "льготн" in about["body"].lower() or "льготн" in about["excerpt"].lower()
    assert "<ul>" in about["body"]


def test_ensure_seed_blog_posts_skips_existing():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
    assert ensure_seed_blog_posts(db) == 0
    db.add.assert_not_called()
    db.commit.assert_not_called()

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.blog_posts import _SEED_BLOG_POSTS, blog_slugify, ensure_seed_blog_posts


def test_blog_slugify_cyrillic():
    assert blog_slugify("Как привезти авто") == "kak-privezti-avto"


def test_blog_slugify_fallback():
    assert blog_slugify("!!!") == "post"


def test_seed_blog_posts_include_about_us():
    about = next(item for item in _SEED_BLOG_POSTS if item["slug"] == "kto-my-i-chem-zanimaemsya")
    body = about["body"].lower()
    assert "белорус" in body
    assert "европ" in body
    assert "рф" in body and "рб" in body
    assert "<ul>" in about["body"]


def test_ensure_seed_blog_posts_updates_existing_content():
    about = next(item for item in _SEED_BLOG_POSTS if item["slug"] == "kto-my-i-chem-zanimaemsya")
    post = SimpleNamespace(
        title="old",
        body="old",
        excerpt="old",
        is_published=True,
        published_at=object(),
        updated_at=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = post
    assert ensure_seed_blog_posts(db) == 1
    assert post.title == about["title"]
    assert post.body == about["body"]
    assert post.excerpt == about["excerpt"]
    db.commit.assert_called_once()
    db.add.assert_not_called()

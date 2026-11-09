from app.blog_posts import blog_slugify


def test_blog_slugify_cyrillic():
    assert blog_slugify("Как привезти авто") == "kak-privezti-avto"


def test_blog_slugify_fallback():
    assert blog_slugify("!!!") == "post"

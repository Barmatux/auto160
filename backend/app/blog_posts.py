"""Blog posts: public list/detail and admin CRUD."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import BlogPost

_CYR_TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def blog_slugify(title: str) -> str:
    t = title.strip().lower()
    out: list[str] = []
    for ch in t:
        if ch in _CYR_TRANSLIT:
            out.append(_CYR_TRANSLIT[ch])
        elif "a" <= ch <= "z" or ch.isdigit():
            out.append(ch)
        elif ch in " -_":
            out.append("-")
    slug = re.sub(r"-+", "-", "".join(out)).strip("-")
    return (slug[:180] if slug else "post")


def _ensure_unique_slug(db: Session, slug: str, *, exclude_id: int | None = None) -> str:
    base = slug or "post"
    candidate = base
    n = 2
    while True:
        q = db.query(BlogPost.id).filter(BlogPost.slug == candidate)
        if exclude_id is not None:
            q = q.filter(BlogPost.id != exclude_id)
        if q.first() is None:
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def list_published_blog_posts(db: Session, *, limit: int = 50, offset: int = 0) -> list[BlogPost]:
    return (
        db.query(BlogPost)
        .filter(BlogPost.is_published.is_(True))
        .order_by(desc(BlogPost.published_at), desc(BlogPost.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def list_all_blog_posts(db: Session) -> list[BlogPost]:
    return db.query(BlogPost).order_by(desc(BlogPost.updated_at), desc(BlogPost.id)).all()


def get_published_blog_post_by_slug(db: Session, slug: str) -> BlogPost | None:
    slug_clean = slug.strip().lower()
    if not slug_clean:
        return None
    return (
        db.query(BlogPost)
        .filter(BlogPost.slug == slug_clean, BlogPost.is_published.is_(True))
        .first()
    )


def get_blog_post(db: Session, post_id: int) -> BlogPost | None:
    return db.get(BlogPost, post_id)


def create_blog_post(
    db: Session,
    *,
    author_id: int | None,
    title: str,
    slug: str | None,
    body: str,
    excerpt: str | None,
    is_published: bool,
) -> BlogPost:
    title_clean = title.strip()
    if not title_clean:
        raise ValueError("Укажите заголовок")
    slug_base = blog_slugify(slug.strip() if slug and slug.strip() else title_clean)
    slug_final = _ensure_unique_slug(db, slug_base)
    now = datetime.utcnow()
    post = BlogPost(
        title=title_clean,
        slug=slug_final,
        body=body or "",
        excerpt=(excerpt.strip() if excerpt else None) or None,
        is_published=is_published,
        published_at=now if is_published else None,
        author_id=author_id,
        created_at=now,
        updated_at=now,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def update_blog_post(
    db: Session,
    post: BlogPost,
    *,
    title: str,
    slug: str | None,
    body: str,
    excerpt: str | None,
    is_published: bool,
) -> BlogPost:
    title_clean = title.strip()
    if not title_clean:
        raise ValueError("Укажите заголовок")
    slug_in = (slug or "").strip()
    slug_base = blog_slugify(slug_in if slug_in else title_clean)
    post.slug = _ensure_unique_slug(db, slug_base, exclude_id=post.id)
    post.title = title_clean
    post.body = body or ""
    post.excerpt = (excerpt.strip() if excerpt else None) or None
    was_published = post.is_published
    post.is_published = is_published
    if is_published and post.published_at is None:
        post.published_at = datetime.utcnow()
    if not is_published and not was_published:
        post.published_at = None
    post.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(post)
    return post


def delete_blog_post(db: Session, post: BlogPost) -> None:
    db.delete(post)
    db.commit()


# Default published posts seeded once (slug → fields). Existing rows are left alone.
_SEED_BLOG_POSTS: tuple[dict[str, str], ...] = (
    {
        "slug": "kto-my-i-chem-zanimaemsya",
        "title": "Кто мы и чем занимаемся",
        "excerpt": (
            "Auto160 — сервис подбора автомобилей до 160 л.с. из Беларуси и Европы "
            "под льготный утильсбор для физлиц в РФ."
        ),
        "body": """
<p><strong>Auto160</strong> — подбор и доставка легковых авто с упором на порог <strong>до 160 л.с.</strong>,
чтобы машина проходила под льготный утильсбор для физлиц в России.</p>

<h2>Кто мы</h2>
<ul>
  <li>Сервис <a href="/">auto160.ru</a> оператора ООО «Сканди Моторс».</li>
  <li>Работаем с рынками Беларуси и Европы.</li>
  <li>Ориентир — прозрачный расчёт до сделки и безнал по правилам РФ.</li>
</ul>

<h2>Чем занимаемся</h2>
<ul>
  <li><strong>Беларусь:</strong> поиск и проверка объявлений, дата ввоза, осмотр, подбор под ключ, доставка в Москву и регионы.</li>
  <li><strong>Европа:</strong> подбор на площадках и аукционах, проверка истории и пробега, расчёт таможни и утильсбора, сопровождение покупки и логистики.</li>
  <li><strong>До задатка:</strong> проверка VIN и калькулятор растаможки на сайте.</li>
</ul>

<h2>Что важно в подборе</h2>
<ul>
  <li>Мощность до 160 л.с. и объём до 3 л — критерии льготного утильсбора для физлиц.</li>
  <li>Для авто из Беларуси критична дата ввоза в РБ.</li>
  <li>Считаем пошлину и утильсбор до решения о сделке.</li>
</ul>

<h2>Как начать</h2>
<ul>
  <li><a href="/by">Заявка на авто из Беларуси</a></li>
  <li><a href="/eu">Подбор из Европы</a></li>
  <li><a href="/inspection">Проверка даты ввоза по VIN</a></li>
  <li><a href="/calculator">Калькулятор растаможки</a></li>
  <li><a href="/catalog">Каталог комплектаций до 160 л.с.</a></li>
</ul>
""".strip(),
    },
)


def ensure_seed_blog_posts(db: Session) -> int:
    """Insert missing default published posts. Returns number of created rows."""
    created = 0
    now = datetime.utcnow()
    for item in _SEED_BLOG_POSTS:
        slug = item["slug"]
        exists = db.query(BlogPost.id).filter(BlogPost.slug == slug).first()
        if exists:
            continue
        db.add(
            BlogPost(
                title=item["title"],
                slug=slug,
                body=item["body"],
                excerpt=item.get("excerpt"),
                is_published=True,
                published_at=now,
                author_id=None,
                created_at=now,
                updated_at=now,
            )
        )
        created += 1
    if created:
        db.commit()
    return created

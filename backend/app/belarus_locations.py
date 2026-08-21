"""Belarus regions and city grouping for listings location filter."""

from __future__ import annotations

MINSK_CITY = "Минск"

REGION_SLUG_BREST = "brest"
REGION_SLUG_VITEBSK = "vitebsk"
REGION_SLUG_GOMEL = "gomel"
REGION_SLUG_GRODNO = "grodno"
REGION_SLUG_MINSK = "minsk-region"
REGION_SLUG_MOGILEV = "mogilev"

LOCATION_REGIONS: list[dict[str, str]] = [
    {"slug": REGION_SLUG_BREST, "label": "Брестская область"},
    {"slug": REGION_SLUG_VITEBSK, "label": "Витебская область"},
    {"slug": REGION_SLUG_GOMEL, "label": "Гомельская область"},
    {"slug": REGION_SLUG_GRODNO, "label": "Гродненская область"},
    {"slug": REGION_SLUG_MINSK, "label": "Минская область"},
    {"slug": REGION_SLUG_MOGILEV, "label": "Могилёвская область"},
]

_REGION_SLUG_ALIASES: dict[str, str] = {
    "brest": REGION_SLUG_BREST,
    "брестская": REGION_SLUG_BREST,
    "брестская область": REGION_SLUG_BREST,
    "vitebsk": REGION_SLUG_VITEBSK,
    "витебская": REGION_SLUG_VITEBSK,
    "витебская область": REGION_SLUG_VITEBSK,
    "gomel": REGION_SLUG_GOMEL,
    "гомельская": REGION_SLUG_GOMEL,
    "гомельская область": REGION_SLUG_GOMEL,
    "grodno": REGION_SLUG_GRODNO,
    "гродненская": REGION_SLUG_GRODNO,
    "гродненская область": REGION_SLUG_GRODNO,
    "minsk-region": REGION_SLUG_MINSK,
    "minsk_region": REGION_SLUG_MINSK,
    "minskaya": REGION_SLUG_MINSK,
    "минская": REGION_SLUG_MINSK,
    "минская область": REGION_SLUG_MINSK,
    "mogilev": REGION_SLUG_MOGILEV,
    "mogilevskaya": REGION_SLUG_MOGILEV,
    "могилевская": REGION_SLUG_MOGILEV,
    "могилёвская": REGION_SLUG_MOGILEV,
    "могилевская область": REGION_SLUG_MOGILEV,
    "могилёвская область": REGION_SLUG_MOGILEV,
}

CITY_TO_REGION_SLUG: dict[str, str] = {
    "Барановичи": REGION_SLUG_BREST,
    "Белоозёрск": REGION_SLUG_BREST,
    "Береза": REGION_SLUG_BREST,
    "Брест": REGION_SLUG_BREST,
    "Дрогичин": REGION_SLUG_BREST,
    "Ганцевичи": REGION_SLUG_BREST,
    "Иваново": REGION_SLUG_BREST,
    "Ивацевичи": REGION_SLUG_BREST,
    "Каменец": REGION_SLUG_BREST,
    "Кобрин": REGION_SLUG_BREST,
    "Лунинец": REGION_SLUG_BREST,
    "Ляховичи": REGION_SLUG_BREST,
    "Малорита": REGION_SLUG_BREST,
    "Микашевичи": REGION_SLUG_BREST,
    "Пинск": REGION_SLUG_BREST,
    "Пружаны": REGION_SLUG_BREST,
    "Столин": REGION_SLUG_BREST,
    "Жабинка": REGION_SLUG_BREST,
    "Барань": REGION_SLUG_VITEBSK,
    "Бешенковичи": REGION_SLUG_VITEBSK,
    "Браслав": REGION_SLUG_VITEBSK,
    "Витебск": REGION_SLUG_VITEBSK,
    "Глубокое": REGION_SLUG_VITEBSK,
    "Городок": REGION_SLUG_VITEBSK,
    "Докшицы": REGION_SLUG_VITEBSK,
    "Лепель": REGION_SLUG_VITEBSK,
    "Лиозно": REGION_SLUG_VITEBSK,
    "Миоры": REGION_SLUG_VITEBSK,
    "Новолукомль": REGION_SLUG_VITEBSK,
    "Новополоцк": REGION_SLUG_VITEBSK,
    "Орша": REGION_SLUG_VITEBSK,
    "Полоцк": REGION_SLUG_VITEBSK,
    "Поставы": REGION_SLUG_VITEBSK,
    "Россоны": REGION_SLUG_VITEBSK,
    "Россь": REGION_SLUG_VITEBSK,
    "Сенно": REGION_SLUG_VITEBSK,
    "Толочин": REGION_SLUG_VITEBSK,
    "Ушачи": REGION_SLUG_VITEBSK,
    "Чашники": REGION_SLUG_VITEBSK,
    "Шарковщина": REGION_SLUG_VITEBSK,
    "Шумилино": REGION_SLUG_VITEBSK,
    "Буда-Кошелево": REGION_SLUG_GOMEL,
    "Ветка": REGION_SLUG_GOMEL,
    "Гомель": REGION_SLUG_GOMEL,
    "Добруш": REGION_SLUG_GOMEL,
    "Ельск": REGION_SLUG_GOMEL,
    "Житковичи": REGION_SLUG_GOMEL,
    "Жлобин": REGION_SLUG_GOMEL,
    "Калинковичи": REGION_SLUG_GOMEL,
    "Корма": REGION_SLUG_GOMEL,
    "Лельчицы": REGION_SLUG_GOMEL,
    "Лоев": REGION_SLUG_GOMEL,
    "Мозырь": REGION_SLUG_GOMEL,
    "Наровля": REGION_SLUG_GOMEL,
    "Октябрьский": REGION_SLUG_GOMEL,
    "Петриков": REGION_SLUG_GOMEL,
    "Речица": REGION_SLUG_GOMEL,
    "Рогачев": REGION_SLUG_GOMEL,
    "Светлогорск": REGION_SLUG_GOMEL,
    "Хойники": REGION_SLUG_GOMEL,
    "Чечерск": REGION_SLUG_GOMEL,
    "Большая Берестовица": REGION_SLUG_GRODNO,
    "Волковыск": REGION_SLUG_GRODNO,
    "Вороново": REGION_SLUG_GRODNO,
    "Высокое": REGION_SLUG_GRODNO,
    "Гродно": REGION_SLUG_GRODNO,
    "Дятлово": REGION_SLUG_GRODNO,
    "Зельва": REGION_SLUG_GRODNO,
    "Ивье": REGION_SLUG_GRODNO,
    "Кореличи": REGION_SLUG_GRODNO,
    "Лида": REGION_SLUG_GRODNO,
    "Мосты": REGION_SLUG_GRODNO,
    "Новогрудок": REGION_SLUG_GRODNO,
    "Островец": REGION_SLUG_GRODNO,
    "Ошмяны": REGION_SLUG_GRODNO,
    "Свислочь": REGION_SLUG_GRODNO,
    "Скидель": REGION_SLUG_GRODNO,
    "Слоним": REGION_SLUG_GRODNO,
    "Сморгонь": REGION_SLUG_GRODNO,
    "Щучин": REGION_SLUG_GRODNO,
    "Березино": REGION_SLUG_MINSK,
    "Берёзовка": REGION_SLUG_MINSK,
    "Борисов": REGION_SLUG_MINSK,
    "Вилейка": REGION_SLUG_MINSK,
    "Воложин": REGION_SLUG_MINSK,
    "Дзержинск": REGION_SLUG_MINSK,
    "Жодино": REGION_SLUG_MINSK,
    "Заславль": REGION_SLUG_MINSK,
    "Ивенец": REGION_SLUG_MINSK,
    "Клецк": REGION_SLUG_MINSK,
    "Копыль": REGION_SLUG_MINSK,
    "Крупки": REGION_SLUG_MINSK,
    "Логойск": REGION_SLUG_MINSK,
    "Любань": REGION_SLUG_MINSK,
    "Марьина Горка": REGION_SLUG_MINSK,
    "Михановичи": REGION_SLUG_MINSK,
    "Молодечно": REGION_SLUG_MINSK,
    "Мядель": REGION_SLUG_MINSK,
    "Несвиж": REGION_SLUG_MINSK,
    "Раков": REGION_SLUG_MINSK,
    "Руденск": REGION_SLUG_MINSK,
    "Слуцк": REGION_SLUG_MINSK,
    "Смолевичи": REGION_SLUG_MINSK,
    "Солигорск": REGION_SLUG_MINSK,
    "Старые Дороги": REGION_SLUG_MINSK,
    "Столбцы": REGION_SLUG_MINSK,
    "Узда": REGION_SLUG_MINSK,
    "Фаниполь": REGION_SLUG_MINSK,
    "Червень": REGION_SLUG_MINSK,
    "Белыничи": REGION_SLUG_MOGILEV,
    "Бобруйск": REGION_SLUG_MOGILEV,
    "Быхов": REGION_SLUG_MOGILEV,
    "Глуск": REGION_SLUG_MOGILEV,
    "Горки": REGION_SLUG_MOGILEV,
    "Кировск": REGION_SLUG_MOGILEV,
    "Климовичи": REGION_SLUG_MOGILEV,
    "Кличев": REGION_SLUG_MOGILEV,
    "Костюковичи": REGION_SLUG_MOGILEV,
    "Краснополье": REGION_SLUG_MOGILEV,
    "Кричев": REGION_SLUG_MOGILEV,
    "Круглое": REGION_SLUG_MOGILEV,
    "Могилев": REGION_SLUG_MOGILEV,
    "Мстиславль": REGION_SLUG_MOGILEV,
    "Осиповичи": REGION_SLUG_MOGILEV,
    "Славгород": REGION_SLUG_MOGILEV,
    "Хотимск": REGION_SLUG_MOGILEV,
    "Чаусы": REGION_SLUG_MOGILEV,
    "Шклов": REGION_SLUG_MOGILEV,
}

_REGION_LABEL_BY_SLUG = {item["slug"]: item["label"] for item in LOCATION_REGIONS}


def normalize_region_slug(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower().replace("ё", "е")
    if not key:
        return None
    if key in _REGION_SLUG_ALIASES:
        return _REGION_SLUG_ALIASES[key]
    for slug in _REGION_LABEL_BY_SLUG:
        if slug == key:
            return slug
    return None


def parse_location_filter_values(
    raw_regions: list[str] | None,
    raw_cities: list[str] | None,
) -> tuple[list[str], list[str]]:
    regions: list[str] = []
    cities: list[str] = []
    for raw in raw_regions or []:
        slug = normalize_region_slug(raw)
        if slug and slug not in regions:
            regions.append(slug)
    for raw in raw_cities or []:
        name = (raw or "").strip()
        if not name:
            continue
        if name == MINSK_CITY and name not in cities:
            cities.append(name)
            continue
        if name in CITY_TO_REGION_SLUG and name not in cities:
            cities.append(name)
    return regions, cities


def cities_for_region_slug(slug: str) -> list[str]:
    return sorted(city for city, region_slug in CITY_TO_REGION_SLUG.items() if region_slug == slug)


def location_filter_groups(db_cities: list[str]) -> list[dict]:
    available = set(db_cities)
    groups: list[dict] = [
        {
            "type": "standalone",
            "slug": MINSK_CITY,
            "label": MINSK_CITY,
        }
    ]
    for region in LOCATION_REGIONS:
        cities = [
            {"slug": city, "label": city}
            for city in cities_for_region_slug(region["slug"])
            if city in available
        ]
        groups.append(
            {
                "type": "region",
                "slug": region["slug"],
                "label": region["label"],
                "cities": cities,
            }
        )
    return groups


def expand_location_filter_to_city_names(
    region_slugs: list[str],
    city_names: list[str],
    *,
    available_cities: set[str] | None = None,
) -> list[str]:
    matched: set[str] = set()
    available = available_cities or set(CITY_TO_REGION_SLUG) | {MINSK_CITY}
    for city in city_names:
        if city in available:
            matched.add(city)
    for slug in region_slugs:
        for city in cities_for_region_slug(slug):
            if city in available:
                matched.add(city)
    return sorted(matched)


def location_filter_checked_state(
    region_slugs: list[str],
    city_names: list[str],
) -> dict[str, set[str] | bool]:
    checked_regions = set(region_slugs)
    checked_standalone = MINSK_CITY in city_names
    checked_cities: set[str] = set()
    for city in city_names:
        if city == MINSK_CITY:
            continue
        region_slug = CITY_TO_REGION_SLUG.get(city)
        if region_slug and region_slug in checked_regions:
            continue
        checked_cities.add(city)
    visible_checked_cities: set[str] = set(checked_cities)
    for slug in checked_regions:
        visible_checked_cities.update(cities_for_region_slug(slug))
    return {
        "standalone": checked_standalone,
        "regions": checked_regions,
        "cities": visible_checked_cities,
    }


def location_filter_display_label(region_slugs: list[str], city_names: list[str]) -> str:
    labels: list[str] = []
    if MINSK_CITY in city_names:
        labels.append(MINSK_CITY)
    for slug in region_slugs:
        label = _REGION_LABEL_BY_SLUG.get(slug)
        if label:
            labels.append(label)
    explicit_cities = [
        city
        for city in city_names
        if city != MINSK_CITY and CITY_TO_REGION_SLUG.get(city) not in region_slugs
    ]
    labels.extend(explicit_cities)
    if not labels:
        return "Любой"
    if len(labels) == 1:
        return labels[0]
    return f"Выбрано пунктов: {len(labels)}"


def apply_listings_location_filter(query, column, *, region_slugs: list[str], city_names: list[str], available_cities: set[str]):
    matched = expand_location_filter_to_city_names(
        region_slugs,
        city_names,
        available_cities=available_cities,
    )
    if not matched:
        return query
    return query.filter(column.in_(matched))

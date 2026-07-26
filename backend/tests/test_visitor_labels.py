from starlette.requests import Request

from app.visitor_labels import classify_visitor, event_actor_label, format_actor_name


def _request(
    *,
    user_agent: str = "",
    client_header: str = "",
    ip: str = "203.0.113.10",
) -> Request:
    headers = []
    if user_agent:
        headers.append((b"user-agent", user_agent.encode()))
    if client_header:
        headers.append((b"x-auto160-client", client_header.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/listings",
        "headers": headers,
        "client": (ip, 12345),
    }
    return Request(scope)


def test_classify_yandex_bot():
    result = classify_visitor(_request(user_agent="Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"))
    assert result["visitor_name"] == "Яндекс-бот"


def test_classify_internal_client_header():
    result = classify_visitor(_request(client_header="avby-sync"))
    assert result["visitor_name"] == "Сервис: Парсинг av.by"


def test_classify_internal_user_agent():
    result = classify_visitor(_request(user_agent="Auto160Internal/avby-archive"))
    assert result["visitor_name"] == "Сервис: Архивация av.by"


def test_classify_script_user_agent():
    result = classify_visitor(_request(user_agent="python-requests/2.32.3"))
    assert result["visitor_name"] == "Скрипт (curl/Python)"


def test_format_actor_name_decodes_json_string():
    assert format_actor_name('"\\u042f\\u043d\\u0434\\u0435\\u043a\\u0441-\\u0431\\u043e\\u0442"') == "Яндекс-бот"


def test_format_actor_name_empty():
    assert format_actor_name(None) == "Без метки (старые записи)"


def test_event_actor_label_prefers_email():
    assert event_actor_label(user_email="admin@auto160.com", details={"visitor_name": "Яндекс-бот"}) == "admin@auto160.com"

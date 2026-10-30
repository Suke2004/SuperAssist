from urllib.parse import urlsplit


def same_origin(origin: str, scheme: str, host: str) -> bool:
    """Match the complete browser origin, including its effective port."""
    try:
        supplied = urlsplit(origin)
        expected = urlsplit(f"{scheme}://{host}")
        return (supplied.scheme in ("http", "https")
                and not supplied.username and not supplied.password
                and supplied.path in ("", "/") and not supplied.query and not supplied.fragment
                and (supplied.scheme, supplied.hostname, supplied.port or (443 if supplied.scheme == "https" else 80))
                == (expected.scheme, expected.hostname, expected.port or (443 if expected.scheme == "https" else 80)))
    except (ValueError, TypeError):
        return False

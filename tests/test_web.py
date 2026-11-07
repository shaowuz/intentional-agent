"""Network-free tests of the public web reader's access boundary."""

import asyncio
import socket
import threading
import time

import pytest

from intentional_agent.web import (
    FetchResult,
    WebReadError,
    _PinnedConnection,
    _fetch,
    _validate_target,
    read_webpage,
)


PUBLIC_IP = "93.184.216.34"


def resolve_public(host, port):
    return [PUBLIC_IP]


def read(url="https://example.com/page", **kwargs):
    return asyncio.run(read_webpage(url, _resolver=resolve_public, **kwargs))


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/file", "http://localhost/api",
    "http://app.local/api", "http://app.internal/api", "http://metadata/api",
    "http://127.0.0.1/api", "http://10.0.0.1/", "http://169.254.169.254/",
    "http://192.168.1.1/", "http://[::1]/", "http://[fc00::1]/",
    "http://[::ffff:127.0.0.1]/", "http://[2002:7f00:1::]/",
    "http://user:password@example.com/", "http://example.com:8000/",
    "http://example.com\\@127.0.0.1/", "http://example.com/\nheader",
    "https://example.com:0/", "https://example.com:65536/",
])
def test_rejects_non_public_and_credential_urls_before_fetch(url):
    def forbidden_fetch(*args):
        pytest.fail("A prohibited URL reached the HTTP client")

    with pytest.raises(WebReadError):
        read(url, _fetcher=forbidden_fetch)


def test_rejects_mixed_public_private_dns_answers():
    with pytest.raises(WebReadError, match="public internet"):
        asyncio.run(read_webpage(
            "https://example.com/",
            _resolver=lambda *_: [PUBLIC_IP, "127.0.0.1"],
            _fetcher=lambda *_: pytest.fail("No request should be sent"),
        ))


def test_dns_resolves_once_and_passes_pinned_addresses():
    calls = []

    def resolver(host, port):
        calls.append((host, port))
        return [PUBLIC_IP] if len(calls) == 1 else ["127.0.0.1"]

    def fetcher(target, max_bytes, timeout):
        assert target.host == "example.com"
        assert target.addresses == (PUBLIC_IP,)
        return FetchResult(200, {"content-type": "text/plain"}, b"Public result")

    result = asyncio.run(read_webpage("https://example.com/", _resolver=resolver, _fetcher=fetcher))
    assert result["text"] == "Public result"
    assert calls == [("example.com", 443)]


def test_actual_connector_uses_numeric_address_and_original_tls_hostname(monkeypatch):
    seen = {}

    class FakeSocket:
        def settimeout(self, timeout):
            assert timeout > 0

        def connect(self, address):
            seen["address"] = address

        def close(self):
            pass

        def do_handshake(self):
            seen["handshake"] = True

    class FakeContext:
        def wrap_socket(self, connection, server_hostname, do_handshake_on_connect):
            assert do_handshake_on_connect is False
            seen["server_hostname"] = server_hostname
            return connection

    def create_socket(family, kind):
        assert family == socket.AF_INET
        assert kind == socket.SOCK_STREAM
        return FakeSocket()

    monkeypatch.setattr("intentional_agent.web.socket.socket", create_socket)
    monkeypatch.setattr("intentional_agent.web.httpx.create_ssl_context", lambda **kwargs: FakeContext())
    target = _validate_target("https://example.com/", resolve_public)
    connection = _PinnedConnection(target, 3)
    connection.connect()
    assert seen == {"address": (PUBLIC_IP, 443), "server_hostname": "example.com", "handshake": True}


def test_redirect_to_private_address_is_blocked():
    calls = []

    def fetcher(target, *_):
        calls.append(target.url)
        return FetchResult(302, {"location": "http://169.254.169.254/metadata"}, b"")

    with pytest.raises(WebReadError, match="public internet"):
        read(_fetcher=fetcher)
    assert len(calls) == 1


def test_each_redirect_is_resolved_again_and_rebinding_is_blocked():
    resolutions = 0

    def resolver(*_):
        nonlocal resolutions
        resolutions += 1
        return [PUBLIC_IP] if resolutions == 1 else ["127.0.0.1"]

    with pytest.raises(WebReadError, match="public internet"):
        asyncio.run(read_webpage(
            "https://example.com/", _resolver=resolver,
            _fetcher=lambda *_: FetchResult(302, {"location": "/next"}, b""),
        ))
    assert resolutions == 2


def test_redirect_limit():
    calls = []

    def fetcher(target, *_):
        calls.append(target.url)
        return FetchResult(302, {"location": "/loop"}, b"")

    with pytest.raises(WebReadError, match="too many"):
        read(_fetcher=fetcher)
    assert len(calls) == 4


def test_html_returns_text_not_scripts_or_markup():
    body = b"""<html><head><title>Example &amp; Evidence</title>
    <style>hidden css</style></head><body><h1>Heading</h1>
    <script>stealKeys()</script><p>Useful <b>text</b>.</p></body></html>"""
    result = read(_fetcher=lambda *_: FetchResult(200, {"Content-Type": "text/html; charset=utf-8"}, body))
    assert result["title"] == "Example & Evidence"
    assert result["text"] == "Heading\nUseful text."
    assert result["source_type"] == "external_webpage"
    assert result["content_truncated"] is False


def test_bounded_output_is_marked_truncated():
    result = read(max_chars=5, _fetcher=lambda *_: FetchResult(200, {"content-type": "text/plain"}, b"abcdefghij"))
    assert result["text"] == "abcde"
    assert result["content_truncated"] is True
    result = read(_fetcher=lambda *_: FetchResult(200, {"content-type": "text/plain"}, b"abc", True))
    assert result["content_truncated"] is True


@pytest.mark.parametrize("headers", [
    {"content-type": "application/octet-stream"},
    {"content-type": "image/png"},
    {"content-type": "text/html", "content-encoding": "gzip"},
])
def test_unsupported_content_is_rejected(headers):
    with pytest.raises(WebReadError):
        read(_fetcher=lambda *_: FetchResult(200, headers, b"data"))


def test_network_error_does_not_echo_sensitive_details():
    def fetcher(*_):
        raise OSError("Some provider failure with a secret-token")

    with pytest.raises(WebReadError) as error:
        read(_fetcher=fetcher)
    assert "secret-token" not in str(error.value)


def test_unicode_host_and_path_are_normalized():
    target = _validate_target("https://b\u00fccher.example/hello\u4e16\u754c?q=\u4e16\u754c#fragment", resolve_public)
    assert target.host == "xn--bcher-kva.example"
    assert "%E4%B8%96%E7%95%8C" in target.path
    assert "fragment" not in target.url


def test_transport_reads_only_one_byte_beyond_limit(monkeypatch):
    body = b"abcdefghij"
    reads = []

    class Response:
        status = 200

        def getheaders(self):
            return [("Content-Type", "text/plain")]

        def read1(self, count):
            reads.append(count)
            return body[:count]

    class Connection:
        def __init__(self, target, timeout):
            self.deadline = time.monotonic() + timeout

        def request(self, method, path, headers):
            assert method == "GET"
            assert headers["Accept-Encoding"] == "identity"

        def getresponse(self):
            return Response()

        def abort(self):
            pass

    monkeypatch.setattr("intentional_agent.web._PinnedConnection", Connection)
    result = _fetch(_validate_target("https://example.com/", resolve_public), 5, 1)
    assert reads == [6]
    assert result.body == b"abcde"
    assert result.truncated is True


def test_transport_watchdog_interrupts_stalled_response(monkeypatch):
    closed = threading.Event()

    class Connection:
        def __init__(self, target, timeout):
            self.deadline = time.monotonic() + timeout

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            assert closed.wait(1), "The watchdog did not close the stalled connection"
            raise OSError("Connection closed")

        def abort(self):
            closed.set()

    monkeypatch.setattr("intentional_agent.web._PinnedConnection", Connection)
    with pytest.raises(OSError):
        _fetch(_validate_target("https://example.com/", resolve_public), 5, 0.01)
    assert closed.is_set()


def test_slow_dns_keeps_admission_bounded_after_caller_timeout():
    release = threading.Event()
    started = []
    lock = threading.Lock()

    def slow_resolver(*args):
        with lock:
            started.append(threading.current_thread().name)
        release.wait(2)
        return [PUBLIC_IP]

    async def exercise():
        tasks = [asyncio.create_task(read_webpage(
            "https://example.com/", timeout=0.01, _resolver=slow_resolver,
            _fetcher=lambda *_: pytest.fail("An expired request reached the network"),
        )) for _ in range(4)]
        try:
            errors = await asyncio.gather(*tasks, return_exceptions=True)
            assert all(isinstance(error, WebReadError) for error in errors)
            assert len(started) == 4
            assert all(name.startswith("public-web") for name in started)
            with pytest.raises(WebReadError, match="busy"):
                await read_webpage("https://example.com/", _resolver=resolve_public)
            # Slow web DNS does not occupy the executor used by the rest of the app.
            assert await asyncio.wait_for(asyncio.to_thread(lambda: "available"), 0.1) == "available"
        finally:
            release.set()
            # Allow actual worker completion callbacks to return admission slots.
            for _ in range(100):
                try:
                    await read_webpage(
                        "https://example.com/", _resolver=resolve_public,
                        _fetcher=lambda *_: FetchResult(200, {"content-type": "text/plain"}, b"ok"),
                    )
                    break
                except WebReadError:
                    await asyncio.sleep(0.01)

    asyncio.run(exercise())

"""Bounded public-web reading without access to local or private networks.

The resolver and connector share a validated, pinned IP list. Resolving a hostname
again inside an HTTP client would make an initial SSRF check vulnerable to DNS
rebinding. TLS still verifies the original hostname, not the pinned address.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import http.client
import ipaddress
import re
import socket
import threading
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable, Iterable
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpx


class WebReadError(RuntimeError):
    """A sanitized, safe-to-display web reader failure."""


@dataclass(frozen=True)
class ValidatedTarget:
    url: str
    scheme: str
    host: str
    port: int
    path: str
    addresses: tuple[str, ...]


@dataclass(frozen=True)
class FetchResult:
    status: int
    headers: dict[str, str]
    body: bytes
    truncated: bool = False


Resolver = Callable[[str, int], Iterable[str]]
Fetcher = Callable[[ValidatedTarget, int, float], FetchResult]
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
# DNS resolution is a blocking system call that Python cannot forcibly cancel.
# Bound outstanding readers independently of asyncio's shared executor, keeping
# each slot until its actual worker exits even if its caller has timed out.
_WEB_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="public-web")
_WEB_SLOTS = threading.BoundedSemaphore(4)


def _public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if "%" in value:
        return False
    if not address.is_global or address.is_multicast or address.is_reserved:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return _public_address(str(address.ipv4_mapped))
        # Transition mechanisms can hide a second, otherwise restricted address.
        if address.sixtofour is not None or address.teredo is not None:
            return False
    return True


def _default_resolver(host: str, port: int) -> Iterable[str]:
    return [
        info[4][0]
        for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    ]


def _validate_target(url: str, resolver: Resolver) -> ValidatedTarget:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise WebReadError("Provide an HTTP or HTTPS URL of at most 4096 characters.")
    if "\\" in url or any(ord(character) < 33 or ord(character) == 127 for character in url):
        raise WebReadError("The URL contains unsupported whitespace or control characters.")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise WebReadError("The URL is malformed.") from None
    if parts.scheme not in {"http", "https"} or not host:
        raise WebReadError("Only HTTP and HTTPS URLs are supported.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise WebReadError("URLs containing credentials are not allowed.")
    port = port if port is not None else (443 if parts.scheme == "https" else 80)
    if port not in {80, 443}:
        raise WebReadError("Only public web ports 80 and 443 are allowed.")
    host = host.rstrip(".").lower()
    if not host or "%" in host:
        raise WebReadError("The URL hostname is not supported.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is None:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise WebReadError("The URL hostname is not valid.") from None
        if len(host) > 253 or not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        ):
            raise WebReadError("The URL hostname is not valid.")
        if "." not in host or host.endswith((".localhost", ".local", ".internal", ".test")):
            raise WebReadError("Local and internal hostnames are not allowed.")
        try:
            addresses = tuple(dict.fromkeys(resolver(host, port)))
        except (OSError, ValueError, UnicodeError):
            raise WebReadError("The webpage hostname could not be resolved.") from None
    else:
        addresses = (str(literal),)
    if not addresses or any(not _public_address(address) for address in addresses):
        raise WebReadError("The URL must resolve only to public internet addresses.")
    if len(addresses) > 32:
        raise WebReadError("The hostname returned too many network addresses.")

    netloc = f"[{host}]" if ":" in host else host
    default_port = 443 if parts.scheme == "https" else 80
    if port != default_port:
        netloc += f":{port}"
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="/?%:@!$&'()*+,;=-._~")
    normalized = urlunsplit((parts.scheme, netloc, path, query, ""))
    target_path = path + (f"?{query}" if query else "")
    return ValidatedTarget(normalized, parts.scheme, host, port, target_path, addresses)


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, target: ValidatedTarget, timeout: float):
        super().__init__(target.host, target.port, timeout=timeout)
        self.target = target
        self.deadline = time.monotonic() + timeout
        self.active_socket: socket.socket | None = None
        self.aborted = threading.Event()

    def abort(self) -> None:
        # shutdown interrupts a read even while HTTPResponse owns a socket file.
        self.aborted.set()
        active_socket = self.active_socket
        if active_socket is not None:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            active_socket.close()
        self.close()

    def connect(self) -> None:
        last_error: OSError | None = None
        for address in self.target.addresses:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Web request timed out.")
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            connection = socket.socket(family, socket.SOCK_STREAM)
            self.active_socket = connection
            try:
                if self.aborted.is_set():
                    raise TimeoutError("Web request timed out.")
                connection.settimeout(remaining)
                # Numeric socket.connect does not re-resolve the hostname.
                connection.connect((address, self.target.port))
                if self.target.scheme == "https":
                    # Use the same verified CA bundle as the OpenRouter client;
                    # Python installations do not always have a system CA path.
                    connection = httpx.create_ssl_context(verify=True, trust_env=False).wrap_socket(
                        connection, server_hostname=self.target.host, do_handshake_on_connect=False
                    )
                    self.active_socket = connection
                    if self.aborted.is_set():
                        raise TimeoutError("Web request timed out.")
                    connection.do_handshake()
                self.sock = connection
                return
            except OSError as error:
                last_error = error
                connection.close()
                self.active_socket = None
        raise last_error or OSError("No public address could be reached.")


def _fetch(target: ValidatedTarget, max_bytes: int, timeout: float) -> FetchResult:
    connection = _PinnedConnection(target, timeout)
    timer = threading.Timer(timeout, connection.abort)
    timer.daemon = True
    timer.start()
    try:
        connection.request(
            "GET",
            target.path,
            headers={
                "User-Agent": "IntentionalAgentResearch/0.1",
                "Accept": "text/html, text/plain;q=0.9",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        if response.status in REDIRECT_STATUSES:
            return FetchResult(response.status, headers, b"")
        body = bytearray()
        while len(body) <= max_bytes:
            if time.monotonic() >= connection.deadline:
                raise TimeoutError("Web request timed out.")
            chunk = response.read1(min(65536, max_bytes + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        return FetchResult(response.status, headers, bytes(body[:max_bytes]), len(body) > max_bytes)
    finally:
        timer.cancel()
        connection.abort()


class _TextExtractor(HTMLParser):
    EXCLUDED_TAGS = {"script", "style", "noscript", "svg", "template", "iframe"}
    BLOCK_TAGS = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.excluded: list[str] = []
        self.in_title = False
        self.title: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.EXCLUDED_TAGS:
            self.excluded.append(tag)
        if tag == "title":
            self.in_title = True
        if not self.excluded and tag in self.BLOCK_TAGS:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.excluded and tag == self.excluded[-1]:
            self.excluded.pop()
        if tag == "title":
            self.in_title = False
        if not self.excluded and tag in self.BLOCK_TAGS:
            self.text.append("\n")

    def handle_data(self, data: str) -> None:
        if self.excluded:
            return
        if self.in_title:
            self.title.append(data)
        else:
            self.text.append(data)


def _extract(result: FetchResult, url: str, max_chars: int) -> dict:
    headers = {name.lower(): value for name, value in result.headers.items()}
    content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"text/html", "text/plain"}:
        raise WebReadError("Only HTML and plain-text webpages can be read.")
    if headers.get("content-encoding", "identity").strip().lower() not in {"", "identity"}:
        raise WebReadError("Compressed responses are not supported by the bounded web reader.")
    match = re.search(r"charset\s*=\s*[\"']?([a-zA-Z0-9_-]+)", headers.get("content-type", ""), re.I)
    charset = match.group(1).lower() if match else "utf-8"
    if charset not in {"utf-8", "utf8", "ascii", "iso-8859-1", "latin-1", "windows-1252", "utf-16", "utf-16le", "utf-16be"}:
        charset = "utf-8"
    decoded = result.body.decode(charset, errors="replace")
    title = ""
    if content_type == "text/html":
        parser = _TextExtractor()
        parser.feed(decoded)
        title = " ".join("".join(parser.title).split())[:256]
        decoded = "".join(parser.text)
    text = "\n".join(
        normalized for line in decoded.splitlines()
        if (normalized := " ".join(line.split()))
    )
    return {
        "url": url,
        "title": title,
        "text": text[:max_chars],
        "content_truncated": result.truncated or len(text) > max_chars,
        "source_type": "external_webpage",
    }


def _read_sync(
    url: str, timeout: float, max_bytes: int, max_chars: int,
    resolver: Resolver, fetcher: Fetcher,
) -> dict:
    deadline = time.monotonic() + timeout
    for redirects in range(4):
        target = _validate_target(url, resolver)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WebReadError("The webpage request timed out.")
        try:
            result = fetcher(target, max_bytes, remaining)
        except (OSError, http.client.HTTPException, ValueError):
            raise WebReadError("The webpage request failed or timed out.") from None
        if result.status in REDIRECT_STATUSES:
            if redirects == 3:
                raise WebReadError("The webpage redirected too many times.")
            location = next((v for k, v in result.headers.items() if k.lower() == "location"), "")
            if not location:
                raise WebReadError("The webpage redirect has no destination.")
            url = urljoin(target.url, location)
            continue
        if result.status < 200 or result.status >= 300:
            raise WebReadError(f"The webpage returned HTTP {result.status}.")
        return _extract(result, target.url, max_chars)
    raise WebReadError("The webpage redirected too many times.")


async def read_webpage(
    url: str, *, timeout: float = 10.0, max_bytes: int = 524288,
    max_chars: int = 16000, _resolver: Resolver | None = None,
    _fetcher: Fetcher | None = None,
) -> dict:
    """Read public HTML/plain text; returned content is untrusted external data.

    The underscored dependency hooks support offline tests. Agent tool handlers
    must expose only the URL argument and choose their own bounded limits.
    """
    if not 0 < timeout <= 30 or not 1 <= max_bytes <= 1048576 or not 1 <= max_chars <= 32000:
        raise WebReadError("The web reader limits are outside the supported range.")
    if not _WEB_SLOTS.acquire(blocking=False):
        raise WebReadError("The web reader is busy. Retry after outstanding requests finish.")
    try:
        worker = _WEB_EXECUTOR.submit(
            _read_sync, url, timeout, max_bytes, max_chars,
            _resolver or _default_resolver, _fetcher or _fetch,
        )
    except BaseException:
        _WEB_SLOTS.release()
        raise
    worker.add_done_callback(lambda _: _WEB_SLOTS.release())
    try:
        return await asyncio.wait_for(
            asyncio.wrap_future(worker),
            timeout=timeout + 0.25,
        )
    except TimeoutError:
        raise WebReadError("The webpage request timed out.") from None

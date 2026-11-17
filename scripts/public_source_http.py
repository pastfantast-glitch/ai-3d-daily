"""Bounded HTTPS fetch pinned to a validated public DNS address (including redirects)."""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urljoin
import requests
from collection_settings import public_url


def get(url, timeout, headers=None):
    for _ in range(5):
        if not public_url(url):
            raise requests.RequestException('unsafe-source-url')
        parts = urlsplit(url)
        try:
            addresses = list(dict.fromkeys(r[4][0] for r in socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)))
            if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
                raise ValueError('unsafe-source-address')
            class PinnedTLS(http.client.HTTPSConnection):
                def connect(self):
                    self.sock = ssl.create_default_context().wrap_socket(
                        socket.create_connection((addresses[0],443),timeout), server_hostname=parts.hostname)
            connection = PinnedTLS(parts.hostname, timeout=timeout)
            try:
                safe_headers = {k:v for k,v in (headers or {}).items() if k.lower() in ('user-agent','accept','accept-language')}
                safe_headers['Accept-Encoding'] = 'identity'
                connection.request('GET', parts.path + ('?' + parts.query if parts.query else '') or '/', headers=safe_headers)
                response = connection.getresponse()
                if response.status in (301,302,303,307,308):
                    url = urljoin(url, response.getheader('Location', ''))
                    continue
                body = response.read(2_000_001)
                if len(body)>2_000_000: raise ValueError('source-response-too-large')
                out = requests.Response()
                out.status_code = response.status
                out.headers.update(dict(response.getheaders()))
                out.url = url
                out._content = body
                out.encoding = requests.utils.get_encoding_from_headers(out.headers)
                return out
            finally:
                connection.close()
        except (OSError, ValueError, http.client.HTTPException) as exc:
            raise requests.RequestException(str(exc)) from exc
    raise requests.RequestException('too-many-source-redirects')

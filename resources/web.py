"""
Read a web page aloud: fetch a URL server-side (the browser can't, due to CORS),
extract the readable English text, and return it for the client to speak.
"""

import ipaddress
import json
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required

MAX_BYTES = 3_000_000   # don't download more than ~3 MB of HTML
MAX_CHARS = 20_000      # cap extracted text so TTS stays manageable


def _json(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


def _host_is_safe(host):
    """Block loopback/private/link-local/reserved targets (basic SSRF guard)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def _extract(html, fallback_title):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer",
                     "nav", "aside", "form", "svg"]):
        tag.decompose()
    title = fallback_title
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    # Prefer the main article region if the page marks one up.
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = " ".join(main.get_text(separator=" ").split())
    return title, text[:MAX_CHARS]


class ReadUrlAPI(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        url = (data.get("url") or "").strip()
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return _json({"message": "Please enter a valid web address starting with http:// or https://"}, 400)
        if not _host_is_safe(parsed.hostname):
            return _json({"message": "That address can’t be read for security reasons."}, 400)

        try:
            resp = requests.get(
                url, timeout=15, allow_redirects=True,
                headers={"User-Agent": "EyewazReader/1.0 (+accessibility reader)"},
            )
        except requests.RequestException as e:
            return _json({"message": f"Could not open the page: {e}"}, 502)

        # Re-check the final host in case a redirect pointed somewhere internal.
        final_host = urlparse(resp.url).hostname
        if final_host and not _host_is_safe(final_host):
            return _json({"message": "That address can’t be read for security reasons."}, 400)

        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype:
            return _json({"message": "That link is not a readable web page."}, 415)

        html = resp.content[:MAX_BYTES].decode(resp.encoding or "utf-8", errors="ignore")
        title, text = _extract(html, parsed.hostname)

        if not text:
            return _json({"message": "No readable text was found on that page."}, 422)

        return _json({"title": title, "text": text, "url": resp.url}, 200)

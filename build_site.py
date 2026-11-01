from http.cookiejar import CookieJar
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener
from zipfile import ZipFile
import shutil

SOURCE_URL = (
    "https://drive.usercontent.google.com/download"
    "?id=1umW35rNBjePIV5oN2Pf7Jukv9SCxKR7B&export=download"
)
OUTPUT = Path("public")


class DownloadFormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_download_form = False
        self.action = ""
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "download-form":
            self.in_download_form = True
            self.action = attrs.get("action", "")
        elif tag == "input" and self.in_download_form:
            name = attrs.get("name")
            value = attrs.get("value")
            if name and value is not None:
                self.values[name] = value

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_download_form = False


def request_bytes(opener, url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(request, timeout=180) as response:
        return response.read(), response.headers.get_content_type()


opener = build_opener(HTTPCookieProcessor(CookieJar()))
payload, content_type = request_bytes(opener, SOURCE_URL)

if content_type == "text/html":
    parser = DownloadFormParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    if not parser.action or not parser.values:
        raise RuntimeError("Google Drive confirmation form was not found.")
    confirmed_url = urljoin(SOURCE_URL, parser.action) + "?" + urlencode(parser.values)
    payload, content_type = request_bytes(opener, confirmed_url)

if not payload.startswith(b"PK"):
    raise RuntimeError(f"Expected a ZIP file, received {content_type!r}.")

if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
OUTPUT.mkdir(parents=True)

with ZipFile(BytesIO(payload)) as archive:
    output_root = OUTPUT.resolve()
    for member in archive.infolist():
        destination = (OUTPUT / member.filename).resolve()
        if destination != output_root and output_root not in destination.parents:
            raise RuntimeError(f"Unsafe ZIP path: {member.filename}")
    archive.extractall(OUTPUT)

required = [
    OUTPUT / "index.html",
    OUTPUT / "style.css",
    OUTPUT / "script.js",
    OUTPUT / "hero-entrance.js",
    OUTPUT / "images",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise RuntimeError(f"Missing website files after extraction: {missing}")

print(f"Prepared {sum(1 for path in OUTPUT.rglob('*') if path.is_file())} website files.")

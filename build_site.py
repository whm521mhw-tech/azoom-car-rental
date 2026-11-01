from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin
from zipfile import ZipFile, is_zipfile
import shutil
import subprocess

SOURCE_URL = (
    "https://drive.usercontent.google.com/download"
    "?id=1umW35rNBjePIV5oN2Pf7Jukv9SCxKR7B&export=download"
)
OUTPUT = Path("public")
DOWNLOAD = Path("site-source-download.zip")
COOKIE_JAR = Path("site-source-cookies.txt")


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


def curl_download(url, output, use_cookies=False):
    command = [
        "curl",
        "-L",
        "--fail",
        "--retry",
        "5",
        "--retry-all-errors",
        "--user-agent",
        "Mozilla/5.0",
        "--output",
        str(output),
    ]
    if use_cookies:
        command.extend(["--cookie", str(COOKIE_JAR)])
    else:
        command.extend(["--cookie-jar", str(COOKIE_JAR)])
    command.append(url)
    subprocess.run(command, check=True)


curl_download(SOURCE_URL, DOWNLOAD)
if not is_zipfile(DOWNLOAD):
    parser = DownloadFormParser()
    parser.feed(DOWNLOAD.read_text(encoding="utf-8", errors="replace"))
    if not parser.action or not parser.values:
        raise RuntimeError("Google Drive confirmation form was not found.")
    confirmed_url = urljoin(SOURCE_URL, parser.action) + "?" + urlencode(parser.values)
    curl_download(confirmed_url, DOWNLOAD, use_cookies=True)

if not is_zipfile(DOWNLOAD):
    raise RuntimeError("Google Drive did not return the expected ZIP file.")

if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
OUTPUT.mkdir(parents=True)

with ZipFile(DOWNLOAD) as archive:
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

DOWNLOAD.unlink(missing_ok=True)
COOKIE_JAR.unlink(missing_ok=True)
print(f"Prepared {sum(1 for path in OUTPUT.rglob('*') if path.is_file())} website files.")


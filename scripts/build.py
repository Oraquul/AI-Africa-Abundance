#!/usr/bin/env python3
"""Build the AI Africa Abundance static site.

Reads the verified white paper, oracle YAML, progress entries, and Markdown
collections. Validates data against JSON Schema. Writes HTML, an RSS feed,
a JSON export, and a PDF of the paper into dist/.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from xml.sax.saxutils import escape as xml_escape

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jsonschema import Draft202012Validator, FormatChecker
from markupsafe import Markup
from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
DIST = ROOT / "dist"
PAPER_SRC = CONTENT / "paper" / "white-paper-v3.1.md"

ORIGIN = "https://oraquul.github.io"
BASE_PATH = "/AI-Africa-Abundance"
REPO = "https://github.com/Oraquul/AI-Africa-Abundance"
SITE = ORIGIN + BASE_PATH

STATUS_ORDER = [
    "proposed",
    "specified",
    "data-sourcing",
    "prototype",
    "published",
    "leaderboard-live",
    "retired",
]
STATUS_LABEL = {
    "proposed": "Proposed",
    "specified": "Specified",
    "data-sourcing": "Data sourcing",
    "prototype": "Prototype",
    "published": "Published",
    "leaderboard-live": "Leaderboard live",
    "retired": "Retired",
}
LAYER_ORDER = ["benchmark", "simulator", "data", "lab", "field"]
LAYER_LABEL = {
    "benchmark": "Benchmark",
    "data": "Data",
    "lab": "Laboratory",
    "field": "Field network",
    "simulator": "Simulator",
}
DOMAIN_ORDER = [
    "Logistics and trade",
    "Connectivity",
    "Energy",
    "Housing and built environment",
    "Health",
    "Agriculture",
    "Environment",
    "Language and access",
]
NAV = [
    ("Home", "/"),
    ("White paper", "/paper/"),
    ("Oracles", "/oracles/"),
    ("Progress", "/progress/"),
    ("Share", "/share/"),
    ("Blog", "/blog/"),
    ("Research", "/research/"),
    ("Contribute", "/contribute/"),
    ("About", "/about/"),
]
FORBIDDEN = [
    re.compile(r"\bPACTS\b", re.I),
    re.compile(r"\bExportReady\b", re.I),
    re.compile(r"\bEUDR\b", re.I),
]

MD = markdown.Markdown(extensions=["tables", "sane_lists", "fenced_code"])


def url(path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        raise ValueError(f"path must start with /: {path}")
    return BASE_PATH + path


def absurl(path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    return ORIGIN + url(path)


def correction_url(section_label: str) -> str:
    query = urlencode(
        {
            "template": "correct-paper.yml",
            "title": f"Correction: {section_label}",
            "section": section_label,
            "labels": "paper",
        }
    )
    return f"{REPO}/issues/new?{query}"


def loosen_lists(text: str) -> str:
    """The master often puts a list directly under a bold label, with no blank line.

    CommonMark then keeps the dashes inside the paragraph. Insert the blank line
    at render time so the lists are lists, without editing the verified file.
    """
    output: list[str] = []
    for line in text.splitlines():
        previous = output[-1] if output else ""
        is_list = line.startswith("- ") or re.match(r"\d+\.\s", line) is not None
        previous_is_list = previous.startswith("- ") or re.match(r"\d+\.\s", previous) is not None
        if is_list and previous.strip() and not previous_is_list:
            output.append("")
        output.append(line)
    return "\n".join(output)


def render_markdown(text: str) -> str:
    MD.reset()
    return MD.convert(text)


def plain_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(text).strip()


def slugify(text: str) -> str:
    value = text.lower().replace("—", " ").replace("–", " ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "section"


def enrich_html(raw_html: str, corrections: bool) -> tuple[Markup, list[dict]]:
    used: dict[str, int] = {}
    toc: list[dict] = []

    def replace(match: re.Match) -> str:
        level = int(match.group(1))
        inner = match.group(2)
        text = plain_text(inner)
        base = slugify(text)
        used[base] = used.get(base, 0) + 1
        slug = base if used[base] == 1 else f"{base}-{used[base]}"
        if level in (2, 3):
            toc.append({"id": slug, "text": text, "level": level})
        heading = f'<h{level} id="{slug}">{inner}</h{level}>'
        if not corrections or level > 3:
            return heading
        link = correction_url(text)
        hidden = html.escape(text)
        return (
            '<div class="section-head">'
            f"{heading}"
            f'<a class="correction" href="{html.escape(link, quote=True)}">'
            "Suggest a correction"
            f'<span class="visually-hidden"> to {hidden}</span></a>'
            "</div>"
        )

    enriched = re.sub(r"<h([1-6])>(.*?)</h\1>", replace, raw_html)
    enriched = enriched.replace(
        "<table>",
        '<div class="table-wrap" tabindex="0" role="region" aria-label="Table, scroll horizontally if it is wider than the screen"><table>',
    )
    enriched = enriched.replace("</table>", "</table></div>")
    return Markup(enriched), toc


def clean_body(text: str) -> str:
    lines = text.strip().splitlines()
    while lines and lines[0].strip() in {"---", ""}:
        lines.pop(0)
    while lines and lines[-1].strip() in {"---", "", "*End of document.*"}:
        lines.pop()
    return "\n".join(lines).strip()


def load_schema(name: str) -> Draft202012Validator:
    schema = json.loads((DATA / "schema" / name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def schema_errors(validator: Draft202012Validator, document: object) -> list[str]:
    found = []
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path)):
        loc = "/".join(str(part) for part in error.absolute_path) or "(root)"
        found.append(f"{loc}: {error.message}")
    return found


def fail(messages: list[str]) -> None:
    print("\n".join(messages), file=sys.stderr)
    sys.exit(1)


def stringify_dates(value):
    """YAML turns YYYY-MM-DD into datetime.date. Schema and templates expect strings."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: stringify_dates(item) for key, item in value.items()}
    if isinstance(value, list):
        return [stringify_dates(item) for item in value]
    return value


def split_front_matter(text: str, path: Path) -> tuple[dict, str]:
    text = text.lstrip("\ufeff")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path}: unterminated front matter")
    meta = yaml.safe_load(text[4:end])
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: front matter must be a mapping")
    return meta, text[end + 5 :]


def parse_paper(text: str) -> tuple[str, list[dict]]:
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    note_at = next(i for i, line in enumerate(lines) if line.strip() == "### Note on status and method")
    toc_at = next(i for i, line in enumerate(lines) if line.strip() == "## Table of Contents")
    body_at = next(i for i, line in enumerate(lines) if line.startswith("# Part "))
    title_md = "\n".join(lines[:note_at]).strip()
    note_body = clean_body("\n".join(lines[note_at + 1 : toc_at]))

    sections: list[dict] = []
    part = "Front matter"
    current: dict | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        current["body"] = clean_body("\n".join(buffer))
        sections.append(current)
        current = None

    note = {
        "kind": "note",
        "slug": "note",
        "number": "",
        "title": "Note on status and method",
        "part": "Front matter",
        "heading": "Note on status and method",
        "body": note_body,
    }
    sections.append(note)

    for line in lines[body_at:]:
        if line.startswith("# "):
            flush()
            buffer = []
            part = line[2:].strip()
            continue
        if line.startswith("## "):
            flush()
            buffer = []
            heading = line[3:].strip()
            chapter = re.match(r"(\d+)\.\s+(.+)", heading)
            annex = re.match(r"Annex ([A-Z])\s+[—–-]\s+(.+)", heading)
            if chapter:
                current = {
                    "kind": "chapter",
                    "slug": chapter.group(1),
                    "number": chapter.group(1),
                    "title": chapter.group(2),
                    "part": part,
                    "heading": heading,
                }
            elif annex:
                letter = annex.group(1)
                current = {
                    "kind": "annex",
                    "slug": f"annex-{letter.lower()}",
                    "number": letter,
                    "title": annex.group(2),
                    "part": part,
                    "heading": heading,
                }
            else:
                raise ValueError(f"Unrecognised paper heading: {heading}")
            continue
        if current is not None:
            buffer.append(line)
    flush()

    numbers = [item["number"] for item in sections if item["kind"] == "chapter"]
    letters = [item["number"] for item in sections if item["kind"] == "annex"]
    if numbers != [str(n) for n in range(1, 34)]:
        raise ValueError(f"Expected chapters 1–33, found {numbers}")
    if letters != ["A", "B", "C", "D", "F", "E"]:
        raise ValueError(f"Expected annexes A B C D F E, found {letters}")
    return title_md, sections


def prepare_section_html(section: dict) -> None:
    body = section["body"]
    body = re.sub(r"^### ", "## ", body, flags=re.M)
    rendered, toc = enrich_html(render_markdown(loosen_lists(body)), corrections=True)
    section["html"] = rendered
    section["toc"] = toc
    section["label"] = section["heading"]
    section["correction"] = correction_url(section["label"])


def paper_links(paper_section: str) -> list[dict]:
    links: list[dict] = []
    seen: set[str] = set()
    for letter in re.findall(r"Annex\s+([A-Z])", paper_section):
        href = f"/paper/annex-{letter.lower()}/"
        if href not in seen:
            links.append({"label": f"Annex {letter}", "href": href})
            seen.add(href)
    for token in re.findall(r"\d+(?:\.\d+)?", paper_section):
        chapter = token.split(".")[0]
        href = f"/paper/{chapter}/"
        label = f"Section {token}"
        if href not in seen:
            links.append({"label": label, "href": href})
            seen.add(href)
    return links


def load_oracles() -> list[dict]:
    validator = load_schema("oracle.schema.json")
    errors: list[str] = []
    oracles: list[dict] = []
    files = sorted((DATA / "oracles").glob("*.yml"))
    if not files:
        fail(["No oracle files in data/oracles/"])
    for path in files:
        try:
            document = stringify_dates(yaml.safe_load(path.read_text(encoding="utf-8")))
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        for message in schema_errors(validator, document):
            errors.append(f"{path.name}: {message}")
        if not isinstance(document, dict):
            continue
        if document.get("id") != path.stem:
            errors.append(f"{path.name}: filename must match id")
        for item in document.get("evidence") or []:
            evidence_url = item.get("url", "")
            if not evidence_url.startswith(("https://", "http://")):
                errors.append(f"{path.name}: evidence URL must start with http:// or https://")
        if isinstance(document, dict) and "id" in document:
            document["links"] = paper_links(str(document.get("paper_section", "")))
            document["status_label"] = STATUS_LABEL.get(document.get("status"), document.get("status"))
            document["layer_label"] = LAYER_LABEL.get(document.get("layer"), document.get("layer"))
            oracles.append(document)
    ids = [item["id"] for item in oracles]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate oracle ids")
    if errors:
        fail(errors)

    def sort_key(item: dict) -> tuple:
        domain = item["domain"]
        domain_index = DOMAIN_ORDER.index(domain) if domain in DOMAIN_ORDER else len(DOMAIN_ORDER)
        return (domain_index, domain, item["name"].lower())

    oracles.sort(key=sort_key)
    return oracles


def load_progress() -> list[dict]:
    validator = load_schema("progress.schema.json")
    errors: list[str] = []
    entries: list[dict] = []
    for path in sorted((DATA / "progress").glob("*.md")):
        try:
            meta, body = split_front_matter(path.read_text(encoding="utf-8"), path)
            meta = stringify_dates(meta)
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(str(exc))
            continue
        if isinstance(meta.get("x"), str):
            meta["x"] = meta["x"].strip()
        if isinstance(meta.get("linkedin"), str):
            meta["linkedin"] = meta["linkedin"].strip()
        if isinstance(meta.get("link"), str) and not meta["link"].startswith(("https://", "http://")):
            errors.append(f"{path.name}: link must be an http(s) URL")
        for message in schema_errors(validator, meta):
            errors.append(f"{path.name}: {message}")
        slug = path.stem
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug)
        if path.stem[:10] != meta.get("date"):
            errors.append(f"{path.name}: filename date must match the date field")
        rendered, _toc = enrich_html(render_markdown(body), corrections=False)
        meta["slug"] = slug
        meta["html"] = rendered
        meta["rfc822"] = datetime.strptime(meta["date"], "%Y-%m-%d").strftime("%a, %d %b %Y 00:00:00 GMT")
        entries.append(meta)
    if errors:
        fail(errors)
    entries.sort(key=lambda item: (item["date"], item["title"]), reverse=True)
    return entries


def load_collection(folder: Path, kind: str) -> list[dict]:
    items: list[dict] = []
    errors: list[str] = []
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith("_"):
            continue
        try:
            meta, body = split_front_matter(path.read_text(encoding="utf-8"), path)
            meta = stringify_dates(meta)
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(str(exc))
            continue
        meta["byline_opt_in"] = bool(meta.get("byline_opt_in", False))
        if meta["byline_opt_in"] and not str(meta.get("author") or "").strip():
            errors.append(f"{path.name}: byline_opt_in requires an author name")
        if not meta["byline_opt_in"]:
            meta["public_author"] = None
            meta["author_slug"] = ""
        else:
            meta["public_author"] = str(meta["author"]).strip()
            meta["author_slug"] = slugify(meta["public_author"])
        if kind == "blog":
            if "date" not in meta or "title" not in meta or "summary" not in meta:
                errors.append(f"{path.name}: blog posts need title, date, and summary")
            slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)
        else:
            if meta.get("status") not in {"planned", "note", "preprint", "dataset"}:
                errors.append(f"{path.name}: status must be planned, note, preprint, or dataset")
            if not meta.get("title") or not meta.get("summary"):
                errors.append(f"{path.name}: research notes need title and summary")
            slug = path.stem
        rendered, toc = enrich_html(render_markdown(body), corrections=False)
        meta["slug"] = slug
        meta["html"] = rendered
        meta["toc"] = toc
        meta["kind"] = kind
        items.append(meta)
    if errors:
        fail(errors)
    if kind == "blog":
        items.sort(key=lambda item: item.get("date", ""), reverse=True)
    else:
        items.sort(key=lambda item: ({"planned": 0, "note": 1, "preprint": 2, "dataset": 3}.get(item["status"], 9), item["title"]))
    return items


def ordered_counts(counter: Counter, order: list[str]) -> list[dict]:
    rows = []
    seen = set()
    for key in order:
        rows.append({"key": key, "label": STATUS_LABEL.get(key, LAYER_LABEL.get(key, key)), "count": counter.get(key, 0)})
        seen.add(key)
    for key in sorted(k for k in counter if k not in seen):
        rows.append({"key": key, "label": key, "count": counter[key]})
    return rows


def domain_rows(oracles: list[dict]) -> list[dict]:
    counter = Counter(item["domain"] for item in oracles)
    rows = []
    seen = set()
    for domain in DOMAIN_ORDER:
        if domain in counter:
            rows.append({"key": domain, "count": counter[domain]})
            seen.add(domain)
    for domain in sorted(k for k in counter if k not in seen):
        rows.append({"key": domain, "count": counter[domain]})
    return rows


def build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        {
            "url": url,
            "absurl": absurl,
            "site": SITE,
            "repo": REPO,
            "status_label": STATUS_LABEL,
            "layer_label": LAYER_LABEL,
            "nav_items": NAV,
        }
    )
    return env


def write_page(env: Environment, template: str, dest: str, **context) -> None:
    current = context["current"]
    nav = []
    for label, path in NAV:
        active = path == current if path == "/" else current == path or current.startswith(path)
        nav.append({"label": label, "href": url(path), "current": active})
    html_out = env.get_template(template).render(nav=nav, **context)
    target = DIST / dest
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html_out, encoding="utf-8")


def write_pdf(title_and_body_md: str) -> None:
    env = build_env()
    body, _toc = enrich_html(render_markdown(loosen_lists(title_and_body_md)), corrections=False)
    pdf_html = env.get_template("pdf.html.j2").render(body=body, current="/paper/")
    tmp = DIST / "paper" / "_print.html"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(pdf_html, encoding="utf-8")
    document = HTML(filename=str(tmp), base_url=str(tmp.parent)).render()
    pages = len(document.pages)
    pdf_path = DIST / "paper" / "the-oracle-and-the-partner-v3.1.pdf"
    document.write_pdf(str(pdf_path))
    tmp.unlink()
    if pages < 25:
        fail([f"PDF is only {pages} pages; the paper did not render fully."])
    print(f"PDF pages: {pages}")


def write_feed(env: Environment, entries: list[dict]) -> None:
    xml = env.get_template("feed.xml.j2").render(entries=entries, current="/feed.xml", built=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"))
    (DIST / "feed.xml").write_text(xml, encoding="utf-8")


def write_sitemap(paths: list[str]) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in paths:
        lines.append("  <url><loc>" + xml_escape(absurl(path)) + "</loc></url>")
    lines.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def assert_site(oracles: list[dict], sections: list[dict]) -> None:
    index = (DIST / "oracles" / "index.html").read_text(encoding="utf-8")
    messages = []
    for oracle in oracles:
        href = f"{BASE_PATH}/oracles/{oracle['id']}/"
        if href not in index:
            messages.append(f"Tracker index missing {oracle['id']}")
        page = DIST / "oracles" / oracle["id"] / "index.html"
        if not page.exists():
            messages.append(f"Missing detail page for {oracle['id']}")
    for section in sections:
        page = DIST / "paper" / section["slug"] / "index.html"
        if not page.exists():
            messages.append(f"Missing paper page {section['slug']}")
        text = page.read_text(encoding="utf-8")
        if "Suggest a correction" not in text:
            messages.append(f"Paper page {section['slug']} has no correction link")
    required = [
        DIST / "index.html",
        DIST / "paper" / "index.html",
        DIST / "paper" / "versions" / "index.html",
        DIST / "paper" / "the-oracle-and-the-partner-v3.1.pdf",
        DIST / "share" / "index.html",
        DIST / "progress" / "index.html",
        DIST / "feed.xml",
        DIST / "contribute" / "index.html",
        DIST / "about" / "index.html",
    ]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            messages.append(f"Missing or empty {path.relative_to(DIST)}")
    blob = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in DIST.rglob("*") if path.suffix in {".html", ".xml", ".json", ".txt"})
    for pattern in FORBIDDEN:
        if pattern.search(blob):
            messages.append(f"Forbidden term matched {pattern.pattern}")
    if messages:
        fail(messages)


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    for item in STATIC.iterdir():
        target = DIST / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    env = build_env()
    oracles = load_oracles()
    progress = load_progress()
    posts = load_collection(CONTENT / "blog", "blog")
    notes = load_collection(CONTENT / "research", "research")
    title_md, sections = parse_paper(PAPER_SRC.read_text(encoding="utf-8"))
    for section in sections:
        prepare_section_html(section)
    title_html, _title_toc = enrich_html(render_markdown(title_md), corrections=False)

    by_status = Counter(item["status"] for item in oracles)
    by_layer = Counter(item["layer"] for item in oracles)
    counts = {
        "total": len(oracles),
        "by_status": ordered_counts(by_status, STATUS_ORDER),
        "by_domain": domain_rows(oracles),
        "by_layer": ordered_counts(by_layer, LAYER_ORDER),
        "benchmarks": by_layer.get("benchmark", 0),
        "other": len(oracles) - by_layer.get("benchmark", 0),
        "all_proposed": by_status.get("proposed", 0) == len(oracles),
    }
    domains = []
    for row in counts["by_domain"]:
        if row["key"] not in domains:
            domains.append(row["key"])
    for oracle in oracles:
        if oracle["domain"] not in domains:
            domains.append(oracle["domain"])

    citation = (
        "Itegbe, Benedict. 2026. The Oracle and the Partner: Africa's Path to an Age of Abundance. "
        "Version 3.1, July 2026. AI Africa Abundance. "
        f"{absurl('/paper/')} "
        "Text licensed under CC BY 4.0."
    )
    bibtex = """@techreport{itegbe2026oracle,
  title = {The Oracle and the Partner: Africa's Path to an Age of Abundance},
  author = {Itegbe, Benedict},
  year = {2026},
  month = jul,
  type = {White paper},
  number = {3.1},
  institution = {AI Africa Abundance},
  url = {https://oraquul.github.io/AI-Africa-Abundance/paper/},
  note = {Independent publication. Text licensed under CC BY 4.0.}
}"""

    common = {
        "counts": counts,
        "citation": citation,
        "bibtex": bibtex,
    }
    sitemap_paths = ["/"]

    write_page(
        env,
        "home.html.j2",
        "index.html",
        current="/",
        title="AI Africa Abundance",
        description="An open record of The Oracle and the Partner, and a public tracker of the oracles the paper proposes.",
        progress=progress[:5],
        **common,
    )

    write_page(
        env,
        "paper_index.html.j2",
        "paper/index.html",
        current="/paper/",
        title="Read the white paper",
        description="The Oracle and the Partner, version 3.1, July 2026, by Benedict Itegbe.",
        title_html=title_html,
        sections=sections,
        **common,
    )
    sitemap_paths.append("/paper/")

    for index, section in enumerate(sections):
        previous_section = sections[index - 1] if index else None
        next_section = sections[index + 1] if index + 1 < len(sections) else None
        path = f"/paper/{section['slug']}/"
        write_page(
            env,
            "chapter.html.j2",
            f"paper/{section['slug']}/index.html",
            current=path,
            title=section["heading"],
            description=f"{section['heading']} of The Oracle and the Partner, version 3.1.",
            section=section,
            previous_section=previous_section,
            next_section=next_section,
            **common,
        )
        sitemap_paths.append(path)

    versions_md = (CONTENT / "paper" / "versions.md").read_text(encoding="utf-8")
    versions_html, _toc = enrich_html(render_markdown(versions_md), corrections=False)
    write_page(
        env,
        "document.html.j2",
        "paper/versions/index.html",
        current="/paper/versions/",
        title="Version history and errata",
        description="How version 3.1 of The Oracle and the Partner differs from version 3.0.",
        document=versions_html,
        **common,
    )
    sitemap_paths.append("/paper/versions/")

    write_page(
        env,
        "oracles.html.j2",
        "oracles/index.html",
        current="/oracles/",
        title="Oracle tracker",
        description="Proposed benchmarks and infrastructure oracles from the white paper, with status, domain, and loop speed.",
        oracles=oracles,
        domains=domains,
        statuses=STATUS_ORDER,
        layers=LAYER_ORDER,
        **common,
    )
    sitemap_paths.append("/oracles/")

    for oracle in oracles:
        path = f"/oracles/{oracle['id']}/"
        write_page(
            env,
            "oracle.html.j2",
            f"oracles/{oracle['id']}/index.html",
            current=path,
            title=oracle["name"],
            description=f"{oracle['name']} — {oracle['status_label']} oracle in {oracle['domain']}.",
            oracle=oracle,
            **common,
        )
        sitemap_paths.append(path)

    export = {
        "licence": "https://creativecommons.org/licenses/by/4.0/",
        "paper": absurl("/paper/"),
        "total": len(oracles),
        "oracles": [
            {key: value for key, value in oracle.items() if key not in {"links", "status_label", "layer_label"}}
            for oracle in oracles
        ],
    }
    (DIST / "oracles" / "oracles.json").write_text(json.dumps(export, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    write_page(
        env,
        "progress.html.j2",
        "progress/index.html",
        current="/progress/",
        title="Progress",
        description="Dated public notes on AI Africa Abundance.",
        entries=progress,
        **common,
    )
    sitemap_paths.append("/progress/")

    write_page(
        env,
        "share.html.j2",
        "share/index.html",
        current="/share/",
        title="Share",
        description="Ready-to-copy X and LinkedIn text for each progress entry. Nothing is posted automatically.",
        entries=progress,
        **common,
    )
    sitemap_paths.append("/share/")
    write_feed(env, progress)

    write_page(
        env,
        "blog_index.html.j2",
        "blog/index.html",
        current="/blog/",
        title="Blog",
        description="Essays from AI Africa Abundance. One launch essay is published. Further titles are not yet written.",
        posts=posts,
        **common,
    )
    sitemap_paths.append("/blog/")
    authors: dict[str, dict] = {}
    for post in posts:
        path = f"/blog/{post['slug']}/"
        write_page(
            env,
            "blog_post.html.j2",
            f"blog/{post['slug']}/index.html",
            current=path,
            title=post["title"],
            description=post["summary"],
            post=post,
            **common,
        )
        sitemap_paths.append(path)
        if post.get("public_author"):
            author_slug = slugify(post["public_author"])
            bucket = authors.setdefault(author_slug, {"name": post["public_author"], "slug": author_slug, "posts": []})
            bucket["posts"].append(post)
    for author in authors.values():
        path = f"/blog/authors/{author['slug']}/"
        write_page(
            env,
            "author.html.j2",
            f"blog/authors/{author['slug']}/index.html",
            current=path,
            title=author["name"],
            description=f"Essays credited to {author['name']}, who opted in to a byline.",
            author=author,
            **common,
        )
        sitemap_paths.append(path)

    write_page(
        env,
        "research_index.html.j2",
        "research/index.html",
        current="/research/",
        title="Research",
        description="Planned concept notes and a reading path into the white paper. Nothing here is presented as finished research.",
        notes=notes,
        **common,
    )
    sitemap_paths.append("/research/")
    for note in notes:
        path = f"/research/{note['slug']}/"
        write_page(
            env,
            "research_note.html.j2",
            f"research/{note['slug']}/index.html",
            current=path,
            title=note["title"],
            description=note["summary"],
            note=note,
            **common,
        )
        sitemap_paths.append(path)

    write_page(
        env,
        "contribute.html.j2",
        "contribute/index.html",
        current="/contribute/",
        title="Contribute",
        description="How to propose an oracle, correct the paper, submit research, or pitch an essay. Credit is opt-in.",
        **common,
    )
    sitemap_paths.append("/contribute/")

    write_page(
        env,
        "about.html.j2",
        "about/index.html",
        current="/about/",
        title="About",
        description="Benedict Itegbe, founder and editor, writing in a personal capacity. An independent initiative.",
        **common,
    )
    sitemap_paths.append("/about/")

    for source, dest, page_title, description in [
        (ROOT / "CONTRIBUTING.md", "contributing/index.html", "Contributing", "How to contribute to the AI Africa Abundance repository."),
        (ROOT / "CODE_OF_CONDUCT.md", "conduct/index.html", "Code of conduct", "Contributor Covenant code of conduct for AI Africa Abundance."),
    ]:
        body, _toc = enrich_html(render_markdown(source.read_text(encoding="utf-8")), corrections=False)
        path = "/" + dest.split("/")[0] + "/"
        write_page(
            env,
            "document.html.j2",
            dest,
            current=path,
            title=page_title,
            description=description,
            document=body,
            **common,
        )
        sitemap_paths.append(path)

    write_page(
        env,
        "404.html.j2",
        "404.html",
        current="/404.html",
        title="Page not found",
        description="That page is not on this site.",
        **common,
    )

    paper_text = PAPER_SRC.read_text(encoding="utf-8").lstrip("\ufeff")
    write_pdf(paper_text)
    sitemap_paths.append("/paper/the-oracle-and-the-partner-v3.1.pdf")
    write_sitemap(sitemap_paths)
    assert_site(oracles, sections)
    print(f"Oracle count: {len(oracles)}")
    print(f"Progress entries: {len(progress)}")
    print(f"Blog posts: {len(posts)}")
    print(f"Research notes: {len(notes)}")
    print(f"Paper pages: {len(sections)}")
    print(f"Wrote {DIST}")


if __name__ == "__main__":
    main()

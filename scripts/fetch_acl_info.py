# Fetch paper metadata from ACL Anthology event pages.
# ACL Website: https://aclanthology.org/

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://aclanthology.org"
DEFAULT_VENUES = ("ACL", "EMNLP", "NAACL", "CoNLL", "TACL")
SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / "cache"
CACHE_JSON = CACHE_DIR / "papers.json"
CACHE_JSONL = CACHE_DIR / "papers.jsonl"
REQUEST_TIMEOUT = 30


def normalize_venue(venue: str) -> str:
    return venue.strip()


def event_url(venue: str, year: int) -> str:
    return f"{BASE_URL}/events/{venue.lower()}-{year}/"


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "acl-article-finder/1.0 "
                "(metadata collection for research filtering)"
            )
        }
    )
    return session


def get_page(session: requests.Session, url: str) -> Optional[str]:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        print(f"ERROR: failed to fetch {url}: {exc}")
        return None

    if response.status_code == 404:
        return None

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"ERROR: failed to fetch {url}: {exc}")
        return None

    return response.text


def latest_available_year(
    session: requests.Session,
    venue: str,
    start_year: Optional[int] = None,
    min_year: int = 2000,
) -> Optional[int]:
    year = start_year or datetime.now().year
    for candidate_year in range(year, min_year - 1, -1):
        if get_page(session, event_url(venue, candidate_year)) is not None:
            return candidate_year
    return None


def resolve_event_page(
    session: requests.Session,
    venue: str,
    requested_year: Optional[int],
) -> Tuple[Optional[int], Optional[str]]:
    if requested_year is None:
        year = latest_available_year(session, venue)
        if year is None:
            print(f"ERROR: no available event page found for {venue}.")
            return None, None
        return year, get_page(session, event_url(venue, year))

    html = get_page(session, event_url(venue, requested_year))
    if html is not None:
        return requested_year, html

    fallback_year = latest_available_year(session, venue, requested_year - 1)
    if fallback_year is None:
        print(f"ERROR: no available event page found for {venue} near {requested_year}.")
        return None, None

    print(
        "WARNING: "
        f"{venue} {requested_year} is unavailable; using {venue} {fallback_year}."
    )
    return fallback_year, get_page(session, event_url(venue, fallback_year))


def title_from_link(anchor) -> str:
    text = " ".join(anchor.get_text(" ", strip=True).split())
    if text:
        return text

    parent = anchor.find_parent(["p", "li", "div"])
    if parent is None:
        return ""

    return " ".join(parent.get_text(" ", strip=True).split())


def is_paper_href(href: str, venue: str, year: int) -> bool:
    if not href:
        return False

    path = href.split("#", 1)[0].split("?", 1)[0]
    if path.endswith(".pdf") or path.endswith(".bib"):
        return False

    paper_id_pattern = re.compile(
        rf"^/?{year}\.{re.escape(venue.lower())}[-.][^/]+/\s*$",
        re.IGNORECASE,
    )
    if not paper_id_pattern.match(path):
        return False

    paper_id = path.strip("/")
    return not paper_id.endswith(".0")


def pdf_url_from_page_url(page_url: str) -> str:
    clean_url = page_url.rstrip("/")
    return f"{clean_url}.pdf"


def parse_papers(html: str, venue: str, year: int) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    papers: List[Dict[str, str]] = []
    seen_urls = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not is_paper_href(href, venue, year):
            continue

        page_url = urljoin(BASE_URL, href)
        if page_url in seen_urls:
            continue

        title = title_from_link(anchor)
        if not title:
            continue

        seen_urls.add(page_url)
        papers.append(
            {
                "title": title,
                "venue": venue.upper(),
                "year": str(year),
                "source": f"{venue.upper()} {year}",
                "url": page_url,
                "pdf_url": pdf_url_from_page_url(page_url),
            }
        )

    return papers


def fetch_acl_info(
    conference_name: str,
    conference_year: Optional[int] = None,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, str]]:
    venue = normalize_venue(conference_name)
    session = session or build_session()
    resolved_year, html = resolve_event_page(session, venue, conference_year)
    if resolved_year is None or html is None:
        return []

    papers = parse_papers(html, venue, resolved_year)
    print(f"INFO: loaded {len(papers)} papers from {venue.upper()} {resolved_year}.")
    return papers


def clear_cache() -> None:
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def save_papers(papers: Sequence[Dict[str, str]]) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(papers),
        "papers": list(papers),
    }
    CACHE_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with CACHE_JSONL.open("w", encoding="utf-8") as file:
        for paper in papers:
            file.write(json.dumps(paper, ensure_ascii=False) + "\n")


def parse_years(raw_years: Optional[Sequence[str]]) -> Optional[List[int]]:
    if not raw_years:
        return None
    return [int(year) for year in raw_years]


def pair_venues_and_years(
    venues: Sequence[str],
    years: Optional[Sequence[int]],
) -> List[Tuple[str, Optional[int]]]:
    if years is None:
        return [(venue, None) for venue in venues]

    if len(years) == 1:
        return [(venue, years[0]) for venue in venues]

    if len(years) != len(venues):
        raise ValueError(
            "When multiple years are provided, their count must be 1 or match "
            "the number of venues."
        )

    return list(zip(venues, years))


def load_config(path: Path) -> List[Tuple[str, Optional[int]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    conferences = data.get("Conference", [])
    pairs = []
    for conference in conferences:
        name = conference.get("name")
        if not name:
            continue
        year = conference.get("year")
        pairs.append((name, int(year) if year else None))
    return pairs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch ACL Anthology paper titles and links for selected venues."
        )
    )
    parser.add_argument(
        "--venue",
        "--conference",
        dest="venues",
        action="append",
        help=(
            "Venue to fetch, for example ACL, EMNLP, NAACL, CoNLL, TACL. "
            "Can be repeated."
        ),
    )
    parser.add_argument(
        "--year",
        dest="years",
        action="append",
        help=(
            "Year to fetch. One year applies to all venues; multiple years "
            "must match the number of venues."
        ),
    )
    parser.add_argument(
        "--use-config",
        action="store_true",
        help="Read Conference entries from config.json instead of CLI defaults.",
    )
    parser.add_argument(
        "--config",
        default=str(SCRIPT_DIR / "config.json"),
        help="Path to config.json when --use-config is set.",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.use_config:
            targets = load_config(Path(args.config))
        else:
            venues = args.venues or list(DEFAULT_VENUES)
            targets = pair_venues_and_years(venues, parse_years(args.years))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    clear_cache()
    session = build_session()
    all_papers: List[Dict[str, str]] = []

    for venue, year in targets:
        all_papers.extend(fetch_acl_info(venue, year, session=session))

    save_papers(all_papers)
    print(f"INFO: saved {len(all_papers)} papers to {CACHE_JSON}.")
    print(f"INFO: jsonl cache is available at {CACHE_JSONL}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

    
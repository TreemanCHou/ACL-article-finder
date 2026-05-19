import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / "cache"
DEFAULT_CACHE_FILE = CACHE_DIR / "papers.json"
DEFAULT_STATE_FILE = CACHE_DIR / "show_state.json"
DEFAULT_PAGE_SIZE = 100
ALL_LOADED_MESSAGE = "ALL PAPERS IS LOADED."


def load_papers(cache_file: Path) -> List[Dict[str, str]]:
    if not cache_file.exists():
        raise FileNotFoundError(
            f"{cache_file} does not exist. Run fetch_acl_info.py first."
        )

    data = json.loads(cache_file.read_text(encoding="utf-8"))
    papers = data.get("papers")
    if not isinstance(papers, list):
        raise ValueError(f"{cache_file} does not contain a papers list.")

    return papers


def load_offset(state_file: Path) -> int:
    if not state_file.exists():
        return 0

    data = json.loads(state_file.read_text(encoding="utf-8"))
    return int(data.get("offset", 0))


def save_offset(state_file: Path, offset: int, total: int) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "offset": offset,
                "total": total,
                "all_loaded": offset >= total,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show cached ACL Anthology paper records in pages."
    )
    parser.add_argument(
        "--cache-file",
        default=str(DEFAULT_CACHE_FILE),
        help="Path to the cached papers.json file.",
    )
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="Path to the temporary paging state JSON file.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Number of records to print each time.",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.page_size <= 0:
        parser.error("--page-size must be greater than 0.")

    cache_file = Path(args.cache_file)
    state_file = Path(args.state_file)

    try:
        papers = load_papers(cache_file)
        offset = load_offset(state_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    total = len(papers)
    if offset >= total:
        save_offset(state_file, total, total)
        print(ALL_LOADED_MESSAGE)
        return 0

    next_offset = min(offset + args.page_size, total)
    payload = {
        "offset": offset,
        "next_offset": next_offset,
        "page_size": args.page_size,
        "total": total,
        "papers": papers[offset:next_offset],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    save_offset(state_file, next_offset, total)
    if next_offset >= total:
        print(ALL_LOADED_MESSAGE)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

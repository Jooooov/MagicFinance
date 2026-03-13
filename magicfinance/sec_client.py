"""
MagicFinance — SEC EDGAR Client (Module C)
==========================================
Free access to SEC 10-Q/10-K filings — no API key required.
Rate limit: ~10 req/sec (we stay well under with 0.2s sleeps).

Data sources:
  - https://data.sec.gov/             — EDGAR company API
  - https://www.sec.gov/files/        — ticker→CIK map (cached once)
  - https://www.sec.gov/Archives/     — actual filing documents
"""

import re
import time
import logging
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "MagicFinance/1.0 magicfinance@research.dev"}
_SEC_BASE = "https://data.sec.gov"
_EDGAR_BASE = "https://www.sec.gov"

# Regex patterns to locate the MD&A section start and end
_MDA_START_RE = re.compile(
    r"(ITEM\s+2[\.\s]+MANAGEMENT.S\s+DISCUSSION|MANAGEMENT.S\s+DISCUSSION\s+AND\s+ANALYSIS)",
    re.IGNORECASE,
)
_MDA_END_RE = re.compile(
    r"(ITEM\s+3[\.\s]+QUANTITATIVE|ITEM\s+4[\.\s]+CONTROLS|QUANTITATIVE\s+AND\s+QUALITATIVE)",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _get_cik_map() -> dict:
    """Download and cache the full ticker→CIK mapping from SEC (loaded once per process)."""
    try:
        resp = requests.get(
            f"{_EDGAR_BASE}/files/company_tickers.json",
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        # Format: {0: {cik_str: "...", ticker: "...", title: "..."}, ...}
        return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()}
    except Exception as exc:
        logger.warning("Could not load CIK map from SEC: %s", exc)
        return {}


def get_cik(ticker: str) -> str | None:
    """Return zero-padded 10-digit CIK for a ticker symbol, or None if not found."""
    return _get_cik_map().get(ticker.upper())


def get_latest_10q_filing(cik: str) -> dict | None:
    """
    Return metadata for the most recent 10-Q filing for a given CIK.

    Returns dict with: accession_number (no dashes), filing_date, primary_document, cik
    Returns None if no 10-Q found or request fails.
    """
    try:
        resp = requests.get(
            f"{_SEC_BASE}/submissions/CIK{cik}.json",
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        dates = filings.get("filingDate", [])
        docs = filings.get("primaryDocument", [])

        for i, form in enumerate(forms):
            if form == "10-Q":
                return {
                    "accession_number": accessions[i].replace("-", ""),
                    "filing_date": dates[i],
                    "primary_document": docs[i],
                    "cik": cik,
                }
    except Exception as exc:
        logger.warning("Could not fetch filings for CIK %s: %s", cik, exc)
    return None


def _fetch_filing_text(cik: str, accession_number: str, primary_document: str) -> str:
    """Download and clean a filing document, stripping HTML tags."""
    url = (
        f"{_EDGAR_BASE}/Archives/edgar/data/"
        f"{int(cik)}/{accession_number}/{primary_document}"
    )
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"&[a-zA-Z0-9#]+;", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text
    except Exception as exc:
        logger.warning("Could not fetch filing document %s: %s", url, exc)
        return ""


def extract_mda(text: str, max_chars: int = 8000) -> str:
    """
    Extract the MD&A section from a 10-Q/10-K filing text.
    Returns up to max_chars characters. Falls back to the first max_chars if
    the section boundary cannot be located.
    """
    start_match = _MDA_START_RE.search(text)
    if not start_match:
        return text[:max_chars]

    start_pos = start_match.start()
    search_region = text[start_pos + 200:]
    end_match = _MDA_END_RE.search(search_region)
    end_pos = start_pos + 200 + end_match.start() if end_match else len(text)

    return text[start_pos:end_pos][:max_chars]


def get_mda_for_ticker(ticker: str) -> dict:
    """
    Full pipeline: ticker → CIK → latest 10-Q → cleaned MD&A text.

    Returns dict with:
        ticker, cik, filing_date, source, mda_text, error (None on success)
    """
    cik = get_cik(ticker)
    if not cik:
        return {"ticker": ticker, "cik": None, "mda_text": "", "error": f"CIK not found for {ticker}"}

    filing = get_latest_10q_filing(cik)
    if not filing:
        return {"ticker": ticker, "cik": cik, "mda_text": "", "error": "No 10-Q filing found in EDGAR"}

    time.sleep(0.3)  # be gentle with SEC servers
    full_text = _fetch_filing_text(cik, filing["accession_number"], filing["primary_document"])
    if not full_text:
        return {
            "ticker": ticker,
            "cik": cik,
            "filing_date": filing["filing_date"],
            "mda_text": "",
            "error": "Could not download filing document",
        }

    mda = extract_mda(full_text)
    return {
        "ticker": ticker,
        "cik": cik,
        "filing_date": filing["filing_date"],
        "source": f"SEC EDGAR 10-Q ({filing['filing_date']})",
        "mda_text": mda,
        "error": None,
    }

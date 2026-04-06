"""SRU (Search/Retrieve via URL) client for querying library catalogs.

Provides a configurable SRU client with pre-built instances for NLI, LC,
and VIAF catalogs. Uses httpx for HTTP, with polite delays between requests
and structured error handling via result dataclasses.
"""

import os
import re
import time
from dataclasses import dataclass

import httpx


# --- Result types ---


@dataclass
class SRUResult:
    """Structured result from an SRU request.

    success: True if the request completed and returned XML.
    data: Raw XML response text on success, empty string on failure.
    error: Error description on failure, empty string on success.
    """

    success: bool
    data: str = ""
    error: str = ""


# --- CQL query helpers ---


# Pattern matching alma.* index terms in CQL queries.
# Captures: index_name = value (where value may or may not already be quoted).
_ALMA_INDEX_RE = re.compile(
    r"""
    (alma\.\w+)        # group 1: the alma.* index name
    \s*=\s*            # the = operator with optional whitespace
    (?!"[^"]*")        # negative lookahead: skip already-quoted values
    (\S(?:[^"]*?\S)?)  # group 2: unquoted value (non-greedy)
    (?=\s+\b(?:AND|OR|NOT|PROX|SORTBY)\b|\s*$)  # stop at CQL boolean or end
    """,
    re.VERBOSE | re.IGNORECASE,
)


def quote_alma_values(query: str) -> str:
    """Wrap unquoted alma.* index values in double quotes.

    NLI's Alma SRU requires phrase values to be double-quoted.
    Already-quoted values are left untouched.

    >>> quote_alma_values('alma.title = Talmud Bavli')
    'alma.title = "Talmud Bavli"'
    >>> quote_alma_values('alma.title = "already quoted"')
    'alma.title = "already quoted"'
    """

    def _quote_match(m: re.Match) -> str:
        index_name = m.group(1)
        value = m.group(2).strip()
        return f'{index_name} = "{value}"'

    return _ALMA_INDEX_RE.sub(_quote_match, query)


def build_sru_params(
    query: str,
    version: str = "1.1",
    max_records: int = 20,
    record_schema: str = "marcxml",
) -> dict[str, str]:
    """Build the query-string parameters for an SRU searchRetrieve request."""
    return {
        "operation": "searchRetrieve",
        "version": version,
        "query": query,
        "maximumRecords": str(max_records),
        "recordSchema": record_schema,
    }


# --- SRU client ---

# Default timeout for HTTP requests (seconds).
REQUEST_TIMEOUT = 30


@dataclass
class SRUClient:
    """Configurable SRU client for a single catalog endpoint.

    Parameters
    ----------
    base_url : str
        The SRU endpoint URL.
    version : str
        SRU protocol version (default ``"1.1"``).
    auto_quote_alma : bool
        If True, automatically double-quote unquoted alma.* index values
        in CQL queries (needed for NLI).
    request_delay : float | None
        Seconds to sleep before each HTTP request. If None, reads
        ``SRU_REQUEST_DELAY`` from the environment (default 3).
    """

    base_url: str
    version: str = "1.1"
    auto_quote_alma: bool = False
    request_delay: float | None = None

    def _get_delay(self) -> float:
        if self.request_delay is not None:
            return self.request_delay
        return float(os.environ.get("SRU_REQUEST_DELAY", "3"))

    def search(
        self,
        query: str,
        max_records: int = 20,
        record_schema: str = "marcxml",
    ) -> SRUResult:
        """Execute an SRU searchRetrieve request.

        Returns an ``SRUResult`` with ``success=True`` and the raw XML in
        ``data`` on success, or ``success=False`` with a message in ``error``.
        """
        if self.auto_quote_alma:
            query = quote_alma_values(query)

        params = build_sru_params(
            query=query,
            version=self.version,
            max_records=max_records,
            record_schema=record_schema,
        )

        delay = self._get_delay()
        if delay > 0:
            time.sleep(delay)

        try:
            response = httpx.get(self.base_url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        except httpx.TimeoutException:
            return SRUResult(
                success=False,
                error=f"Request timed out after {REQUEST_TIMEOUT}s",
            )
        except httpx.HTTPStatusError as exc:
            return SRUResult(
                success=False,
                error=f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}",
            )
        except httpx.HTTPError as exc:
            return SRUResult(
                success=False,
                error=f"HTTP error: {exc}",
            )

        # Basic sanity check: response should look like XML.
        text = response.text
        if not text.strip().startswith("<"):
            return SRUResult(
                success=False,
                error="Response does not appear to be XML",
            )

        return SRUResult(success=True, data=text)


# --- Pre-configured catalog instances ---


def _nli_client() -> SRUClient:
    base = os.environ.get(
        "SRU_NLI_URL",
        "https://nli.alma.exlibrisgroup.com/view/sru/972NNL_INST",
    )
    return SRUClient(base_url=base, version="1.2", auto_quote_alma=True)


def _lc_client() -> SRUClient:
    base = os.environ.get("SRU_LC_URL", "http://lx2.loc.gov:210/LCDB")
    return SRUClient(base_url=base, version="1.1")


def _viaf_client() -> SRUClient:
    base = os.environ.get("SRU_VIAF_URL", "https://viaf.org/viaf/search")
    return SRUClient(base_url=base, version="1.1")


nli_client = _nli_client()
lc_client = _lc_client()
viaf_client = _viaf_client()

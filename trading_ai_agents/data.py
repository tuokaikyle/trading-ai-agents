"""Small yfinance wrapper. Every fetch records its provenance and coverage.

The cache lasts for one workflow run. Indicators and both news agents therefore
use the same underlying observations, without a database or persistent cache.
"""

import math
from datetime import UTC, datetime
from statistics import mean

import yfinance as yf


def clean(value):
    """Convert pandas/numpy values to ordinary, finite JSON values."""
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def calculate_indicators(rows: list[dict]) -> dict:
    """Simple, inspectable calculations on adjusted daily closes.

    RSI here uses simple averages over 14 changes, not Wilder smoothing. We
    label that explicitly so learners can compare or replace the formula.
    """
    closes = [row["close"] for row in rows]
    if not closes:
        return {}
    rsi = None
    if len(closes) >= 15:
        changes = [right - left for left, right in zip(closes[-15:], closes[-14:])]
        gains = mean(max(change, 0) for change in changes)
        losses = mean(max(-change, 0) for change in changes)
        rsi = 50.0 if gains == losses == 0 else (
            100.0 if losses == 0 else 100 - 100 / (1 + gains / losses)
        )
    return {
        "latest_bar_date": rows[-1]["date"],
        "latest_adjusted_close": closes[-1],
        "previous_bar_change_pct": (
            (closes[-1] / closes[-2] - 1) * 100 if len(closes) > 1 else None
        ),
        "sma_20": mean(closes[-20:]) if len(closes) >= 20 else None,
        "sma_50": mean(closes[-50:]) if len(closes) >= 50 else None,
        "rsi_14_simple": rsi,
        "observations": len(closes),
    }


class YahooData:
    def __init__(self, symbol: str, ticker=None, news_search=None):
        self.symbol = symbol
        self.ticker = ticker if ticker is not None else yf.Ticker(symbol)
        self.news_search = news_search if news_search is not None else (
            lambda: yf.Search(symbol, news_count=8).news
        )
        self.evidence: dict[str, dict] = {}

    def _fetch(self, name, loader, note="") -> dict:
        if name not in self.evidence:
            record = {
                "source": "Yahoo Finance via yfinance",
                "symbol": self.symbol,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "note": note,
            }
            try:
                payload = clean(loader())
                record.update(status="ok" if payload else "empty", data=payload)
            except Exception as exc:
                # Do not confuse a network/source failure with an empty result.
                record.update(status="unavailable", data=None, error=type(exc).__name__)
            self.evidence[name] = record
        return self.evidence[name]

    def prices(self):
        def load():
            frame = self.ticker.history(period="6mo", auto_adjust=True, timeout=15)
            rows = []
            for timestamp, row in frame.sort_index().iterrows():
                close = clean(row.get("Close"))
                if close is None or close <= 0:
                    continue
                rows.append({
                    "date": timestamp.date().isoformat(),
                    **{key.lower(): clean(row.get(key))
                       for key in ("Open", "High", "Low", "Close", "Volume")},
                })
            return rows

        return self._fetch(
            "prices", load,
            "Six months of adjusted daily OHLCV. Latest bar may be incomplete "
            "during a market session. Prices are in the instrument's quote currency.",
        )

    def indicators(self):
        prices = self.prices()
        if prices["status"] != "ok":
            self.evidence["indicators"] = {
                **prices, "note": "Indicators unavailable without price observations."
            }
            return self.evidence["indicators"]
        return self._fetch(
            "indicators", lambda: calculate_indicators(prices["data"]),
            "Calculated locally from cached adjusted closes. RSI uses simple "
            "averages; null means insufficient history. Same evidence as prices.",
        )

    def company(self):
        def load():
            info = self.ticker.info or {}
            keys = (
                "shortName", "sector", "industry", "currency", "financialCurrency",
                "marketCap", "trailingPE", "forwardPE", "totalRevenue", "revenueGrowth",
                "profitMargins", "totalDebt", "totalCash", "freeCashflow",
            )
            return {key: info[key] for key in keys if info.get(key) is not None}

        return self._fetch("company", load, "Current snapshot; not historical as-of data.")

    def financials(self):
        specs = {
            "income_statement": (self.ticker.get_income_stmt,
                                 ("TotalRevenue", "OperatingIncome", "NetIncome")),
            "balance_sheet": (self.ticker.get_balance_sheet,
                              ("TotalAssets", "TotalLiabilitiesNetMinorityInterest", "TotalDebt")),
            "cashflow": (self.ticker.get_cashflow,
                         ("OperatingCashFlow", "CapitalExpenditure", "FreeCashFlow")),
        }
        results = {}
        for name, (getter, metrics) in specs.items():
            def load(getter=getter, metrics=metrics):
                frame = getter(freq="quarterly")
                if frame is None or frame.empty:
                    return []
                periods = []
                for column in frame.columns[:2]:
                    values = {metric: clean(frame.loc[metric, column])
                              for metric in metrics if metric in frame.index}
                    if any(value is not None for value in values.values()):
                        periods.append({"period_end": column.date().isoformat(), "values": values})
                return periods

            results[name] = self._fetch(
                name, load,
                "Latest available quarterly values, in reporting currency; period end "
                "is not publication date. Values may have been restated.",
            )
        return results

    def news(self):
        def load():
            articles = []
            items = self.ticker.get_news(count=8) or []
            if not items:
                # Yahoo's company feed can be empty even when search has news.
                # Keep only search articles explicitly tagged with this symbol.
                items = [item for item in (self.news_search() or [])
                         if self.symbol in [str(t).upper() for t in item.get("relatedTickers", [])]]
            for item in items[:8]:
                content = item.get("content") or item
                title = content.get("title")
                if not title:
                    continue
                published = content.get("pubDate")
                if not published and content.get("providerPublishTime"):
                    published = datetime.fromtimestamp(content["providerPublishTime"], UTC).isoformat()
                url = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
                articles.append({
                    "title": str(title)[:400],
                    "summary": str(content.get("summary") or "")[:1200],
                    "published_at": published,
                    "publisher": (content.get("provider") or {}).get("displayName")
                                 or content.get("publisher"),
                    "url": url.get("url") or content.get("link"),
                })
            return articles

        return self._fetch(
            "news", load,
            "Recent Yahoo feed/search sample; not exhaustive or an archive. Headlines "
            "may mention peers or broader markets. Unknown publication dates remain null.",
        )

"""Query resolver with Korean hints for cycle/period and alias matching."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
import re
from typing import Any

from .aliases import AliasEntry, COMMON_ALIASES
from .models import ResolutionCandidate, SearchArgs
from .normalizers import normalize_cycle


class QueryResolver:
    """Resolves natural-language queries to ECOS search arguments."""

    def __init__(self, aliases: tuple[AliasEntry, ...] = COMMON_ALIASES) -> None:
        self._aliases = aliases

    def resolve(self, query: str, top_k: int = 5) -> dict[str, Any]:
        clean_query = query.strip()
        lowered = clean_query.lower()
        cycle_hint, cycle_reasons = self._infer_cycle_hint(lowered)

        candidates: list[ResolutionCandidate] = []
        for alias in self._aliases:
            candidate = self._score_alias(alias=alias, query_lower=lowered, cycle_hint=cycle_hint)
            if candidate is not None:
                args, period_reasons = self._apply_period_hints(
                    query=clean_query,
                    args=candidate.search_args,
                    cycle_hint=cycle_hint,
                )
                updated_reasons = candidate.reasons + cycle_reasons + period_reasons
                candidates.append(
                    ResolutionCandidate(
                        alias=candidate.alias,
                        score=candidate.score,
                        confidence=candidate.confidence,
                        reasons=updated_reasons,
                        search_args=args,
                    )
                )

        explicit_code = self._extract_table_code(clean_query)
        if explicit_code is not None:
            fallback_cycle = cycle_hint or "M"
            fallback_args = SearchArgs(
                table_code=explicit_code,
                cycle=fallback_cycle,
                start_date=self._default_period(fallback_cycle)[0],
                end_date=self._default_period(fallback_cycle)[1],
            )
            explicit_reasons = ["query contains explicit table code"]
            if cycle_hint is not None:
                explicit_reasons.append(f"cycle hint matched: {cycle_hint}")
            candidates.append(
                ResolutionCandidate(
                    alias=f"TABLE:{explicit_code}",
                    score=55,
                    confidence=0.55,
                    reasons=explicit_reasons,
                    search_args=fallback_args,
                )
            )

        candidates.sort(key=lambda item: item.score, reverse=True)
        limited = candidates[: max(1, top_k)]

        warnings: list[str] = []
        if not limited:
            warnings.append("No strong alias match found; use search_tables for discovery")
        elif limited[0].confidence < 0.6:
            warnings.append("Low confidence resolution; verify table_code and item codes")

        return {
            "query": clean_query,
            "detected_cycle": cycle_hint,
            "candidates": [candidate.to_dict() for candidate in limited],
            "search_args": limited[0].search_args.to_dict() if limited else None,
            "warnings": warnings,
        }

    def _score_alias(
        self,
        *,
        alias: AliasEntry,
        query_lower: str,
        cycle_hint: str | None,
    ) -> ResolutionCandidate | None:
        score = 0
        reasons: list[str] = []

        alias_lower = alias.alias.lower()
        if alias_lower in query_lower:
            score += 60
            reasons.append(f"explicit alias match: {alias.alias}")

        keyword_hits = 0
        for keyword in alias.keywords:
            if keyword.lower() in query_lower:
                score += 20
                keyword_hits += 1
                reasons.append(f"keyword match: {keyword}")

        if keyword_hits == 0 and alias_lower not in query_lower:
            return None

        if cycle_hint is not None:
            if cycle_hint == alias.default_args.cycle:
                score += 10
                reasons.append(f"cycle hint aligns with alias default cycle ({cycle_hint})")
            else:
                score -= 5
                reasons.append(
                    f"cycle hint ({cycle_hint}) differs from alias default ({alias.default_args.cycle})"
                )

        score = max(1, min(100, score))
        confidence = round(min(0.99, score / 100), 2)
        return ResolutionCandidate(
            alias=alias.alias,
            score=score,
            confidence=confidence,
            reasons=reasons,
            search_args=alias.default_args,
        )

    def _infer_cycle_hint(self, query_lower: str) -> tuple[str | None, list[str]]:
        hints: list[tuple[str, tuple[str, ...]]] = [
            ("D", ("일간", "일별", "daily", "하루", "매일")),
            ("SM", ("반월", "semi-monthly", "상반월", "하반월")),
            ("M", ("월간", "월별", "monthly", "매월")),
            ("Q", ("분기", "분기별", "quarter", "분기당")),
            ("S", ("반기", "half-year", "semiannual")),
            ("A", ("연간", "연도", "년간", "annual", "yearly")),
        ]
        for cycle, terms in hints:
            for term in terms:
                if term in query_lower:
                    return cycle, [f"cycle hint detected from term '{term}'"]

        explicit_patterns: list[tuple[str, re.Pattern[str]]] = [
            ("Q", re.compile(r"\b\d{4}Q[1-4]\b", re.IGNORECASE)),
            ("D", re.compile(r"\b\d{8}\b")),
            ("M", re.compile(r"\b\d{6}\b")),
            ("A", re.compile(r"\b\d{4}\b")),
        ]
        for cycle, pattern in explicit_patterns:
            if pattern.search(query_lower) is not None:
                return cycle, [f"cycle inferred from explicit date format ({cycle})"]

        return None, []

    def _apply_period_hints(
        self,
        *,
        query: str,
        args: SearchArgs,
        cycle_hint: str | None,
    ) -> tuple[SearchArgs, list[str]]:
        cycle = normalize_cycle(cycle_hint or args.cycle)
        reasons: list[str] = []

        explicit = self._extract_explicit_range(query=query, cycle=cycle)
        if explicit is not None:
            reasons.append("explicit period range detected in query")
            return (
                replace(
                    args,
                    cycle=cycle,
                    start_date=explicit[0],
                    end_date=explicit[1],
                ),
                reasons,
            )

        relative = self._extract_relative_range(query=query, cycle=cycle)
        if relative is not None:
            reasons.append("relative period detected in query")
            return (
                replace(
                    args,
                    cycle=cycle,
                    start_date=relative[0],
                    end_date=relative[1],
                ),
                reasons,
            )

        default_start, default_end = self._default_period(cycle)
        reasons.append("default period window applied")
        return (
            replace(args, cycle=cycle, start_date=default_start, end_date=default_end),
            reasons,
        )

    def _extract_explicit_range(self, *, query: str, cycle: str) -> tuple[str, str] | None:
        if cycle == "Q":
            match = re.search(
                r"(\d{4}Q[1-4])\s*(?:~|\-|to|부터)\s*(\d{4}Q[1-4])",
                query,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).upper(), match.group(2).upper()
        elif cycle == "M":
            match = re.search(r"(\d{6})\s*(?:~|\-|to|부터)\s*(\d{6})", query)
            if match:
                return match.group(1), match.group(2)
        elif cycle == "D":
            match = re.search(r"(\d{8})\s*(?:~|\-|to|부터)\s*(\d{8})", query)
            if match:
                return match.group(1), match.group(2)
        elif cycle == "A":
            match = re.search(r"(\d{4})\s*(?:~|\-|to|부터)\s*(\d{4})", query)
            if match:
                return match.group(1), match.group(2)
        elif cycle == "S":
            match = re.search(r"(\d{4}[12])\s*(?:~|\-|to|부터)\s*(\d{4}[12])", query)
            if match:
                return match.group(1), match.group(2)
        elif cycle == "SM":
            match = re.search(r"(\d{6}[12])\s*(?:~|\-|to|부터)\s*(\d{6}[12])", query)
            if match:
                return match.group(1), match.group(2)
        return None

    def _extract_relative_range(self, *, query: str, cycle: str) -> tuple[str, str] | None:
        now = datetime.now()

        year_match = re.search(r"최근\s*(\d+)\s*년", query)
        month_match = re.search(r"최근\s*(\d+)\s*개월", query)
        quarter_match = re.search(r"최근\s*(\d+)\s*분기", query)
        day_match = re.search(r"최근\s*(\d+)\s*일", query)

        if cycle == "A" and year_match:
            years = int(year_match.group(1))
            end = now.year
            start = end - max(0, years - 1)
            return f"{start}", f"{end}"

        if cycle == "Q" and quarter_match:
            count = int(quarter_match.group(1))
            end_index = now.year * 4 + ((now.month - 1) // 3 + 1)
            start_index = end_index - max(0, count - 1)
            return self._quarter_from_index(start_index), self._quarter_from_index(end_index)

        if cycle == "M" and month_match:
            count = int(month_match.group(1))
            end = now.year * 12 + now.month - 1
            start = end - max(0, count - 1)
            return self._month_from_index(start), self._month_from_index(end)

        if cycle == "D" and day_match:
            count = int(day_match.group(1))
            end_day = date.today()
            start_day = end_day - timedelta(days=max(0, count - 1))
            return start_day.strftime("%Y%m%d"), end_day.strftime("%Y%m%d")

        if year_match and cycle in {"Q", "M", "S", "SM"}:
            years = int(year_match.group(1))
            if cycle == "Q":
                end_index = now.year * 4 + ((now.month - 1) // 3 + 1)
                start_index = end_index - max(0, years * 4 - 1)
                return self._quarter_from_index(start_index), self._quarter_from_index(end_index)
            if cycle == "M":
                end = now.year * 12 + now.month - 1
                start = end - max(0, years * 12 - 1)
                return self._month_from_index(start), self._month_from_index(end)
            if cycle == "S":
                current_half = 1 if now.month <= 6 else 2
                end_index = now.year * 2 + current_half - 1
                start_index = end_index - max(0, years * 2 - 1)
                return self._semi_from_index(start_index), self._semi_from_index(end_index)
            if cycle == "SM":
                semimonth = 1 if now.day <= 15 else 2
                end_index = (now.year * 12 + now.month - 1) * 2 + semimonth - 1
                start_index = end_index - max(0, years * 24 - 1)
                return self._semimonth_from_index(start_index), self._semimonth_from_index(end_index)

        return None

    def _default_period(self, cycle: str) -> tuple[str, str]:
        normalized_cycle = normalize_cycle(cycle)
        now = datetime.now()
        if normalized_cycle == "A":
            end = now.year
            return f"{end - 9}", f"{end}"
        if normalized_cycle == "S":
            current_half = 1 if now.month <= 6 else 2
            end_index = now.year * 2 + current_half - 1
            start_index = end_index - 7
            return self._semi_from_index(start_index), self._semi_from_index(end_index)
        if normalized_cycle == "Q":
            quarter = (now.month - 1) // 3 + 1
            end_index = now.year * 4 + quarter
            start_index = end_index - 11
            return self._quarter_from_index(start_index), self._quarter_from_index(end_index)
        if normalized_cycle == "M":
            end_index = now.year * 12 + now.month - 1
            start_index = end_index - 23
            return self._month_from_index(start_index), self._month_from_index(end_index)
        if normalized_cycle == "SM":
            semimonth = 1 if now.day <= 15 else 2
            end_index = (now.year * 12 + now.month - 1) * 2 + semimonth - 1
            start_index = end_index - 47
            return self._semimonth_from_index(start_index), self._semimonth_from_index(end_index)
        end_date = date.today()
        start_date = end_date - timedelta(days=89)
        return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")

    def _extract_table_code(self, query: str) -> str | None:
        match = re.search(r"\b\d{3}[A-Z]\d{3}\b", query)
        if match is None:
            return None
        return match.group(0)

    def _quarter_from_index(self, index: int) -> str:
        year = index // 4
        quarter = index % 4
        if quarter == 0:
            quarter = 4
            year -= 1
        return f"{year}Q{quarter}"

    def _month_from_index(self, index: int) -> str:
        year = index // 12
        month = index % 12 + 1
        if month == 13:
            month = 1
            year += 1
        return f"{year:04d}{month:02d}"

    def _semi_from_index(self, index: int) -> str:
        year = index // 2
        half = index % 2 + 1
        return f"{year:04d}{half}"

    def _semimonth_from_index(self, index: int) -> str:
        month_index = index // 2
        half = index % 2 + 1
        year = month_index // 12
        month = month_index % 12 + 1
        return f"{year:04d}{month:02d}{half}"

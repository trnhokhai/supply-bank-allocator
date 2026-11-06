"""Source-of-input provenance for the free public supply-planning app.

This tracks HOW a dataset entered the active Streamlit session, not whether
uploaded operational records are authentic or independently verified.
"""

from collections.abc import Mapping

ORIGIN_DEMO = "synthetic_demo"
ORIGIN_UPLOADED = "user_supplied_unverified"
ORIGIN_MIXED = "mixed_sources"
ORIGIN_UNKNOWN = "unspecified"

VALID_ORIGINS = frozenset({ORIGIN_DEMO, ORIGIN_UPLOADED, ORIGIN_MIXED, ORIGIN_UNKNOWN})


def resolve_report_context(cleaned_results: Mapping, source_by_dataset: Mapping | None) -> str:
    """Return a conservative label for ALL cleaned inputs in a report session.

    Untracked / malformed metadata is not evidence of a real upload. The
    source map must identify every dataset currently used by the session.
    """
    if (
        not isinstance(cleaned_results, Mapping)
        or not cleaned_results
        or not isinstance(source_by_dataset, Mapping)
    ):
        return ORIGIN_UNKNOWN

    origins = []
    for dataset_name in cleaned_results:
        source = source_by_dataset.get(dataset_name)
        if not isinstance(source, str) or source not in VALID_ORIGINS:
            return ORIGIN_UNKNOWN
        origins.append(source)

    if ORIGIN_UNKNOWN in origins:
        return ORIGIN_UNKNOWN
    if ORIGIN_MIXED in origins or len(set(origins)) > 1:
        return ORIGIN_MIXED
    return origins[0]


def survey_source_after_change(previous_origin: str | None, *, mode: str,
                               retained_rows: int) -> str:
    """Conservatively label a survey updated by form or Google Forms CSV.

    `replace` or an upsert retaining zero old records is entirely newly
    user-supplied. An upsert retaining old records can mix demo and user
    survey rows. Unknown old provenance remains unknown when rows survive.
    """
    if mode not in {"upsert", "replace"}:
        raise ValueError("Survey mode must be 'upsert' or 'replace'.")
    if isinstance(retained_rows, bool) or not isinstance(retained_rows, int) or retained_rows < 0:
        raise ValueError("retained_rows must be a nonnegative integer.")
    if mode == "replace" or retained_rows == 0:
        return ORIGIN_UPLOADED
    if previous_origin == ORIGIN_UPLOADED:
        return ORIGIN_UPLOADED
    if isinstance(previous_origin, str) and previous_origin in {ORIGIN_DEMO, ORIGIN_MIXED}:
        return ORIGIN_MIXED
    return ORIGIN_UNKNOWN

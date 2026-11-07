"""Read-only, repository-controlled defaults for the nonprofit funder PDF.

The Streamlit Report page lets users override defaults for a single generation.
Neither the UI nor this loader writes a branding configuration or logo.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath


class BrandingConfigError(ValueError):
    """Invalid or unsafe report branding configuration."""


@dataclass(frozen=True)
class ReportBranding:
    bank_name: str
    logo: bytes | None
    signature: str


def load_report_branding(repo_root: Path | None = None) -> ReportBranding:
    """Load config/report_branding.json; reject ambiguous or unsafe values.

    Optional logos must be stored inside config/branding_assets/ and committed
    only when their inclusion in this PUBLIC repository is authorized.
    """
    root = (Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]).resolve()
    config_path = root / "config" / "report_branding.json"
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BrandingConfigError("Cannot read a valid config/report_branding.json file.") from exc

    if not isinstance(values, dict) or set(values) != {"bank_name", "logo_path"}:
        raise BrandingConfigError("Branding config must contain only bank_name and logo_path.")
    name = values["bank_name"]
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise BrandingConfigError("bank_name must be 1-120 nonblank characters.")
    name = name.strip()

    raw_logo = values["logo_path"]
    logo: bytes | None = None
    if raw_logo is not None and raw_logo != "":
        if not isinstance(raw_logo, str) or "\\" in raw_logo:
            raise BrandingConfigError("logo_path must be a forward-slash relative path.")
        segments = raw_logo.split("/")
        rel = PurePosixPath(raw_logo)
        if (rel.is_absolute() or len(segments) < 3 or segments[:2] != ["config", "branding_assets"]
                or any(s in {"", ".", ".."} for s in segments)
                or rel.suffix.lower() not in {".png", ".jpg", ".jpeg"}):
            raise BrandingConfigError("logo_path must point to a PNG/JPEG inside config/branding_assets/.")
        base = (root / "config" / "branding_assets").resolve()
        candidate = (root / Path(*rel.parts)).resolve()
        if not candidate.is_relative_to(base) or not candidate.is_file():
            raise BrandingConfigError("Configured logo is missing or outside config/branding_assets/.")
        try:
            if candidate.stat().st_size > 2_000_000:
                raise BrandingConfigError("Configured logo must be at most 2 MB.")
            logo = candidate.read_bytes()
        except OSError as exc:
            raise BrandingConfigError("Unable to read the configured logo.") from exc

    signature = sha256(name.encode("utf-8") + b"\x00" + (logo or b"")).hexdigest()
    return ReportBranding(name, logo, signature)


def select_report_branding(
    configured: ReportBranding, name_input: str, uploaded_logo: bytes | None,
) -> tuple[str, bytes | None]:
    """User-supplied values override defaults for this generated report only."""
    if not isinstance(name_input, str):
        raise BrandingConfigError("Bank name must be text.")
    return name_input.strip() or configured.bank_name, (uploaded_logo if uploaded_logo is not None else configured.logo)

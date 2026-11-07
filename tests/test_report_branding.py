"""CP7.4B: nonprofit configuration defaults and safe report overrides."""

import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from src.report_branding import (
    BrandingConfigError,
    load_report_branding,
    select_report_branding,
)


def _configured(tmp_path, bank_name="Example Supply Bank", logo_path=None):
    conf = tmp_path / "config"
    conf.mkdir(exist_ok=True)
    (conf / "report_branding.json").write_text(
        json.dumps({"bank_name": bank_name, "logo_path": logo_path}), encoding="utf-8"
    )
    return conf


def test_default_repository_config_has_safe_unbranded_values():
    brand = load_report_branding()
    assert brand.bank_name == "Supply Bank"
    assert brand.logo is None
    assert len(brand.signature) == 64


def test_custom_name_and_single_report_override(tmp_path):
    _configured(tmp_path)
    config = load_report_branding(tmp_path)
    assert select_report_branding(config, "Local Program", b"uploaded") == ("Local Program", b"uploaded")
    assert select_report_branding(config, "  ", None) == ("Example Supply Bank", None)
    assert load_report_branding(tmp_path).bank_name == "Example Supply Bank"  # not persisted by UI


def test_valid_logo_in_configuration_and_uploaded_logo_precedence(tmp_path):
    folder = _configured(tmp_path, logo_path="config/branding_assets/logo.png")
    assets = folder / "branding_assets"
    assets.mkdir()
    out = BytesIO()
    Image.new("RGB", (80, 30), (250, 250, 250)).save(out, format="PNG")
    (assets / "logo.png").write_bytes(out.getvalue())
    brand = load_report_branding(tmp_path)
    assert brand.logo == out.getvalue()
    assert select_report_branding(brand, "", b"new upload")[1] == b"new upload"
    assert select_report_branding(brand, "", None)[1] == out.getvalue()
    (assets / "logo.png").write_bytes(out.getvalue() + b"extra")
    assert load_report_branding(tmp_path).signature != brand.signature


@pytest.mark.parametrize("name", ["", "  ", "x" * 121, None, 17])
def test_bank_name_is_validated(tmp_path, name):
    _configured(tmp_path, bank_name=name)
    with pytest.raises(BrandingConfigError, match="bank_name"):
        load_report_branding(tmp_path)


@pytest.mark.parametrize("path", [
    "../secret.png", "config/branding_assets/../secret.png", "config/branding_assets//bad.png",
    "../../etc/passwd", "C:\\Windows\\secrets.png", "config/other/logo.png", "/tmp/logo.png",
    "config/branding_assets/logo.gif", 123,
])
def test_unsafe_logo_paths_rejected(tmp_path, path):
    _configured(tmp_path, logo_path=path)
    with pytest.raises(BrandingConfigError, match="logo_path"):
        load_report_branding(tmp_path)


def test_missing_or_malformed_config_fails_with_explanation(tmp_path):
    with pytest.raises(BrandingConfigError, match="Cannot read"):
        load_report_branding(tmp_path)
    folder = _configured(tmp_path)
    (folder / "report_branding.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(BrandingConfigError, match="Cannot read"):
        load_report_branding(tmp_path)


def test_missing_or_oversized_logo_rejected(tmp_path):
    folder = _configured(tmp_path, logo_path="config/branding_assets/logo.png")
    with pytest.raises(BrandingConfigError, match="missing"):
        load_report_branding(tmp_path)
    assets = folder / "branding_assets"
    assets.mkdir()
    (assets / "logo.png").write_bytes(b"z" * 2_000_001)
    with pytest.raises(BrandingConfigError, match="2 MB"):
        load_report_branding(tmp_path)


def test_report_page_uses_config_and_invalidates_old_pdf_when_config_changes():
    page = (Path(__file__).resolve().parents[1] / "pages" / "6_Report.py").read_text(encoding="utf-8")
    assert "load_report_branding()" in page
    assert "value=configured_brand.bank_name" in page
    assert "select_report_branding(" in page
    assert '"branding_signature": configured_brand.signature' in page
    assert 'output.get("branding_signature") != configured_brand.signature' in page
    assert 'data_context=data_context' in page  # provenance preserved

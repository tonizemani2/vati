"""CEPII BACI compact global dependency slice.

BACI is the harmonized global bilateral trade dataset at HS6 product level. The full files are
large, so this collector does not persist the ZIP locally and does not ingest every flow into
SQLite. It downloads the current compact HS22 archive to a temporary file, streams the yearly CSVs,
keeps only a critical-product basket, and emits derived world-state rows:

  * global import value by product/year
  * global exporter/importer concentration by product/year
  * import value and supplier concentration for major economies by product/year

Leak discipline: BACI values are trade-year events, but the current 202601 release was published by
CEPII on 2026-01-22. Rows therefore carry `event_time` = Dec 31 of the trade year and `published_at`
= 2026-01-22, so world-state snapshots before the release cannot see these revised values.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from engine import disk_guard

UA = "predictthefuture research (research@vaticinus.com)"
VERSION = "202601"
HS_REVISION = "HS22"
RELEASE_DATE = date(2026, 1, 22)
BACI_URL = f"https://www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_{HS_REVISION}_V{VERSION}.zip"
OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "feeds" / "baci.jsonl"

# HS22 critical-product basket. These codes are stable enough to read directly from BACI HS22 and
# cover the supply-chain domains the forecast layer keeps asking about: batteries, chips, solar,
# magnets, rare earths, polysilicon, and major mined inputs.
PRODUCTS: dict[str, str] = {
    "850760": "Lithium-ion accumulators",
    "854231": "Electronic integrated circuits: processors/controllers",
    "854142": "Photovoltaic cells not assembled in modules/panels",
    "854143": "Photovoltaic cells assembled in modules or panels",
    "280461": "Silicon containing at least 99.99% by weight of silicon",
    "284690": "Rare-earth, yttrium, or scandium compounds",
    "850511": "Permanent magnets of metal",
    "260300": "Copper ores and concentrates",
    "260400": "Nickel ores and concentrates",
    "260200": "Manganese ores and concentrates",
}

TARGET_IMPORTER_ISO3 = (
    "USA", "CHN", "DEU", "JPN", "KOR", "FRA", "GBR", "IND", "CAN", "MEX", "NLD", "ITA",
)
DEFAULT_YEARS = (2022, 2023, 2024)


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    iso3: str


def _download(url: str, *, max_mb: float, log=print) -> Path:
    limit = int(max_mb * 1024 * 1024)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    tmp = tempfile.NamedTemporaryFile(prefix="baci-", suffix=".zip", delete=False)
    path = Path(tmp.name)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 official public data
            declared = int(resp.headers.get("Content-Length") or "0")
            if declared and declared > limit:
                raise RuntimeError(f"BACI archive is {declared / 1e6:.1f} MB, above --max-mb {max_mb:g}")
            read = 0
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                read += len(chunk)
                if read > limit:
                    raise RuntimeError(f"BACI archive exceeded --max-mb {max_mb:g}")
                tmp.write(chunk)
        tmp.close()
        log(f"downloaded BACI {HS_REVISION} V{VERSION}: {path.stat().st_size / 1e6:.1f} MB")
        return path
    except Exception:
        tmp.close()
        path.unlink(missing_ok=True)
        raise


def _find_member(zf: zipfile.ZipFile, *needles: str) -> str:
    lower_needles = tuple(n.lower() for n in needles)
    for name in zf.namelist():
        low = name.lower()
        if all(n in low for n in lower_needles):
            return name
    raise RuntimeError(f"could not find BACI member containing: {', '.join(needles)}")


def _read_countries(zf: zipfile.ZipFile) -> dict[str, Country]:
    member = _find_member(zf, "country", ".csv")
    out: dict[str, Country] = {}
    with zf.open(member) as fh:
        reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", newline=""))
        for row in reader:
            normalized = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            code = (
                normalized.get("country_code")
                or normalized.get("code")
                or normalized.get("i")
                or normalized.get("j")
            )
            iso3 = (
                normalized.get("iso_3digit_alpha")
                or normalized.get("iso3")
                or normalized.get("iso3_alpha")
                or normalized.get("iso_alpha3")
                or normalized.get("country_iso3")
                or ""
            )
            name = (
                normalized.get("country_name")
                or normalized.get("name")
                or normalized.get("country")
                or code
            )
            if code:
                out[str(int(code)) if str(code).isdigit() else str(code)] = Country(
                    code=str(int(code)) if str(code).isdigit() else str(code),
                    name=name,
                    iso3=iso3.upper(),
                )
    return out


def _year_members(zf: zipfile.ZipFile, years: Iterable[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    names = zf.namelist()
    for y in years:
        token = f"Y{y}_"
        for name in names:
            low = name.lower()
            if HS_REVISION.lower() in low and token.lower() in low and low.endswith(".csv"):
                out[y] = name
                break
        if y not in out:
            raise RuntimeError(f"could not find BACI {HS_REVISION} trade-flow CSV for {y}")
    return out


def _hhi_and_top_share(values_by_key: dict[str, float]) -> tuple[float, float]:
    total = sum(values_by_key.values())
    if total <= 0:
        return 0.0, 0.0
    shares = [v / total for v in values_by_key.values() if v > 0]
    hhi = sum((s * 100.0) ** 2 for s in shares)
    return round(hhi, 2), round(max(shares) if shares else 0.0, 6)


def _series_row(
    *,
    series_id: str,
    metric: str,
    event_year: int,
    value: float,
    unit: str,
    title: str,
) -> dict:
    event_time = date(event_year, 12, 31).isoformat()
    return {
        "series_id": series_id,
        "date": event_time,
        "event_time": event_time,
        "published_at": RELEASE_DATE.isoformat(),
        "observed_at": event_time,
        "value": value,
        "unit": unit,
        "metric": metric,
        "title": title,
        "source_version": f"BACI {HS_REVISION} V{VERSION}",
    }


def _process_zip(zf: zipfile.ZipFile, *, years: Iterable[int], log=print) -> list[dict]:
    countries = _read_countries(zf)
    importer_codes = {
        c.code: c for c in countries.values() if c.iso3.upper() in set(TARGET_IMPORTER_ISO3)
    }
    if not importer_codes:
        raise RuntimeError("BACI country metadata did not resolve any target importer ISO3 codes")

    members = _year_members(zf, years)
    global_total: dict[tuple[int, str], float] = defaultdict(float)
    global_exporters: dict[tuple[int, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    global_importers: dict[tuple[int, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    importer_total: dict[tuple[int, str, str], float] = defaultdict(float)
    importer_suppliers: dict[tuple[int, str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for year, member in sorted(members.items()):
        kept = 0
        with zf.open(member) as fh:
            reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", newline=""))
            for row in reader:
                hs = str(row.get("k") or "").strip().zfill(6)
                if hs not in PRODUCTS:
                    continue
                try:
                    value_usd = float(row["v"]) * 1000.0  # BACI v is thousands of current USD.
                except (KeyError, TypeError, ValueError):
                    continue
                if value_usd <= 0:
                    continue
                exporter = str(row.get("i") or "").strip()
                importer = str(row.get("j") or "").strip()
                if not exporter or not importer or exporter == importer:
                    continue
                key = (year, hs)
                global_total[key] += value_usd
                global_exporters[key][exporter] += value_usd
                global_importers[key][importer] += value_usd
                if importer in importer_codes:
                    ikey = (year, hs, importer)
                    importer_total[ikey] += value_usd
                    importer_suppliers[ikey][exporter] += value_usd
                kept += 1
        log(f"processed {year}: kept {kept:,} critical-product flows from {member}")

    rows: list[dict] = []
    for (year, hs), total in sorted(global_total.items()):
        product = PRODUCTS[hs]
        exp_hhi, exp_top = _hhi_and_top_share(global_exporters[(year, hs)])
        imp_hhi, imp_top = _hhi_and_top_share(global_importers[(year, hs)])
        base = f"baci:{HS_REVISION.lower()}:{hs}:{year}"
        rows.extend([
            _series_row(
                series_id=f"{base}:global_import_value",
                metric="baci_global_import_value",
                event_year=year,
                value=round(total, 2),
                unit="USD",
                title=f"BACI {year} global import value — HS{hs} {product}",
            ),
            _series_row(
                series_id=f"{base}:global_exporter_hhi",
                metric="baci_global_exporter_hhi",
                event_year=year,
                value=exp_hhi,
                unit="hhi_0_10000",
                title=f"BACI {year} global exporter concentration — HS{hs} {product}",
            ),
            _series_row(
                series_id=f"{base}:global_top_exporter_share",
                metric="baci_global_top_exporter_share",
                event_year=year,
                value=exp_top,
                unit="share",
                title=f"BACI {year} top exporter share — HS{hs} {product}",
            ),
            _series_row(
                series_id=f"{base}:global_importer_hhi",
                metric="baci_global_importer_hhi",
                event_year=year,
                value=imp_hhi,
                unit="hhi_0_10000",
                title=f"BACI {year} global importer concentration — HS{hs} {product}",
            ),
            _series_row(
                series_id=f"{base}:global_top_importer_share",
                metric="baci_global_top_importer_share",
                event_year=year,
                value=imp_top,
                unit="share",
                title=f"BACI {year} top importer share — HS{hs} {product}",
            ),
        ])

    for (year, hs, importer), total in sorted(importer_total.items()):
        product = PRODUCTS[hs]
        country = importer_codes[importer]
        hhi, top_share = _hhi_and_top_share(importer_suppliers[(year, hs, importer)])
        base = f"baci:{HS_REVISION.lower()}:{hs}:{country.iso3.lower()}:{year}"
        rows.extend([
            _series_row(
                series_id=f"{base}:import_value",
                metric="baci_import_value",
                event_year=year,
                value=round(total, 2),
                unit="USD",
                title=f"BACI {year} {country.name} import value — HS{hs} {product}",
            ),
            _series_row(
                series_id=f"{base}:supplier_hhi",
                metric="baci_supplier_hhi",
                event_year=year,
                value=hhi,
                unit="hhi_0_10000",
                title=f"BACI {year} {country.name} supplier concentration — HS{hs} {product}",
            ),
            _series_row(
                series_id=f"{base}:top_supplier_share",
                metric="baci_top_supplier_share",
                event_year=year,
                value=top_share,
                unit="share",
                title=f"BACI {year} {country.name} top supplier share — HS{hs} {product}",
            ),
        ])
    rows.sort(key=lambda r: (r["series_id"], r["date"]))
    return rows


def collect(*, years: Iterable[int] = DEFAULT_YEARS, max_mb: float = 450.0, log=print) -> list[dict]:
    stats = disk_guard.assert_safe(Path(__file__).resolve().parents[2], label="BACI compact collection")
    log(f"disk ok for BACI: free {stats['free_gb']:.1f}GiB, used {stats['used_pct']:.1f}%")
    zip_path = _download(BACI_URL, max_mb=max_mb, log=log)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            rows = _process_zip(zf, years=years, log=log)
    finally:
        zip_path.unlink(missing_ok=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    log(f"wrote {len(rows)} BACI observations -> {OUT_PATH}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", dest="years", action="append", type=int, help="trade year to keep")
    ap.add_argument("--max-mb", type=float, default=450.0, help="abort if the official ZIP is larger")
    a = ap.parse_args()
    rows = collect(years=tuple(a.years or DEFAULT_YEARS), max_mb=a.max_mb)
    for row in rows[:5]:
        print("  " + json.dumps({k: row[k] for k in ("series_id", "date", "published_at", "value", "unit", "title")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

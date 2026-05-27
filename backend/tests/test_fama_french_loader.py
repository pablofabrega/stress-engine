from __future__ import annotations

from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import pytest

from app.domain.data.cache import LocalParquetCache
from app.domain.data.fama_french import FamaFrenchLoader


def _build_fake_zip(rows: list[str]) -> bytes:
    """Create an in-memory ZIP containing a fake Fama-French CSV."""
    header = (
        "\n"
        "Some preamble text\n"
        "that should be skipped\n"
        "\n"
    )
    body = header + "\n".join(rows) + "\n"
    buf = BytesIO()
    with ZipFile(buf, "w") as zf:
        zf.writestr("F-F_Research_Data_Factors_daily.CSV", body)
    return buf.getvalue()


class StubFamaFrenchLoader(FamaFrenchLoader):
    """Subclass that overrides network download with deterministic test data."""

    def __init__(self, rows: list[str], cache: LocalParquetCache) -> None:
        super().__init__(cache=cache)
        self._zip_bytes = _build_fake_zip(rows)
        self.download_count = 0

    def _download_and_parse(self) -> pd.DataFrame:
        self.download_count += 1

        from io import StringIO
        from zipfile import ZipFile as ZF

        with ZF(BytesIO(self._zip_bytes)) as archive:
            file_name = archive.namelist()[0]
            raw_text = archive.read(file_name).decode("utf-8")

        factor_lines = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            first_cell = stripped.split(",")[0].strip()
            if first_cell.isdigit() and len(first_cell) == 8:
                factor_lines.append(stripped)

        frame = pd.read_csv(
            StringIO("\n".join(["date,Mkt-RF,SMB,HML,RF", *factor_lines])),
            parse_dates=["date"],
            date_format="%Y%m%d",
        )
        frame = frame.rename(columns={"Mkt-RF": "mkt_rf", "SMB": "smb", "HML": "hml", "RF": "rf"})
        for column in ["mkt_rf", "smb", "hml", "rf"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce") / 100.0

        normalized = frame.set_index("date").sort_index()
        normalized.index.name = "date"
        return normalized


SAMPLE_ROWS = [
    "20240102,  0.50,  0.10, -0.20,  0.02",
    "20240103,  1.20, -0.30,  0.40,  0.02",
    "20240104, -0.80,  0.05,  0.10,  0.02",
    "20240105,  0.30,  0.20, -0.15,  0.02",
    "20240108,  0.10, -0.10,  0.05,  0.02",
]


class TestFamaFrenchParsing:
    def test_columns_present(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))
        df = loader.load(force_refresh=True)
        assert list(df.columns) == ["mkt_rf", "smb", "hml", "rf"]

    def test_values_divided_by_100(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))
        df = loader.load(force_refresh=True)
        assert df["mkt_rf"].iloc[0] == pytest.approx(0.005)
        assert df["smb"].iloc[0] == pytest.approx(0.001)

    def test_index_is_datetime(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))
        df = loader.load(force_refresh=True)
        assert df.index.name == "date"
        assert pd.api.types.is_datetime64_any_dtype(df.index)

    def test_row_count_matches(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))
        df = loader.load(force_refresh=True)
        assert len(df) == len(SAMPLE_ROWS)


class TestFamaFrenchCaching:
    def test_second_load_uses_cache(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))

        first = loader.load(force_refresh=True)
        second = loader.load()

        assert loader.download_count == 1
        pd.testing.assert_frame_equal(first, second, check_freq=False)

    def test_force_refresh_bypasses_cache(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))

        loader.load(force_refresh=True)
        loader.load(force_refresh=True)

        assert loader.download_count == 2


class TestFamaFrenchSlicing:
    def test_start_date_filter(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))
        df = loader.load(start_date=date(2024, 1, 4), force_refresh=True)
        assert df.index.min() >= pd.Timestamp("2024-01-04")

    def test_end_date_filter(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))
        df = loader.load(end_date=date(2024, 1, 3), force_refresh=True)
        assert df.index.max() <= pd.Timestamp("2024-01-03")

    def test_date_range_filter(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))
        df = loader.load(start_date=date(2024, 1, 3), end_date=date(2024, 1, 4), force_refresh=True)
        assert len(df) == 2

    def test_no_filter_returns_all(self, tmp_path: str) -> None:
        loader = StubFamaFrenchLoader(SAMPLE_ROWS, cache=LocalParquetCache(root_dir=tmp_path))
        df = loader.load(force_refresh=True)
        assert len(df) == len(SAMPLE_ROWS)

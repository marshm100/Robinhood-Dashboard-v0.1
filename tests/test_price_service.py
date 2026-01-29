"""
Unit tests for price_service.py

Tests the robust yfinance handling including:
- Single ticker Series→DataFrame conversion
- Multiple ticker batch downloads
- Batch→individual fallback
- Caching functionality
"""

import os
import tempfile
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Set up test cache directory before imports
TEST_CACHE_DIR = tempfile.mkdtemp()
os.environ["PRICE_CACHE_DIR"] = TEST_CACHE_DIR
os.environ["PRICE_CACHE_TTL"] = "60"

from api.services.price_service import (
    get_historical_prices,
    get_single_ticker_prices,
    _get_cache_key,
    _load_from_cache,
    _save_to_cache,
)


class TestGetHistoricalPrices:
    """Tests for get_historical_prices function."""

    def test_empty_tickers_returns_empty_df(self):
        """Empty ticker list should return empty DataFrame."""
        result = get_historical_prices([])
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_whitespace_tickers_returns_empty_df(self):
        """Whitespace-only tickers should be filtered out."""
        result = get_historical_prices(["", " ", "  "])
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_tickers_are_uppercased(self):
        """Tickers should be normalized to uppercase."""
        with patch("api.services.price_service.yf.download") as mock_download:
            # Mock successful single-ticker download
            mock_data = pd.DataFrame(
                {"Close": [100.0, 101.0, 102.0]},
                index=pd.date_range("2024-01-01", periods=3)
            )
            mock_download.return_value = mock_data

            result = get_historical_prices(["aapl"], "5d")

            # Should have called with uppercase ticker
            call_args = mock_download.call_args
            assert "AAPL" in call_args[1]["tickers"] or call_args[1]["tickers"] == "AAPL"

    def test_single_ticker_returns_dataframe_with_column(self):
        """Single ticker should return DataFrame with ticker as column name."""
        with patch("api.services.price_service.yf.download") as mock_download:
            # yfinance returns Series for single ticker
            mock_series = pd.Series(
                [100.0, 101.0, 102.0],
                index=pd.date_range("2024-01-01", periods=3),
                name="Close"
            )
            mock_download.return_value = pd.DataFrame({"Close": mock_series})

            result = get_historical_prices(["AAPL"], "5d")

            assert isinstance(result, pd.DataFrame)
            assert "AAPL" in result.columns
            assert len(result) == 3

    def test_multiple_tickers_returns_all_columns(self):
        """Multiple tickers should return DataFrame with all ticker columns."""
        with patch("api.services.price_service.yf.download") as mock_download:
            # yfinance returns MultiIndex DataFrame for multiple tickers
            dates = pd.date_range("2024-01-01", periods=3)
            mock_data = pd.DataFrame(
                {
                    ("Close", "AAPL"): [100.0, 101.0, 102.0],
                    ("Close", "MSFT"): [200.0, 201.0, 202.0],
                },
                index=dates
            )
            mock_data.columns = pd.MultiIndex.from_tuples(mock_data.columns)
            mock_download.return_value = mock_data

            result = get_historical_prices(["AAPL", "MSFT"], "5d")

            assert isinstance(result, pd.DataFrame)
            assert "AAPL" in result.columns
            assert "MSFT" in result.columns

    def test_deduplicates_tickers(self):
        """Duplicate tickers should be deduplicated."""
        with patch("api.services.price_service.yf.download") as mock_download:
            mock_data = pd.DataFrame(
                {"Close": [100.0, 101.0]},
                index=pd.date_range("2024-01-01", periods=2)
            )
            mock_download.return_value = mock_data

            get_historical_prices(["AAPL", "aapl", "AAPL"], "5d")

            # Should only call once with single ticker
            call_args = mock_download.call_args
            tickers = call_args[1]["tickers"]
            if isinstance(tickers, list):
                assert len(tickers) == 1


class TestBatchFallback:
    """Tests for batch→individual fallback behavior."""

    def test_fallback_on_missing_tickers(self):
        """Should fall back to individual downloads when batch misses tickers."""
        with patch("api.services.price_service.yf.download") as mock_download:
            dates = pd.date_range("2024-01-01", periods=3)

            def download_side_effect(tickers, **kwargs):
                if isinstance(tickers, list) and len(tickers) > 1:
                    # Batch call - only return AAPL, missing TSLL
                    data = pd.DataFrame(
                        {("Close", "AAPL"): [100.0, 101.0, 102.0]},
                        index=dates
                    )
                    data.columns = pd.MultiIndex.from_tuples(data.columns)
                    return data
                else:
                    # Individual call
                    ticker = tickers if isinstance(tickers, str) else tickers[0]
                    return pd.DataFrame(
                        {"Close": [100.0, 101.0, 102.0]},
                        index=dates
                    )

            mock_download.side_effect = download_side_effect

            result = get_historical_prices(["AAPL", "TSLL"], "5d")

            # Should have fallen back and fetched individually
            assert mock_download.call_count >= 2  # batch + individual calls


class TestCaching:
    """Tests for caching functionality."""

    def test_cache_key_generation(self):
        """Cache keys should be consistent for same inputs."""
        key1 = _get_cache_key(["AAPL", "MSFT"], "1y")
        key2 = _get_cache_key(["MSFT", "AAPL"], "1y")  # Different order, same set

        assert key1 == key2  # Should produce same key since tickers are sorted

    def test_cache_key_differs_by_period(self):
        """Different periods should produce different cache keys."""
        key1 = _get_cache_key(["AAPL"], "1y")
        key2 = _get_cache_key(["AAPL"], "6mo")

        assert key1 != key2

    def test_cache_save_and_load(self):
        """Should be able to save and load from cache."""
        test_df = pd.DataFrame(
            {"AAPL": [100.0, 101.0, 102.0]},
            index=pd.date_range("2024-01-01", periods=3)
        )
        cache_key = "test_cache_key"

        _save_to_cache(cache_key, test_df)
        loaded = _load_from_cache(cache_key)

        assert loaded is not None
        pd.testing.assert_frame_equal(loaded, test_df)


class TestGetSingleTickerPrices:
    """Tests for get_single_ticker_prices function."""

    def test_returns_dict_format(self):
        """Should return date->price dictionary."""
        with patch("api.services.price_service.get_historical_prices") as mock_get:
            mock_df = pd.DataFrame(
                {"AAPL": [100.0, 101.0]},
                index=pd.to_datetime(["2024-01-01", "2024-01-02"])
            )
            mock_get.return_value = mock_df

            result = get_single_ticker_prices("AAPL", "5d")

            assert isinstance(result, dict)
            assert "2024-01-01" in result
            assert result["2024-01-01"] == 100.0

    def test_handles_lowercase_ticker(self):
        """Should handle lowercase ticker input."""
        with patch("api.services.price_service.get_historical_prices") as mock_get:
            mock_df = pd.DataFrame(
                {"AAPL": [100.0]},
                index=pd.to_datetime(["2024-01-01"])
            )
            mock_get.return_value = mock_df

            result = get_single_ticker_prices("aapl", "5d")

            assert "2024-01-01" in result

    def test_returns_empty_dict_on_no_data(self):
        """Should return empty dict when no data available."""
        with patch("api.services.price_service.get_historical_prices") as mock_get:
            mock_get.return_value = pd.DataFrame()

            result = get_single_ticker_prices("INVALID", "5d")

            assert result == {}


# Integration test (requires network, skip in CI)
@pytest.mark.skip(reason="Requires network access to yfinance")
class TestIntegration:
    """Integration tests that hit real yfinance API."""

    def test_real_single_ticker(self):
        """Test with real single ticker."""
        df = get_historical_prices(["SPY"], "5d")
        assert not df.empty
        assert "SPY" in df.columns
        assert isinstance(df, pd.DataFrame)

    def test_real_multiple_tickers(self):
        """Test with real multiple tickers."""
        df = get_historical_prices(["AAPL", "MSFT", "SPY"], "5d")
        assert not df.empty
        assert set(df.columns) >= {"AAPL", "MSFT", "SPY"}

    def test_real_leveraged_etfs(self):
        """Test with the problem leveraged ETFs."""
        df = get_historical_prices(["TSLL", "BITU", "AGQ"], "1mo")
        # These may or may not have data depending on market conditions
        assert isinstance(df, pd.DataFrame)

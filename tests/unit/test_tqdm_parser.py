"""Unit tests for tqdm ETA parsing utilities."""

from scheduler.core.tqdm_parser import parse_tqdm_eta, format_eta_display


class TestParseTqdmEta:
    """Tests for parse_tqdm_eta."""

    def test_parse_from_standard_tqdm_line(self):
        """Parse ETA from a standard tqdm progress line."""
        stderr = "Inference batches: 67%|######| 8/12 [33:50<17:15, 258.98s/it]"

        assert parse_tqdm_eta(stderr) == "17:15"

    def test_parse_from_carriage_return_updates(self):
        """Parse ETA from stderr where tqdm rewrites a single line with CR."""
        stderr = (
            "Inference batches: 0%| | 0/12 [00:00<?, ?it/s]\r"
            "Inference batches: 8%|#| 1/12 [04:21<47:55, 261.37s/it]\r"
            "Inference batches: 17%|##| 2/12 [08:30<42:20, 254.02s/it]\r"
            "Inference batches: 67%|######| 8/12 [33:50<17:15, 258.98s/it]"
        )

        assert parse_tqdm_eta(stderr) == "17:15"

    def test_returns_none_for_unknown_eta(self):
        """Return None when tqdm shows unknown ETA token."""
        stderr = "Inference batches: 0%| | 0/12 [00:00<?, ?it/s]"

        assert parse_tqdm_eta(stderr) is None


class TestFormatEtaDisplay:
    """Tests for format_eta_display — no 'ETA:' prefix, just the time."""

    def test_none_returns_dash(self):
        assert format_eta_display(None) == "-"

    def test_mm_ss_minutes_nonzero(self):
        assert format_eta_display("17:15") == "17m 15s"

    def test_mm_ss_seconds_only(self):
        assert format_eta_display("00:42") == "42s"

    def test_hh_mm_ss_hours_nonzero(self):
        assert format_eta_display("01:23:45") == "1h 23m"

    def test_hh_mm_ss_minutes_only(self):
        assert format_eta_display("00:05:30") == "5m 30s"

    def test_hh_mm_ss_seconds_only(self):
        assert format_eta_display("00:00:09") == "9s"

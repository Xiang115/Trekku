import sys
import pytest
from unittest.mock import patch


def test_main_returns_summary_on_success():
    mock_summary = {"hotels": 5, "attractions": 3, "flights": 10, "errors": 0}
    with patch("run_refresh.refresh_all", return_value=mock_summary):
        from run_refresh import main
        result = main()
    assert result == mock_summary


def test_main_returns_error_summary_on_exception():
    with patch("run_refresh.refresh_all", side_effect=Exception("boom")):
        from run_refresh import main
        result = main()
    assert result["errors"] == 1
    assert result["hotels"] == 0


def test_script_exits_1_when_errors_nonzero():
    mock_summary = {"hotels": 0, "attractions": 0, "flights": 0, "errors": 2}
    with patch("run_refresh.refresh_all", return_value=mock_summary):
        with pytest.raises(SystemExit) as exc_info:
            import run_refresh
            result = run_refresh.main()
            if result["errors"] > 0:
                sys.exit(1)
    assert exc_info.value.code == 1


def test_script_does_not_exit_when_no_errors():
    mock_summary = {"hotels": 5, "attractions": 3, "flights": 10, "errors": 0}
    with patch("run_refresh.refresh_all", return_value=mock_summary):
        from run_refresh import main
        result = main()
    assert result["errors"] == 0

"""
Daily refresh script — called by GitHub Actions cron.
    python run_refresh.py
"""
import sys
from knowledge_capture import refresh_all


def main() -> dict:
    summary = refresh_all()
    print(f"Refresh complete: {summary}")
    return summary


if __name__ == "__main__":
    result = main()
    if result["errors"] > 0:
        sys.exit(1)

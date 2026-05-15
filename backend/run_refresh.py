"""
Daily refresh script — called by GitHub Actions cron.
    cd backend && python run_refresh.py
"""
import sys
from knowledge_capture import refresh_all


def main() -> dict:
    try:
        summary = refresh_all()
    except Exception as exc:
        print(f"[run_refresh] Unhandled error: {exc}", file=sys.stderr)
        return {"hotels": 0, "attractions": 0, "flights": 0, "errors": 1}
    print(f"Refresh complete: {summary}", file=sys.stderr)
    return summary


if __name__ == "__main__":
    result = main()
    if result["errors"] > 0:
        sys.exit(1)

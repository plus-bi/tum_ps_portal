"""Consistent gzip TTFB measurements. Does not collect cookies or search terms."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
from pathlib import Path


def measure(url):
    result = subprocess.run(["curl", "--compressed", "--silent", "--show-error", "--max-time", "30",
                             "--output", "/dev/null", "--write-out", "%{http_code} %{time_starttransfer}", url],
                            check=True, capture_output=True, text=True)
    status, timing = result.stdout.split()
    if status != "200":
        raise RuntimeError(f"Unexpected HTTP status {status}")
    return float(timing) * 1000


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = {}
    for locale in ("en", "de"):
        url = f"{args.base}/{locale}"
        measure(url)
        sequential = [measure(url) for _ in range(30)]
        with ThreadPoolExecutor(max_workers=10) as pool:
            concurrent = list(pool.map(measure, [url] * 30))
        report[locale] = {"sequential_p95_ms": sorted(sequential)[28], "concurrent_p95_ms": sorted(concurrent)[28]}
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

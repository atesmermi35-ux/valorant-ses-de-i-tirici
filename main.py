"""Run with Python 3.10+; the desktop companion has no pip dependencies."""

import argparse
import json

from voicebridge import core


def main():
    parser = argparse.ArgumentParser(description="VoiceBridge · Valorant ses motoru kurulum yardımcısı")
    parser.add_argument("--diagnose", action="store_true", help="GPU ve platform bilgisini yazdır")
    parser.add_argument("--catalog", action="store_true", help="Resmî Windows CUDA ZIP kataloğunu sorgula")
    args = parser.parse_args()
    if args.diagnose:
        import platform
        print(json.dumps({"platform": platform.system(), "python": platform.python_version(), "gpu": core.gpu_report()}, ensure_ascii=False, indent=2))
    elif args.catalog:
        from dataclasses import asdict
        try:
            print(json.dumps([asdict(r) for r in core.fetch_catalog()], indent=2))
        except Exception as exc:
            parser.exit(1, f"Katalog okunamadı: {exc}\n")
    else:
        from voicebridge.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()

"""python -m triage [--dry-run] [--ticket ID] [--sin-analisis] [--config config.toml]"""
import argparse
import sys

from triage.brains import build_brain
from triage.config import Config
from triage.dashboard import write_dashboard
from triage.notify import build_notifier
from triage.pipeline import Pipeline
from triage.sources import build_sources
from triage.store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(prog="triage", description="Triage automático de una mesa de ayuda.")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--dry-run", action="store_true", help="no guarda estado ni publica en el chat")
    parser.add_argument("--ticket", help="procesa solo ese ticket, aunque ya se haya visto")
    parser.add_argument("--sin-analisis", action="store_true", help="solo triage y relación, sin revisar código")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config = Config(args.config)
    profile = config.resolve(config["project"]["profile"]).read_text(encoding="utf-8")
    tickets, issues = build_sources(config)
    db_path = config.resolve(config.get("store", {}).get("path", "data/triage.db"))
    if not args.dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(":memory:" if args.dry_run else str(db_path))

    pipeline = Pipeline(config, build_brain(config, profile), tickets, issues, store,
                        build_notifier(config, args.dry_run), analyze=not args.sin_analisis)
    results = pipeline.run(only=args.ticket)
    if not args.dry_run:
        out = write_dashboard(store, issues, config)
        print(f"\n[dashboard] {out}")
    print(f"[ciclo] listo: {len(results)} tickets procesados")


if __name__ == "__main__":
    main()

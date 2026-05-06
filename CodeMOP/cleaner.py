# CodeMOP — Cleaner
# Keeps ~/.agents/app/ healthy.
# Archives old sessions, compresses ancient ones,
# vacuums SQLite. Never touches decisions table.
# Decisions are forever.

from pathlib import Path
import os
import sys
import gzip
import shutil
import logging
import json
from datetime import datetime, timedelta
from crontab import CronTab
from codemop import (
    APP_ROOT,
    SESSIONS_DIR,
    ARCHIVE_DIR,
    DB_PATH,
    load_config,
)
from codemop.indexer import Database

log = logging.getLogger("codemop.cleaner")


class Cleaner:

    def __init__(self):
        self.config = load_config()
        self.db = Database()
        self.cleaner_config = self.config.get(
            "cleaner", {})

        self.active_days = (
            self.cleaner_config.get(
                "active_retention_days", 30))
        self.archive_days = (
            self.cleaner_config.get(
                "archive_retention_days", 90))
        self.compress = (
            self.cleaner_config.get(
                "compress", True))

        self.active_cutoff = (
            datetime.now() -
            timedelta(days=self.active_days))
        self.archive_cutoff = (
            datetime.now() -
            timedelta(days=self.archive_days))

    # ── Main entry point ──────────────────────────────
    def run(self, dry_run: bool = False) -> dict:
        """
        Full clean cycle.
        dry_run=True shows what would happen
        without doing anything.
        """
        log.info(
            f"Cleaner starting "
            f"{'(dry run) ' if dry_run else ''}"
            f"active cutoff: "
            f"{self.active_cutoff.date()} "
            f"archive cutoff: "
            f"{self.archive_cutoff.date()}")

        report = {
            "started_at": (
                datetime.now().isoformat()),
            "dry_run": dry_run,
            "archived": [],
            "deleted": [],
            "compressed": [],
            "errors": [],
            "db_vacuumed": False
        }

        self._clean_sessions(report, dry_run)

        if self.compress:
            self._compress_archive(report, dry_run)

        if not dry_run:
            self._vacuum_db(report)

        self._write_report(report)

        log.info(
            f"Cleaner done — "
            f"archived: {len(report['archived'])} "
            f"deleted: {len(report['deleted'])} "
            f"compressed: "
            f"{len(report['compressed'])}")

        return report

    def preview(self) -> dict:
        return self.run(dry_run=True)

    # ── Session cleaning ──────────────────────────────
    def _clean_sessions(self,
                        report: dict,
                        dry_run: bool):
        if not SESSIONS_DIR.exists():
            return

        for filepath in SESSIONS_DIR.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.stem.endswith("_parsed"):
                continue
            try:
                self._apply_rules(
                    filepath, report, dry_run)
            except Exception as e:
                log.warning(
                    f"Error processing "
                    f"{filepath.name}: {e}")
                report["errors"].append(
                    str(filepath))

    def _apply_rules(self,
                     filepath: Path,
                     report: dict,
                     dry_run: bool):
        file_age = self._file_age(filepath)
        outcome = self._get_outcome(filepath)
        has_sidecar = self._has_sidecar(filepath)

        # Abandoned — delete immediately
        if outcome == "abandoned":
            log.info(
                f"Deleting abandoned: "
                f"{filepath.name}")
            if not dry_run:
                self._delete_file(filepath)
            report["deleted"].append(
                str(filepath))
            return

        # Old + no sidecar — delete
        if (file_age > self.active_days and
                not has_sidecar):
            log.info(
                f"Deleting unindexed: "
                f"{filepath.name}")
            if not dry_run:
                self._delete_file(filepath)
            report["deleted"].append(
                str(filepath))
            return

        # Old + has sidecar — archive
        if (file_age > self.active_days and
                has_sidecar):
            log.info(
                f"Archiving: {filepath.name}")
            if not dry_run:
                self._archive_file(filepath)
            report["archived"].append(
                str(filepath))
            return

        log.debug(
            f"Keeping: {filepath.name} "
            f"(age: {file_age}d)")

    # ── Archive ───────────────────────────────────────
    def _archive_file(self, filepath: Path):
        mtime = datetime.fromtimestamp(
            filepath.stat().st_mtime)
        month_dir = (
            ARCHIVE_DIR /
            filepath.parent.name /
            mtime.strftime("%Y-%m"))
        month_dir.mkdir(
            parents=True, exist_ok=True)

        dest = month_dir / filepath.name
        shutil.move(str(filepath), str(dest))

        sidecar = self._sidecar_path(filepath)
        if sidecar and sidecar.exists():
            shutil.move(
                str(sidecar),
                str(month_dir / sidecar.name))

        self._update_session_path(
            str(filepath), str(dest))

    def _compress_archive(self,
                          report: dict,
                          dry_run: bool):
        if not ARCHIVE_DIR.exists():
            return

        for filepath in ARCHIVE_DIR.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.suffix == ".gz":
                continue
            if filepath.suffix == ".json":
                continue

            if self._file_age(
                    filepath) > self.archive_days:
                log.info(
                    f"Compressing: "
                    f"{filepath.name}")
                if not dry_run:
                    self._compress_file(filepath)
                report["compressed"].append(
                    str(filepath))

    def _compress_file(self, filepath: Path):
        compressed = Path(str(filepath) + ".gz")
        try:
            with open(filepath, 'rb') as f_in:
                with gzip.open(
                        str(compressed), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            filepath.unlink()
            self._update_session_path(
                str(filepath), str(compressed))
        except Exception as e:
            log.warning(
                f"Compression failed "
                f"{filepath.name}: {e}")
            if compressed.exists():
                compressed.unlink()

    # ── Database ──────────────────────────────────────
    def _vacuum_db(self, report: dict):
        try:
            self.db.vacuum()
            report["db_vacuumed"] = True
        except Exception as e:
            log.warning(f"Vacuum failed: {e}")
            report["errors"].append(
                f"vacuum: {e}")

    def _update_session_path(self,
                              old: str,
                              new: str):
        with self.db._connect() as conn:
            conn.execute(
                "UPDATE sessions SET "
                "filepath = ? "
                "WHERE filepath = ?",
                (new, old))

    # ── Cron ──────────────────────────────────────────
    def install_cron(self) -> bool:
        schedule = self.cleaner_config.get(
            "run_schedule", "0 2 * * 0")
        
        # Use absolute path of current script
        script_path = os.path.abspath(__file__)
        command = (
            f"{sys.executable} {script_path} --run >> "
            f"{APP_ROOT}/cleaner.log 2>&1")

        try:
            cron = CronTab(user=True)
            cron.remove_all(
                comment="codemop-cleaner")
            job = cron.new(
                command=command,
                comment="codemop-cleaner")
            job.setall(schedule)
            cron.write()
            log.info(
                f"Cron installed: {schedule} -> {script_path}")
            return True
        except Exception as e:
            log.warning(
                f"Could not install cron: {e}")
            return False

    def remove_cron(self) -> bool:
        try:
            cron = CronTab(user=True)
            cron.remove_all(
                comment="codemop-cleaner")
            cron.write()
            log.info("Cron removed")
            return True
        except Exception as e:
            log.warning(
                f"Could not remove cron: {e}")
            return False

    def next_run(self) -> str:
        try:
            cron = CronTab(user=True)
            for job in cron:
                if (job.comment ==
                        "codemop-cleaner"):
                    delta = (job.schedule()
                               .get_next(datetime))
                    return delta.strftime(
                        "%A %d %b at %H:%M")
            return "Not scheduled"
        except Exception:
            return "Unknown"

    def last_run(self) -> str:
        report_log = (APP_ROOT /
                      "cleaner_reports.jsonl")
        if not report_log.exists():
            return "Never"
        try:
            last_line = None
            with open(report_log, 'r') as f:
                for line in f:
                    if line.strip():
                        last_line = line.strip()
            if last_line:
                data = json.loads(last_line)
                return data.get(
                    "started_at", "Unknown")
        except Exception:
            pass
        return "Unknown"

    # ── Report ────────────────────────────────────────
    def _write_report(self, report: dict):
        report["completed_at"] = (
            datetime.now().isoformat())
        report_log = (APP_ROOT /
                      "cleaner_reports.jsonl")
        try:
            with open(report_log, 'a') as f:
                f.write(
                    json.dumps(
                        report,
                        default=str) + "\n")
        except Exception as e:
            log.warning(
                f"Could not write report: {e}")

    # ── Utilities ─────────────────────────────────────
    def _file_age(self, filepath: Path) -> int:
        mtime = datetime.fromtimestamp(
            filepath.stat().st_mtime)
        return (datetime.now() - mtime).days

    def _get_outcome(self,
                     filepath: Path) -> str:
        sidecar = self._sidecar_path(filepath)
        if not sidecar or not sidecar.exists():
            return "unknown"
        try:
            with open(sidecar, 'r') as f:
                data = json.load(f)
            return data.get("outcome", "unknown")
        except Exception:
            return "unknown"

    def _has_sidecar(self,
                     filepath: Path) -> bool:
        sidecar = self._sidecar_path(filepath)
        return (sidecar is not None and
                sidecar.exists())

    def _sidecar_path(self,
                      filepath: Path):
        candidate = (
            filepath.parent /
            f"{filepath.stem}_parsed.json")
        return (candidate
                if candidate != filepath
                else None)

    def _delete_file(self, filepath: Path):
        sidecar = self._sidecar_path(filepath)
        if sidecar and sidecar.exists():
            sidecar.unlink()
        filepath.unlink()
        with self.db._connect() as conn:
            conn.execute(
                "DELETE FROM sessions "
                "WHERE filepath = ?",
                (str(filepath),))


# ── CLI entry point ───────────────────────────────────
def main():
    cleaner = Cleaner()

    if "--run" in sys.argv:
        cleaner.run()
    elif "--preview" in sys.argv:
        report = cleaner.preview()
        print(json.dumps(report, indent=2))
    elif "--install-cron" in sys.argv:
        cleaner.install_cron()
    elif "--remove-cron" in sys.argv:
        cleaner.remove_cron()
    else:
        cleaner.run()


if __name__ == "__main__":
    main()

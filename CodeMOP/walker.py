# CodeMOP — Walker
# Walks up the directory tree collecting rtfm.md files.
# Like how git finds .git/ — start where you are,
# walk up, stop at configured root.

from pathlib import Path
import hashlib
import logging
import json
from datetime import datetime
from codemop import (
    APP_ROOT,
    PROJECTS_DIR,
    DB_PATH,
    load_config,
)

log = logging.getLogger("codemop.walker")

RTFM_FILENAME = "rtfm.md"
HOME = Path.home()


class Walker:
    """
    Walks up the directory tree from CWD
    collecting rtfm.md files. Returns ordered
    list — root first, most specific last.
    """

    def __init__(self):
        self.config = load_config()
        self._cache = None
        self.cache_path = DB_PATH.parent / "walker_cache.json"

    @property
    def cache(self):
        if self._cache is None:
            self._load_cache()
        return self._cache

    # ── Main entry point ──────────────────────────────
    def walk(self, cwd: Path = None) -> list:
        """
        Walk up from cwd collecting rtfm.md files.
        Returns ordered list root first,
        most specific last.
        """
        cwd = cwd or Path.cwd()
        log.info(f"Walking from: {cwd}")

        found = self._collect_rtfm_files(cwd)

        if not found:
            log.info("No rtfm.md files found in tree")
            return []

        log.info(f"Found {len(found)} rtfm.md files")
        for f in found:
            log.debug(f"  {f}")

        return found

    def walk_and_check_cache(self,
                              cwd: Path = None
                              ) -> dict:
        """
        Walk and check cache in one call.
        Returns cached context if unchanged,
        or dict with _files and _hash for
        assembler to rebuild.
        """
        cwd = cwd or Path.cwd()
        found = self.walk(cwd)

        if not found:
            return {}

        current_hash = self._hash_chain(found)
        cached = self.cache.get(str(cwd))

        if cached and cached.get(
                "hash") == current_hash:
            log.info(
                "rtfm chain unchanged "
                "— serving cache")
            return cached.get("context", {})

        log.info(
            "rtfm chain changed "
            "— needs rebuild")
        return {
            "_files": found,
            "_hash": current_hash
        }

    def save_to_cache(self,
                      cwd: Path,
                      context: dict,
                      chain_hash: str):
        """
        Save assembled context to cache.
        Called by assembler after building
        context so walker can serve it next time.
        """
        self.cache[str(cwd)] = {
            "hash": chain_hash,
            "context": context,
            "cached_at": datetime.now().isoformat()
        }
        self._save_cache()

    # ── Tree walking ──────────────────────────────────
    def _collect_rtfm_files(self,
                             cwd: Path) -> list:
        """
        Walk UP the tree from cwd.
        Respects root boundary and max_ascent
        from config. Checks both real path
        and mirror path in .agents/app/projects/.
        Returns list reversed so root is first.
        """
        found = []
        current = cwd
        ascent = 0

        walker_config = self.config.get(
            "walker", {})
        root = Path(
            walker_config.get(
                "root",
                str(HOME / "Projects"))
        ).expanduser()
        max_ascent = walker_config.get(
            "max_ascent", -1)
        exclude = walker_config.get("exclude", [])

        while True:
            # Never go above configured root
            if not self._is_within_root(
                    current, root):
                log.debug(
                    f"Reached root boundary: {root}")
                break

            # Respect max ascent
            if (max_ascent != -1 and
                    ascent > max_ascent):
                log.debug(
                    f"Reached max ascent: "
                    f"{max_ascent}")
                break

            # Skip excluded directories
            if current.name in exclude:
                log.debug(
                    f"Skipping excluded: {current}")
                break

            # Check real path
            rtfm = current / RTFM_FILENAME
            if rtfm.exists():
                found.append(rtfm)
                log.debug(f"Found: {rtfm}")

            # Check mirror path
            mirror = self._mirror_path(current)
            if (mirror and mirror.exists()
                    and mirror != rtfm):
                found.append(mirror)
                log.debug(f"Found mirror: {mirror}")

            # Stop at home
            if current == HOME:
                break

            # Stop at filesystem root
            if current == current.parent:
                break

            current = current.parent
            ascent += 1

        found.reverse()
        return found

    def _mirror_path(self,
                     real_path: Path):
        """
        Convert real path to mirror equivalent
        in ~/.agents/app/projects/
        """
        try:
            # Try relative to HOME first
            relative = real_path.resolve().relative_to(HOME.resolve())
            return PROJECTS_DIR / relative / RTFM_FILENAME
        except ValueError:
            try:
                # Fallback: Try relative to root boundary
                walker_config = self.config.get("walker", {})
                root = Path(walker_config.get("root", str(HOME / "Projects"))).expanduser().resolve()
                relative = real_path.resolve().relative_to(root)
                return PROJECTS_DIR / "root_external" / relative / RTFM_FILENAME
            except ValueError:
                return None

    def _is_within_root(self,
                        path: Path,
                        root: Path) -> bool:
        """
        Check if path is within root boundary.
        Checks both raw and resolved paths for symlink compatibility.
        """
        try:
            path.relative_to(root)
            return True
        except ValueError:
            try:
                path.resolve().relative_to(root.resolve())
                return True
            except ValueError:
                return False

    # ── Hashing ───────────────────────────────────────
    def _hash_chain(self, files: list) -> str:
        """
        Hash contents of all rtfm.md files.
        Any change invalidates the cache.
        """
        hasher = hashlib.md5()
        for filepath in files:
            try:
                with open(filepath, 'rb') as f:
                    hasher.update(f.read())
                hasher.update(
                    str(filepath).encode())
            except Exception as e:
                log.warning(
                    f"Could not hash "
                    f"{filepath}: {e}")
        return hasher.hexdigest()

    # ── Cache ─────────────────────────────────────────
    def _load_cache(self):
        try:
            with open(self.cache_path, 'r') as f:
                self._cache = json.load(f)
        except FileNotFoundError:
            log.debug(
                "No walker cache — starting fresh")
            self._cache = {}
        except Exception as e:
            log.warning(
                f"Could not load cache: {e}")
            self._cache = {}

    def _save_cache(self):
        try:
            with open(self.cache_path, 'w') as f:
                json.dump(
                    self.cache, f,
                    indent=2,
                    default=str)
        except Exception as e:
            log.warning(
                f"Could not save cache: {e}")

    def invalidate_cache(self,
                         cwd: Path = None):
        """
        Invalidate cache for specific path
        or everything. Called by CodeMaid
        after editing an rtfm.md.
        """
        if cwd:
            self.cache.pop(str(cwd), None)
            log.info(
                f"Cache invalidated: {cwd}")
        else:
            self.cache.clear()
            log.info("Full cache invalidated")
        self._save_cache()

    # ── Utilities for CodeMaid ────────────────────────
    def list_projects(self) -> list:
        """
        List all known projects by scanning
        mirror tree. Used by CodeMaid.
        """
        projects = []
        if not PROJECTS_DIR.exists():
            return projects

        for rtfm in PROJECTS_DIR.rglob(
                RTFM_FILENAME):
            projects.append({
                "mirror_path": rtfm,
                "name": rtfm.parent.name,
                "depth": (
                    len(rtfm.parts) -
                    len(PROJECTS_DIR.parts))
            })

        return sorted(
            projects,
            key=lambda x: x["depth"])

    def find_rtfm(self,
                  project_name: str):
        """
        Find a specific project's rtfm.md
        by name. Used by CodeMaid.
        """
        for rtfm in PROJECTS_DIR.rglob(
                RTFM_FILENAME):
            if rtfm.parent.name == project_name:
                return rtfm
        return None

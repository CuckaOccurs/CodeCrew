# CodeMOP — Utilities
import os
from pathlib import Path

class ChunkedReader:
    """
    Reads files in chunks to stay within context limits (e.g., 50KB).
    """
    def __init__(self, chunk_size: int = 50 * 1024):
        self.chunk_size = chunk_size

    def read_file(self, file_path: Path, chunk_index: int = 0):
        """
        Read a specific chunk of a file.
        """
        if not file_path.exists():
            return None
        
        file_size = file_path.stat().st_size
        start = chunk_index * self.chunk_size
        
        if start >= file_size:
            return ""

        with open(file_path, 'r', errors='replace') as f:
            f.seek(start)
            return f.read(self.chunk_size)

    def get_info(self, file_path: Path):
        """
        Get metadata about chunks for a file.
        """
        if not file_path.exists():
            return None
        file_size = file_path.stat().st_size
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        return {
            "size": file_size,
            "total_chunks": total_chunks,
            "chunk_size": self.chunk_size
        }

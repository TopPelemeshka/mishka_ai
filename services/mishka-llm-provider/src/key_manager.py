import os
import time
from itertools import cycle
from typing import List

class KeyManager:
    def __init__(self):
        self.keys = []
        self._load_keys()
        self._iterator = cycle(self.keys) if self.keys else None

    def _load_keys(self):
        # Try new plural env var first
        keys_str = os.getenv("GOOGLE_API_KEYS") or os.getenv("GEMINI_API_KEYS")
        if keys_str:
            self.keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        
        # Fallback to singular
        if not self.keys:
            single = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if single:
                self.keys = [single]
        
        print(f"Loaded {len(self.keys)} API Keys.")

    def get_next_key(self) -> str:
        """Returns the next key in rotation strategy (Round Robin)."""
        if not self.keys:
            return None
        return next(self._iterator)

    def get_all_keys(self) -> List[str]:
        return self.keys

key_manager = KeyManager()

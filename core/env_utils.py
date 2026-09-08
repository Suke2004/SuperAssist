import os
import re
from typing import Dict, Optional

class EnvManager:
    """Manages reading and writing to the .env file while preserving structure and comments."""
    
    def __init__(self, file_path: str = ".env"):
        self.file_path = file_path

    def update_key(self, key: str, value: str) -> bool:
        """
        Updates a specific key in the .env file. 
        Creates the file if it doesn't exist.
        """
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w") as f:
                f.write(f"{key}=\"{value}\"\n")
            return True

        with open(self.file_path, "r") as f:
            lines = f.readlines()

        key_pattern = re.compile(f"^{re.escape(key)}\\s*=")
        found = False
        new_lines = []

        for line in lines:
            if key_pattern.match(line.strip()):
                new_lines.append(f"{key}=\"{value}\"\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            # If line doesn't end with newline, add one
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"{key}=\"{value}\"\n")

        with open(self.file_path, "w") as f:
            f.writelines(new_lines)
            
        return True

    def get_value(self, key: str) -> Optional[str]:
        """Reads a specific value from the .env file manually (to avoid caching issues)."""
        if not os.path.exists(self.file_path):
            return None
            
        with open(self.file_path, "r") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    # Basic quote stripping
                    parts = line.strip().split("=", 1)
                    if len(parts) > 1:
                        val = parts[1].strip()
                        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                            return val[1:-1]
                        return val
        return None

# Global instance
env_manager = EnvManager()

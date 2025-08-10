#!/usr/bin/env python3
"""Debug configuration loading"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Force clear all modules
modules_to_clear = [key for key in sys.modules.keys() if key.startswith('app.')]
for module in modules_to_clear:
    del sys.modules[module]

print("=== Direct Config File Test ===")

# Read the file directly
config_path = r"C:\Projects\enhanced-RAG-3\backend\app\core\config.py"
with open(config_path, 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        if 'ALLOWED_EXTENSIONS' in line:
            print(f"Line {i}: {line.strip()}")

print("\n=== Pydantic Settings Test ===")

# Import and test settings
from pydantic_settings import BaseSettings
from pydantic import Field

class TestSettings(BaseSettings):
    ALLOWED_EXTENSIONS: str = Field(default="pdf,docx,txt,xlsx,xls")
    
    @property
    def allowed_extensions_list(self):
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(',')]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

test_settings = TestSettings()
print(f"Test ALLOWED_EXTENSIONS: {test_settings.ALLOWED_EXTENSIONS}")
print(f"Test allowed_extensions_list: {test_settings.allowed_extensions_list}")

print("\n=== App Settings Test ===")

# Now try the actual app settings
from app.core.config import settings
print(f"App ALLOWED_EXTENSIONS: {settings.ALLOWED_EXTENSIONS}")
print(f"App allowed_extensions_list: {settings.allowed_extensions_list}")

# Check if there's any override happening
print(f"\nDirect field access: {settings.__fields__['ALLOWED_EXTENSIONS'].default}")
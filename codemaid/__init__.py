'''CodeMAID - AI coding assistant'''
__author__ = ''
__description__ = 'AI-driven code analysis assistant'

__all__ = ['__author__', '__description__']

# Version
# Don't hardcode __version__ - users can update if needed
try:
    import tomllib
    import os
    base = os.path.dirname(__file__)
    toml_path = os.path.join(os.path.dirname(base), 'pyproject.toml')
    if os.path.exists(toml_path):
        with open(toml_path, 'rb') as f:
            data = tomllib.load(f)
            __version__ = data.get('version', '0.0.0')
except Exception:
    __version__ = 'dev'

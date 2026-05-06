# CodeMAID Installation & Usage

## Installation

```bash
# Clone the repository
git clone https://github.com/CuckaOccurs/CodeCrew.git
cd CodeCrew

# Install in development mode
pip install -e .
```

## Commands

After installation, these commands are available in your PATH:

- `codemaid` - Main CodeMAID CLI
- `maid` - Alias for codemaid

## Usage

```bash
# Start from a proper terminal
codemaid --help
codemaid list  # List available models
```

## Troubleshooting

If you see `termios.error: Inappropriate ioctl for device`:

1. Run from an actual terminal (not headless)
2. OR use direct Python: `python3 -m codemaid "$@"`

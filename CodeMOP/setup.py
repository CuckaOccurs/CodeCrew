from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements = []
req_file = Path(__file__).parent / "requirements.txt"
if req_file.exists():
    with open(req_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                requirements.append(line)

# Read readme if exists
readme = ""
readme_file = Path(__file__).parent / "README.md"
if readme_file.exists():
    with open(readme_file) as f:
        readme = f.read()

setup(
    name="codemop",
    version="0.1.0",
    description=(
        "Manager Of Personas — "
        "AI infrastructure for "
        "persistent memory and "
        "cascading project context"
    ),
    long_description=readme,
    long_description_content_type="text/markdown",
    author="",
    author_email="",
    packages=find_packages(),
    package_dir={"": "."},
    install_requires=requirements,
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "codemop-setup=codemop.onboarder:main",
            "codemop-clean=codemop.cleaner:main",
            "codemop-index=codemop.indexer:main",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Scientific/Engineering :: "
        "Artificial Intelligence",
    ],
    package_data={
        "codemop": [
            "*.yaml",
            "*.md",
            "*.json",
        ]
    },
)

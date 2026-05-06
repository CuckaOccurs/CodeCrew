#!/usr/bin/env python3
import os
from pathlib import Path

# Base template for new RTFM hooks
TEMPLATE = """---
project: {name}
description: "RTFM hook for {name}."
---

# {name} RTFM

This project is part of the MAID/MOP ecosystem. 
Refer to the master RTFM in AgentStack for core operational mandates.

## Project Specifics
- Add project-specific technical debt, constraints, or unique identity here.
"""

def audit_projects(projects_dir):
    projects_root = Path(projects_dir)
    if not projects_root.exists():
        print(f"Error: Projects directory {projects_dir} not found.")
        return

    print(f"Auditing projects in: {projects_root}")
    
    for project_dir in projects_root.iterdir():
        if project_dir.is_dir() and not project_dir.name.startswith('.'):
            rtfm_path = project_dir / "rtfm.md"
            if not rtfm_path.exists():
                print(f"[-] Missing RTFM in: {project_dir.name}")
                choice = input(f"    Create rtfm.md for {project_dir.name}? (y/n): ")
                if choice.lower() == 'y':
                    with open(rtfm_path, 'w') as f:
                        f.write(TEMPLATE.format(name=project_dir.name))
                    print(f"    [+] Created: {rtfm_path}")
            else:
                print(f"[+] Found: {project_dir.name}/rtfm.md")

if __name__ == "__main__":
    audit_projects("/home/rumor/Projects")

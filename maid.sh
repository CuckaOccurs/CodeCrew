#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 -m codemaid.cli.main "$@"

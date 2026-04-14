# Project 1 - PDF KDE Extraction and Comparison

## Author
- Robert Henning - rch0061@auburn.edu

## LLM used for Task-1
- Google Gemma 3 1B (`google/gemma-3-1b-it`)

## What is included
- `run.py`: Main CLI entry point for extraction, comparison, and Kubescape execution.
- `requirements.txt`: Python package dependencies used for Tasks 1, 2, and 3.
- `.github/workflows/tests.yml`: GitHub Actions workflow that runs unit tests on push and pull requests.
- `run.sh`: BASH script for running the project without having to create an executable.

## Running the Project

1. Create a virtual environment
   python -m venv venv
   source venv/bin/activate

2. Run Shell Script
   ./run.sh data/cis-r1.pdf data/cis-r2.pdf


## GitHub Actions
- The workflow in `.github/workflows/tests.yml` automatically installs dependencies and runs `python -m unittest discover -s tests` on every push and pull request.

## Notes
- `project-yamls.zip` is required for Kubescape execution when that step is enabled.

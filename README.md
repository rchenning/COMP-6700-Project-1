# Project 1 - PDF KDE Extraction and Comparison

## Author
- Robert Henning - rch0061@auburn.edu

## LLM used for Task-1
- Google Gemma 3 1B (`google/gemma-3-1b-it`)

## What is included
- `run.py`: Main CLI entry point for extraction, comparison, and Kubescape execution.
- `requirements.txt`: Python package dependencies used for Tasks 1, 2, and 3.
- `.github/workflows/tests.yml`: GitHub Actions workflow that runs unit tests on push and pull requests.
- `dist/project1.exe`: PyInstaller-built executable binary.

## Running the project locally
1. Create a virtual environment:
   "python -m venv venv"
   ".\venv\Scripts\activate"

2. Install dependencies:
   "python -m pip install --upgrade pip"
   "python -m pip install -r requirements.txt"

3. Run the default pair processing using built-in sample inputs:
   "python run.py"
   

## Running with custom PDF input pairs
Provide nine pairs of PDF paths:
```powershell
python run.py --pairs data\cis-r1.pdf data\cis-r1.pdf data\cis-r1.pdf data\cis-r2.pdf data\cis-r1.pdf data\cis-r3.pdf data\cis-r1.pdf data\cis-r4.pdf data\cis-r2.pdf data\cis-r2.pdf data\cis-r2.pdf data\cis-r3.pdf data\cis-r2.pdf data\cis-r4.pdf data\cis-r3.pdf data\cis-r3.pdf data\cis-r3.pdf data\cis-r4.pdf
```

Or use a pairs file with one pair per line, separated by `|`, `,`, or whitespace:
"cis-r1.pdf | cis-r1.pdf"
"cis-r1.pdf , cis-r2.pdf"


## GitHub Actions
- The workflow in `.github/workflows/tests.yml` automatically installs dependencies and runs `python -m unittest discover -s tests` on every push and pull request.

## Binary
- The project binary is built using PyInstaller from `run.py`.
  ".\dist\project1.exe --pairs ..."

## Notes
- `project-yamls.zip` is required for Kubescape execution when that step is enabled.

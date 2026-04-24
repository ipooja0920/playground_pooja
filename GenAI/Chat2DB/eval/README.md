# EVALUATION FRAMEWORK

## Usage

### 1. Run the evaluations
- Need to be under Dev environment. If Docker not yet on, under `Chat2DB/` folder run `make dev`
- Once docker is on, go to the jupyter notebook: `eval.ipynb` and run the steps (recommend Visual Studio Code with Jupyter extension)
- Dev mode requires Python 3.11+ from the system running the Docker
- Keep `eval_set.csv` in the `data/` folder

## Folder Contents

### `evaltools.py`
- Set of functions used to call LLMs, manipulate SQLs and responses, calculate metrics
- Functions in this file are called by eval.ipynb

### `sqltr.py`
- A class that communicates with the Domain DB to execute expected or generated SQL
- Converts response to a DataFrame for comparison
- Called by eval.ipynb

### `data/`
- Folder containing the test dataset
- Dataset name: `eval_set.csv`

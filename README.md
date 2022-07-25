# SFILES 2.0 
This repository is published together with the paper: *SFILES 2.0: An extended text-based flowsheet representation*<br>
The repository contains functionality for the conversion between PFD-graphs/P&ID-graphs and SFILES 2.0 strings. In the paper, we describe the structure of the graphs, notation rules of the SFILES 2.0, and the conversion algorithm.  

## How to use this repository? 
To use the SFILES 2.0 code, first clone the repository: 
```sh
git clone git@github.com:process-intelligence-research/SFILES2.git
```
After creating and activating a new virtual environment, you can use the requirements.txt file to install all required packages:
```sh
pip install -r requirements.txt
```
The repository contains a notebook for demonstration. To use this notebook, you need to install the ipykernel: 
```sh
source activate envname # activate environment
python -m ipykernel install --user --name envname --display-name "Python (envname)"
```
## Demonstration of functionality
You can either have a look at the `demonstration.ipynb` which demonstrates SFILES 2.0 strings for a variety of PFDs and P&IDs or run the python file `run_demonstration.py`.

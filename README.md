# SFILES 2.0 
This repository is published together with the paper: *SFILES 2.0: An extended text-based flowsheet representation*<br>
The repository contains functionality for the conversion between PFD-graphs/P&ID-graphs and SFILES 2.0 strings. In the paper, we describe the structure of the graphs, notation rules of the SFILES 2.0, and the conversion algorithm.  

## Installation

To install the SFILES 2.0 package via `pip`, simply run:

```sh
pip install SFILES2
```

## Exploring the Repository and Demonstrations

For users who want to explore the functionality with the provided demonstrations and example files:
```sh
git clone https://github.com/process-intelligence-research/SFILES2.git
```
After creating and activating a new virtual environment (python 3.9), you can use the requirements.txt file to install all required packages:
```sh
pip install -r requirements.txt
```
### Demonstration of functionality
You can either have a look at the `demonstration.ipynb` which demonstrates SFILES 2.0 strings for a variety of PFDs and P&IDs or run the python file `run_demonstration.py`.

## References

If you use this package or find it helpful in your research, please consider citing:

```text
@article{hirtreiter2024toward,
  title={Toward automatic generation of control structures for process flow diagrams with large language models},
  author={Hirtreiter, Edwin and Schulze Balhorn, Lukas and Schweidtmann, Artur M},
  journal={AIChE Journal},
  volume={70},
  number={1},
  pages={e18259},
  year={2024},
  publisher={Wiley Online Library}
}
```

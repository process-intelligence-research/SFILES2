"""
Reconstruction of SFILES data for testing if MultiDiGraph implementation is working.

Datasets:

1.  Hirtreiter, E., Schulze Balhorn, L., & Schweidtmann, A. M. (2023). 
    Supplementary data for: "Towards automatic generation of control structures 
    for Process Flow Diagrams (PFDs) with Artificial Intelligence" [Data set]. 
    Zenodo. https://doi.org/10.5281/zenodo.7658798

2.  Rocha Azevedo, Antonio; Nabil, Tahar; Loubière, Valentin; Privat, Romain; 
    Neveux, Thibaut; Commenge, Jean-Marc (2025), “Supplementary data for: 
    "Comparing generative process synthesis approaches with superstructure 
    optimization for the conception of supercritical CO2 Brayton cycles"”,
    Mendeley Data, V1, doi: 10.17632/9zvhjctwh3.1

"""

from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

def check_flowsheets(args):
    i, process = args
    from copy import deepcopy
    from Flowsheet_Class.flowsheet import Flowsheet
    from Flowsheet_Class.utils_isomorphism import check_isomorphism

    correct_sfiles = True
    correct_graph = True

    try:
        # --- PFD ---
        f = Flowsheet(sfiles_in=process)
        f1 = deepcopy(f)
        g1 = deepcopy(f.state)

        f.create_from_nx(g1)
        f.convert_to_sfiles()
        sfiles = f.sfiles

        if sfiles != process:
            correct_sfiles = False

        f.create_from_sfiles(sfiles_in=sfiles, overwrite_nx=True)
        f2 = deepcopy(f)

        if not check_isomorphism(f1, f2):
            correct_graph = False

    except Exception as e:
        return (i, e)

    return (i, correct_sfiles, correct_graph)


DEBUG = None # 10

if __name__ == "__main__":
    import os, sys
    from pathlib import Path
    import json
    from copy import deepcopy

    import networkx as nx

    from Flowsheet_Class.flowsheet import Flowsheet
    from Flowsheet_Class.utils_isomorphism import check_isomorphism
    current_file = Path(__file__).resolve().parent
    # Dataset 1:
    dataset_1_path = current_file/"data"/"Training Data Public Upload"
    json_files = [
        f for f in os.listdir(dataset_1_path)
        if f.endswith(".json")
    ]
        
    for file_name in json_files:
        with open(dataset_1_path/file_name, "r") as f:
            try:
                flowsheet_list = json.load(f)
                if "data" in flowsheet_list:
                    flowsheet_list = flowsheet_list["data"]
            except json.JSONDecodeError:
                _ = f.seek(0) # Just making sure
                text = f.read()
                comma_separated_text = ','.join(text.split("\n"))[:-1] # [:-1] --> Removing ending comma
                flowsheet_list = json.loads(f"[{comma_separated_text}]")

        print(f"Converting {file_name}...")
        for _type in ["PFD", "PID"]:
            print(f"\tChecking {_type}...")
            num_workers = multiprocessing.cpu_count()
            results = [None] * len(flowsheet_list)
            
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                futures = [
                    executor.submit(check_flowsheets, (i, process[_type]))
                    for i, process in enumerate(flowsheet_list)
                ]

                for future in as_completed(futures):
                    res = future.result()

                    if len(res) == 2:  # error case
                        i, e = res
                        print("Error at process nb:", i)
                        correct_sfiles = False
                        correct_graph = False
                    else:
                        i, correct_sfiles, correct_graph = res
                    
                    results[i] = (correct_sfiles, correct_graph)
            
            correct_sfiles = [r[0] for r in results]
            correct_graph = [r[1] for r in results]
            if DEBUG is not None: break
            print(f"\t\tPercentage of correct SFILES conversion: {100*sum(correct_sfiles)/len(flowsheet_list)}.")
            print(f"\t\tPercentage of correct GRAPH conversion: {100*sum(correct_graph)/len(flowsheet_list)}.")
    # Dataset 2:
    dataset_2_path = current_file/"data"/"RochaAzevedo_et_al"
    csv_files = [
        dataset_2_path/"Machine Learning"/f for f in os.listdir(dataset_2_path/"Machine Learning")
        if f.endswith(".csv")
    ]
    csv_files.extend([
        dataset_2_path/"Evolutionary Programming"/f for f in os.listdir(dataset_2_path/"Evolutionary Programming")
        if f.endswith(".csv")
    ])
    csv_files.extend([
        dataset_2_path/f for f in os.listdir(dataset_2_path)
        if f.endswith(".csv")
    ])
    
    for file_path in csv_files:
        
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Parse columns:        
        columns = lines[0].split(",")
        # Get SFILES columns, except for the one including process parameters:
        sfiles_cols = [col for col in columns if "SFILES" in col.upper() and "parameters" not in col]

        print(f"Converting {file_path}...")

        for col in sfiles_cols:
            col_idx = columns.index(col)
            flowsheet_list = [line.split(",")[col_idx] for line in lines]
            if flowsheet_list[0].endswith("\n"):
                flowsheet_list = [flowsheet[:-1] if flowsheet.endswith("\n") else flowsheet for flowsheet in flowsheet_list]

            print(f"\tColumn: {col}: {len(flowsheet_list)} entries...")
            num_workers = multiprocessing.cpu_count()
            results = [None] * len(flowsheet_list)
            
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                futures = [
                    executor.submit(check_flowsheets, (i, process))
                    for i, process in enumerate(flowsheet_list)
                ]

                for future in as_completed(futures):
                    res = future.result()

                    if len(res) == 2:  # error case
                        i, e = res
                        print("Error at process nb:", i, "process:", flowsheet_list[i])
                        correct_sfiles = False
                        correct_graph = False
                    else:
                        i, correct_sfiles, correct_graph = res
                    
                    results[i] = (correct_sfiles, correct_graph)

            correct_sfiles = [r[0] for r in results]
            correct_graph = [r[1] for r in results]
            if DEBUG is not None: break
            print(f"\t\tPercentage of correct SFILES conversion: {100*sum(correct_sfiles)/len(flowsheet_list)}.")
            print(f"\t\tPercentage of correct GRAPH conversion: {100*sum(correct_graph)/len(flowsheet_list)}.")

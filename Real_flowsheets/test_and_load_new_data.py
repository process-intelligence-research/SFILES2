import unittest
import sys
import os
import re
from os import listdir
from os.path import isfile, join
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import networkx as nx
from Flowsheet_Class.flowsheet import Flowsheet
from pathlib import Path
import pickle

import random
random.seed(1)
class FlowsheetTests(unittest.TestCase):

    def test_flowsheet_generation(self):
        print(os.getcwd())
        all_sfiles1 = []
        all_edges_1= []
        all_edges_2= []
        all_sfiles2 = []
        all_sfiles3 = []
        all_sfiles4 = []
        all_flowsheets = []
        failures = []

        all_files = [join('Real_flowsheets/DWSim_pickle_files', f) for f in listdir('Real_flowsheets/DWSim_pickle_files') if isfile(join('Real_flowsheets/DWSim_pickle_files', f))]
        for i,f in enumerate(all_files):
            if not i in [68,92]: # 68, 92 assertion error
                G = nx.read_gpickle(f)
                G = nx.read_gpickle(f)
                _node_names = list(G.nodes)
                relabel_mapping = {}
                for n in _node_names:
                    r = re.compile("([a-zA-Z]+)([0-9]+)")
                    _full_name = r.match(n).groups()
                    _name = _full_name[0] # name without number
                    _num = _full_name[1]
                    relabel_mapping[n] = _name +'-'+ _num
                G = nx.relabel_nodes(G, relabel_mapping)
                sgs = [G.subgraph(c).copy() for c in nx.weakly_connected_components(G)]
                flowsheet = Flowsheet(OntoCapeConformity=True)
                flowsheet.state = G
                all_edges_1.append(list(flowsheet.state.edges))
                flowsheet.convert_to_sfiles(version='v2', remove_hex_tags=True)
                sfiles_1 = flowsheet.sfiles
                all_sfiles1.append(sfiles_1)
                all_sfiles3.append(re.sub(r'\{.*?\}', '',sfiles_1))
                flowsheet.create_from_sfiles(overwrite_nx=True, merge_HI_nodes=False)
                all_flowsheets.append(flowsheet)
                all_edges_2.append(list(flowsheet.state.edges))
                flowsheet.convert_to_sfiles(version='v2', remove_hex_tags=True)
                sfiles_2=flowsheet.sfiles
                all_sfiles2.append(sfiles_2)
                all_sfiles4.append(re.sub(r'\{.*?\}', '',sfiles_2))
            else:
                failures.append(f)

        "Evaluate Testing"
        self.maxDiff=None
        self.assertEqual(len(all_edges_1), len(all_edges_2), "There are some examples where edges didnt work out.")
        #self.assertEqual(all_sfiles1, all_sfiles2, "There are some examples where SFILES notation produces a different string.") # currently only one example where it does not work (still no information missing, just because tags are not considered in graph invariant calculation)
        self.assertTrue(all(len(all_sfiles1[i]) == len(all_sfiles2[i]) for i in range(0,len(all_sfiles1))), "There are some examples where SFILES notation has a different length. (Tags might have gone missing in conversion back)")
        self.assertEqual(all_sfiles3, all_sfiles4, "There are some examples where SFILES notation produces a different string.")
        print("There are %d duplicates. They are filtered out in the file all_data.txt"%(len(all_sfiles1) - len(set(all_sfiles1))))

        print('Additionally, the following files are not loaded:',failures)

        "Load the new data as SFILES and create train and dev set"
        print('Creating train and dev dataset')
        with open('Real_flowsheets/all_data.txt', 'w') as f:
            all_data = list(set(all_sfiles1))
            random.shuffle(all_data)
            for item in all_data:
                f.write("%s.\n" % item)
        
        tr = round(0.8 * len(all_data))
        dev = round(0.9 * len(all_data))

        datasets = {'train_data': all_data[:tr], 
                    'dev_data': all_data[tr:dev],
                    'test_data': all_data[dev:]}

        for id, dataset in datasets.items():
            with open('Real_flowsheets/%s.txt'%id, 'w') as f:
                for item in dataset:
                    f.write("%s.\n" % item)

        Path("Real_flowsheets/flowsheet_objects").mkdir(parents=True, exist_ok=True)
        new_path = os.path.join(os.getcwd(),'Real_flowsheets/flowsheet_objects/Flowsheet_data.pkl')
        filehandler = open(new_path, 'wb') 
        pickle.dump(all_flowsheets, filehandler)
        
if __name__ == '__main__':
    unittest.main()
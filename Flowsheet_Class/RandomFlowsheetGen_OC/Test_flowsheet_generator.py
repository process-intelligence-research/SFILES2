import unittest
import sys
import os
import re
# Workaround. relative imports can be used when the repository is a package 
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from Flowsheet_Class.flowsheet import Flowsheet
import random
random.seed(1)
class FlowsheetTests(unittest.TestCase):

    def test_flowsheet_generation(self):
        """ 
        This test generates one thousand graphs, writes the sfiles representation,
        reconstructs the graph and writes sfiles2 representation.
        The two strings have to be of equal length for all examples and the strings without tags have to be equal -> Test passed.
        (Renumbering while reconstructing the graph sometimes changes the ordering of numbers of equally ranked nodes:
        e.g. the node that is first generated gets lower number, e.g. hex-1 and hex-2/1. But if hex-2 is heat integrated (hex-2/1) with another hex,
        that is noted first in SFILES -> renumbering will change it to hex-1/1 and hence it is noted before hex-2  -> changes where the {1} HI tag 
        appears in SFILES. Nevertheless, it does not change the SFILES without tags. -> all_sfiles3 == all_sfiles4.
        )
        Besides the user will see the number of duplicates in the the generated data,
        """
        # Dict of multiple random flowsheets
        flowsheets = {i: Flowsheet(OntoCapeConformity=True) for i in range(1, 1000)}
        all_sfiles1 = []
        all_sfiles2 = []
        all_sfiles3 = []
        all_sfiles4 = []
        for key, ob in flowsheets.items():
            #print(key)
            ob.create_random_flowsheet()
            #ob.convert_to_sfiles(version='v2')
            sfiles_1=ob.sfiles
            all_sfiles1.append(sfiles_1)
            all_sfiles3.append(re.sub(r'\{.*?\}', '',sfiles_1))
            ob.create_from_sfiles(override_nx=True)
            ob.convert_to_sfiles(version='v2')
            sfiles_2=ob.sfiles
            all_sfiles2.append(sfiles_2)
            all_sfiles4.append(re.sub(r'\{.*?\}', '',sfiles_2))
        self.maxDiff=None
        self.assertEqual(len(all_sfiles1), len(all_sfiles2), "There are some examples where SFILES notation has a different length.")
        self.assertEqual(all_sfiles3, all_sfiles4, "There are some examples where SFILES notation produces a different string.")
        print("There are %d duplicates"%(len(all_sfiles1) - len(set(all_sfiles1))))

        with open(r'C:\Users\hirtr\OneDrive - TUM\Dokumente\PI Research\SFILES2_0\new.txt', 'w') as fp:
            for item in all_sfiles1:
                # write each item on a new line
                fp.write("%s\n" % item)
            print('Done')

        old = []
        with open(r'C:\Users\hirtr\OneDrive - TUM\Dokumente\PI Research\SFILES2_0\old.txt', 'r') as fp:
            for line in fp:
                # remove linebreak from a current name
                # linebreak is the last character of each line
                x = line[:-1]

                # add current item to the list
                old.append(x)

        #self.assertEqual(all_sfiles1, old, "Error!!")

if __name__ == '__main__':
    unittest.main()
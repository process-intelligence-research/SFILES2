import unittest
import networkx as nx
from Flowsheet_Class.flowsheet import Flowsheet


class TestSFILESctrl(unittest.TestCase):

    def test_case_1a(self):
        # 1) Measuring point in/at unit operation
        test_case = '1a'
        edges = [('IO-1', 'tank-1'), ('tank-1', 'IO-2'), ('tank-1', 'C-1/TIR'), ('tank-1', 'C-2/LIR')]
        self.SFILESctrl(test_case, edges)

    def test_case_1b(self):
        test_case = '1b'
        edges = [('IO-1', 'tank-1'), ('C-1/LIR', 'v-1', {'tags': {'signal': ['not_next_unitop']}}),
                 ('tank-1', 'C-1/LIR'), ('v-1', 'IO-2'), ('tank-1', 'v-1')]
        self.SFILESctrl(test_case, edges)

    def test_case_2(self):
        # 2) Measuring point at material stream
        test_case = '2'
        edges = [('IO-1', 'C-1/FC'), ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2')]
        self.SFILESctrl(test_case, edges)

    def test_case_3(self):
        # 3) Cascade control
        test_case = '3'
        edges = [('IO-1', 'tank-1'), ('tank-1', 'C-1/LC'),
                 ('C-1/LC', 'C-2/FC', {'tags': {'signal': ['not_next_unitop']}}),
                 ('tank-1', 'C-2/FC'), ('C-2/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2')]
        self.SFILESctrl(test_case, edges)

    def test_case_A(self):
        # A)
        test_case = 'A'
        edges = [('IO-1', 'C-1/FC'), ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2')]
        self.SFILESctrl(test_case, edges)

    def test_case_B(self):
        # B)
        test_case = 'B'
        edges = [('IO-1', 'C-1/F'), ('C-1/F', 'C-2/FFC', {'tags': {'signal': ['not_next_unitop']}}),
                 ('C-2/FFC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2'), ('IO-3', 'C-3/F'),
                 ('C-3/F', 'C-2/FFC', {'tags': {'signal': ['next_unitop']}}),
                 ('C-3/F', 'IO-4')]
        self.SFILESctrl(test_case, edges)

    def test_case_C(self):
        # C)
        test_case = 'C'
        edges = [('IO-1', 'C-1/T'), ('C-1/T', 'IO-2'), ('IO-3', 'C-2/FQC'),
                 ('C-1/T', 'C-2/FQC', {'tags': {'signal': ['not_next_unitop']}}),
                 ('C-2/FQC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-4')]
        self.SFILESctrl(test_case, edges)

    def test_case_D(self):
        # D)
        test_case = 'D'
        edges = [('IO-1', 'hex-1/1'), ('hex-1/1', 'C-1/TC'), ('C-1/TC', 'IO-2'), ('IO-3', 'C-2/FC'),
                 ('C-2/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'hex-1/2'),
                 ('hex-1/2', 'IO-4'), ('C-1/TC', 'C-2/FC', {'tags': {'signal': ['not_next_unitop']}})]
        self.SFILESctrl(test_case, edges)

    def test_case_E(self):
        # E)
        test_case = 'E'
        edges = [('IO-1', 'splt-1'), ('splt-1', 'v-1'), ('v-1', 'IO-2'), ('splt-1', 'C-1/FC'),
                 ('C-1/FC', 'v-2', {'tags': {'signal': ['next_unitop']}}), ('v-2', 'IO-3')]
        self.SFILESctrl(test_case, edges)

    def test_case_F(self):
        # F)
        test_case = 'F'
        edges = [('IO-1', 'tank-1'), ('tank-1', 'IO-2'), ('tank-1', 'C-1/FC'),
                 ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-3')]
        self.SFILESctrl(test_case, edges)

    def test_case_G(self):
        # G)
        test_case = 'G'
        edges = [('IO-1', 'tank-1'), ('tank-1', 'C-1/LC'), ('tank-1', 'splt-1'), ('splt-1', 'C-2/FC'),
                 ('C-2/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2'), ('splt-1', 'v-2'),
                 ('v-2', 'IO-3'), ('C-1/LC', 'v-2', {'tags': {'signal': ['not_next_unitop']}})]
        self.SFILESctrl(test_case, edges)

    def test_case_HX_4(self):
        # HX_4)
        test_case = 'HX_4'
        edges = [('IO-1', 'C-1/TC'), ('C-1/TC', 'hex-1/1'), ('hex-1/1', 'IO-2'), ('IO-3', 'C-2/FC'),
                 ('C-2/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'hex-1/2'), ('hex-1/2', 'IO-4'),
                 ('C-1/TC', 'C-2/FC', {'tags': {'signal': ['not_next_unitop']}})]
        self.SFILESctrl(test_case, edges)

    def test_case_Umpumpanalge(self):
        # Umpumpanlage
        test_case = 'Umpumpanlage'
        edges = [('IO-1', 'v-1'), ('v-1', 'tank-1'), ('tank-1', 'v-2'), ('v-2', 'pp-1'), ('pp-1', 'v-3'),
                 ('v-3', 'C-4/FRC'), ('C-4/FRC', 'splt-1'), ('splt-1', 'v-4'), ('v-4', 'v-5'), ('v-5', 'v-6'),
                 ('v-6', 'mix-1'), ('mix-1', 'v-7'), ('splt-1', 'v-8'), ('v-8', 'mix-1'), ('v-7', 'tank-2'),
                 ('tank-2', 'v-9'), ('v-9', 'IO-2'), ('tank-1', 'C-1/TIR'), ('tank-1', 'C-2/LIR'), ('pp-1', 'C-3/M'),
                 ('v-8', 'C-5/H'), ('tank-2', 'C-6/TIR'), ('tank-2', 'C-7/PICA'),
                 ('C-4/FRC', 'v-5', {'tags': {'signal': ['not_next_unitop']}})]
        self.SFILESctrl(test_case, edges)

    def test_case_Rectification(self):
        # Rectification)
        test_case = 'Rectification'
        edges = [('IO-1', 'C-1/FC'), ('C-1/FC', 'v-1'), ('v-1', 'hex-1/1'), ('hex-1/1', 'C-2/TC'), ('C-2/TC', 'dist-1'),
                 ('dist-1', 'C-3/PC'), ('dist-1', 'C-4/LC'), ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}),
                 ('C-2/TC', 'v-2', {'tags': {'signal': ['not_next_unitop']}}), ('IO-2', 'v-2'),
                 ('v-2', 'hex-1/2'), ('hex-1/2', 'IO-3'), ('dist-1', 'hex-2', {'tags': {'col': ['tout']}}),
                 ('hex-2', 'tank-1'), ('tank-1', 'C-5/LC'), ('tank-1', 'splt-1'), ('splt-1', 'v-3'), ('v-3', 'dist-1'),
                 ('C-5/LC', 'v-3', {'tags': {'signal': ['not_next_unitop']}}), ('splt-1', 'C-6/FC'),
                 ('C-6/FC', 'v-4', {'tags': {'signal': ['next_unitop']}}), ('v-4', 'IO-4'), ('tank-1', 'v-5'),
                 ('v-5', 'IO-5'), ('C-3/PC', 'v-5', {'tags': {'signal': ['not_next_unitop']}}),
                 ('dist-1', 'splt-2', {'tags': {'col': ['bout']}}), ('splt-2', 'v-6'), ('v-6', 'IO-6'),
                 ('C-4/LC', 'v-6', {'tags': {'signal': ['not_next_unitop']}}), ('splt-2', 'hex-3/1'),
                 ('hex-3/1', 'dist-1'), ('IO-7', 'C-7/FC'), ('C-7/FC', 'v-7', {'tags': {'signal': ['next_unitop']}}),
                 ('v-7', 'hex-3/2'), ('hex-3/2', 'IO-8')]
        self.SFILESctrl(test_case, edges)

    def test_case_H(self):
        # Test case H
        test_case = 'H'
        edges = [('IO-1', 'pp-1'), ('pp-1', 'C-1/FC'), ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}),
                 ('v-1', 'hex-1'), ('hex-1', 'mix-1'), ('mix-1', 'r-1'),
                 ('r-1', 'mix-2', {'tags': {'col': ['tout']}}), ('mix-2', 'mix-1'), ('IO-2', 'mix-2'),
                 ('r-1', 'C-2/TC', {'tags': {'col': ['bout']}}), ('C-2/TC', 'dist-1'),
                 ('dist-1', 'pp-2', {'tags': {'col': ['bout']}}), ('pp-2', 'hex-2'), ('hex-2', 'splt-1'),
                 ('splt-1', 'dist-1'), ('splt-1', 'C-3/FC'), ('C-3/FC', 'v-2', {'tags': {'signal': ['next_unitop']}}),
                 ('v-2', 'IO-3'), ('dist-1', 'C-4/LC'), ('C-4/LC', 'C-3/FC', {'tags': {'signal': ['not_next_unitop']}}),
                 ('C-2/TC', 'C-1/FC', {'tags': {'signal': ['not_next_unitop']}}),
                 ('dist-1', 'IO-4', {'tags': {'col': ['tout']}}), ('IO-5', 'r-1'), ('IO-6', 'tank-1'),
                 ('tank-1', 'pp-3'), ('pp-3', 'C-5/FC'), ('C-5/FC', 'v-3', {'tags': {'signal': ['next_unitop']}}),
                 ('v-3', 'hex-3'), ('hex-3', 'mix-1')]
        self.SFILESctrl(test_case, edges)

    def SFILESctrl(self, test_case, edges):
        graph = nx.DiGraph()
        graph.add_edges_from(edges)

        flowsheet = Flowsheet()
        flowsheet.state = graph
        flowsheet.convert_to_sfiles()
        sfilesctrl1 = flowsheet.sfiles
        flowsheet.create_from_sfiles(sfilesctrl1, overwrite_nx=True)
        flowsheet.convert_to_sfiles()
        sfilesctrl2 = flowsheet.sfiles

        sfiles = flowsheet.convert_sfilesctrl_to_sfiles()
        flowsheet.sfiles = sfiles
        flowsheet.create_from_sfiles(sfiles, overwrite_nx=True)
        flowsheet.convert_to_sfiles()
        sfiles2 = flowsheet.sfiles

        if sfilesctrl1 == sfilesctrl2 and sfiles == sfiles2:
            print(
                '-----------------------------------------------------------------------------------------------------')
            print('Test case ', test_case)
            print('Conversion back successful')
            print('SFILESctrl: ', sfilesctrl1)
            print('SFILES: ', sfiles)
        else:
            print(
                '-----------------------------------------------------------------------------------------------------')
            print('Test case ', test_case)
            print('Conversion back produced a different SFILES string. Input:', sfilesctrl1, 'Output:', sfilesctrl2)
            print('Conversion back produced a different SFILES string. Input:', sfiles, 'Output:', sfiles2)

        self.assertEqual(sfilesctrl1, sfilesctrl2, "Not correct!")
        self.assertEqual(sfiles, sfiles2, "Not correct!")


if __name__ == '__main__':
    unittest.main()

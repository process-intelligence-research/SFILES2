from Flowsheet_Class.flowsheet import Flowsheet
import networkx as nx

# 1) Measuring point in/at unit operation
graph_one = nx.DiGraph()
graph_one.add_nodes_from(['IO-1', 'IO-2', 'tank-1', 'C-1/TIR', 'C-2/LIR'])
graph_one.add_edges_from([('IO-1', 'tank-1'), ('tank-1', 'IO-2'),
                          ('tank-1', 'C-1/TIR'),
                          ('tank-1', 'C-2/LIR')])

flowsheet_one = Flowsheet()
flowsheet_one.state = graph_one
flowsheet_one.convert_to_sfiles()
sfiles1 = flowsheet_one.sfiles
flowsheet_one.create_from_sfiles(sfiles1, override_nx=True)
flowsheet_one.convert_to_sfiles()
sfiles2 = flowsheet_one.sfiles
if sfiles1 == sfiles2:
    print('Conversion back successful')
    print(sfiles1)
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles1, 'Output:', sfiles2)

graph_two = nx.DiGraph()
graph_two.add_nodes_from(['IO-1', 'IO-2', 'tank-1', 'C-1/LIR', 'v-1'])
graph_two.add_edges_from([('IO-1', 'tank-1'),
                          ('C-1/LIR', 'v-1', {'tags':{'he': [], 'col': [], 'signal2unitop':[True]}}),
                          ('tank-1', 'C-1'), ('v-1', 'IO-2'), ('tank-1', 'v-1')])

flowsheet_two = Flowsheet()
flowsheet_two.state = graph_two
flowsheet_two.convert_to_sfiles()
sfiles1 = flowsheet_two.sfiles
flowsheet_two.create_from_sfiles(sfiles1, override_nx=True, merge_HI_nodes=False)
flowsheet_two.convert_to_sfiles()
sfiles2 = flowsheet_two.sfiles
if sfiles1 == sfiles2:
    print('Conversion back successful')
    print(sfiles1)
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles1, 'Output:', sfiles2)

# 1) Measuring point at material stream
graph_three = nx.MultiDiGraph()
graph_three.add_nodes_from(['IO-1', 'IO-2', 'v-1', 'C-1/FC'])
graph_three.add_edges_from([('IO-1', 'C-1'), ('C-1/FC', 'v-1', {'tags': {'signal': ['L']}}),
                            ('C-1/FC', 'v-1', {'tags': {'he': [], 'col': [], 'signal2unitop':[True]}}),
                            ('v-1', 'IO-2')])

flowsheet_three = Flowsheet()
flowsheet_three.state = graph_three
flowsheet_three.convert_to_sfiles()
sfiles1 = flowsheet_three.sfiles
flowsheet_three.create_from_sfiles(sfiles1, override_nx=True)
flowsheet_three.convert_to_sfiles()
sfiles2 = flowsheet_three.sfiles
if sfiles1 == sfiles2:
    print('Conversion back successful')
    print(sfiles1)
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles1, 'Output:', sfiles2)
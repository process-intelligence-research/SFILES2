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
graph_two.add_edges_from([('IO-1', 'tank-1'), ('C-1/LIR', 'v-1', {'tags': {'signal': ['not_next_unitop']}}),
                          ('tank-1', 'C-1/LIR'), ('v-1', 'IO-2'), ('tank-1', 'v-1')])

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

# 2) Measuring point at material stream
graph_three = nx.DiGraph()
graph_three.add_nodes_from(['IO-1', 'IO-2', 'v-1', 'C-1/FC'])
graph_three.add_edges_from([('IO-1', 'C-1/FC'), ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}),
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

# 3) Cascade control
graph_four = nx.DiGraph()
graph_four.add_nodes_from(['IO-1', 'IO-2', 'v-1', 'C-1/LC', 'C-2/FC', 'tank-1'])
graph_four.add_edges_from([('IO-1', 'tank-1'), ('tank-1', 'C-1/LC'),
                            ('C-1/LC', 'C-2/FC', {'tags': {'signal': ['next_signal']}}), ('tank-1', 'C-2/FC'),
                            ('C-2/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2')])

flowsheet_four = Flowsheet()
flowsheet_four.state = graph_four
flowsheet_four.convert_to_sfiles()
sfiles1 = flowsheet_four.sfiles
flowsheet_four.create_from_sfiles(sfiles1, override_nx=True)
flowsheet_four.convert_to_sfiles()
sfiles2 = flowsheet_four.sfiles
if sfiles1 == sfiles2:
    print('Conversion back successful')
    print(sfiles1)
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles1, 'Output:', sfiles2)

# A)
graph = nx.DiGraph()
graph.add_edges_from([('IO-1', 'C-1/FC'), ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2')])

flowsheet = Flowsheet()
flowsheet.state = graph
flowsheet.convert_to_sfiles()
sfiles1 = flowsheet.sfiles
flowsheet.create_from_sfiles(sfiles1, override_nx=True)
flowsheet.convert_to_sfiles()
sfiles2 = flowsheet.sfiles
if sfiles1 == sfiles2:
    print('Conversion back successful')
    print('A: ', sfiles1)
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles1, 'Output:', sfiles2)

# B)
graph = nx.DiGraph()
graph.add_edges_from([('IO-1', 'C-1/F'), ('C-1/F', 'C-2/FFC', {'tags': {'signal': ['next_signal']}}),
                      ('C-2/FFC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2'), ('IO-3', 'C-3/F'),
                      ('C-3/F', 'C-2/FFC'), ('C-3/F', 'IO-4')])

flowsheet = Flowsheet()
flowsheet.state = graph
flowsheet.convert_to_sfiles()
sfiles1 = flowsheet.sfiles
flowsheet.create_from_sfiles(sfiles1, override_nx=True)
flowsheet.convert_to_sfiles()
sfiles2 = flowsheet.sfiles
if sfiles1 == sfiles2:
    print('Conversion back successful')
    print('B: ', sfiles1)
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles1, 'Output:', sfiles2)

# C)
graph = nx.DiGraph()
graph.add_edges_from([('IO-1', 'C-1/T'), ('C-1/T', 'IO-2'), ('IO-3', 'C-2/FQC'),
                      ('C-1/T', 'C-2/FQC', {'tags': {'signal': ['next_signal']}}),
                      ('C-2/FQC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-4')])

flowsheet = Flowsheet()
flowsheet.state = graph
flowsheet.convert_to_sfiles()
sfiles1 = flowsheet.sfiles
flowsheet.create_from_sfiles(sfiles1, override_nx=True)
flowsheet.convert_to_sfiles()
sfiles2 = flowsheet.sfiles
if sfiles1 == sfiles2:
    print('Conversion back successful')
    print('C: ', sfiles1)
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles1, 'Output:', sfiles2)

# D)
graph = nx.DiGraph()
graph.add_edges_from([('IO-1', 'hex-1/1'), ('hex-1/1', 'C-1/TC'), ('C-1/TC', 'IO-2'), ('IO-3', 'C-2/FC'),
                      ('C-2/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'hex-1/2'),
                      ('hex-1/2', 'IO-4'), ('C-1/TC', 'C-2/FC', {'tags': {'signal': ['next_signal']}})])

flowsheet = Flowsheet()
flowsheet.state = graph
flowsheet.convert_to_sfiles()
sfiles1 = flowsheet.sfiles
flowsheet.create_from_sfiles(sfiles1, override_nx=True)
flowsheet.convert_to_sfiles()
sfiles2 = flowsheet.sfiles
if sfiles1 == sfiles2:
    print('Conversion back successful')
    print('D: ', sfiles1)
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles1, 'Output:', sfiles2)
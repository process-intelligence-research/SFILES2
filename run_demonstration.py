import sys
import os
from Flowsheet_Class.flowsheet import Flowsheet
import networkx as nx

# Methanol process
H=nx.DiGraph()
H.add_nodes_from(['IO-1', 'IO-2','IO-3', 'splt-1', 'pp-1', 'mix-1', 'r-1', 'IO-4', 'IO-5','IO-6'])
H.add_edges_from([('IO-1','pp-1'), ('pp-1','mix-1'), ('mix-1','r-1'),('r-1','IO-4'),('IO-2','splt-1'),('splt-1','pp-1'),('splt-1','mix-1'),('IO-3','IO-5'),('splt-1','IO-6')])
new = Flowsheet()
new.state = H
new.convert_to_sfiles()
s = new.sfiles
new.create_from_sfiles(s, override_nx=True)
new.convert_to_sfiles()
s2=new.sfiles
if s == s2:
    print('Conversion back successful')
else:
    print('Conversion back produced a different SFILES string. Input:', s, 'Output:', s2)

# Methanol process
H=nx.DiGraph()
H.add_nodes_from(['pp-1', 'hex-1','pp-2', 'hex-2', 'pp-3', 'hex-3','pp-4', 'hex-4', 'IO-1'])
H.add_edges_from([('pp-1','hex-1'), ('hex-1','pp-2'), ('pp-2','hex-2'),('hex-2','pp-1'), ('pp-1','pp-2'),
                  ('pp-3','hex-3'), ('hex-3','pp-4'), ('pp-4','hex-4'),('hex-4','pp-3'), ('pp-3','IO-1')
                  ])
new = Flowsheet()
new.state = H
new.convert_to_sfiles()
s = new.sfiles
new.create_from_sfiles(s, override_nx=True)
new.convert_to_sfiles()
s2=new.sfiles
if s == s2:
    print('Conversion back successful')
else:
    print('Conversion back produced a different SFILES string. Input:', s, 'Output:', s2)

# Try to create a new flowsheet from SFILES string
flowsheet_2=Flowsheet()
# TODO: Recycles are not considered as branches?
sfiles_in="(raw)(pp)<1<&|(raw)&|(flash){tout}1{bout}(prod)n|(raw)(prod)" # has to be valid according to SFILES rules
flowsheet_2.create_from_sfiles(sfiles_in)
flowsheet_2.visualize_flowsheet(table=False, pfd_path='plots/flowsheet3', plot_with_stream_labels=False)

# Check if conversion back works
flowsheet_2.sfiles=""
flowsheet_2.convert_to_sfiles(version='v2')
if sfiles_in==flowsheet_2.sfiles:
    print('Conversion back successful')
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles_in, 'Output:', flowsheet_2.sfiles)

# Try to create a new flowsheet from SFILES string
flowsheet_2=Flowsheet()
sfiles_in="(raw)(pp)<1(splt)[(hex)(flash)<&|(raw)&|[{bout}(v)(dist)[{bout}(prod)]{tout}(dist){bout}1<4{tout}(mix)<3(prod)]{bin}(abs)<2<6[{tout}(prod)]{bout}(flash){tout}5[{bout}(flash)[{tout}(comp)(comp)2<5]{bout}(flash){tout}3{bout}4]](hex){tin}6" # has to be valid according to SFILES rules
flowsheet_2.create_from_sfiles(sfiles_in)
flowsheet_2.visualize_flowsheet(table=False, pfd_path='plots/flowsheet3', plot_with_stream_labels=False)

# Check if conversion back works
flowsheet_2.sfiles=""
flowsheet_2.convert_to_sfiles(version='v2')
if sfiles_in==flowsheet_2.sfiles:
    print('Conversion back successful')
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles_in, 'Output:', flowsheet_2.sfiles)

# Random flowsheet generation check
flowsheet_3=Flowsheet(OntoCapeConformity=True)
flowsheet_3.create_random_flowsheet()
flowsheet_3.visualize_flowsheet(table=False, pfd_path='plots/flowsheet4', plot_with_stream_labels=False)
print(flowsheet_3.sfiles)

# Check SFILES v2 notation for a heat exchanger with 2 streams
G = nx.DiGraph()
G.add_nodes_from([('HeatExchanger-0', {'pos': [550, 75.0]}), ('DistillationSystem-1', {'pos': [500, 250]}), ('RawMaterial-1', {'pos': [350, 250]}), ('RawMaterial-2', {'pos': [150, 150]}), ('OutputProduct-1', {'pos': [350, 50]})])
G.add_edges_from([('HeatExchanger-0', 'DistillationSystem-1', {'labels': 'Stream 13', 'tags':{'he': ['hot_out'], 'col': ['bin']}}),('HeatExchanger-0', 'OutputProduct-1', {'labels': 'Stream 13', 'tags':{'he': ['2_out'], 'col': []}}), ('RawMaterial-1', 'HeatExchanger-0', {'labels': 'Stream 13', 'tags':{'he': ['hot_in'], 'col': []}}),('RawMaterial-2', 'HeatExchanger-0', {'labels': 'Stream 13', 'tags':{'he': ['2_in'], 'col': []}})])
flowsheet_4=Flowsheet(OntoCapeConformity=True)
flowsheet_4.state=G
flowsheet_4.convert_to_sfiles(version='v2')
sfiles_1 = flowsheet_4.sfiles
print(sfiles_1)
flowsheet_4.create_from_sfiles(sfiles_1, override_nx=True)
flowsheet_4.convert_to_sfiles(version='v2')
sfiles_2 = flowsheet_4.sfiles
print(sfiles_1==sfiles_2)

#Test merging and splitting of HI nodes
flowsheet_4=Flowsheet()
sfiles_list = ['(raw)','(hex)','{1}','(hex)', '{2}', '(dist)', '[', '{tout}', '(prod)', ']', '{bout}', '(hex)', '{2}', '(prod)', 'n|','(raw)','(hex)','{1}', '(prod)']
flowsheet_2 = Flowsheet()
flowsheet_2.sfiles_list = sfiles_list
flowsheet_2.create_from_sfiles()
flowsheet_2.convert_to_sfiles(version='v2')
print(flowsheet_2.sfiles)

flowsheet_2=Flowsheet()
sfiles_in="(raw)(flash)[{tout}(prod)]{bout}(splt)[(prod)](r)<&|(raw)(flash){tout}&{bout}(prod)|(prod)" # has to be valid according to SFILES rules
flowsheet_2.create_from_sfiles(sfiles_in)
flowsheet_2.visualize_flowsheet(table=False, pfd_path='plots/flowsheet3', plot_with_stream_labels=False)

# Check if conversion back works
flowsheet_2.sfiles=""
flowsheet_2.convert_to_sfiles(version='v2')
if sfiles_in==flowsheet_2.sfiles:
    print('Conversion back successful')
else:
    print('Conversion back produced a different SFILES string. Input:', sfiles_in, 'Output:', flowsheet_2.sfiles)
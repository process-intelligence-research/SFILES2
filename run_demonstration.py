#                   @@@                  
#           @@@@@@@@@@@@@@@@@@@          
#       @@@@@@@@@@@@@@@@@@@@@@@@@@@      
#     @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@    
#   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@  
#  @@@@@@                             @@ 		 __   __   __   __   ___  __   __                    
# @@@                                 @@@		|__) |__) /  \ /  ` |__  /__` /__`                   
# @   .@@@@@    @@@@@@@@@@     @@@@@@@@@@		|    |  \ \__/ \__, |___ .__/ .__/                   
#@@@@@@@@@@@    @@@@@@@@@@     @@@@@@@@@@		       ___  ___              __   ___       __   ___ 
# @@@@@@@@@@    @@@@@@@@@@     @@@@@@@@@@		| |\ |  |  |__  |    |    | / _` |__  |\ | /  ` |__  
# @@@@@@@@@@    @@@@@@@@@@     @@@@@@@@@@		| | \|  |  |___ |___ |___ | \__> |___ | \| \__, |___ 
#  @@@@@@@@@    @@@@@@@@@@     @@@@@@@@@ 		 __   ___  __   ___       __   __                    
#   @@@@@@@@    @@@@@@@@@@     @@@@@@@@  		|__) |__  /__` |__   /\  |__) /  ` |__|              
#     @@@@@@    @@@@@@@@@@     @@@@@@    		|  \ |___ .__/ |___ /~~\ |  \ \__, |  |              
#       @@@     @@@@@@@@@@     @@@@      
#               @@@@@@@@@@     
            
import networkx as nx

from Flowsheet_Class.flowsheet import Flowsheet

# Try to create a new flowsheet from SFILES string
flowsheet_2=Flowsheet()
sfiles_in="(raw)(pp)<1(splt)[(hex)(flash)<&|(raw)&|[{bout}(v)(dist)[{bout}(prod)]{tout}(dist){bout}1<4{tout}(mix)<3(prod)]{bin}(abs)<2<6[{tout}(prod)]{bout}(flash){tout}5[{bout}(flash)[{tout}(comp)(comp)2<5]{bout}(flash){tout}3{bout}4]](hex){tin}6" # has to be valid according to SFILES rules
flowsheet_2.create_from_sfiles(sfiles_in)
flowsheet_2.visualize_flowsheet(table=False, pfd_path="plots/flowsheet3", plot_with_stream_labels=False)

# Check if conversion back works
flowsheet_2.sfiles=""
flowsheet_2.convert_to_sfiles(version="v2")
if sfiles_in==flowsheet_2.sfiles:
    print("Conversion back successful")
else:
    print("Conversion back produced a different SFILES string. Input:", sfiles_in, "Output:", flowsheet_2.sfiles)


# Check SFILES v2 notation for a heat exchanger with 2 streams
G = nx.DiGraph()
G.add_nodes_from([("HeatExchanger-0", {"pos": [550, 75.0]}), ("DistillationSystem-1", {"pos": [500, 250]}), ("RawMaterial-1", {"pos": [350, 250]}), ("RawMaterial-2", {"pos": [150, 150]}), ("OutputProduct-1", {"pos": [350, 50]})])
G.add_edges_from([("HeatExchanger-0", "DistillationSystem-1", {"labels": "Stream 13", "tags":{"he": ["hot_out"], "col": ["bin"]}}),("HeatExchanger-0", "OutputProduct-1", {"labels": "Stream 13", "tags":{"he": ["2_out"], "col": []}}), ("RawMaterial-1", "HeatExchanger-0", {"labels": "Stream 13", "tags":{"he": ["hot_in"], "col": []}}),("RawMaterial-2", "HeatExchanger-0", {"labels": "Stream 13", "tags":{"he": ["2_in"], "col": []}})])
flowsheet_4=Flowsheet(OntoCapeConformity=True)
flowsheet_4.state=G
flowsheet_4.convert_to_sfiles(version="v2")
sfiles_1 = flowsheet_4.sfiles
print(sfiles_1)
flowsheet_4.create_from_sfiles(sfiles_1, overwrite_nx=True)
flowsheet_4.convert_to_sfiles(version="v2")
sfiles_2 = flowsheet_4.sfiles
print(sfiles_1==sfiles_2)

#Test merging and splitting of HI nodes
flowsheet_4=Flowsheet()
sfiles_list = ["(raw)","(hex)","{1}","(hex)", "{2}", "(dist)", "[", "{tout}", "(prod)", "]", "{bout}", "(hex)", "{2}", "(prod)", "n|","(raw)","(hex)","{1}", "(prod)"]
flowsheet_2 = Flowsheet()
flowsheet_2.sfiles_list = sfiles_list
flowsheet_2.create_from_sfiles()
flowsheet_2.convert_to_sfiles(version="v2")
print(flowsheet_2.sfiles)

flowsheet_2=Flowsheet()
sfiles_in="(raw)(flash)[{tout}(prod)]{bout}(splt)[(prod)](r)<&|(raw)(flash){tout}&{bout}(prod)|(prod)" # has to be valid according to SFILES rules
flowsheet_2.create_from_sfiles(sfiles_in)
flowsheet_2.visualize_flowsheet(table=False, pfd_path="plots/flowsheet3", plot_with_stream_labels=False)

# Check if conversion back works
flowsheet_2.sfiles=""
flowsheet_2.convert_to_sfiles(version="v2")
if sfiles_in==flowsheet_2.sfiles:
    print("Conversion back successful")
else:
    print("Conversion back produced a different SFILES string. Input:", sfiles_in, "Output:", flowsheet_2.sfiles)

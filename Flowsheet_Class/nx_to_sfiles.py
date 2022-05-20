# -*- coding: utf-8 -*-
# Author: Gabriel Vogel
# 09/2021
import networkx as nx
import re

import numpy as np

"""
Exposes functionality for writing SFILES (Simplified flowsheet input line entry system) strings
Based on
- d’Anterroches, L. Group contribution based process flowsheet synthesis, design and modelling, Ph.D. thesis. Technical University of Denmark, 2006.
- Zhang, T., Sahinidis, N. V., & Siirola, J. J. (2019). Pattern recognition in chemical process flowsheets. AIChE Journal, 65(2), 592-603.
- Weininger, David (February 1988). "SMILES, a chemical language and information system. 1. Introduction to methodology and encoding rules". Journal of Chemical Information and Computer Sciences. 28 (1): 31–6. 
"""
def nx_to_SFILES(flowsheet, version, remove_hex_tags, init_node=None):
    """
    Returns the SFILES representation (Tuple of list and string)
    Parameters
    ----------
    flowsheet: networkx graph
        flowsheet as networkx graph.
    version: str
        SFILES version, either v1 or v2, default is v1
    remove_hex_tags: bool
        Whether to show the 'he' tags in the SFILES_v2 (Conversion back and merging of hex nodes is not possible if this is set to true)
    init_node: str, optional
        node where to start the graph traversal
    
    Returns
    ----------
    sfiles: list 
        SFILES representation of the flowsheet (still parsed)
    sfiles_string: str
        String SFILES representation of flowsheet
    """

    # Calculation of graph invariant / node ranks

    ranks = calc_graph_invariant(flowsheet)

    # If no initial node is provided, select the node with lowest rank and no predecessors
    if not init_node:
        init_nodes = [n for n, d in flowsheet.in_degree() if d == 0]
        # Sort the possible initial nodes for traversal 
        init_nodes = sort_by_rank(init_nodes, ranks)
        if init_nodes:  # always the case except for pure cycle processes
            current_node = init_nodes[0]
        else:  # cycle process
            current_node = sort_by_rank(flowsheet.nodes, ranks)[0]  # select the node in cycle process with the lowest rank
    else:
        current_node = init_node

    visited = set() # Set to keep track of visited nodes.
    sfiles = [] # empty sfiles list of strings
    nr_pre_visited = 0 # counter for nodes that are visited more than once 
    nodes_position_setoffs = {n: 0 for n in flowsheet.nodes} # this dictionary counts outgoing direct cycles and incoming streams per node ('#' and '<#')
    nodes_position_setoffs_cycle = {n: 0 for n in flowsheet.nodes} # this dictionary counts outgoing direct cycles ('#')
    special_edges = {}

    # First traversal
    sfiles, nr_pre_visited = dfs(visited, flowsheet, current_node, 
                                sfiles, nr_pre_visited, ranks, 
                                nodes_position_setoffs, nodes_position_setoffs_cycle, special_edges)

    # Further traversals
    not_visited = (set(flowsheet.nodes) - visited)
    init_nodes_2 = [] # List of initial nodes for further traversals
    for n in not_visited:
        predeccs = list(flowsheet.predecessors(n))
        if len(predeccs) == 0:
            init_nodes_2.append(n)

    # Continue with traversals as long as there are unvisited initial nodes
    init_nodes_2 = sort_by_rank(init_nodes_2, ranks)
    init_nodes_2.reverse()
    visited_2 = visited.copy()
    while init_nodes_2:
        current_node = init_nodes_2.pop()
        branch_sfiles = []
        visited=visited_2.copy()
        node_insertion=''
        branch_sfiles, nr_pre_visited, node_insertion = dfs_2nd(visited, visited_2, flowsheet, current_node, sfiles,
                                                branch_sfiles, nr_pre_visited, ranks, nodes_position_setoffs, 
                                                nodes_position_setoffs_cycle, node_insertion, special_edges)

        if not node_insertion=='':
            branch_sfiles.append('|')
            branch_sfiles.insert(0,'<&|')
            pos = position_finder(nodes_position_setoffs, node_insertion, sfiles, 
                                            nodes_position_setoffs_cycle, cycle=False)
            # Insert the branch next to node_insertion
            insert_element(sfiles,pos,branch_sfiles)
        else: # This can happen for very large graphs with multiple branches (2nd traversal does not end in a previously visited node but in an untraversed branch)
            # we just append it as we did in the previous SFILES version 
            # In the latest notation this is the case for different mass trains, e.g refrigerant cycle is only coupled via heat integration
            sfiles.append('n|')
            sfiles.extend(branch_sfiles)

    # In case there are still unvisited nodes: Separate (or heat integrated) cycle process
    not_visited = (set(flowsheet.nodes) - visited_2)
    while not_visited:
        current_node = sort_by_rank(not_visited, ranks)[0] # select the node in cycle process with the lowest rank
        branch_sfiles = []
        visited=visited_2.copy()
        node_insertion=''
        branch_sfiles, nr_pre_visited, node_insertion = dfs_2nd(visited, visited_2, flowsheet, current_node, sfiles,
                                                branch_sfiles, nr_pre_visited, ranks, nodes_position_setoffs, 
                                                nodes_position_setoffs_cycle, node_insertion, special_edges)

        if not node_insertion=='':
            branch_sfiles.append('|')
            branch_sfiles.insert(0,'<&|')
            pos = position_finder(nodes_position_setoffs, node_insertion, sfiles, 
                                            nodes_position_setoffs_cycle, cycle=False)
            # Insert the branch next to node_insertion
            insert_element(sfiles,pos,branch_sfiles)
        else: # This can happen for very large graphs with multiple branches (2nd traversal does not end in a previously visited node but in an untraversed branch)
            # we just append it as we did in the previous SFILES version 
            # In the latest notation this is the case for different mass trains, e.g refrigerant cycle is only coupled via heat integration
            sfiles.append('n|')
            sfiles.extend(branch_sfiles)
            
        #check if still unvisited nodes:
        not_visited = (set(flowsheet.nodes) - visited_2)
    # Flatten nested list
    sfiles = flatten(sfiles)
    sfiles_string = ''.join(sfiles)
    
    # The following section is for SFILES_2.0
    if version=='v2':
        sfiles_v2 = SFILES_v2(flowsheet, sfiles, special_edges, remove_hex_tags)
        # generalization of SFILES (remove node numbering) as last step
        sfiles_v2_gen = generalize_SFILES(sfiles_v2)
        sfiles_string_v2_gen = ''.join(sfiles_v2_gen)

        return sfiles_v2_gen, sfiles_string_v2_gen
    # Version 1:
    else:
        # generalization of SFILES (remove node numbering) as last step
        sfiles_gen = generalize_SFILES(sfiles)
        sfiles_string_gen = ''.join(sfiles_gen)

        return sfiles_gen, sfiles_string_gen

def dfs(visited, flowsheet, current_node, sfiles,
        nr_pre_visited, ranks, nodes_position_setoffs,
        nodes_position_setoffs_cycle, special_edges):
    """ 
    Depth first search implementation to traverse the directed graph from initial node
    Note that this traversal may not visit all nodes, since the graph is directed (e.g. multiple raw materials/Input streams)
    In this case the function dfs_2nd(...) is used for the next traversals
    Parameters
    ----------
    visited: list
        list of visited nodes
    flowsheet: networkx graph
        flowsheet as networkx graph.
    current_node: str
        current node in depth first search
    sfiles: list
        SFILES representation of the flowsheet
    nr_pre_visited: int
        counter variable for cycles
    ranks: dict
        ranks for branching decisions
    nodes_position_setoffs: dict
        counts the occurences of outgoing and incoming cycles per node
    nodes_position_setoffs_cycle: dict
        counts the occurences only of outgoing cycles per node
    special_edges: dict
        saves, whether an edge (in,out) is a cycle (number>1) or not (number=0)
    Returns
    -------
    sfiles: list
        SFILES representation of the flowsheet
    nr_pre_visited: int
        counter variable
    
    """
    if current_node not in visited:

        succs = list(flowsheet.successors(current_node))
        
        # New branching
        if len(succs) > 1: 
            sfiles.append('('+current_node+')')
            visited.add(current_node)

            # Branching decision requires ranks of nodes:
            neighbours = sort_by_rank(flowsheet[current_node], ranks, visited)
            for neighbour in neighbours:

                # Open a bracket
                if not neighbour==neighbours[-1]:
                    sfiles.append('[')

                # If neighbor is already visited, that's a direct cycle -> we need no branch brackets
                if neighbour not in visited:
                    sfiles, nr_pre_visited = dfs(visited, flowsheet, neighbour, sfiles, 
                                                nr_pre_visited, ranks, nodes_position_setoffs, 
                                                nodes_position_setoffs_cycle, special_edges)
                    if not neighbour==neighbours[-1]:
                        sfiles.append(']') # Close bracket/branch
                else: 
                    if sfiles[-1] == '[':
                        sfiles.pop()
                    nr_pre_visited += 1
                    pos = position_finder(nodes_position_setoffs, neighbour, sfiles, 
                                        nodes_position_setoffs_cycle, cycle=False)
                    # sfiles.insert(pos + 1,'<'+str(nr_pre_visited))
                    insert_element(sfiles,pos,'<'+str(nr_pre_visited))
                    pos = position_finder(nodes_position_setoffs, current_node, sfiles, 
                                        nodes_position_setoffs_cycle, cycle=True)
                    # according to SMILES notation, for two digit cycles a % sign is put before the number
                    if nr_pre_visited > 9: 
                        # sfiles.insert(pos + 1, '%'+str(nr_pre_visited))
                        insert_element(sfiles,pos,'%'+str(nr_pre_visited))
                    else:
                        # sfiles.insert(pos + 1, str(nr_pre_visited))
                        insert_element(sfiles,pos,str(nr_pre_visited))

                    # additional info: edge is a cycle edge in SFILES
                    special_edges[(current_node,neighbour)] = nr_pre_visited

                    # No bracket/branch closing

        # Only one successor, no branching
        elif len(succs) == 1: 
            sfiles.append('('+current_node+')')
            visited.add(current_node)
            for neighbour in flowsheet[current_node]: # future: invariant to select next node
                sfiles, nr_pre_visited = dfs(visited, flowsheet, neighbour,
                                            sfiles, nr_pre_visited, ranks,
                                            nodes_position_setoffs, nodes_position_setoffs_cycle, special_edges)

        # Dead end
        elif len(succs) == 0: 
            visited.add(current_node)
            sfiles.append('('+current_node+')')


    # Already visited node
    else: 
        # Append the branch that lead there
        nr_pre_visited += 1
        pos = position_finder(nodes_position_setoffs, current_node, sfiles, 
                            nodes_position_setoffs_cycle, cycle=False)
        # sfiles.insert(pos + 1, '<'+str(nr_pre_visited))
        insert_element(sfiles, pos, '<'+str(nr_pre_visited))
        last_node = last_node_finder(sfiles)
        pos = position_finder(nodes_position_setoffs, last_node, sfiles,
                            nodes_position_setoffs_cycle, cycle=True)
        # according to SMILES notation, for two digit cycles a % sign is put before the number
        if nr_pre_visited > 9: 
            # sfiles.insert(pos + 1, '%'+str(nr_pre_visited))
            insert_element(sfiles, pos, '%'+str(nr_pre_visited))
        else:
            # sfiles.insert(pos + 1, str(nr_pre_visited))
            insert_element(sfiles, pos, str(nr_pre_visited))
        
        # additional info: edge is a cycle edge in SFILES
        special_edges[(last_node,current_node)] = nr_pre_visited
        
    return sfiles, nr_pre_visited

def dfs_2nd(visited, visited_2, flowsheet, current_node, 
            sfiles_full, sfiles, nr_pre_visited, ranks,
            nodes_position_setoffs, nodes_position_setoffs_cycle, node_insertion, special_edges):
    """ 
    Second traversal: Depth first search implementation to traverse
    the directed graph from other than first initial node.
    This stops when visiting a node from previous traversal(s)
    and all nodes of the branch are explored.
    Parameters
    ----------
    visited: list
        list of visited nodes from previous traversals
    visited_2: list 
        list of visited nodes in total
    flowsheet: networkx graph
        flowsheet as networkx graph.
    current_node: str
        current node in depth first search
    sfiles_full: list
        SFILES representation of the flowsheet (full string so far)
    sfiles: list
        SFILES representation of the flowsheet (branch)
    nr_pre_visited: int
        counter variable
    ranks: dict
        ranks for branching decisions
    nodes_position_setoffs: dict
        counts the occurences of outgoing and incoming cycles per node
    nodes_position_setoffs_cycle: dict
        counts the occurences only of outgoing cycles per node
    node_insertion: str
        a node of previous traversal(s) where branch (first) ends, default is an empty string
    
    Returns
    -------
    sfiles: list
        SFILES representation of the flowsheet
    nr_pre_visited: int
        counter variable
    node_insertion: str
        a node of previous traversal(s) where branch (first) ends 
    
    """
    already_loop_to_previous = False
    
    if current_node not in visited: # NODES OF THIS TRAVERSAL
        if current_node not in visited_2: # Node is not visited
            succs = list(flowsheet.successors(current_node))
            
            # New branching
            if len(succs) > 1: 
                sfiles.append('('+current_node+')')
                visited_2.add(current_node)

                # Branching decision requires ranks of nodes:
                neighbours = sort_by_rank(flowsheet[current_node], ranks, visited_2)
                for neighbour in neighbours:

                    # Open a bracket
                    if not neighbour==neighbours[-1]:
                        sfiles.append('[')

                    # If neighbor is already visited, that's a direct cycle -> we need no branch brackets
                    if neighbour not in visited_2: # NEITHER IN PREVIOUS NOR IN THIS TRAVERSAL
                        sfiles, nr_pre_visited, node_insertion = dfs_2nd(visited, visited_2, flowsheet, 
                                                        neighbour, sfiles_full, sfiles,
                                                        nr_pre_visited, ranks, nodes_position_setoffs,
                                                        nodes_position_setoffs_cycle, node_insertion, special_edges)
                        if not neighbour==neighbours[-1]:
                            sfiles.append(']') # close bracket/branch
                    else: 
                        if neighbour not in visited: # NEIGHBOR NOT IN PREVIOUS BUT ALREADY IN THIS TRAVERSAL
                            if sfiles[-1] == '[':
                                sfiles.pop()
                            nr_pre_visited += 1
                            pos = position_finder(nodes_position_setoffs, neighbour, sfiles,
                                                nodes_position_setoffs_cycle, cycle = False)
                            # sfiles.insert(pos + 1,'<'+str(nr_pre_visited))
                            insert_element(sfiles, pos, '<'+str(nr_pre_visited))
                            pos = position_finder(nodes_position_setoffs, current_node, sfiles,
                                                nodes_position_setoffs_cycle, cycle = True)
                            # according to SMILES notation, for two digit cycles a % sign is put before the number
                            if nr_pre_visited > 9: 
                                # sfiles.insert(pos + 1, '%'+str(nr_pre_visited))
                                insert_element(sfiles, pos, '%'+str(nr_pre_visited))
                            else:
                                # sfiles.insert(pos + 1, str(nr_pre_visited))
                                insert_element(sfiles, pos, str(nr_pre_visited))

                            # additional info: edge is a cycle edge in SFILES
                            special_edges[(current_node,neighbour)] = nr_pre_visited

                        else: # NEIGHBOR NODE IN PREVIOUS TRAVERSAL
                            if sfiles[-1] == '[':
                                sfiles.pop()
                            if node_insertion == '': # only insert sfiles once. If there are multiple backloops to previous traversal, treat them as cycles
                                # NEW: Insert a & sign where branch connects to node of previous traversal
                                node_insertion = neighbour
                                pos = position_finder(nodes_position_setoffs, current_node, sfiles, 
                                                        nodes_position_setoffs_cycle, cycle = True)
                                insert_element(sfiles, pos, '&')
                                # additional info: edge is a new incoming branch edge in SFILES
                                special_edges[(current_node,neighbour)] = '&'
                                
                            else:
                                # Incoming branches are referenced with a number, if there already is a node_insertion
                                nr_pre_visited += 1
                                pos = position_finder(nodes_position_setoffs, neighbour, sfiles_full, 
                                                        nodes_position_setoffs_cycle, cycle = False)
                                # sfiles_full.insert(pos + 1, '<'+str(nr_pre_visited))
                                insert_element(sfiles_full, pos, '<'+str(nr_pre_visited))
                                pos = position_finder(nodes_position_setoffs, current_node, sfiles, 
                                                        nodes_position_setoffs_cycle, cycle = True)
                                # according to SMILES notation, for two digit cycles a % sign is put before the number
                                if nr_pre_visited > 9: 
                                    # sfiles.insert(pos + 1, '%'+str(nr_pre_visited))
                                    insert_element(sfiles, pos, '%'+str(nr_pre_visited))
                                else:
                                    # sfiles.insert(pos + 1, str(nr_pre_visited))
                                    insert_element(sfiles, pos, str(nr_pre_visited))
                                
                                # additional info: edge is a cycle edge in SFILES
                                special_edges[(current_node,neighbour)] = nr_pre_visited

                            
            # Only one successor, no branching
            elif len(succs) == 1: 
                sfiles.append('('+current_node+')')
                visited_2.add(current_node)

                # Branching decision requires ranks of nodes:
                neighbours = sort_by_rank(flowsheet[current_node], ranks, visited_2)
                for neighbour in neighbours:
                    sfiles, nr_pre_visited, node_insertion = dfs_2nd(visited, visited_2, flowsheet, 
                                                    neighbour, sfiles_full, sfiles, 
                                                    nr_pre_visited, ranks, nodes_position_setoffs,
                                                    nodes_position_setoffs_cycle, node_insertion, special_edges)
            # Dead end
            elif len(succs) == 0: 
                visited_2.add(current_node)
                sfiles.append('('+current_node+')')

        # Cycle or mixing of two raw materials
        # Already visited node
        else: 
            # Append the branch that lead there
            nr_pre_visited += 1
            pos = position_finder(nodes_position_setoffs, current_node, sfiles, 
                                nodes_position_setoffs_cycle, cycle = False)
            # sfiles.insert(pos + 1, '<'+str(nr_pre_visited))
            insert_element(sfiles, pos, '<'+str(nr_pre_visited))
            last_node = last_node_finder(sfiles)
            pos = position_finder(nodes_position_setoffs, last_node, sfiles, 
                                nodes_position_setoffs_cycle, cycle = True)
            # according to SMILES notation, for two digit cycles a % sign is put before the number
            if nr_pre_visited > 9: 
                # sfiles.insert(pos + 1, '%'+str(nr_pre_visited))
                insert_element(sfiles, pos, '%'+str(nr_pre_visited))
            else:
                # sfiles.insert(pos + 1, str(nr_pre_visited))
                insert_element(sfiles, pos, str(nr_pre_visited))
            # additional info: edge is a cycle edge in SFILES
            special_edges[(last_node,current_node)] = nr_pre_visited
    
    else: # NODES OF PREVIOUS TRAVERSAL, this else case is visited when there is no branching but node of previous traversal
        """ 
        # OLD: Incoming branches are appended at the end and referenced with a number
        nr_pre_visited += 1
        pos = position_finder(nodes_position_setoffs, current_node, sfiles_full,
                            nodes_position_setoffs_cycle, cycle = False)
        sfiles_full.insert(pos+1,'<'+str(nr_pre_visited))
        last_node = last_node_finder(sfiles)
        pos = position_finder(nodes_position_setoffs, last_node, sfiles, 
                            nodes_position_setoffs_cycle, cycle = True)
        # according to SMILES notation, for two digit cycles a % sign is put before the number
        if nr_pre_visited > 9: 
            sfiles.insert(pos + 1, '%'+str(nr_pre_visited))
        else:
            sfiles.insert(pos + 1, str(nr_pre_visited)) """
        # NEW: Incoming branches are inserted at mixing point in SFILES surrounded by <|...|
        if node_insertion == '': # only insert sfiles once. If there are multiple backloops to previous traversal, treat them as cycles
            # NEW: Insert a & sign where branch connects to node of previous traversal
            node_insertion = current_node
            last_node = last_node_finder(sfiles)
            pos = position_finder(nodes_position_setoffs, last_node, sfiles, 
                                    nodes_position_setoffs_cycle, cycle = True)
            insert_element(sfiles, pos, '&')

            # additional info: edge is a new incoming branch edge in SFILES
            special_edges[(last_node,current_node)] = '&'

        else: # Incoming branches are referenced with a number, if there already is a node_insertion
            nr_pre_visited += 1
            pos = position_finder(nodes_position_setoffs, current_node, sfiles_full, 
                                nodes_position_setoffs_cycle, cycle = False)
            # sfiles.insert(pos + 1, '<'+str(nr_pre_visited))
            insert_element(sfiles_full, pos, '<'+str(nr_pre_visited))
            last_node = last_node_finder(sfiles)
            pos = position_finder(nodes_position_setoffs, last_node, sfiles, 
                                nodes_position_setoffs_cycle, cycle = True)
            # according to SMILES notation, for two digit cycles a % sign is put before the number
            if nr_pre_visited > 9: 
                # sfiles.insert(pos + 1, '%'+str(nr_pre_visited))
                insert_element(sfiles, pos, '%'+str(nr_pre_visited))
            else:
                # sfiles.insert(pos + 1, str(nr_pre_visited))
                insert_element(sfiles, pos, str(nr_pre_visited))
            
            # additional info: edge is a cycle edge in SFILES
            special_edges[(last_node,current_node)] = nr_pre_visited

    return sfiles, nr_pre_visited, node_insertion

def SFILES_v2(flowsheet, sfiles, special_edges, remove_hex_tags=False):

    """ 
    Method to construct the SFILES 2.0:
    Additional information in egde attributes regarding connectivity (Top or bottom in distillation, absorption, or extraction columns)

    
    Parameters
    ----------
    flowsheet (nx graph): flowsheet as directed networkx graph.
    sfiles (list): SFILES representation of the flowsheet (still parsed)
    special_edges (dict): contains edge and cycle number>0 -> different notation of tags
    remove_hex_tags (bool): Whether to show the 'he' tags in the SFILES_v2 (Conversion back and merging of hex nodes is not possible if this is set to true)

    Returns
    -------
    sfiles_v2 (list): SFILES representation (2.0) of the flowsheet (still parsed)
    
    """
    sfiles_v2 = sfiles.copy()
    edge_infos = nx.get_edge_attributes(flowsheet, "tags")
    if remove_hex_tags: # only save the column related tags
        edge_infos = {k:{'col':v['col']} for k,v in edge_infos.items() if 'col' in v.keys()}
    edge_infos = {k:flatten(v.values()) for k,v in edge_infos.items()} #merge he and col tags
    edge_infos = {k:v for k,v in edge_infos.items() if v}# filter out empty tags lists, and 
    if edge_infos: # only if there are additional sfiles_info attributes
        # first assign edge attributes to nodes
        for e,at in edge_infos.items():
            # e: tuple (in_node name, out_node name); at: attribute
            if type(at) == str:
                #print('Info: Changed the tag of edge %s to type list with one element.'%str(e))
                at = [at]
            in_node = e[0]
            out_node = e[1]
            if e in special_edges:
                edge_type = str(special_edges[e])
            else: 
                edge_type = 'normal'
            tags = '{'+'}{'.join(at)+'}' # every single tag of that stream in own braces
            
            """  search position where to insert tag """
            if edge_type=='normal':
                for s_idx, s in enumerate(sfiles_v2):
                    if s == '('+out_node+')': # this is the out_node 
                        sfiles_v2.insert(s_idx, tags)
                        break
            # a bit more complicated, we need to find the right & sign
            elif edge_type=='&': 
                search_and = False
                for s_idx, s in enumerate(sfiles_v2):
                    if s == '('+in_node+')': # this is the out_node 
                        search_and = True
                        counter = 0
                    if search_and:
                        if s == '&' and counter ==0: # no second branch within branch with <&| notation
                            sfiles_v2.insert(s_idx, tags)
                            break
                        if s == '&' and counter >0: counter -= 1
                        if s == '<&|': counter += 1
            else: # edge_type > 0 Recycle edge, so we search for the corresponding recycle number
                for s_idx, s in enumerate(sfiles_v2):
                    if s == edge_type:
                        sfiles_v2.insert(s_idx, tags)
                        break
                
    """ 
    Heat integration tags 
    Heat integration is noted with a mix between recycle and connectivity notation, e.g. (hex){1}...(hex){1}. 
    To distinguish from other (hex).
    The {1} does not need an '<' operator because there is no connection in the graph. 
    Networkx node names with slash: e.g. hex-1/1 and hex-1/2
    """
    HI_eqs = [] # Heat integrated heat exchangers 
    for s_idx, s in enumerate(sfiles_v2):
        if 'hex' in s and '/' in s: 
            hex = s.split(sep='/')[0][1:]
            if hex not in HI_eqs:
                HI_eqs.append(hex)
    _HI_counter = 1
    for hex in HI_eqs: 
        indices = [i for i, x in enumerate(sfiles_v2) if x.split(sep='/')[0][1:] == hex]
        for i in indices: 
            previous = sfiles_v2[i]
            sfiles_v2[i] = [previous, '{'+str(_HI_counter)+'}']
        # flatten list
        sfiles_v2 = flatten(sfiles_v2)
        _HI_counter+=1


    return sfiles_v2

def generalize_SFILES(sfiles):
    """ 
    Method to construct the generalized SFILES 2.0:
    This means that the unit numbers (necessary in graph node names) are removed

    
    Parameters
    ----------
    sfiles (list): SFILES representation of the flowsheet

    Returns
    -------
    sfiles_gen (list): generalized SFILES representation of the flowsheet
    
    """
    sfiles_gen = sfiles.copy()
    for i, s in enumerate(sfiles_gen):
        if bool(re.match(r'\(.*?\)',s)):
            sfiles_gen[i] = s.split(sep='-')[0]+')'
    
    return sfiles_gen
    

""" Helper functions """

def sort_by_rank(nodes_to_sort,ranks,visited=[]):

    """ 
    Method to sort the nodes by their ranks.
    Second traversal: Depth first search implementation to traverse the directed graph from other than initial node
    This stops when visiting a node from 1. traversal and all nodes of the branch are explored.
    Parameters
    ----------
    nodes_to_sort: list
    ranks: dict
        node ranks calculated in calc_graph_invariant()
    visited: list
        list of already visited nodes
    Returns
    -------
    nodes_sorted: list
        contains certain neighbour nodes in sorted manner
    
    """
    # first only 
    nodes_sorted_dict = {}
    nodes_sorted_dict_cycle = {}
    for n in nodes_to_sort: 
        if n in ranks:
            if n in visited: 
                nodes_sorted_dict_cycle[n] = ranks[n]
            else: nodes_sorted_dict[n] = ranks[n]

    
    # sorting
    nodes_sorted_dict = dict(sorted(nodes_sorted_dict.items(), key = lambda item: item[1]))
    nodes_sorted_dict_cycle = dict(sorted(nodes_sorted_dict_cycle.items(), key = lambda item: item[1]))
    
    #concatenate -> direct cycle nodes are visited first
    all_nodes_sorted = dict(nodes_sorted_dict_cycle, **nodes_sorted_dict)
    # only take the sorted keys as list
    nodes_sorted = list(all_nodes_sorted.keys())

    return nodes_sorted

def calc_graph_invariant(flowsheet):

    """ 
    Calculates the graph invariant, which ranks the nodes for branching decisions in graph traversal.
    1. Morgan Algorithm based on: Zhang, T., Sahinidis, N. V., & Siirola, J. J. (2019). 
    Pattern recognition in chemical process flowsheets. AIChE Journal, 65(2), 592-603.
    2. Equal ranks (e.g. two raw material nodes) are ranked by additional rules in function rank_by_dfs_tree
    Parameters
    ----------
    flowsheet: networkx graph
        flowsheet as networkx graph.
    Returns
    -------
    Ranks: dict
        ranks of graph nodes 
    
    """
    # First generate subgraphs (different mass trains in flowsheet)
    _sgs = [flowsheet.subgraph(c).copy() for c in nx.weakly_connected_components(flowsheet)]
    # Sort subgraphs, such that larger subgraphs are used first
    _sgs.sort(key=lambda x:-len(list(x.nodes)))
    rank_offset=0
    all_unique_ranks={}
    
    for sg in _sgs:
        # 1. Morgan algorithm
        # Elements of the adjacency matrix show whether nodes are connected in the graph (1) or not (0)
        # Summing over the rows of the adjacency matrix results in the connectivity number of each node
        # The Morgan algorithm is performed via a matrix multiplication of the connectivity and the adjacency matrix.
        # This equals a summing of the connectivity values of the neighbour nodes for each node in a for-loop.

        undirected_graph = nx.to_undirected(sg)
        adjacency_matrix = nx.to_numpy_matrix(undirected_graph)
        connectivity = sum(adjacency_matrix)
        node_labels = list(sg)
        unique_values_temp = 0
        counter = 0
        morgan_iter = connectivity * adjacency_matrix

        while counter < 5:
            morgan_iter = morgan_iter * adjacency_matrix
            unique_values = np.unique(morgan_iter, axis=1).size
            if unique_values == unique_values_temp:
                counter += 1
            else:
                unique_values_temp = unique_values
                morgan_iter_vec = np.squeeze(np.asarray(morgan_iter))
                morgan_iter_dict = dict(zip(node_labels, morgan_iter_vec))

        # Assign ranks based on the connectivity values
        r = {key: rank for rank, key in enumerate(sorted(set(morgan_iter_dict.values())), 1)}
        Ranks = {k: r[v] for k, v in morgan_iter_dict.items()}

        # use rank as keys
        k_v_exchanged = {}
        for key, value in Ranks.items():
            if value not in k_v_exchanged:
                k_v_exchanged[value] = [key]
            else:
                k_v_exchanged[value].append(key)

        # 1. We first sort (ascending) the dict and afterwards create a nested list
        k_v_exchanged_sorted = {k: k_v_exchanged[k] for k in sorted(k_v_exchanged)}
        ranks_list = []
        for key, value in k_v_exchanged_sorted.items():
            ranks_list.append(value)

        # 2. We afterwards sort the nested lists (same rank)
        # This is the tricky part of breaking the ties
        for pos, eq_ranked_nodes in enumerate(ranks_list):
            # eq_ranked_nodes is a list itself
            # they are sorted, so the unique ranks depend on their names
            dfs_trees=[]
            # sorting rules to achieve unique ranks are described in the SFILES documentation
            if len(eq_ranked_nodes) >1:
                for n in eq_ranked_nodes:
                    # construct depth first search tree for each node
                    dfs_tr = nx.dfs_tree(sg,source=n)
                    dfs_trees.append(dfs_tr)
                
                # we remove the numbering of the nodes (the numbering should not change the generalized SFILES!)    
                dfs_trees_generalized={eq_ranked_nodes[i]:[el.split(sep='-')[0] for el in list(dfs_trees[i].nodes)] for i in range(0,len(eq_ranked_nodes))}

                # We sort the nodes by 4 criteria: Input/output/other node, number of successors in dfs_tree, successors names (without numbering), node names with numbering
                sorted_eq_ranked_nodes= rank_by_dfs_tree(dfs_trees_generalized)

            else:
                sorted_eq_ranked_nodes = sorted(eq_ranked_nodes)
            ranks_list[pos] = sorted_eq_ranked_nodes

        # 3. We flatten the list and create the new ranks dictionary with unique ranks
        # (form: node:rank) starting with rank 1
        flattened_ranks_list = flatten(ranks_list)
        unique_ranks = {n: r + 1 + rank_offset for r, n in enumerate(flattened_ranks_list)}
        
        # all unique ranks in separate dict 
        all_unique_ranks.update(unique_ranks)
        # Change rank offset in case there are subgraphs
        rank_offset += len(list(sg.nodes))
    
    return all_unique_ranks

def position_finder(nodes_position_setoffs, node, sfiles, 
                    nodes_position_setoffs_cycle, cycle=False):
    """
    Returns position where to insert a certain new list element in sfiles list, 
    adjusted by position setoffs. 
    Parameters
    ----------
    nodes_position_setoffs: dict
        counts the occurences of outgoing and incoming cycles per node
    node: str
        node, for which position is searched
    sfiles: list
        list of strings 
    nodes_position_setoffs_cycle: dict
        counts the occurences only of outgoing cycles per node
    cycle: boolean
        wether the format is of form # (outgoing cycle); default is False
    
    Returns
    ----------
    pos: int 
        position where to insert new element
    """

    # If the node is not found, it is in a nested list:
    # Function to find positions in nested list
    indices = find_nested_indices(sfiles, '('+node+')')

    if cycle:
        # this ensures that # are always listed before <#
        
        indices[-1] += nodes_position_setoffs_cycle[node] 
        # this updates the node position setoff for cycles only
        nodes_position_setoffs_cycle[node] += 1 
        # this updates the overall node position setoff
        nodes_position_setoffs[node] += 1 
    else: 
        indices[-1] += nodes_position_setoffs[node]
        # this updates the overall node position setoff
        nodes_position_setoffs[node] += 1 
    return indices

def last_node_finder(sfiles):
    """
    Returns th last node in sfiles
    Parameters
    ----------
    sfiles: list
    
    Returns
    ----------
    last_node: str
    """
    for element in reversed(sfiles):
        if element.startswith('(') and element.endswith(')'):
            last_node = element[1:-1]
            break
    return last_node

def flatten(l):
    """
    Returns a flattened list
    Parameters
    ----------
    l: nested list
    
    Returns
    ----------
    l_flat: list 
        flat list
    """
    l_flat = []
    for i in l:
        if isinstance(i,list): l_flat.extend(flatten(i))
        else: l_flat.append(i)
    return l_flat

def find_nested_indices(li,node):
    temp_li = li.copy()
    indices=[]
    while True:
        try:
            pos = temp_li.index(node)
            indices.append(pos)
            break
        except: #we need to go one level deeper
            for idx,i in enumerate(temp_li): 
                if node in flatten(i):
                    temp_li = i.copy()
                    indices.append(idx)
    return indices

def insert_element(lst, indices, value):
    if(len(indices)==1):
        lst.insert(indices[0]+1,value)
    else:
        insert_element(lst[indices[0]],indices[1:],value)

def rank_by_dfs_tree(dfs_trees_generalized):
    """ 
    Sorts the nodes with equal ranks (still after application of morgan algorithm) 
    Criteria:
    1. Ranks: Output node < Input node < All other nodes
    2.1. Input nodes: The higher the number of succesors in dfs_tree the lower the rank -> first build long SFILES parts (if 1. did not yield unique ranks)
    2.2. Other nodes: The lower the number of succesors in dfs_tree the lower the rank -> short branches in brackets  (if 1. did not yield unique ranks)
    3. Alphabetical comparison of successor names (if 1. & 2. did not yield unique ranks)
    4. Unit operations of equally ranked nodes are the same -> Considering node numbers of equally ranked nodes (if 1. & 2. & 3. did not yield unique ranks)
    
    Note: Criteria 4 implies that the node numbering matters in SFILES construction.
          Nevertheless, if we remove the numbers in SFILES (generalized SFILES), the SFILES will be independent of numbering
          This is based on Criteria 3, which implies that all the successors are the same.

    Parameters
    ----------
    dfs_trees_generalized: dict
        equally ranked nodes with their respective dfs_trees (node names without unit numbers) in the flowsheet graph

    Returns
    -------
    sorted_nodes: list
        list of sorted nodes with previously equal ranks 
    """

    output_nodes = {}
    input_nodes = {}
    other_nodes = {}
    for n,s in dfs_trees_generalized.items():
        succ_str = ''.join(list(s))
        if succ_str == 'prod': 
            #output node
            output_nodes[n] = (len(dfs_trees_generalized[n]),succ_str)

        elif succ_str.startswith('raw'):
            #input node
            input_nodes[n] = (len(dfs_trees_generalized[n]),succ_str)
        
        else:
            #other node
            other_nodes[n] = (len(dfs_trees_generalized[n]),succ_str)

    # Sort all dicts first according list length (input/output: long is better, other nodes: short is better-> less in brackets), then generalized string alphabetically, then real node name (i.e. node number)
    # real node name (with numbering is only accessed if the generalized string is the same -> graph structure is the same)
    sorted_nodes = []
    for d in [output_nodes, input_nodes]:
        # 3 sort criteria in that order list length (- sign), then generalized string alphabetically, then node number
        sorted_nodes_sub = sorted(d, key=lambda k: (-d[k][0], d[k][1], int(re.split('-|/',k)[1])))
        sorted_nodes.extend(sorted_nodes_sub) # implies the order of first output, then input, then other nodess
    # other nodes
    # 3 sort criteria in that order list length (+ sign), then generalized string alphabetically,  then node number
    sorted_nodes_sub = sorted(other_nodes, key=lambda k: (other_nodes[k][0], other_nodes[k][1], int(re.split('-|/',k)[1])))
    sorted_nodes.extend(sorted_nodes_sub) #  implies the order of first output, then input, then other nodess

    return sorted_nodes
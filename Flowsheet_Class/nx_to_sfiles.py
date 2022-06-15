import networkx as nx
import re
import numpy as np

"""
Exposes functionality for writing SFILES (Simplified flowsheet input line entry system) strings
Based on
- d’Anterroches, L. Group contribution based process flowsheet synthesis, design and modelling, Ph.D. thesis. 
  Technical University of Denmark, 2006.
- Zhang, T., Sahinidis, N. V., & Siirola, J. J. (2019). Pattern recognition in chemical process flowsheets.
  AIChE Journal, 65(2), 592-603.
- Weininger, David (February 1988). "SMILES, a chemical language and information system. 1. Introduction to 
  methodology and encoding rules". Journal of Chemical Information and Computer Sciences. 28 (1): 31–6. 
"""


def nx_to_SFILES(flowsheet, version, remove_hex_tags):
    """
    Returns the SFILES representation (Tuple of list and string)
    Parameters
    ----------
    flowsheet: networkx graph
        flowsheet as networkx graph.
    version: str
        SFILES version, either v1 or v2, default is v1
    remove_hex_tags: bool
        Whether to show the 'he' tags in the SFILES_v2 (Conversion back and merging of hex nodes is not possible if
        this is set to true)
    
    Returns
    ----------
    sfiles_part: list
        SFILES representation of the flowsheet (still parsed)
    sfiles_string: str
        String SFILES representation of flowsheet
    """

    # Calculation of graph invariant / node ranks
    ranks = calc_graph_invariant(flowsheet)

    # Find initial nodes of graph. Initial nodes are determined by an in-degree of zero.
    init_nodes = [n for n, d in flowsheet.in_degree() if d == 0]
    # Sort the possible initial nodes for traversal depending on their rank.
    init_nodes = sort_by_rank(init_nodes, ranks)

    # Add an additional virtual node, which is connected to every initial node. Thus, one graph traversal is sufficient
    # to access every node in the graph.
    flowsheet.add_node('virtual')
    virtual_edges = [('virtual', i) for i in init_nodes]
    flowsheet.add_edges_from(virtual_edges)
    current_node = 'virtual'
    ranks['virtual'] = 0

    # Nodes in cycle-processes are not determined since their in_degree is greater than zero.
    # Thus, as long as not every node of flowsheet is connected to the virtual node, the node with the lowest rank
    # (which is not a outlet node) is connected to the virtual node.
    flowsheet_undirected = nx.to_undirected(flowsheet)
    connected_to_virtual = set(nx.node_connected_component(flowsheet_undirected, 'virtual'))
    not_connected = set(flowsheet.nodes) - connected_to_virtual
    while not_connected:
        rank_not_connected = sort_by_rank(not_connected, ranks)
        # Nodes with an out_degree of zero are removed since they are not suitable initial nodes.
        rank_not_connected = [k for k in rank_not_connected if flowsheet.out_degree(k) > 0]
        flowsheet.add_edges_from([('virtual', rank_not_connected[0])])
        connected_to_virtual = set(nx.node_connected_component(flowsheet_undirected, 'virtual'))
        not_connected = set(flowsheet.nodes) - connected_to_virtual

    # Initialization of variables.
    visited = set()  # Set to keep track of visited nodes.
    sfiles_part = []  # empty sfile_part list of strings
    nr_pre_visited = 0  # counter for nodes that are visited more than once
    # Dictionary nodes_position_setoffs counts outgoing direct cycles and incoming streams per node ('#' and '<#')
    nodes_position_setoffs = {n: 0 for n in flowsheet.nodes}
    # Dictionary nodes_position_setoffs_cycle counts outgoing direct cycles ('#')
    nodes_position_setoffs_cycle = {n: 0 for n in flowsheet.nodes}
    special_edges = {}

    # Graph traversal (depth-first-search dfs)
    sfiles_part, nr_pre_visited, node_insertion, sfiles = dfs(visited, flowsheet, current_node, sfiles_part,
                                                              nr_pre_visited, ranks, nodes_position_setoffs,
                                                              nodes_position_setoffs_cycle, special_edges,
                                                              first_traversal=True, sfiles=[], node_insertion='')

    # Flatten nested list of sfile_part
    sfiles = flatten(sfiles)
    sfiles_string = ''.join(sfiles)

    # The following section is for SFILES_2.0
    if version == 'v2':
        sfiles_v2 = SFILES_v2(flowsheet, sfiles, special_edges, remove_hex_tags)
        # Generalization of SFILES (remove node numbering) as last step
        sfiles_v2_gen = generalize_SFILES(sfiles_v2)
        sfiles_string_v2_gen = ''.join(sfiles_v2_gen)
        return sfiles_v2_gen, sfiles_string_v2_gen
    # SFILES Version 1:
    else:
        # Generalization of SFILES (remove node numbering) as last step
        sfiles_gen = generalize_SFILES(sfiles)
        sfiles_string_gen = ''.join(sfiles_gen)
        return sfiles_gen, sfiles_string_gen


def dfs(visited, flowsheet, current_node, sfiles_part, nr_pre_visited, ranks, nodes_position_setoffs,
        nodes_position_setoffs_cycle, special_edges, first_traversal, sfiles, node_insertion):
    """ 
    Depth first search implementation to traverse the directed graph from the virtual node
    Parameters
    ----------
    visited: list
        list of visited nodes
    flowsheet: networkx graph
        flowsheet as networkx graph.
    current_node: str
        current node in depth first search
    sfiles_part: list
        SFILES representation of a single traversal of the flowsheet
    nr_pre_visited: int
        counter variable for cycles
    ranks: dict
        ranks for branching decisions
    nodes_position_setoffs: dict
        counts the occurrences of outgoing and incoming cycles per node
    nodes_position_setoffs_cycle: dict
        counts the occurrences only of outgoing cycles per node
    special_edges: dict
        saves, whether an edge (in,out) is a cycle (number>1) or not (number=0)
    first_traversal: bool
        saves, whether the graph traversal is the first (True) or a further traversal (False)
    sfiles: list
        SFILES representation of the flowsheet
    node_insertion: str
        Node of previous traversal(s) where branch (first) ends, default is an empty string
    Returns
    -------
    sfiles: list
        SFILES representation of the flowsheet
    nr_pre_visited: int
        counter variable
    """

    # Remove all signal edges (except signals which are connected directly to the next unit operation)
    # before sfiles generation through DFS
    edge_infos = nx.get_edge_attributes(flowsheet, 'tags')
    edge_infos_signal1 = {k: v for k, v in edge_infos.items() if 'signal' in v.keys()}
    edge_infos_signal = {k: flatten(v['signal']) for k, v in edge_infos_signal1.items()
                         if v['signal'] == ['not_next_unitop']}
    # This maybe redundant
    edge_infos_signal1 = {k: flatten(v['signal']) for k, v in edge_infos_signal1.items() if v['signal']}

    flowsheet.remove_edges_from(edge_infos_signal.keys())

    if current_node == 'virtual':
        visited.add(current_node)
        # Branching decision requires ranks of nodes:
        neighbours = sort_by_rank(flowsheet[current_node], ranks, visited)
        for neighbour in neighbours:
            # Reset sfiles_part for every new traversal starting from 'virtual'
            sfiles_part = []
            sfiles_part, nr_pre_visited, node_insertion, sfiles = dfs(visited, flowsheet, neighbour, sfiles_part,
                                                                      nr_pre_visited, ranks, nodes_position_setoffs,
                                                                      nodes_position_setoffs_cycle, special_edges,
                                                                      first_traversal, sfiles, node_insertion='')
            # First traversal: sfiles_part is equal to sfiles
            # Further traversals: traversals, which are connected to the first traversal are inserted with '<&|...&|'
            # and independent subgraphs are inserted with 'n|'
            if first_traversal:
                sfiles.extend(sfiles_part)
                first_traversal = 0
            else:
                if not node_insertion == '':
                    sfiles_part.append('|')
                    sfiles_part.insert(0, '<&|')
                    pos = position_finder(nodes_position_setoffs, node_insertion, sfiles,
                                          nodes_position_setoffs_cycle, cycle=False)
                    # Insert the branch next to node_insertion
                    insert_element(sfiles, pos, sfiles_part)
                else:
                    sfiles.append('n|')
                    sfiles.extend(sfiles_part)

        # After last traversal, search for signal connections.
        if neighbour == neighbours[-1]:
            sfiles = insert_signal_connections(edge_infos_signal1, ranks, sfiles, nodes_position_setoffs_cycle,
                                               nodes_position_setoffs, special_edges)

    # DFS is performed if current_node is not already visited and not the artificially introduced virtual node.
    if current_node not in visited and not current_node == 'virtual':
        successors = list(flowsheet.successors(current_node))

        # New branching if current_node has more than one successor.
        if len(successors) > 1:
            sfiles_part.append('(' + current_node + ')')
            visited.add(current_node)

            # Branching decision requires ranks of nodes:
            neighbours = sort_by_rank(flowsheet[current_node], ranks, visited)
            for neighbour in neighbours:
                # Open a bracket
                if not neighbour == neighbours[-1]:
                    sfiles_part.append('[')

                if neighbour not in visited:
                    sfiles_part, nr_pre_visited, node_insertion, sfiles = dfs(visited, flowsheet, neighbour,
                                                                              sfiles_part, nr_pre_visited,
                                                                              ranks, nodes_position_setoffs,
                                                                              nodes_position_setoffs_cycle,
                                                                              special_edges, first_traversal,
                                                                              sfiles, node_insertion)
                    if sfiles_part[-1] == '[':
                        sfiles_part.pop()
                    elif not neighbour == neighbours[-1]:
                        sfiles_part.append(']')  # Close bracket/branch

                # If neighbor is already visited, that's a direct cycle. Thus, the branch brackets can be removed.
                elif first_traversal:
                    if sfiles_part[-1] == '[':
                        sfiles_part.pop()

                    nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part,
                                                                                      sfiles,
                                                                                      special_edges,
                                                                                      nodes_position_setoffs,
                                                                                      nodes_position_setoffs_cycle,
                                                                                      neighbour, current_node,
                                                                                      inverse_special_edge=False,
                                                                                      pos1_in_sfiles=False)

                elif not first_traversal:  # NEIGHBOR NODE IN PREVIOUS TRAVERSAL
                    if sfiles_part[-1] == '[':
                        sfiles_part.pop()

                    if bool(re.match(r'C-\d+\/[A-Z]+', current_node)):
                        flowsheet.add_edges_from([(current_node, neighbour,
                                                   {'tags': {'signal': ['not_next_unitop']}})])
                    # Only insert sfiles once. If there are multiple backloops to previous traversal,
                    # treat them as cycles.
                    # Insert a & sign where branch connects to node of previous traversal
                    elif node_insertion == '' and '(' + neighbour + ')' not in flatten(sfiles_part):
                        node_insertion = neighbour
                        pos = position_finder(nodes_position_setoffs, current_node, sfiles_part,
                                              nodes_position_setoffs_cycle, cycle=True)
                        insert_element(sfiles_part, pos, '&')
                        # Additional info: edge is a new incoming branch edge in SFILES
                        special_edges[(current_node, neighbour)] = '&'

                    elif '(' + neighbour + ')' in flatten(sfiles_part):
                        nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part,
                                                                                          sfiles,
                                                                                          special_edges,
                                                                                          nodes_position_setoffs,
                                                                                          nodes_position_setoffs_cycle,
                                                                                          neighbour,
                                                                                          current_node,
                                                                                          inverse_special_edge=True,
                                                                                          pos1_in_sfiles=False)

                    else:
                        nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part,
                                                                                          sfiles,
                                                                                          special_edges,
                                                                                          nodes_position_setoffs,
                                                                                          nodes_position_setoffs_cycle,
                                                                                          neighbour,
                                                                                          current_node,
                                                                                          inverse_special_edge=True,
                                                                                          pos1_in_sfiles=True)
                    # No bracket/branch closing

        # Only one successor, no branching
        elif len(successors) == 1:
            sfiles_part.append('(' + current_node + ')')
            visited.add(current_node)
            sfiles_part, nr_pre_visited, node_insertion, sfiles = dfs(visited, flowsheet, successors[0], sfiles_part,
                                                                      nr_pre_visited, ranks, nodes_position_setoffs,
                                                                      nodes_position_setoffs_cycle, special_edges,
                                                                      first_traversal, sfiles, node_insertion)
        # Dead end
        elif len(successors) == 0:
            visited.add(current_node)
            sfiles_part.append('(' + current_node + ')')

    # NODES OF PREVIOUS TRAVERSAL, this elif case is visited when there is no branching but node of previous traversal
    elif not current_node == 'virtual' and not first_traversal:

        # Incoming branches are inserted at mixing point in SFILES surrounded by <&|...&|
        # Only insert sfiles once. If there are multiple backloops to previous traversal, treat them as cycles.
        # TODO: Check if this is correct!
        if bool(re.match(r'C-\d+\/[A-Z]+', current_node)):
            for i in flowsheet.predecessors(current_node):
                if bool(re.match(r'C-\d+\/[A-Z]+', i)):
                    flowsheet.add_edges_from([(i, current_node, {'tags': {'signal': ['not_next_unitop']}})])
        elif node_insertion == '' and '(' + current_node + ')' in flatten(sfiles):
            # Insert a & sign where branch connects to node of previous traversal
            node_insertion = current_node
            last_node = last_node_finder(sfiles_part)
            pos = position_finder(nodes_position_setoffs, last_node, sfiles_part,
                                  nodes_position_setoffs_cycle, cycle=True)
            insert_element(sfiles_part, pos, '&')

            # Additional info: edge is a new incoming branch edge in SFILES
            special_edges[(last_node, current_node)] = '&'

        else:  # Incoming branches are referenced with a number, if there already is a node_insertion
            if '(' + current_node + ')' in flatten(sfiles_part):
                nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part, sfiles,
                                                                                  special_edges, nodes_position_setoffs,
                                                                                  nodes_position_setoffs_cycle,
                                                                                  current_node, node2='last_node',
                                                                                  inverse_special_edge=False,
                                                                                  pos1_in_sfiles=False)
            else:
                nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part, sfiles,
                                                                                  special_edges, nodes_position_setoffs,
                                                                                  nodes_position_setoffs_cycle,
                                                                                  current_node, node2='last_node',
                                                                                  inverse_special_edge=False,
                                                                                  pos1_in_sfiles=True)

    elif not current_node == 'virtual':
        nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part, sfiles,
                                                                          special_edges, nodes_position_setoffs,
                                                                          nodes_position_setoffs_cycle,
                                                                          current_node, node2='last_node',
                                                                          inverse_special_edge=False,
                                                                          pos1_in_sfiles=False)

    return sfiles_part, nr_pre_visited, node_insertion, sfiles


def insert_cycle(nr_pre_visited, sfiles_part, sfiles, special_edges, nodes_position_setoffs,
                 nodes_position_setoffs_cycle, node1, node2, inverse_special_edge, pos1_in_sfiles, signal=False):
    if pos1_in_sfiles:
        pos1 = position_finder(nodes_position_setoffs, node1, sfiles,
                               nodes_position_setoffs_cycle, cycle=False)
        nr_pre_visited += 1
        insert_element(sfiles, pos1, '<' + ('_' if signal else '') + str(nr_pre_visited))
    else:
        pos1 = position_finder(nodes_position_setoffs, node1, sfiles_part,
                               nodes_position_setoffs_cycle, cycle=False)
        nr_pre_visited += 1
        insert_element(sfiles_part, pos1, '<' + ('_' if signal else '') + str(nr_pre_visited))

    if node2 == 'last_node':
        node2 = last_node_finder(sfiles_part)
    pos2 = position_finder(nodes_position_setoffs, node2, sfiles_part,
                           nodes_position_setoffs_cycle, cycle=True)

    # According to SMILES notation, for two digit cycles a % sign is put before the number
    if nr_pre_visited > 9 and not signal:
        insert_element(sfiles_part, pos2, '%' + str(nr_pre_visited))
    else:
        insert_element(sfiles_part, pos2, ('_' if signal else '') + str(nr_pre_visited))

    # Additional info: edge is a cycle edge in SFILES
    if inverse_special_edge:
        special_edges[(node1, node2)] = nr_pre_visited
    else:
        special_edges[(node2, node1)] = nr_pre_visited

    return nr_pre_visited, special_edges, sfiles_part, sfiles


def SFILES_v2(flowsheet, sfiles, special_edges, remove_hex_tags=False):
    """
    Method to construct the SFILES 2.0:
    Additional information in edge attributes regarding connectivity (Top or bottom in distillation, absorption, or
    extraction columns)

    Parameters
    ----------
    flowsheet (nx graph): flowsheet as directed networkx graph.
    sfiles (list): SFILES representation of the flowsheet (still parsed)
    special_edges (dict): contains edge and cycle number>0 -> different notation of tags
    remove_hex_tags (bool): Whether to show the 'he' tags in the SFILES_v2
    (Conversion back and merging of hex nodes is not possible if this is set to true)

    Returns
    -------
    sfiles_v2 (list): SFILES representation (2.0) of the flowsheet (still parsed)
    
    """
    sfiles_v2 = sfiles.copy()
    edge_infos = nx.get_edge_attributes(flowsheet, "tags")
    if remove_hex_tags:  # only save the column related tags
        edge_infos = {k: {'col': v['col']} for k, v in edge_infos.items() if 'col' in v.keys()}
    edge_infos = {k: flatten(v.values()) for k, v in edge_infos.items()}  # merge he and col tags
    edge_infos = {k: v for k, v in edge_infos.items() if v}  # filter out empty tags lists, and
    if edge_infos:  # only if there are additional sfiles_info attributes
        # first assign edge attributes to nodes
        for e, at in edge_infos.items():
            # e: tuple (in_node name, out_node name); at: attribute
            if type(at) == str:
                # print('Info: Changed the tag of edge %s to type list with one element.'%str(e))
                at = [at]
            in_node = e[0]
            out_node = e[1]
            if e in special_edges:
                edge_type = str(special_edges[e])
            else:
                edge_type = 'normal'
            tags = '{' + '}{'.join(at) + '}'  # every single tag of that stream in own braces

            """  search position where to insert tag """
            if edge_type == 'normal':
                for s_idx, s in enumerate(sfiles_v2):
                    if s == '(' + out_node + ')':  # this is the out_node
                        sfiles_v2.insert(s_idx, tags)
                        break
            # a bit more complicated, we need to find the right & sign
            elif edge_type == '&':
                search_and = False
                for s_idx, s in enumerate(sfiles_v2):
                    if s == '(' + in_node + ')':  # this is the out_node
                        search_and = True
                        counter = 0
                    if search_and:
                        if s == '&' and counter == 0:  # no second branch within branch with <&| notation
                            sfiles_v2.insert(s_idx, tags)
                            break
                        if s == '&' and counter > 0: counter -= 1
                        if s == '<&|': counter += 1
            else:  # edge_type > 0 Recycle edge, so we search for the corresponding recycle number
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
    HI_eqs = []  # Heat integrated heat exchangers
    for s_idx, s in enumerate(sfiles_v2):
        if 'hex' in s and '/' in s:
            heatexchanger = s.split(sep='/')[0][1:]
            if heatexchanger not in HI_eqs:
                HI_eqs.append(heatexchanger)
    _HI_counter = 1
    for heatexchanger in HI_eqs:
        indices = [i for i, x in enumerate(sfiles_v2) if x.split(sep='/')[0][1:] == heatexchanger]
        for i in indices:
            previous = sfiles_v2[i]
            sfiles_v2[i] = [previous, '{' + str(_HI_counter) + '}']
        # flatten list
        sfiles_v2 = flatten(sfiles_v2)
        _HI_counter += 1

    # Store information about control structure in stream tag
    for s_idx, s in enumerate(sfiles_v2):
        if 'C' in s and '/' in s:
            insert_element(sfiles_v2, [s_idx], '{' + str(s.split(sep='/')[1][:-1]) + '}')
            sfiles_v2[s_idx] = s.split(sep='/')[0] + ')'

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
        if bool(re.match(r'\(.*?\)', s)):
            sfiles_gen[i] = s.split(sep='-')[0] + ')'

    return sfiles_gen


""" Helper functions """


def sort_by_rank(nodes_to_sort, ranks, visited=[]):
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
            else:
                nodes_sorted_dict[n] = ranks[n]

    # sorting
    nodes_sorted_dict = dict(sorted(nodes_sorted_dict.items(), key=lambda item: item[1]))
    nodes_sorted_dict_cycle = dict(sorted(nodes_sorted_dict_cycle.items(), key=lambda item: item[1]))

    # concatenate -> direct cycle nodes are visited first
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

    # Remove signal nodes before ranking, otherwise interoperability with SFILES2.0 cannot be ensured.
    edge_infos = nx.get_edge_attributes(flowsheet, 'tags')
    edge_infos_signal = {k: v for k, v in edge_infos.items() if 'signal' in v.keys()}
    edge_infos_signal = {k: flatten(v['signal']) for k, v in edge_infos_signal.items() if v['signal'] == ['not_next_unitop']}
    flowsheet_temp = flowsheet.copy()

    flowsheet_temp.remove_edges_from(edge_infos_signal.keys())

    # First generate subgraphs (different mass trains in flowsheet)
    _sgs = [flowsheet_temp.subgraph(c).copy() for c in nx.weakly_connected_components(flowsheet_temp)]
    # Sort subgraphs, such that larger subgraphs are used first
    _sgs.sort(key=lambda x: -len(list(x.nodes)))
    rank_offset = 0
    all_unique_ranks = {}

    for sg in _sgs:
        # 1. Morgan algorithm
        # Elements of the adjacency matrix show whether nodes are connected in the graph (1) or not (0)
        # Summing over the rows of the adjacency matrix results in the connectivity number of each node
        # The Morgan algorithm is performed via a matrix multiplication of the connectivity and the adjacency matrix.
        # This equals a summing of the connectivity values of the neighbour nodes for each node in a for-loop.

        undirected_graph = nx.to_undirected(sg)
        adjacency_matrix = nx.to_numpy_array(undirected_graph, dtype=np.int64)
        connectivity = sum(adjacency_matrix)
        node_labels = list(sg)
        unique_values_temp = 0
        counter = 0
        maximum_iteration = 0
        morgan_iter = connectivity @ adjacency_matrix

        # Morgan algorithm is stopped if the number of unique values is stable and maximum number of iteration is
        # reached. Maximum number of iteration is necessary since the number of unique values may not be stable for
        # e.g. cycle processes.
        while counter < 5 and maximum_iteration < 100:
            maximum_iteration += 1
            morgan_iter = morgan_iter @ adjacency_matrix
            unique_values = np.unique(morgan_iter).size
            if unique_values > unique_values_temp:
                unique_values_temp = unique_values
                morgan_iter_dict = dict(zip(node_labels, morgan_iter))
            else:
                counter += 1

            #if unique_values == unique_values_temp:
            #    counter += 1
            #else:
            #    unique_values_temp = unique_values
            #    morgan_iter_dict = dict(zip(node_labels, morgan_iter))

        # Assign ranks based on the connectivity values
        r = {key: rank for rank, key in enumerate(sorted(set(morgan_iter_dict.values())), 1)}
        ranks = {k: r[v] for k, v in morgan_iter_dict.items()}

        # use rank as keys
        k_v_exchanged = {}
        for key, value in ranks.items():
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
            dfs_trees = []
            # sorting rules to achieve unique ranks are described in the SFILES documentation
            if len(eq_ranked_nodes) > 1:
                for n in eq_ranked_nodes:
                    # construct depth first search tree for each node
                    dfs_tr = nx.dfs_tree(sg, source=n)
                    dfs_trees.append(dfs_tr)

                # Edges of DFS tree are sorted alphabetically. The numbering of the nodes is removed first (since it
                # should not change the generalized SFILES).
                sorted_edges = []
                for k in range(0, len(eq_ranked_nodes)):
                    edges = sorted(list(dfs_trees[k].edges), key=lambda element: (element[0], element[1]))
                    edges = [(k.split(sep='-')[0], v.split(sep='-')[0]) for k, v in edges]
                    sorted_edge = sorted(edges, key=lambda element: (element[0], element[1]))
                    sorted_edge = [i for sub in sorted_edge for i in sub]
                    sorted_edges.append(sorted_edge)

                dfs_trees_generalized = {eq_ranked_nodes[i]: sorted_edges[i] for i in range(0, len(eq_ranked_nodes))}

                # We sort the nodes by 4 criteria: Input/output/other node, number of successors in dfs_tree,
                # successors names (without numbering), node names with numbering
                sorted_eq_ranked_nodes = rank_by_dfs_tree(dfs_trees_generalized)

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
    indices = find_nested_indices(sfiles, '(' + node + ')')

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


def flatten(k):
    """
    Returns a flattened list
    Parameters
    ----------
    k: nested list
    
    Returns
    ----------
    l_flat: list 
        flat list
    """
    l_flat = []
    for i in k:
        if isinstance(i, list):
            l_flat.extend(flatten(i))
        else:
            l_flat.append(i)
    return l_flat


def find_nested_indices(li, node):
    temp_li = li.copy()
    indices = []
    while True:
        try:
            pos = temp_li.index(node)
            indices.append(pos)
            break
        except:  # we need to go one level deeper
            for idx, i in enumerate(temp_li):
                if node in flatten(i):
                    temp_li = i.copy()
                    indices.append(idx)
    return indices


def insert_element(lst, indices, value):
    if len(indices) == 1:
        lst.insert(indices[0] + 1, value)
    else:
        insert_element(lst[indices[0]], indices[1:], value)


def rank_by_dfs_tree(dfs_trees_generalized):
    """ 
    Sorts the nodes with equal ranks (still after application of morgan algorithm) 
    Criteria:
    1. Ranks: Output node < Input node < All other nodes
    2.1. Input nodes: The higher the number of succesors in dfs_tree the lower the rank -> first build long SFILES parts
    (if 1. did not yield unique ranks)
    2.2. Other nodes: The lower the number of succesors in dfs_tree the lower the rank -> short branches in brackets
    (if 1. did not yield unique ranks)
    3. Alphabetical comparison of successor names (if 1. & 2. did not yield unique ranks)
    4. Unit operations of equally ranked nodes are the same -> Considering node numbers of equally ranked nodes
    (if 1. & 2. & 3. did not yield unique ranks)
    
    Note: Criteria 4 implies that the node numbering matters in SFILES construction.
          Nevertheless, if we remove the numbers in SFILES (generalized SFILES), the SFILES will be independent of
          numbering. This is based on Criteria 3, which implies that all the successors are the same.

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
    signal_nodes = {}
    other_nodes = {}
    for n, s in dfs_trees_generalized.items():
        succ_str = ''.join(list(s))
        if 'prod' in n:
            # output node
            output_nodes[n] = (len(dfs_trees_generalized[n]), succ_str)

        elif succ_str.startswith('raw'):
            # input node
            input_nodes[n] = (len(dfs_trees_generalized[n]), succ_str)

        elif bool(re.match(r'C-\d+', n)):
            # Signal node
            signal_nodes[n] = (len(dfs_trees_generalized[n]), succ_str)
        else:
            # other node
            other_nodes[n] = (len(dfs_trees_generalized[n]), succ_str)

    # Sort all dicts first according list length (input/output: long is better, other nodes: short is better->
    # less in brackets), then generalized string alphabetically, then real node name (i.e. node number)
    # real node name (with numbering is only accessed if the generalized string is the same
    # -> graph structure is the same)
    sorted_nodes = []
    for d in [signal_nodes, output_nodes, input_nodes]:
        # 3 sort criteria in that order list length (- sign), then generalized string alphabetically, then node number
        sorted_nodes_sub = sorted(d, key=lambda k: (-d[k][0], d[k][1], int(re.split('-|/', k)[1])))
        sorted_nodes.extend(sorted_nodes_sub)  # implies the order of first output, then input, then other nodes
    # other nodes
    # 3 sort criteria in that order list length (+ sign), then generalized string alphabetically,  then node number
    sorted_nodes_sub = sorted(other_nodes,
                              key=lambda k: (other_nodes[k][0], other_nodes[k][1], int(re.split('-|/', k)[1])))
    sorted_nodes.extend(sorted_nodes_sub)  # implies the order of first output, then input, then other nodes

    return sorted_nodes


def insert_signal_connections(edge_infos_signal, ranks, sfiles, nodes_position_setoffs_cycle, nodes_position_setoffs,
                              special_edges):
    """
        Inserts signal connections in sfiles

        Parameters
        ----------
        edge_infos_signal: nested list
            contains information about signal edges
        sfiles: list
            list of strings
        ranks: dict
            ranks for branching decisions
        nodes_position_setoffs: dict
            counts the occurrences of outgoing and incoming cycles per node
        nodes_position_setoffs_cycle: dict
            counts the occurrences only of outgoing cycles per node
        special_edges: dict
            saves, whether an edge (in,out) is a cycle (number>1) or not (number=0)

        Returns
        ----------
        sfiles: list
        """
    nr_pre_visited_signal = 0
    res_list = [x[0] for x in edge_infos_signal.keys()]
    if res_list:
        res_list_sorted = sort_by_rank(res_list, ranks)
        edge_infos_signal = dict(
            sorted(edge_infos_signal.items(), key=lambda pair: res_list_sorted.index(pair[0][0])))

    if bool(edge_infos_signal):
        for k, v in edge_infos_signal:
            if edge_infos_signal[k, v][0]:
                nr_pre_visited_signal, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited_signal, sfiles,
                                                                                         sfiles,
                                                                                         special_edges,
                                                                                         nodes_position_setoffs,
                                                                                         nodes_position_setoffs_cycle,
                                                                                         v, k,
                                                                                         inverse_special_edge=False,
                                                                                         pos1_in_sfiles=False,
                                                                                         signal=True)
    return sfiles

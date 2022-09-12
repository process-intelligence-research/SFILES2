import random
import networkx as nx
import re
import numpy as np

random.seed(1)

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


def nx_to_SFILES(flowsheet, version, remove_hex_tags, canonical=True):
    """Converts a networkx graph to its corresponding SFILES notation.

    Parameters
    ----------
    flowsheet: networkx graph
        Process flowsheet as networkx graph.
    version: str, default='v1'
        SFILES version, either 'v1' or 'v2'.
    remove_hex_tags: bool
        Whether to show the 'he' tags in the SFILES_v2 (Conversion back and merging of hex nodes is not possible if
        this is set to true).
    
    Returns
    ----------
    sfiles_gen: list [str]
        Generalized SFILES representation of the flowsheet (parsed).
    sfiles_string_gen: str
        Generalized SFILES representation of flowsheet.
    """

    # Signal edges are removed from flowsheet graph as they are inserted later with recycle notation to SFILES.
    # Remove signal nodes before ranking, otherwise interoperability with SFILES2.0 cannot be ensured.
    # Edges of signals connected directly to the next unit operation shall not be removed, since they represent both
    # material stream and signal connection.
    flowsheet_wo_signals = flowsheet.copy()
    edge_information = nx.get_edge_attributes(flowsheet, 'tags')
    edge_information_signal = {k: flatten(v['signal']) for k, v in edge_information.items() if 'signal' in v.keys()
                               if v['signal']}
    edges_to_remove = [k for k, v in edge_information_signal.items() if v == ['not_next_unitop']]
    flowsheet_wo_signals.remove_edges_from(edges_to_remove)

    # Calculation of graph invariant / node ranks
    ranks = calc_graph_invariant(flowsheet_wo_signals)

    # Find initial nodes of graph. Initial nodes are determined by an in-degree of zero.
    init_nodes = [n for n, d in flowsheet_wo_signals.in_degree() if d == 0]
    # Sort the possible initial nodes for traversal depending on their rank.
    init_nodes = sort_by_rank(init_nodes, ranks, canonical=True)

    # Add an additional virtual node, which is connected to every initial node. Thus, one graph traversal is sufficient
    # to access every node in the graph.
    flowsheet_wo_signals.add_node('virtual')
    virtual_edges = [('virtual', i) for i in init_nodes]
    flowsheet_wo_signals.add_edges_from(virtual_edges)
    current_node = 'virtual'
    ranks['virtual'] = 0

    # Nodes in cycle-processes are not determined since their in_degree is greater than zero.
    # Thus, as long as not every node of flowsheet is connected to the virtual node, the node with the lowest rank
    # (which is not a outlet node) is connected to the virtual node.
    flowsheet_undirected = nx.to_undirected(flowsheet_wo_signals)
    connected_to_virtual = set(nx.node_connected_component(flowsheet_undirected, 'virtual'))
    not_connected = set(flowsheet_wo_signals.nodes) - connected_to_virtual
    while not_connected:
        rank_not_connected = sort_by_rank(not_connected, ranks, canonical=True)
        rank_not_connected = [k for k in rank_not_connected if flowsheet_wo_signals.out_degree(k) > 0]
        flowsheet_wo_signals.add_edges_from([('virtual', rank_not_connected[0])])
        connected_to_virtual = set(nx.node_connected_component(flowsheet_undirected, 'virtual'))
        not_connected = set(flowsheet_wo_signals.nodes) - connected_to_virtual

    # Initialization of variables.
    visited = set()
    sfiles_part = []
    nr_pre_visited = 0
    nodes_position_setoffs = {n: 0 for n in flowsheet_wo_signals.nodes}
    nodes_position_setoffs_cycle = {n: 0 for n in flowsheet_wo_signals.nodes}
    special_edges = {}

    # Graph traversal (depth-first-search dfs).
    sfiles_part, nr_pre_visited, node_insertion, sfiles = dfs(visited, flowsheet_wo_signals, current_node, sfiles_part,
                                                              nr_pre_visited, ranks, nodes_position_setoffs,
                                                              nodes_position_setoffs_cycle, special_edges,
                                                              edge_information_signal, first_traversal=True, sfiles=[],
                                                              node_insertion='', canonical=canonical)

    # Flatten nested list of sfile_part
    sfiles = flatten(sfiles)

    # SFILES Version 2.0:
    if version == 'v2':
        sfiles = SFILES_v2(sfiles, special_edges, edge_information, remove_hex_tags)

    # Generalization of SFILES (remove node numbering) as last step
    sfiles_gen = generalize_SFILES(sfiles)
    sfiles_string_gen = ''.join(sfiles_gen)

    return sfiles_gen, sfiles_string_gen


def dfs(visited, flowsheet, current_node, sfiles_part, nr_pre_visited, ranks, nodes_position_setoffs,
        nodes_position_setoffs_cycle, special_edges, edge_information, first_traversal, sfiles, node_insertion,
        canonical=True):
    """Depth first search implementation to traverse the directed graph from the virtual node.

    Parameters
    ----------
    visited: set
        Keeps track of visited nodes.
    flowsheet: networkx graph
        Process flowsheet as networkx graph.
    current_node: str
        Current node in depth first search.
    edge_information: dict
        Stores information about edge tags.
    sfiles_part: list [str]
        SFILES representation of a single traversal of the flowsheet.
    nr_pre_visited: int
        Counter variable for cycles.
    ranks: dict
        Ranks of nodes required for branching decisions.
    nodes_position_setoffs: dict
        Counts the occurrences of outgoing and incoming cycles per node.
    nodes_position_setoffs_cycle: dict
        Counts the occurrences only of outgoing cycles per node.
    special_edges: dict
        Saves, whether an edge (in, out) is a cycle (number>1) or not (number=0).
    first_traversal: bool
        Saves, whether the graph traversal is the first (True) or a further traversal (False).
    sfiles: list [str]
        SFILES representation of the flowsheet (parsed).
    node_insertion: str
        Node of previous traversal(s) where branch (first) ends, default is an empty string.
    canonical: bool, default=True
        Whether the resulting SFILES should be canonical (True) or not (False).

    Returns
    -------
    sfiles: list
        SFILES representation of the flowsheet (parsed).
    sfiles_part: list
        SFILES representation of the flowsheet of a single traversal.
    node_insertion: list
        Node of previous traversal(s) where branch (first) ends.
    nr_pre_visited: int
        Counter variable for cycles.
    """

    if current_node == 'virtual':
        visited.add(current_node)
        # Traversal order according to ranking of nodes.
        neighbours = sort_by_rank(flowsheet[current_node], ranks, visited, canonical=True)
        for neighbour in neighbours:
            # Reset sfiles_part for every new traversal starting from 'virtual', since new traversal is started.
            sfiles_part = []
            sfiles_part, nr_pre_visited, node_insertion, sfiles = dfs(visited, flowsheet, neighbour, sfiles_part,
                                                                      nr_pre_visited, ranks, nodes_position_setoffs,
                                                                      nodes_position_setoffs_cycle, special_edges,
                                                                      edge_information, first_traversal, sfiles,
                                                                      node_insertion='', canonical=canonical)
            # First traversal: sfiles_part is equal to sfiles.
            # Further traversals: traversals, which are connected to the first traversal are inserted with '<&|...&|'
            # and independent subgraphs are inserted with 'n|'.
            if first_traversal:
                sfiles.extend(sfiles_part)
                first_traversal = False
            else:
                if not node_insertion == '':
                    sfiles_part.append('|')
                    sfiles_part.insert(0, '<&|')
                    pos = position_finder(nodes_position_setoffs, node_insertion, sfiles, nodes_position_setoffs_cycle,
                                          cycle=False)
                    # Insert the branch next to node_insertion.
                    insert_element(sfiles, pos, sfiles_part)
                else:
                    sfiles.append('n|')
                    sfiles.extend(sfiles_part)

            # After last traversal, insert signal connections with recycle notation.
            if neighbour == neighbours[-1]:
                sfiles = insert_signal_connections(edge_information, sfiles, nodes_position_setoffs_cycle,
                                                   nodes_position_setoffs, special_edges)

    if current_node not in visited and not current_node == 'virtual':
        successors = list(flowsheet.successors(current_node))

        # New branching if current_node has more than one successor.
        if len(successors) > 1:
            sfiles_part.append('(' + current_node + ')')
            visited.add(current_node)
            # Branching decision according to ranking of nodes.
            neighbours = sort_by_rank(flowsheet[current_node], ranks, visited, canonical)
            for neighbour in neighbours:
                if not neighbour == neighbours[-1]:
                    sfiles_part.append('[')

                if neighbour not in visited:
                    sfiles_part, nr_pre_visited, node_insertion, sfiles = dfs(visited, flowsheet, neighbour,
                                                                              sfiles_part, nr_pre_visited,
                                                                              ranks, nodes_position_setoffs,
                                                                              nodes_position_setoffs_cycle,
                                                                              special_edges, edge_information,
                                                                              first_traversal, sfiles, node_insertion,
                                                                              canonical=canonical)
                    if not neighbour == neighbours[-1]:
                        sfiles_part.append(']')

                # If neighbor is already visited, that's a direct cycle. Thus, the branch brackets can be removed.
                elif first_traversal:
                    if sfiles_part[-1] == '[':
                        sfiles_part.pop()
                    # A material cycle is represented using the recycle notation with '<#' and '#'.
                    nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part,
                                                                                      sfiles, special_edges,
                                                                                      nodes_position_setoffs,
                                                                                      nodes_position_setoffs_cycle,
                                                                                      neighbour, current_node,
                                                                                      inverse_special_edge=False)

                elif not first_traversal:  # Neighbour node in previous traversal.
                    if sfiles_part[-1] == '[':
                        sfiles_part.pop()
                    # Only insert sfiles once. If there are multiple backloops to previous traversal,
                    # treat them as cycles. Insert a & sign where branch connects to node of previous traversal.
                    if node_insertion == '' and '(' + neighbour + ')' not in flatten(sfiles_part):
                        node_insertion = neighbour
                        pos = position_finder(nodes_position_setoffs, current_node, sfiles_part,
                                              nodes_position_setoffs_cycle, cycle=True)
                        insert_element(sfiles_part, pos, '&')
                        # Additional info: edge is a new incoming branch edge in SFILES.
                        special_edges[(current_node, neighbour)] = '&'

                    else:
                        nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part,
                                                                                          sfiles, special_edges,
                                                                                          nodes_position_setoffs,
                                                                                          nodes_position_setoffs_cycle,
                                                                                          neighbour, current_node,
                                                                                          inverse_special_edge=False)

        # Node has only one successor, thus no branching.
        elif len(successors) == 1:
            sfiles_part.append('(' + current_node + ')')
            visited.add(current_node)
            sfiles_part, nr_pre_visited, node_insertion, sfiles = dfs(visited, flowsheet, successors[0], sfiles_part,
                                                                      nr_pre_visited, ranks, nodes_position_setoffs,
                                                                      nodes_position_setoffs_cycle, special_edges,
                                                                      edge_information, first_traversal, sfiles,
                                                                      node_insertion, canonical=canonical)
        # Dead end.
        elif len(successors) == 0:
            visited.add(current_node)
            sfiles_part.append('(' + current_node + ')')

    # Nodes of previous traversal, this elif case is visited when there is no branching but node of previous traversal.
    elif not current_node == 'virtual':
        # Incoming branches are inserted at mixing point in SFILES surrounded by '<&|...&|'.
        # Only insert sfiles once. If there are multiple backloops to previous traversal, treat them as cycles.
        if node_insertion == '' and '(' + current_node + ')' in flatten(sfiles) and not first_traversal:
            # Insert a & sign where branch connects to node of previous traversal.
            node_insertion = current_node
            last_node = last_node_finder(sfiles_part)
            pos = position_finder(nodes_position_setoffs, last_node, sfiles_part, nodes_position_setoffs_cycle,
                                  cycle=True)
            insert_element(sfiles_part, pos, '&')
            # Additional info: edge is a new incoming branch edge in SFILES.
            special_edges[(last_node, current_node)] = '&'

        else:  # Incoming branches are referenced with the recycle notation, if there already is a node_insertion.
            nr_pre_visited, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited, sfiles_part, sfiles,
                                                                              special_edges, nodes_position_setoffs,
                                                                              nodes_position_setoffs_cycle,
                                                                              current_node, node2='last_node',
                                                                              inverse_special_edge=False)

    return sfiles_part, nr_pre_visited, node_insertion, sfiles


def insert_cycle(nr_pre_visited, sfiles_part, sfiles, special_edges, nodes_position_setoffs,
                 nodes_position_setoffs_cycle, node1, node2, inverse_special_edge, signal=False):
    """Inserts the cycle numbering of material recycles and signal connections according to the recycle notation.

    Parameters
    ----------
    nr_pre_visited: int
        Counter variable for cycles.
    sfiles_part: list [str]
        SFILES representation of a single traversal of the flowsheet.
    sfiles: list [str]
        SFILES representation of the flowsheet (parsed).
    special_edges: dict
        Saves, whether an edge (in, out) is a cycle (number>1) or not (number=0).
    nodes_position_setoffs: dict
        Counts the occurrences of outgoing and incoming cycles per node.
    nodes_position_setoffs_cycle: dict
        Counts the occurrences only of outgoing cycles per node.
    node1: str
        Node name of connection to incoming cycle.
    node2: str
        Node name of connection to outgoing cycle.
    inverse_special_edge: bool
        Inverts the entry in special_edges.
    signal: bool, default=False
        If true signal connection notation ('<_#' and '_#')is used.

    Returns
    ----------
    nr_pre_visited: int
        Counter variable for cycles.
    special_edges: dict
        Saves, whether an edge (in, out) is a cycle (number>1) or not (number=0).
    sfiles_part: list [str]
        SFILES representation of a single traversal of the flowsheet.
    sfiles: list [str]
        SFILES representation of the flowsheet (parsed).
    """

    # Check if incoming cycle is connected to node of current traversal or previous traversal.
    if '(' + node1 + ')' not in flatten(sfiles_part):
        pos1 = position_finder(nodes_position_setoffs, node1, sfiles, nodes_position_setoffs_cycle, cycle=False)
        nr_pre_visited += 1
        insert_element(sfiles, pos1, '<' + ('_' if signal else '') + str(nr_pre_visited))
    else:
        pos1 = position_finder(nodes_position_setoffs, node1, sfiles_part, nodes_position_setoffs_cycle, cycle=False)
        nr_pre_visited += 1
        insert_element(sfiles_part, pos1, '<' + ('_' if signal else '') + str(nr_pre_visited))

    if node2 == 'last_node':
        node2 = last_node_finder(sfiles_part)
    pos2 = position_finder(nodes_position_setoffs, node2, sfiles_part, nodes_position_setoffs_cycle, cycle=True)

    # According to SMILES notation, for two digit cycles a % sign is put before the number (not required for signals).
    if nr_pre_visited > 9 and not signal:
        insert_element(sfiles_part, pos2, '%' + str(nr_pre_visited))
    else:
        insert_element(sfiles_part, pos2, ('_' if signal else '') + str(nr_pre_visited))

    # Additional info: edge is marked as a cycle edge in SFILES.
    if inverse_special_edge:
        special_edges[(node1, node2)] = ('%' if nr_pre_visited > 9 else '') + str(nr_pre_visited)
    else:
        special_edges[(node2, node1)] = ('%' if nr_pre_visited > 9 else '') + str(nr_pre_visited)

    return nr_pre_visited, special_edges, sfiles_part, sfiles


def SFILES_v2(sfiles, special_edges, edge_information, remove_hex_tags=False):
    """Method to construct the SFILES 2.0: Additional information in edge attributes regarding connectivity
    (Top or bottom in distillation, absorption, or extraction columns, signal connections)

    Parameters
    ----------
    sfiles: list [str]
        SFILES representation of the flowsheet (parsed).
    special_edges: dict
        Contains edge and cycle number>0 -> different notation of tags.
    edge_information: dict
        Stores information about edge tags.
    remove_hex_tags: bool
        Whether to show the 'he' tags in the SFILES_v2
        (Conversion back and merging of hex nodes is not possible if this is set to true).

    Returns
    -------
    sfiles_v2: list [str]
        SFILES representation (2.0) of the flowsheet (parsed).
    """

    sfiles_v2 = sfiles.copy()
    if remove_hex_tags:  # Only save the column related tags.
        edge_information = {k: {'col': v['col']} for k, v in edge_information.items() if 'col' in v.keys()}
    edge_information = {k: flatten(v.values()) for k, v in edge_information.items()}  # Merge he and col tags.
    edge_information = {k: v for k, v in edge_information.items() if v}  # Filter out empty tags lists.

    if edge_information:
        # First assign edge attributes to nodes.
        for e, at in edge_information.items():
            # e: edge-tuple (in_node name, out_node name); at: attribute
            if type(at) == str:
                at = [at]
            in_node = e[0]
            out_node = e[1]
            if e in special_edges:
                edge_type = str(special_edges[e])
            else:
                edge_type = 'normal'
            tags = '{' + '}{'.join(at) + '}'  # Every single tag of that stream inserted in own braces.

            # Search position where to insert tag.
            if edge_type == 'normal':
                for s_idx, s in enumerate(sfiles_v2):
                    if s == '(' + out_node + ')':
                        sfiles_v2.insert(s_idx, tags)
                        break
            # Search the right & sign.
            elif edge_type == '&':
                search_and = False
                for s_idx, s in enumerate(sfiles_v2):
                    if s == '(' + in_node + ')':
                        search_and = True
                        counter = 0
                    if search_and:
                        if s == '&' and counter == 0:  # No second branch within branch with <&| notation.
                            sfiles_v2.insert(s_idx, tags)
                            break
                        if s == '&' and counter > 0:
                            counter -= 1
                        if s == '<&|':
                            counter += 1
            else:  # Edge_type > 0 recycle edge, so we search for the corresponding recycle number.
                for s_idx, s in enumerate(sfiles_v2):
                    if s == edge_type:
                        sfiles_v2.insert(s_idx, tags)
                        break

    # Heat integration tags: Heat integration is noted with a mix between recycle and connectivity notation,
    # e.g. (hex){1}...(hex){1}. Networkx node names indicate heat integration with slash, e.g. hex-1/1 and hex-1/2.
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
        sfiles_v2 = flatten(sfiles_v2)
        _HI_counter += 1

    # Store information about control structure in stream tag.
    for s_idx, s in enumerate(sfiles_v2):
        if 'C' in s and '/' in s:
            insert_element(sfiles_v2, [s_idx], '{' + str(s.split(sep='/')[1][:-1]) + '}')
            sfiles_v2[s_idx] = s.split(sep='/')[0] + ')'

    return sfiles_v2


def generalize_SFILES(sfiles):
    """Method to construct the generalized SFILES 2.0: Unit numbers (necessary in graph node names) are removed.

    Parameters
    ----------
    sfiles: list [str]
        SFILES representation of the flowsheet.

    Returns
    -------
    sfiles_gen: list [str]
        Generalized SFILES representation of the flowsheet.
    """

    sfiles_gen = sfiles.copy()
    for i, s in enumerate(sfiles_gen):
        if bool(re.match(r'\(.*?\)', s)):
            sfiles_gen[i] = s.split(sep='-')[0] + ')'

    return sfiles_gen


def sort_by_rank(nodes_to_sort, ranks, visited=[], canonical=True):
    """Method to sort the nodes by their ranks.

    Parameters
    ----------
    nodes_to_sort: list [str]
        List of nodes which will be sorted according to their rank.
    ranks: dict
        Node ranks calculated in calc_graph_invariant().
    visited: set
        List of already visited nodes.
    canonical: bool, default=True
        Whether the resulting SFILES should be canonical (True) or not (False).

    Returns
    -------
    nodes_sorted: list [str]
        Contains certain neighbour nodes in a sorted manner.
    """

    nodes_sorted_dict = {}
    nodes_sorted_dict_cycle = {}
    for n in nodes_to_sort:
        if n in ranks:
            if n in visited:
                nodes_sorted_dict_cycle[n] = ranks[n]
            else:
                nodes_sorted_dict[n] = ranks[n]

    nodes_sorted_dict = dict(sorted(nodes_sorted_dict.items(), key=lambda item: item[1]))
    nodes_sorted_dict_cycle = dict(sorted(nodes_sorted_dict_cycle.items(), key=lambda item: item[1]))

    # Concatenate -> direct cycle nodes are visited first.
    all_nodes_sorted = dict(nodes_sorted_dict_cycle, **nodes_sorted_dict)
    # Only take the sorted keys as list.
    nodes_sorted = list(all_nodes_sorted.keys())

    if not canonical:
        random.shuffle(nodes_sorted)

    return nodes_sorted


def calc_graph_invariant(flowsheet):
    """Calculates the graph invariant, which ranks the nodes for branching decisions in graph traversal.
    1. Morgan Algorithm based on: Zhang, T., Sahinidis, N. V., & Siirola, J. J. (2019).
    Pattern recognition in chemical process flowsheets. AIChE Journal, 65(2), 592-603.
    2. Equal ranks (e.g. two raw material nodes) are ranked by additional rules in function rank_by_dfs_tree.

    Parameters
    ----------
    flowsheet: networkx graph
        Process flowsheet as networkx graph.

    Returns
    -------
    Ranks: dict
        Ranks of graph nodes.
    """

    # First generate subgraphs (different mass trains in flowsheet).
    _sgs = [flowsheet.subgraph(c).copy() for c in nx.weakly_connected_components(flowsheet)]
    # Sort subgraphs, such that larger subgraphs are used first.
    _sgs.sort(key=lambda x: -len(list(x.nodes)))
    rank_offset = 0
    all_unique_ranks = {}

    for sg in _sgs:
        # Morgan algorithm
        # Elements of the adjacency matrix show whether nodes are connected in the graph (1) or not (0).
        # Summing over the rows of the adjacency matrix results in the connectivity number of each node.
        # The Morgan algorithm is performed via a matrix multiplication of the connectivity and the adjacency matrix.
        # This equals a summing of the connectivity values of the neighbour nodes for each node in a for-loop.
        undirected_graph = nx.to_undirected(sg)
        adjacency_matrix = nx.to_numpy_array(undirected_graph, dtype=np.int64)
        connectivity = sum(adjacency_matrix)
        node_labels = list(sg)
        unique_values_temp = 0
        counter = 0
        morgan_iter_dict = {}
        morgan_iter = connectivity @ adjacency_matrix

        # Morgan algorithm is stopped if the number of unique values is stable.
        while counter < 5:
            morgan_iter = morgan_iter @ adjacency_matrix
            unique_values = np.unique(morgan_iter).size
            if unique_values > unique_values_temp:
                unique_values_temp = unique_values
                morgan_iter_dict = dict(zip(node_labels, morgan_iter))
            else:
                counter += 1

        # Assign ranks based on the connectivity values.
        r = {key: rank for rank, key in enumerate(sorted(set(morgan_iter_dict.values())), 1)}
        ranks = {k: r[v] for k, v in morgan_iter_dict.items()}

        # Use rank as keys. Nodes with the same rank are appended to a list.
        k_v_exchanged = {}
        for key, value in ranks.items():
            if value not in k_v_exchanged:
                k_v_exchanged[value] = [key]
            else:
                k_v_exchanged[value].append(key)

        # 1. We first sort (ascending) the dict and afterwards create a nested list.
        k_v_exchanged_sorted = {k: k_v_exchanged[k] for k in sorted(k_v_exchanged)}
        ranks_list = []
        for key, value in k_v_exchanged_sorted.items():
            ranks_list.append(value)

        edge_information = nx.get_edge_attributes(flowsheet, 'tags')
        edge_information_col = {k: flatten(v['col']) for k, v in edge_information.items() if 'col' in v.keys() if
                                v['col']}

        # 2. We afterwards sort the nested lists (same rank). This is the tricky part of breaking the ties.
        for pos, eq_ranked_nodes in enumerate(ranks_list):
            # eq_ranked_nodes is a list itself. They are sorted, so the unique ranks depend on their names.
            dfs_trees = []
            # Sorting rules to achieve unique ranks are described in the SFILES documentation.
            if len(eq_ranked_nodes) > 1:
                for n in eq_ranked_nodes:
                    # Construct depth first search tree for each node.
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

                    edge_tags = []
                    for edge, tag in edge_information_col.items():
                        if edge[0] == eq_ranked_nodes[k] or edge[1] == eq_ranked_nodes[k]:
                            edge_tags.append(tag[0])

                    edge_tags = ''.join(sorted(edge_tags))
                    if edge_tags:
                        sorted_edge.insert(0, edge_tags)
                    sorted_edges.append(sorted_edge)

                dfs_trees_generalized = {eq_ranked_nodes[i]: sorted_edges[i] for i in range(0, len(eq_ranked_nodes))}

                # We sort the nodes by 4 criteria: Input/output/signal/other node, number of successors in dfs_tree,
                # successors names (without numbering), node names with numbering.
                sorted_eq_ranked_nodes = rank_by_dfs_tree(dfs_trees_generalized)

            else:
                sorted_eq_ranked_nodes = sorted(eq_ranked_nodes)
            ranks_list[pos] = sorted_eq_ranked_nodes

        # 3. We flatten the list and create the new ranks dictionary with unique ranks
        # (form: node:rank) starting with rank 1.
        flattened_ranks_list = flatten(ranks_list)
        unique_ranks = {n: r + 1 + rank_offset for r, n in enumerate(flattened_ranks_list)}

        # All unique ranks in separate dict.
        all_unique_ranks.update(unique_ranks)
        # Change rank offset in case there are subgraphs.
        rank_offset += len(list(sg.nodes))

    return all_unique_ranks


def position_finder(nodes_position_setoffs, node, sfiles, nodes_position_setoffs_cycle, cycle=False):
    """Returns position where to insert a certain new list element in sfiles list, adjusted by position setoffs.

    Parameters
    ----------
    nodes_position_setoffs: dict
        Counts the occurrences of outgoing and incoming cycles per node.
    node: str
        Node name for which position is searched.
    sfiles: list [str]
        SFILES representation of the flowsheet.
    nodes_position_setoffs_cycle: dict
        Counts the occurrences only of outgoing cycles per node.
    cycle: boolean, default=False
        Whether the format is of form # (outgoing cycle)
    
    Returns
    ----------
    pos: int 
        Position where to insert new element.
    """

    # If the node is not found, it is in a nested list: Function to find positions in nested list is utilized.
    indices = find_nested_indices(sfiles, '(' + node + ')')

    if cycle:
        # This ensures that # are always listed before <#.
        indices[-1] += nodes_position_setoffs_cycle[node]
        # This updates the node position setoffs for cycles only.
        nodes_position_setoffs_cycle[node] += 1
        # This updates the overall node position setoffs.
        nodes_position_setoffs[node] += 1
    else:
        indices[-1] += nodes_position_setoffs[node]
        # This updates the overall node position setoffs.
        nodes_position_setoffs[node] += 1

    return indices


def last_node_finder(sfiles):
    """Returns the last node in the sfiles list.
    Parameters
    ----------
    sfiles: list [str]
        SFILES representation of the flowsheet.

    Returns
    ----------
    last_node: str
        Name of last node.
    """

    last_node = ''

    for element in reversed(sfiles):
        if element.startswith('(') and element.endswith(')'):
            last_node = element[1:-1]
            break

    return last_node


def flatten(nested_list):
    """Returns a flattened list.

    Parameters
    ----------
    nested_list: list
        List of lists.
    
    Returns
    ----------
    l_flat: list 
        Flat list without nested lists.
    """

    flat_list = []
    for i in nested_list:
        if isinstance(i, list):
            flat_list.extend(flatten(i))
        else:
            flat_list.append(i)

    return flat_list


def find_nested_indices(nested_list, node):
    """Returns index of node in nested list.

    Parameters
    ----------
    nested_list: list
        List of lists.
    node: str
        Name of node.

    Returns
    ----------
    indices: list
        Flat list without nested lists.
    """

    temp_list = nested_list.copy()
    indices = []
    if node not in flatten(nested_list):
        raise KeyError('Node not in nested list!')
    while True:
        try:
            pos = temp_list.index(node)
            indices.append(pos)
            break
        except:
            for idx, i in enumerate(temp_list):
                if node in flatten(i):
                    temp_list = i.copy()
                    indices.append(idx)

    return indices


def insert_element(lst, indices, value):
    if len(indices) == 1:
        lst.insert(indices[0] + 1, value)
    else:
        insert_element(lst[indices[0]], indices[1:], value)


def rank_by_dfs_tree(dfs_trees_generalized):
    """Sorts the nodes with equal ranks (after application of morgan algorithm) according to the following criteria:
    1. Ranks: Signal node < Output node < Input node < All other nodes
    2.1. Input nodes: The higher the number of successors in dfs_tree the lower the rank. First build long SFILES parts.
    (if 1. did not yield unique ranks)
    2.2. Other nodes: The lower the number of successors in dfs_tree the lower the rank. Short branches in brackets.
    (if 1. did not yield unique ranks)
    3. Alphabetical comparison of successor names (if 1. & 2. did not yield unique ranks).
    4. Unit operations of equally ranked nodes are the same. Considering node numbers of equally ranked nodes.
    (if 1. & 2. & 3. did not yield unique ranks)
    
    Note: Criteria 4 implies that the node numbering matters in SFILES construction.
          Nevertheless, if we remove the numbers in SFILES (generalized SFILES), the SFILES will be independent of
          numbering. This is based on criteria 3, which implies that all the successors are the same.

    Parameters
    ----------
    dfs_trees_generalized: dict
        Equally ranked nodes with their respective dfs_trees (node names without unit numbers) in the flowsheet graph.

    Returns
    -------
    sorted_nodes: list
        List of sorted nodes with previously equal ranks.
    """

    output_nodes = {}
    input_nodes = {}
    signal_nodes = {}
    other_nodes = {}

    for n, s in dfs_trees_generalized.items():
        succ_str = ''.join(list(s))

        if 'prod' in n:
            output_nodes[n] = (len(dfs_trees_generalized[n]), succ_str)
        elif 'raw' in n:
            input_nodes[n] = (len(dfs_trees_generalized[n]), succ_str)
        elif bool(re.match(r'C-\d+', n)):
            signal_nodes[n] = (len(dfs_trees_generalized[n]), succ_str)
        else:
            other_nodes[n] = (len(dfs_trees_generalized[n]), succ_str)

    # Sort all dicts first according list length (input/output: long is better, other nodes: short is better->
    # less in brackets), then generalized string alphabetically, then real node name (i.e. node number).
    # Real node name with numbering is only accessed if the generalized string (graph structure) is the same.
    sorted_nodes = []
    for d in [signal_nodes, output_nodes, input_nodes]:
        # 3 sort criteria in that order list length (- sign), then generalized string alphabetically, then node number.
        sorted_nodes_sub = sorted(d, key=lambda k: (-d[k][0], d[k][1], int(re.split('[-/]', k)[1])))
        sorted_nodes.extend(sorted_nodes_sub)  # Implies the order of first signal then output and input nodes.

    # Other nodes: 3 sort criteria in that order list length (+ sign), then generalized string alphabetically,
    # then node number
    sorted_nodes_sub = sorted(other_nodes,
                              key=lambda k: (other_nodes[k][0], other_nodes[k][1], int(re.split('[-/]', k)[1])))
    sorted_nodes.extend(sorted_nodes_sub)  # Implies the order of first signal, then output, input, and other nodes.

    return sorted_nodes


def insert_signal_connections(edge_infos_signal, sfiles, nodes_position_setoffs_cycle, nodes_position_setoffs,
                              special_edges):
    """Inserts signal connections in SFILES.

    Parameters
    ----------
    edge_infos_signal: dict
        Contains information about signal edges.
    sfiles: list [str]
        SFILES representation of the flowsheet (parsed).
    nodes_position_setoffs: dict
        Counts the occurrences of outgoing and incoming cycles per node.
    nodes_position_setoffs_cycle: dict
        Counts the occurrences only of outgoing cycles per node.
    special_edges: dict
        Saves, whether an edge (in,out) is a cycle (number>1) or not (number=0).

    Returns
    ----------
    sfiles: list
        SFILES list including signal connections.
    """

    nr_pre_visited_signal = 0
    signal_nodes = [k[0] for k in edge_infos_signal.keys()]
    sfiles_flattened = flatten(sfiles)
    pos = {}

    if signal_nodes:
        nodes_position_setoffs_temp = nodes_position_setoffs.copy()
        nodes_position_setoffs_cycle_temp = nodes_position_setoffs_cycle.copy()
        for k in signal_nodes:
            pos.update({position_finder(nodes_position_setoffs, k, sfiles_flattened,
                                        nodes_position_setoffs_cycle)[0]: k})

        # Reset node_position_setoffs since they are manipulated by position_finder.
        nodes_position_setoffs_cycle = nodes_position_setoffs_cycle_temp.copy()
        nodes_position_setoffs = nodes_position_setoffs_temp.copy()

        # TODO: Check if this works!
        #nodes_position_setoffs_cycle = nodes_position_setoffs_cycle.fromkeys(nodes_position_setoffs_cycle, 0)
        #nodes_position_setoffs = nodes_position_setoffs_cycle.fromkeys(nodes_position_setoffs, 0)
        for k, v in special_edges.items():
            if v == '&':
                nodes_position_setoffs[k[1]] = 0

        # Sort the signal nodes according to their position in the SFILES.
        signal_nodes_sorted = dict(sorted(pos.items()))
        signal_nodes_sorted = list(signal_nodes_sorted.values())

        edge_infos_signal = dict(sorted(edge_infos_signal.items(), key=lambda x: signal_nodes_sorted.index(x[0][0])))

    for k, v in edge_infos_signal:
        nr_pre_visited_signal, special_edges, sfiles_part, sfiles = insert_cycle(nr_pre_visited_signal, sfiles, sfiles,
                                                                                 special_edges, nodes_position_setoffs,
                                                                                 nodes_position_setoffs_cycle, v, k,
                                                                                 inverse_special_edge=False,
                                                                                 signal=True)

    return sfiles

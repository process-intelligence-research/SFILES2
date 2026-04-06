"""
Defines function for comparing if two flowsheets are the same.
This can be useful for debugging changes on large datasets.
"""

from typing import Tuple, Dict
from copy import deepcopy
from itertools import permutations, product

import networkx as nx
from networkx.algorithms.isomorphism import is_isomorphic

from Flowsheet_Class.flowsheet import Flowsheet

def edit_graph(graph: nx.MultiDiGraph):
    """Helper for isomorphism test.

    Adds a "_type" attribute for each node of the graph for the
    graph isomorphism test. It is the name of the node without the number
    (example: hex-1 --> hex). If it is a control unit, we also include
    the contents after the "/" (example: C-1/LC --> C/LC).
    """
    for node, attrs in graph.nodes(data=True):
        if "/" in node:
            if not node.split("/")[1].isnumeric():
                # Control structure, we must distinguish it:
                attrs["_type"]= node.split("-")[0] + "/" + node.split("/")[1]
            else:
                attrs["_type"] = node.split("-")[0]
        else:
            attrs["_type"] = node.split("-")[0]
    return graph

def edit_flowsheet(flowsheet: Flowsheet):
    """Prepares a Flowsheet object for the check_isomorphism function.
    NOTE: This modified the Flowsheet in-place. If you need to make sure
    you keep the original version, copy it first (``from copy import deepcopy;
    backup = deecopy(flowsheet)``) 

    Creates 4 graphs, after merging and splitting heat integration (HI) nodes
    twice (which is useful for also seeing if merging and splitting of HI nodes
    is working correctly). Some attributes are added to the nodes for the 
    isomorphism test.

    For two flowsheet graphs to be isomorph, it is necessary that both their
    coupled and decoupled versions be isomorph. This is because the HEX 
    connections must be distinguished, but their numbering is arbitrary
    """
    flowsheet.merge_HI_nodes()
    gm1 = deepcopy(flowsheet.state)
    flowsheet.split_HI_nodes()
    gs1 = deepcopy(flowsheet.state)
    # Do it again so that we can test if multiple merges and splits won't break anything:
    flowsheet.merge_HI_nodes()
    gm2 = deepcopy(flowsheet.state)
    flowsheet.split_HI_nodes()
    gs2 = deepcopy(flowsheet.state)
    
    graph_list = [gm1, gs1, gm2, gs2]
    for g in graph_list:
        g = edit_graph(g)
    return graph_list

def node_match(n1_attrs: Dict, n2_attrs: Dict):
    """
    Checks whether two nodes are analogous (same unit operation type)
    """
    return n1_attrs["_type"] == n2_attrs["_type"]

def edge_match(edge_dict_1: Dict[int, Dict], edge_dict_2: Dict[int, Dict]):
    """
    Checks if two sets of edges are analogous (identical tags, except 
    for "he" tags, which are dealt with indirectly, by checking if both 
    merged and split HI nodes are identical)
    """
    def compare_edge_tags(attrs1: Dict, attrs2: Dict):
        # We don't check for HEX 1 or 2 tags because the numerical
        # value of the tag is arbitrary. However, integration HEXs
        # will be handled in the main isomorphism test because we
        # will check both the graph with merged and split HI nodes. 
        
        col1 = attrs1.get("tags", dict()).get("col", [])
        col2 = attrs2.get("tags", dict()).get("col", [])
        
        if sorted(col1) != sorted(col2): return False

        sig1 = attrs1.get("tags", dict()).get("signal", [])
        sig2 = attrs2.get("tags", dict()).get("signal", [])
        
        if sorted(sig1) != sorted(sig2): return False

        return True

    l1 = len(edge_dict_1)
    l2 = len(edge_dict_2)
    if l1 != l2: return False
    if l1 == 1:
        # Test
        attrs1 = list(edge_dict_1.values())[0]
        attrs2 = list(edge_dict_2.values())[0]
        return compare_edge_tags(attrs1, attrs2)
        
    else:
        # Check all possible combinations and see if one matches...
        """
        We may have something like:
        edge_dict1 = {0: ..., 1: ..., 2: ...}
        edge_dict2 = {0: ..., 1: ..., 2: ...}

        We will have the following possible combinations:
        (a possibility being a list of associations between edges from edge_dict1 and edge_dict2)
        (possibility # : [(key_from_edge1, key_from_edge2), (another_key_from_edge1, another_key_from_edge2), ...])
        possibility 1 : [(0, 0), (1, 1), (2, 2)]
        possibility 2 : [(0, 1), (1, 0), (2, 2)]
        possibility 3 : [(0, 2), (1, 0), (2, 1)]
        ...

        This is analogous to:
        possibility # = [key_from_edge2, another_key_from_edge2, ...],
        where we associate each entry from the list to keys 0, 1 and 2 from edge_dict1:
        --> [(0, key_from_edge2), (1, another_key_from_edge2), ...]

        We can get a list of these possibilities with itertools.permutations(edge_dict2.keys())

        """
        edge_1_keys = list(edge_dict_1.keys())  # [0, 1, 2]
        possibilities = permutations(list(edge_dict_2.keys())) # [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]
        condition = False
        for possibility in possibilities:
            couples = [
                (edge_1_keys[i], possibility[i])
                for i in range(len(possibility))
            ]
            for couple in couples:
                key1, key2 = couple
                attrs1 = edge_dict_1[key1]
                attrs2 = edge_dict_2[key2]
                if not compare_edge_tags(attrs1, attrs2):
                    break
            else:
                # If we got here, we didn't break from the loop:
                # all compare_edge_tags tests were True --> isomorph.
                condition = True

            if condition:
                return True

        else:
            # If we got here, we never returned,
            # meaning our condition is still False
            # Must return False
            return False

def check_graph_isomorphism(g1: nx.MultiDiGraph, g2: nx.MultiDiGraph):
    """
    Checks if two networkx.MultiDiGraphs are isomorphic, using 
    the node_match and edge_match functions defined in this module.
    """
    return is_isomorphic(g1, g2, node_match=node_match, edge_match=edge_match)

def check_isomorphism(f1: Flowsheet, f2: Flowsheet, check_HI_nodes: bool = True):
    """
    Checks if two flowsheets f1 and f2 are isomorphic.
    Optionally, also checks if merging and splitting the 
    heat integration (HI) nodes twice changed anything.
    """
    gm1a, gs1a, gm1b, gs1b = edit_flowsheet(f1)
    gm2a, gs2a, _, _ = edit_flowsheet(f2)
    if not is_isomorphic(gm1a, gm2a, node_match=node_match, edge_match=edge_match):
        return False
    if not is_isomorphic(gs1a, gs2a, node_match=node_match, edge_match=edge_match):
        return False
    if check_HI_nodes:
        # Checking if merging and splitting is working:
        if not is_isomorphic(gm1a, gm1b, node_match=node_match, edge_match=edge_match):
            return False
        if not is_isomorphic(gs1a, gs1b, node_match=node_match, edge_match=edge_match):
            return False
    return True

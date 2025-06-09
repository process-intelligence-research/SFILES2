import re
import warnings

import networkx as nx
from typing import Literal

from .nx_to_sfiles import nx_to_SFILES
from .OntoCape_SFILES_mapping import OntoCape_SFILES_map
from .utils_visualization import (
    create_stream_table,
    create_unit_table,
    plot_flowsheet_nx,
    plot_flowsheet_pyflowsheet,
)

try:
    from PID_generation.PID_generator import Generate_flowsheet
    PID_generator = True
except ImportError:
    PID_generator = False


class Flowsheet:
    """This is a class to create flowsheets represented as a graphs.

    Parameters
    ----------
    self.state: networkx graph
        Stores the process flowsheet represented as networkx graph.
    self.sfiles: str
        String representation of the process flowsheet.
    self.sfiles_list: list [str]
        List of SFILES tokens (parsed SFILES string).
    OntoCapeConformity: bool, default=False
        Specify as True when using OntoCape vocabulary (should be the standard in future).
    sfiles_in: str
        SFILES string input.
    sfiles_list_in: list [str]
        Parsed SFILES string input.
    xml_file: str
        Path to xml file that can be read with nx.read_graphml method.
    """

    def __init__(self, OntoCapeConformity=False, sfiles_in=None, sfiles_list_in=None, xml_file=None):
        self.OntoCapeConform = OntoCapeConformity
        self.sfiles = sfiles_in
        self.sfiles_list = sfiles_list_in
        self.flowsheet_SFILES_names = None
        self.state = nx.DiGraph()  # Default initialization of the flowsheet as a nx Graph
        if xml_file:  # ToDo mapping xml digitization group -> OntoCape vocab
            self.state = nx.read_graphml(xml_file)
        elif sfiles_in:
            self.create_from_sfiles()
        elif sfiles_list_in:
            self.create_from_sfiles()

    def add_unit(self, unique_name:str=None, **kwargs):
        """This method adds a new unit as a new node to the existing flowsheet-graph.

        Parameter
        ---------
        unique_name: str, default=None
            Unique name of the unit, e.g. 'hex-1'.
        kwargs:
            Parameters of new unit as node attributes.
        """

        self.state.add_node(unique_name, **kwargs)

    def add_stream(self, node1, node2, tags={"he": [], "col": []}):
        """Method adds a stream as an edge to the existing flowsheet graph, thereby connecting two unit operations
        (nodes).

        Parameters
        ----------
        node1: str
            Unique name of the node with the unit where the stream origins.
        node2: str
            Unique name of the node with the unit where the stream is fed into.
        tags: dict
            Tags for that stream, of following form: {'he':[],'col':[]}, i.e heat exchanger related tags
            (hot_in,cold_out, ...) and column related tags (t_out,b_out, ...).
        """

        self.state.add_edge(node1, node2, tags=tags)

    def create_from_sfiles(self, sfiles_in="", overwrite_nx=False, merge_HI_nodes=True):
        """Function to read SFILES (parsed or unparsed) and creates units (without child objects) and streams. Result is
         a flowsheet with units with categories and specific categories. Converts the SFILES string to a networkx graph.

        Parameters
        ----------
        sfiles_in: str
            SFILES string input.
        overwrite_nx: bool, default=False
            Defines whether existing networkx graph is overwritten or not.
        merge_HI_nodes: bool, default=True
            If true, merges heat integrated hex nodes into one node and creates connectivity tags, so it is possible to
            split nodes again later.
        """

        # Error handling.
        if not self.sfiles_list:  # Should be empty.
            if self.sfiles:
                self.sfiles_list = self.SFILES_parser()
            else:
                if sfiles_in:
                    self.sfiles = sfiles_in
                    self.sfiles_list = self.SFILES_parser()
                else:
                    raise ValueError("Empty SFILES string! Set the attribute self.sfiles or specify input argument "
                                     "'sfiles_in' or 'sfiles_list_in' before using this method.")
        else:
            if self.sfiles:
                # print('Overwriting the current self.sfiles_list')
                self.sfiles_list = self.SFILES_parser()
            else:
                if sfiles_in:
                    self.sfiles = sfiles_in
                    self.sfiles_list = self.SFILES_parser()
                else:  # SFILES list already set.
                    pass

        # Make sure we start with an empty graph, overwriting possible.
        if not nx.classes.is_empty(self.state):
            if overwrite_nx:
                self.state = nx.DiGraph()
            else:
                raise ValueError("There already exists a nx graph. If you wish to override it, "
                                 "specify 'override_nx=True'")

        # Renumbering of generalized SFILES is necessary for the graph construction.
        nodes = self.renumber_generalized_SFILES()

        # Converting SFILES to graph.
        edges = []
        cycles = []
        tags = []
        last_ops = []  # Tracks already visited unit operations.
        pattern_node = r"\(.*?\)"  # Regex pattern for a node (i.e. unit operation/control unit)
        last_index = len(self.sfiles_list) - 1

        for token_idx, token in enumerate(self.sfiles_list):
            last_ops.append(token)

            # If current token is a node, search the connections that are associated with the node.
            if bool(re.match(pattern_node, token)):
                step = 0
                branches = 0

                while not (token_idx + step) == last_index:
                    step += 1

                    # Next list element is a node, thus it is a normal connection (no branches).
                    if not branches and bool(re.match(pattern_node, self.sfiles_list[token_idx + step])):
                        edges.append((token[1:-1], self.sfiles_list[token_idx + step][1:-1], {"tags": tags}))
                        tags = []
                        break

                    # Next list element is node, open branch.
                    elif branches and bool(re.match(pattern_node, self.sfiles_list[token_idx + step])):
                        edges.append((token[1:-1], self.sfiles_list[token_idx + step][1:-1], {"tags": tags}))
                        tags = []
                        branches -= 1

                    # Cycle: next list element is a single digit or a multiple digit number of form %##.
                    elif bool(re.match(r"^[%_]?\d+", self.sfiles_list[token_idx + step])):
                        cyc_nr = re.findall(r"^[%_]?\d+", self.sfiles_list[token_idx + step])[0]
                        cycles.append((cyc_nr, tags))
                        tags = []

                    # Branch opens. Looping through the branch until it is terminated.
                    elif self.sfiles_list[token_idx + step] == "[":
                        branches = 1
                        found = False
                        while not (token_idx + step) == last_index:
                            step += 1
                            if not found and bool(re.match(pattern_node, self.sfiles_list[token_idx + step])):
                                edges.append((token[1:-1], self.sfiles_list[token_idx + step][1:-1], {"tags": tags}))
                                tags = []
                                found = True
                            # If next token in sfiles_list is '[', a branch inside a branch is present.
                            if self.sfiles_list[token_idx + step] == "[":
                                branches += 1
                            # A branch inside a branch closes.
                            elif branches > 1 and self.sfiles_list[token_idx + step] == "]":
                                branches -= 1
                            # The first opened branch (==1) closes and will cause the exit of the while loop of branch.
                            elif branches == 1 and self.sfiles_list[token_idx + step] == "]":
                                branches -= 1
                                tags = []
                                break
                            # Tags in SFILES v2 in branch (usually the first token after branching)
                            elif bool(re.match(r"{.*?}", self.sfiles_list[token_idx + step])):
                                # Tags that are used for heat integration are not required
                                # (those are incorporated in node names)
                                # Branches needs to be 1 otherwise the tags of subbranches might be added
                                if not bool(re.match(r"^[0-9]+$", self.sfiles_list[token_idx + step][1:-1])) \
                                        and branches == 1:
                                    tags.append(self.sfiles_list[token_idx + step][1:-1])

                    # New incoming branch.
                    elif self.sfiles_list[token_idx + step] == "<&|":
                        # Increase steps until the corresponding | or &| is reached and continue looking for
                        # connections of node.
                        _continue = 1
                        while _continue:
                            step += 1
                            if self.sfiles_list[token_idx + step] == "<&|":
                                _continue += 1
                            if self.sfiles_list[token_idx + step] == "|" or self.sfiles_list[token_idx + step] == "&|":
                                _continue -= 1

                    # Inside an incoming branch |, &| can occur on this level of if clauses.
                    # Find the node the incoming branch is leading to and add the connection.
                    elif self.sfiles_list[token_idx + step] == "&" or self.sfiles_list[token_idx + step] == "&|":
                        # Run backwards through last operations, search for unit operations,
                        # but ignore everything if its token in this or another incoming branch.
                        break_while = False
                        if self.sfiles_list[token_idx + step] == "&|":
                            # Only break searching for connections, when the incoming branch has no branches itself.
                            break_while = True
                        _ignore = 1
                        for e in reversed(last_ops):
                            if e == "<&|":
                                _ignore -= 1
                            if e == "|" or e == "&|":
                                _ignore += 1
                            if not _ignore and bool(re.match(pattern_node, e)):
                                edges.append((token[1:-1], e[1:-1], {"tags": tags}))
                                tags = []
                                break
                        if break_while:
                            break

                    # Tags in SFILES 2.0.
                    elif bool(re.match(r"{.*?}", self.sfiles_list[token_idx + step])):
                        # Tags that are used for heat integration are not required
                        # (those are incorporated in node names).
                        if not bool(re.match(r"^[0-9]+$", self.sfiles_list[token_idx + step][1:-1])):
                            tags.append(self.sfiles_list[token_idx + step][1:-1])

                    elif self.sfiles_list[token_idx + step] == "|":
                        break
                    elif self.sfiles_list[token_idx + step] == "]":
                        break
                    elif self.sfiles_list[token_idx + step] == "n|":
                        break

        for cycle_connection in cycles:
            # Determine index of cycle number in SFILES list and find the corresponding previous unit operation.
            cycle_pos = self.sfiles_list.index(cycle_connection[0])
            pre_op = list(filter(re.compile(pattern_node).match, self.sfiles_list[0: cycle_pos + 1]))[-1]

            # Search for the cycle destination ('<#' or '<_#') and add connection to unit operation that <# refers to.
            if "_" in cycle_connection[0]:
                number = re.findall(r"\d+", cycle_connection[0])
                cycle_tgt = self.sfiles_list.index("<_" + number[0])
                for k in range(0, cycle_tgt):
                    if bool(re.match(pattern_node, self.sfiles_list[cycle_tgt - k])):
                        cycle_op = self.sfiles_list[cycle_tgt - k]
                        edges_wo_tags = [x[0:2] for x in edges]
                        if (pre_op[1:-1], cycle_op[1:-1]) in edges_wo_tags:
                            edges.append((pre_op[1:-1], cycle_op[1:-1], {"tags": "next_unitop"}))
                        else:
                            edges.append((pre_op[1:-1], cycle_op[1:-1], {"tags": "not_next_unitop"}))
                        break
            else:
                number = re.findall(r"\d+", cycle_connection[0])
                cycle_tgt = self.sfiles_list.index("<" + number[0])
                for k in range(0, cycle_tgt + 1):
                    if bool(re.match(pattern_node, self.sfiles_list[cycle_tgt - k])):
                        cycle_op = self.sfiles_list[cycle_tgt - k]
                        edges.append((pre_op[1:-1], cycle_op[1:-1], {"tags": cycle_connection[1]}))
                        break

        # In this next section we loop through the nodes and edges lists and create the flowsheet with all unit and
        # stream objects. Please note that add_unit should not be called with initialize_child=True because
        # self.map_SFILES_to_Ontocape() only changes the state attribute but not the child objects.

        for node in nodes:
            name = node[1:-1]
            self.add_unit(unique_name=name)

        for connection in edges:
            # Adjust tags: tags:[..] to tags:{'he':[..],'col':[..]}
            # Null at the moment is used in Aspen/DWSim graphs for missing hex tags
            regex_he = re.compile(r"(hot.*|cold.*|[0-9].*|Null)")
            regex_col = re.compile(r"(tout|tin|bout|bin)")
            regex_signal = re.compile(r"not_next_unitop|next_unitop")
            old_tags = connection[2]["tags"]
            tags = {"he": [m.group(0) for k in old_tags for m in [regex_he.search(k)] if m],
                    "col": [m.group(0) for k in old_tags for m in [regex_col.search(k)] if m],
                    "signal": [m.group(0) for m in [regex_signal.search(str(old_tags))] if m]}
            self.add_stream(connection[0], connection[1], tags=tags)

        # Finally, the current self.state is not according to the OntoCape naming conventions so we map it back.
        if self.OntoCapeConform:
            self.map_SFILES_to_Ontocape(merge_HI_nodes)
        elif merge_HI_nodes:
            self.merge_HI_nodes()

    def create_from_nx(self, initial_flowsheet):
        """Method to initialize the flowsheet from an already existing nx-Graph.

        Parameters
        ----------
        initial_flowsheet: networkx graph
            Already existing networkx-Graph, default case: initialized with one feed-node ('IO-1'),
            an unprocessed-node ('X-1') and a connecting edge with stream data.
        """

        self.state = initial_flowsheet

    def convert_to_sfiles(self, version="v2", remove_hex_tags=True, canonical=True):
        """Method to convert the flowsheet nx graph to string representation SFILES. Returns an SFILES string and a
        parsed list of the SFILES tokens.

        Parameters
        ----------
        version: str, default='v2'
            Either v1 or v2. SFILES v2 contains more information regarding connectivity.
        remove_hex_tags: bool
            Whether to show heat exchanger tags in SFILES v2.
        """

        if self.OntoCapeConform:
            self.map_Ontocape_to_SFILES()  # sets self.flowsheet_SFILES_names
        else:
            # Does not modify self.state in case there are no multi-stream hex nodes, but already HI nodes
            # in hex-#/# notation
            self.split_HI_nodes()
            self.flowsheet_SFILES_names = self.state.copy()
        self.sfiles_list, self.sfiles = nx_to_SFILES(self.flowsheet_SFILES_names, version, remove_hex_tags, canonical)

    def create_random_flowsheet(self, add_sfiles=True):
        """This methods creates a random flowsheet. The specification for the random flowsheet is created in a separate
        class in the folder RandomFlowsheetGen_OC.

        Parameters
        ----------
        add_sfiles: bool, default=True
            True if SFILES representation should be added.
        """
        if PID_generator:
            random_flowsheet = Generate_flowsheet()

            for name in random_flowsheet.nodes:
                self.add_unit(unique_name=name)

            for connection in random_flowsheet.edges:
                # Adjust tags: tags:[..] to tags:{'he':[..],'col':[..]}
                regex_he = re.compile(r"(hot.*|cold.*|[0-9].*)")
                regex_col = re.compile(r"(tout|tin|bout|bin)")
                regex_signal = re.compile(r"not_next_unitop|next_unitop")
                old_tags = connection[2]["tags"]
                tags = {"he": [m.group(0) for k in old_tags for m in [regex_he.search(k)] if m],
                        "col": [m.group(0) for k in old_tags for m in [regex_col.search(k)] if m],
                        "signal": [m.group(0) for m in [regex_signal.search(str(old_tags))] if m]}
                self.add_stream(connection[0], connection[1], tags=tags)
            if add_sfiles:
                self.convert_to_sfiles(version="v2")

    def visualize_flowsheet(self, figure=True, plot_with_stream_labels=True, table=True, plot_as_pfd=True,
                            pfd_block=True, decimals=3, pfd_path="plots/flowsheet", chemicalspecies=None,
                            add_positions=True):
        """This methods visualizes the process as a flowsheet and/or a streamtable.

        Parameters
        ----------
        figure: bool, default=True
            True if flowsheet should be showed, otherwise False.
        table: bool, default=True
            True if streamtable and unittable should be showed, otherwise False.
        decimals: int, default=3
            Amount of decimals showed in the streamtable.
        plot_with_stream_labels: bool, default=True
            True if labels should be shown in the flowsheet (otherwise just a simple graph visualization)
        plot_as_pfd: bool, default=True
            True if the flowsheet is plotted using the pyflowsheet package. Otherwise, it is plotted using the networkx
            package.
        pfd_block: bool, default=True
            True: creates a block-flowsheet, False: creates a flowsheet with unit-figures.
        pfd_path: str, default='plots/flowsheet'
            Path to save the pfd as svg.
        chemicalspecies: list, default=None
            List with string names of chemical species considered in the process.
        add_positions: bool, default=True
            Telling whether a position attribute already exists.

        Returns
        -------
        fig:
            Figure showing the flowsheet.
        table_streams:
            Table with all stream information.
        table_units:
            Table with all unit information.
        """

        fig = None
        table_streams = None
        table_units = None

        if table:
            # Shows the streamtable for the process including the stream name, corresponding edge, amount of moles,
            # temperature, pressure and molefractions.
            table_streams = create_stream_table(self.state, chemicalspecies, decimals)
            # Shows the unit table for the process including the unit name, unit type, and continuous decision.
            table_units = create_unit_table(self.state, decimals)

        if figure:
            # Plot the nx-graph.
            fig = plot_flowsheet_nx(self.state, plot_with_stream_labels, add_positions)

        if plot_as_pfd:
            # Create a flowsheet.
            plot_flowsheet_pyflowsheet(self.state, block=pfd_block, imagepath=pfd_path, add_positions=add_positions)
            # No return, is directly saved as svg using the image-path.

        return fig, table_streams, table_units

    # Helper functions SFILES related

    def flatten(self, nested_list):
        """Helper function that returns a flattened list.

        Parameters
        ----------
        nested_list: list
            Nested list.

        Returns
        ----------
        flat_list: list
            Flat list.
        """

        flat_list = []
        for i in nested_list:
            if isinstance(i, list):
                flat_list.extend(self.flatten(i))
            else:
                flat_list.append(i)
        return flat_list

    def split_dictionary(self, input_dict, chunk_size):
        """Helper function that returns sliced dictionaries.

        Parameters
        ----------
        input_dict: dict
            Dictionary to be chunked.
        chunk_size: int
            Chunk size.

        Returns
        -------
        res: list
            List of chunked dictionaries.
        """

        res = []
        new_dict = {}
        for k, v in input_dict.items():
            if len(new_dict) < chunk_size:
                new_dict[k] = v
            else:
                res.append(new_dict)
                new_dict = {k: v}
        res.append(new_dict)

        return res

    def SFILES_parser(self):
        """Parses a SFILES string and returns a list with SFILES elements
        ! At the moment assumes that there are less than 100 cycles !

        Returns
        -------
        sfiles_list: list
            SFILES as list.
        """

        sfiles_regex_pattern = r"(\(.+?\)|\{.+?\}|[<%_]+\d+|\]|\[|\<\&\||(?<!<)&\||n\||(?<!&)(?<!n)\||&(?!\|)|\d)"
        regex = re.compile(sfiles_regex_pattern)
        sfiles_list = [token for token in regex.findall(self.sfiles)]

        return sfiles_list

    def map_SFILES_to_Ontocape(self, merge_HI_nodes):
        """Current self.state is according to SFILES abbreviations. This function maps the SFILES abbreviations back to
        OntoCape vocabulary. It uses the Ontocape_SFILES_mapping to modify self.state. The previous self.state is copied
        to the attribute self.flowsheet_SFILES_names.

        Parameters
        ----------
        merge_HI_nodes: bool, default=True
            If true, merges heat integrated hex nodes into one node and creates connectivity tags, so it is possible to
            split nodes again later.
        """

        SFILES_node_names = list(self.state.nodes)
        relabel_mapping = {}
        for n in SFILES_node_names:
            _name = n.split(sep="-")[0]  # Name without number.
            _num = n.split(sep="-")[1]
            _OC_term = list(OntoCape_SFILES_map.keys())[list(OntoCape_SFILES_map.values()).index(_name)]
            relabel_mapping[n] = _OC_term + "-" + _num

        flowsheet_SFILES = self.state.copy()
        self.state = nx.relabel_nodes(self.state, relabel_mapping)

        # Merge heat integrated hex nodes into one node using tags for edges again.
        # This parameter is set to False at the moment, because it might result in unwanted behavior: Assume a heat
        # exchanger that takes both top and bottom product of column -> network x cannot have 2 edges with the same in
        # and out node but different tags :(
        if merge_HI_nodes:
            self.merge_HI_nodes()

        self.flowsheet_SFILES_names = flowsheet_SFILES

    @staticmethod
    def get_he_tag(edge: tuple[str, str, dict], edge_type: Literal["in", "out"]) -> str:
        """Fetch the "in" or "out" hex tag of a given edge, while
        asserting that only one tag of the type is present.

        Parameters
        ----------
        edge: The edge tuple (out_unit, in_unit, atrtibutes).
        edge_type: Either "in" or "out", specifying the edge type.

        Returns
        -------
        The tag without the "_in" (or "_out").

        Examples
        --------
        >>> edge = ("hex-1", "hex-2", {"tags": {"he": ["1_in", "2_out"]}})
        >>> Flowsheet.get_he_tag(edge, "in")
        1
        >>> Flowsheet.get_he_tag(edge, "out")
        2
        """

        if edge_type not in ["in", "out"]:
            raise ValueError(f'Only "in" and "out" values allowed for "edge_type" argument. Received: {edge_type}.')

        # > Get hex tags:
        he_tags = edge[-1]["tags"]["he"]

        # > Get "in" tag, also verify that there is exactly one in tag:
        type_tags = [tag for tag in he_tags if edge_type in tag]
        if len(type_tags) != 1:
            raise RuntimeError(f'> Number of "{edge_type}" tags for edge {edge} != 1: {he_tags}')

        tag = type_tags[0].split(f"_{edge_type}")[0]  # > ["1_in"] -> "1"
        return tag
    
    def merge_HI_nodes(self):
        """For non-ontocape conform SFILES merge heat integrated hex nodes into one node and creating connectivity tags,
        so it is possible to split nodes again later.
        """
        
        relabel_mapping = {}
        create_tags_map = {}
        node_attrs_map = {}
        state_copy = self.state.copy()      # > So we don't alter the state if an error happens.
        # > List nodes which we want to merge:
        for n, node_attrs in state_copy.nodes(data=True):
            if (("hex" in n) or ("HeatExchanger" in n)) \
            and "/" in n \
            and not bool(re.match(r".*/[A-Z]+", n)):  
                relabel_mapping[n] = n.split(sep="/")[0]    # > {"hex-1/2": "hex-1"}
                create_tags_map[n] = n.split(sep="/")[1]    # > {"hex-1/2": "2"}
                node_attrs_map[n] = node_attrs              # > {"hex-1/2": {}}
            
        nodes_to_remove = list(relabel_mapping.keys())      # > ["hex-1/1", "hex-1/2", ...]
        new_edges = []
        new_nodes = []
        for n1, n2 in relabel_mapping.items():      # > n1 = "hex-1/2", n2 = "hex-1"
            counter = create_tags_map[n1]           # counter = "2"
            
            # > Verify that each node only has one in edge and get its attributes:
            edges_in = list(state_copy.in_edges(n1, data=True))
            assert len(edges_in) == 1
            edge_in = edges_in[0]
            edge_in_attrs = edge_in[-1]
            if f"{counter}_in" not in edge_in_attrs["tags"]["he"]:
                edge_in_attrs["tags"]["he"].append(f"{counter}_in")

            # > Verify that each node only has one out edge and get its attributes:
            edges_out = list(state_copy.out_edges(n1, data=True))
            assert len(edges_out) == 1
            edge_out = edges_out[0]
            edge_out_attrs = edge_out[-1]
            if f"{counter}_out" not in edge_out_attrs["tags"]["he"]:
                edge_out_attrs["tags"]["he"].append(f"{counter}_out")
            
            # Remove old node and delete old edges + create new node if it does not exist and edges.
            if n2 not in new_nodes:    
                new_nodes.append(n2)
                node_attrs_map[n2] = {n1: node_attrs_map[n1]}
            else:
                # > Add this entry to the node attributes.
                # > Let's check if it these attributes are equal to the attributes
                # > a previous node (e.g., if the attributes of hex-1/1 are the same
                # > as those for hex-1/2):
                for key, value in node_attrs_map[n2].items():   # > Looping through node_attrs_map["hex-1"]
                    if value == node_attrs_map[n1]:             # > node_attrs_map["hex-1"]["hex-1/1"] == node_attrs_map["hex-1/2"]
                        node_attrs_map[f"{key}, {n1}"] = node_attrs_map[n1]     # > In that case, we'll create entry node_attrs_map["hex-1"]["hex-1/1, hex-1/2"]
                        del node_attrs_map[key] # and delete node_attrs_map["hex-1"]["hex-1/1"]
                        # > note we can't have node_attrs_map["hex-1"][ ["hex-1/1", ...] ] because lists can't be dictionary keys.
                        # > Later, we'll verify if there is only one key for node_attrs_map["hex-1"]
                        break                   
                else:
                    # > If we got here, then we didn't break from the for loop
                    # > and the attributes are different from other the nodes'
                    node_attrs_map[n2][n1] = node_attrs_map[n1]
            
            # > When creating new edges, must be careful if one of them is a decoupled hex too!
            if (("hex" in edge_in[0]) or ("HeatExchanger" in edge_in[0])) \
            and "/" in edge_in[0] \
            and not bool(re.match(r".*/[A-Z]+", edge_in[0])):
                new_edges.append(
                    (edge_in[0].split("/")[0], n2, edge_in_attrs))
            else:
                new_edges.append(
                    (edge_in[0], n2, edge_in_attrs))
                
            if (("hex" in edge_out[1]) or ("HeatExchanger" in edge_out[1])) \
            and "/" in edge_out[1] \
            and not bool(re.match(r".*/[A-Z]+", edge_out[1])):
                new_edges.append(
                    (n2, edge_out[1].split("/")[0], edge_out_attrs))
            else:
                new_edges.append(
                    (n2, edge_out[1], edge_out_attrs))
        
        state_copy.remove_nodes_from(nodes_to_remove)
        # Before adding new nodes, let's handle the node attributes:
        for node in new_nodes:
            if len(node_attrs_map[node]) == 1:
                key = list(node_attrs_map[node])[0]
                node_attrs_map[node] = node_attrs_map[node][key]
        new_nodes = [(node, node_attrs_map[node]) for node in new_nodes]
        state_copy.add_nodes_from(new_nodes)
        state_copy.add_edges_from(new_edges)
        self.state = state_copy
        # if len(state_copy.edges) == len(self.state.edges):  # This has to be still equal, otherwise merge failed.
        #     self.state = state_copy
        # else:
        #     print("Warning: seems like two streams of heat exchanger are connected to same unit operation and in have "
        #           "same edge directions. No merging in NetworkX possible")
        
    def split_HI_nodes(self, OntoCapeNames=False):
        """Heat integrated heat exchanger nodes are splitted. (Only if there is a multistream heat exchanger node with
        corresponding he tags)
        """
        
        if OntoCapeNames:
            heatexchanger = "HeatExchanger"
        else:
            heatexchanger = "hex"

        # Signal edges have to be removed otherwise out_degree of HX may not match in_degree.
        flowsheet_wo_signals = self.state.copy()
        edge_information = nx.get_edge_attributes(self.state, "tags")
        edge_information_signal = {k: self.flatten(v["signal"]) for k, v in edge_information.items() if
                                   "signal" in v.keys() if v["signal"]}
        edges_to_remove = [k for k, v in edge_information_signal.items() if v == ["not_next_unitop"]]
        flowsheet_wo_signals.remove_edges_from(edges_to_remove)

        nodes_to_remove = []    # > We'll remove nodes only at the end, to avoid issues with changing the size of the graph during iterations
        new_nodes = []
        new_edges = []
        for n, node_attrs in flowsheet_wo_signals.nodes(data=True):
            if heatexchanger in n and flowsheet_wo_signals.in_degree(n) > 1:  # Heat exchangers with more than 1 streams
                
                edges_in = flowsheet_wo_signals.in_edges(n, data=True)
                edges_out = flowsheet_wo_signals.out_edges(n, data=True)
                if len(edges_in) != len(edges_out):
                    warnings.warn(
                        f"Skipping decoupling of heat exchanger {n}: Number of in_edges != out_edges."
                        f"in_edges: {edges_in};"
                        f"out_edges: {edges_out}."
                    )
                    continue
                
                nodes_to_remove.append(n)   # > We'll make all changes at the very end.
                
                # Here we try to match the inlet with their corresponding outlet streams using the tags.
                # (This works for tags of the form hot_in,hot_out,cold_in,cold_out,1_in,1_out, ...)
                for in_edge in edges_in:
                    in_tag = Flowsheet.get_he_tag(in_edge, "in")
                    
                    # > Now Loop on out_edges and find associated out_tag:
                    for out_edge in edges_out:
                        out_tag = Flowsheet.get_he_tag(out_edge, "out")
                        if out_tag == in_tag:
                            # > We've found the associated out_tag to our in_tag !
                            break
                    else:
                        # This means we didn't break from the for loop:
                        raise RuntimeError(f"> Couldn't find out tag {in_tag}_out for heat exchanger {n}!\nin_edges: {edges_in},\nout_edges:{edges_out}")
                    
                    # > Ok, so we've found the associated out_edge to the in_edge! 
                    # > Let's add the new edges and nodes:
                    new_nodes.append((f"{n}/{in_tag}", node_attrs))             # hex-1 --> hex-1/1
                    
                    # > ATTENTION WHEN CREATING NEW EDGES !
                    # > Possible issue if the hex is connected to another hex or itself!
                    if heatexchanger in in_edge[0]:
                        extra_tag = Flowsheet.get_he_tag(in_edge, "out")
                        new_edges.append(
                            (f"{in_edge[0]}/{extra_tag}", f"{in_edge[1]}/{in_tag}", in_edge[-1]))
                    else:
                        new_edges.append(
                            (in_edge[0], f"{in_edge[1]}/{in_tag}", in_edge[-1]))
                    
                    if heatexchanger in out_edge[1]:
                        extra_tag = Flowsheet.get_he_tag(out_edge, "in")
                        new_edges.append(
                            (f"{out_edge[0]}/{out_tag}", f"{out_edge[1]}/{extra_tag}", out_edge[-1]))
                    else:
                        new_edges.append(
                            (f"{out_edge[0]}/{out_tag}", out_edge[1], out_edge[-1]))
        
        state_copy = self.state.copy()      # > Avoiding changing the state if an issue arises in the next lines 
        # Delete old nodes and associated edges first.
        state_copy.remove_nodes_from(nodes_to_remove)
        # > Add new ones:
        state_copy.add_nodes_from(new_nodes)
        state_copy.add_edges_from(new_edges)
        self.state = state_copy             # > If we got here then ok

    def map_Ontocape_to_SFILES(self):
        """Function that returns a graph with the node names according to SFILES abbreviations for OntoCape unit
        operation names. Additionally, the heat exchanger nodes (with more than 1 stream) are split up for each stream
        according to the he tags (edge attribute tags:{he:[]}). Uses the Ontocape_SFILES_mapping to set
        self.flowsheet_SFILES_names.
        """

        self.split_HI_nodes(OntoCapeNames=True)

        # Relabel from OntoCape to SFILES abbreviations.
        relabel_mapping = {}
        for n in list(self.state.nodes):
            _name = n.split(sep="-")[0]  # Name without number.
            _num = n.split(sep="-")[1]
            _abbrev = OntoCape_SFILES_map[_name]
            relabel_mapping[n] = _abbrev + "-" + _num

        flowsheet_SFILES = self.state.copy()
        flowsheet_SFILES = nx.relabel_nodes(flowsheet_SFILES, relabel_mapping)

        self.flowsheet_SFILES_names = flowsheet_SFILES

    def add_edge_tags(self, edges, nodes):
        """Helper function that assigns tags in SFILES (node related) to corresponding edges in graph.

        Parameters
        ----------
        edges: list
            List of edges without tags.
        nodes: ditc
            Mapping of nodes and in and out tags.

        Returns
        ----------
        edges: list
            List of edges with tags.
        """

        for i, edge in enumerate(edges):
            e1 = edge[0]
            e2 = edge[1]
            out_con = nodes[e1]["out_connect"]
            in_con = nodes[e2]["in_connect"]
            common_tags = list(set(out_con).intersection(in_con))
            if len(common_tags) > 1:
                raise Exception(f"The used tags are not unambiguous. "
                                f"The edge of nodes {e1} and {e2} has two common tags in the SFILES.")
            elif len(common_tags) == 1:  # Only one tag per edge.
                edges[i] = (e1, e2, {"tags": [common_tags[0]]})
            else:
                edges[i] = (e1, e2, {"tags": []})

        return edges

    def renumber_generalized_SFILES(self):
        """Helper function that renumbers the generalized SFILES, in specific the unit operations. Modifies the
        attribute self.sfiles_list and returns list of node names.

        Returns
        ----------
        nodes: list
            List of numbered node names.
        """

        unit_counting = {}
        HI_hex = {}

        for s_idx, s in enumerate(self.sfiles_list):

            if bool(re.match(r"\(.*?\)", s)):  # Current s is a unit operation.
                unit_cat = s[1:-1]
                if unit_cat not in unit_counting:  # First unit in SFILES of that category.
                    unit_counting[unit_cat] = 1
                    unit_name = unit_cat + "-" + "1"

                    # Check if the current unit is a hex unit with heat integration. -> Special node name
                    # Only if it's not the last token.
                    if s_idx < len(self.sfiles_list) - 1:
                        if bool(re.match(r"{[0-9]+}", self.sfiles_list[s_idx + 1])):
                            _HI_number = self.sfiles_list[s_idx + 1][1:-1]
                            HI_hex[_HI_number] = (unit_name, 1)
                            # Add HI notation to hex node name.
                            unit_name = unit_name + "/1"
                        elif bool(re.match(r"{[A-Z]+}", self.sfiles_list[s_idx + 1])):
                            unit_name = unit_name + "/" + self.sfiles_list[s_idx + 1][1:-1]
                else:
                    # Check if the current unit is a unit with heat integration. -> Special node name
                    # Only possible if it's not the last token.

                    if s_idx < len(self.sfiles_list) - 1:
                        if bool(re.match(r"{[0-9]+}", self.sfiles_list[s_idx + 1])):
                            _HI_number = self.sfiles_list[s_idx + 1][1:-1]
                            # Check if _HI_number is already in HI_hex dict keys.
                            if _HI_number in HI_hex:
                                _occurrence = HI_hex[_HI_number][1] + 1
                                HI_hex[_HI_number] = (HI_hex[_HI_number][0], _occurrence)
                                unit_name = HI_hex[_HI_number][0] + "/" + str(_occurrence)
                            else:
                                _HI_number = self.sfiles_list[s_idx + 1][1:-1]
                                unit_counting[unit_cat] += 1
                                unit_name = unit_cat + "-" + str(unit_counting[unit_cat])
                                HI_hex[_HI_number] = (unit_name, 1)
                                unit_name = unit_name + "/1"

                        elif bool(re.match(r"{[A-Z]+}", self.sfiles_list[s_idx + 1])):
                            unit_counting[unit_cat] += 1
                            unit_name = unit_cat + "-" + str(unit_counting[unit_cat]) + "/" + \
                                        self.sfiles_list[s_idx + 1][1:-1]
                        else:
                            unit_counting[unit_cat] += 1
                            unit_name = unit_cat + "-" + str(unit_counting[unit_cat])
                    else:
                        unit_counting[unit_cat] += 1
                        unit_name = unit_cat + "-" + str(unit_counting[unit_cat])

                # Modify the token in sfiles list.
                self.sfiles_list[s_idx] = "(" + unit_name + ")"

        # Node names from sfiles list.
        r = re.compile(r"(\(.*?\))")
        nodes = list(filter(r.match, self.sfiles_list))

        return nodes

    def convert_sfilesctrl_to_sfiles(self):
        """Function converts sfiles including the control structure to sfiles without the control structure.

        Returns
        ----------
        sfiles: list
            SFILES representation of the process flowsheet excluding the control structure of the process.
        """

        pattern = re.compile(r"<?_+\d+|{[A-Z]+}|\(C\)")
        sfiles = [re.sub(pattern, "", i) for i in self.sfiles_list]

        # This step prevents that the number of a material recylce # occurs after <#.
        sfiles = [item for item in sfiles if not item == ""]
        for k in range(1, len(sfiles)):
            if re.match(r"\d+", sfiles[k]) and re.match(r"<\d+", sfiles[k - 1]):
                outgoing_recycle = sfiles[k]
                incoming_recycle = sfiles[k-1]
                sfiles[k] = incoming_recycle
                sfiles[k-1] = outgoing_recycle

        sfiles = "".join(sfiles)
        sfiles = re.sub(r"\[]", "", sfiles)
        sfiles = re.sub(r"n\|$", "", sfiles)

        # Ensure cannonical SFILE after control structure removal.
        flowsheet = Flowsheet()
        flowsheet.create_from_sfiles(sfiles, overwrite_nx=True)
        flowsheet.convert_to_sfiles()
        sfiles = flowsheet.sfiles
        return sfiles

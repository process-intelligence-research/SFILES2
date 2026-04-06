import re
import warnings

import networkx as nx
from typing import Literal, Dict

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
    use_single_signal_stream_old: str
        For backwards compatibility. If True, control units which have a material AND
        signal stream connection to the same unit will only have one networkx edge 
        associated to both connections ("next_unitop" signal tag must be specified in the edge).
        If False, the graph will have two edges between these nodes. One for the material and 
        another for the signal edge (the latter having a signal tag).
    """

    def __init__(
            self, OntoCapeConformity=False, sfiles_in=None, sfiles_list_in=None, xml_file=None,
            use_single_signal_stream_old: bool = False
        ):
        self.OntoCapeConform = OntoCapeConformity
        self.sfiles = sfiles_in
        self.sfiles_list = sfiles_list_in
        self.flowsheet_SFILES_names = None
        self.state = nx.MultiDiGraph()  # Default initialization of the flowsheet as a nx Graph
        self.use_single_signal_stream_old = use_single_signal_stream_old
        if xml_file:  # ToDo mapping xml digitization group -> OntoCape vocab
            self.state = nx.read_graphml(xml_file, force_multigraph=True)
        elif sfiles_in:
            self.create_from_sfiles()
        elif sfiles_list_in:
            self.create_from_sfiles()

    def add_unit(self, unique_name: str = None, **kwargs):
        """This method adds a new unit as a new node to the existing flowsheet-graph.

        Parameter
        ---------
        unique_name: str, default=None
            Unique name of the unit, e.g. 'hex-1'.
        kwargs:
            Parameters of new unit as node attributes.
        """

        self.state.add_node(unique_name, **kwargs)
    
    def add_stream(self, node1, node2, tags: dict = None, key = None, **kwargs):
        """Method adds a stream as an edge to the existing flowsheet graph, thereby connecting two unit operations
        (nodes).

        Parameters
        ----------
        node1: str
            Unique name of the node with the unit where the stream origins.
        node2: str
            Unique name of the node with the unit where the stream is fed into.
        tags: dict
            Tags for that stream, of following form: {'he':[],'col':[]}, i.e., heat exchanger related tags
            (hot_in,cold_out, ...) and column related tags (t_out,b_out, ...).
        key: hashable identifier, optional
            From networkx's MultiDiGraph documentation: "Used to distinguish multiedges between a pair of nodes."
        kwargs:
            Parameters of new stream as edge attributes.
        """
        if tags is None:    # > Avoiding mutable default argument
            tags = {"he": [], "col": []}

        self.state.add_edge(node1, node2, key=key, tags=tags, **kwargs)

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
                self.state = nx.MultiDiGraph()
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
                current_node = token
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
                        cycles.append((cyc_nr, tags, current_node))
                        tags = []

                    # Branch opens. Looping through the branch until it is terminated.
                    elif self.sfiles_list[token_idx + step] == "[":
                        branches = 1
                        found = False
                        branch_step = 0
                        while not (token_idx + step) == last_index:
                            step += 1
                            branch_step += 1
                            if not found and bool(re.match(pattern_node, self.sfiles_list[token_idx + step])):
                                if branch_step != 1:
                                    raise AssertionError(
                                        f"Error in create_from_sfiles: found = False but branch_step != 1." 
                                        f"Check if the SFILES correctly describes your process."
                                    )
                                edges.append((token[1:-1], self.sfiles_list[token_idx + step][1:-1], {"tags": tags}))
                                tags = []
                                found = True
                            # Cycle: next list element is a single digit or a multiple digit number of form %##.
                            elif not found and bool(re.match(r"^[%_]?\d+", self.sfiles_list[token_idx + step])):
                                # Particular case like (splt)[2]
                                if branch_step != 1:
                                    raise AssertionError(
                                        f"Error in create_from_sfiles: found = False but branch_step != 1." 
                                        f"Check if the SFILES correctly describes your process."
                                    )
                                cyc_nr = re.findall(r"^[%_]?\d+", self.sfiles_list[token_idx + step])[0]
                                cycles.append((cyc_nr, tags, current_node))
                                tags = []
                                found = True
                            elif not found and self.sfiles_list[token_idx + step] == "&":
                                # Special case like (splt)[&]
                                # Run backwards through last operations, search for unit operations,
                                # but ignore everything if its token in this or another incoming branch.
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
                                if not found:
                                    raise AssertionError(
                                        "Error in create_from_sfiles: found the end of the branch"
                                        "without having found downstream unit."
                                        "Check if the SFILES correctly describes your process."
                                    )
                                break
                            # Tags in SFILES v2 in branch (usually the first token after branching)
                            elif bool(re.match(r"{.*?}", self.sfiles_list[token_idx + step])):
                                # Tags that are used for heat integration are not required
                                # (those are incorporated in node names)
                                # Branches needs to be 1 otherwise the tags of subbranches might be added
                                if not bool(re.match(r"^[0-9]+$", self.sfiles_list[token_idx + step][1:-1])) \
                                        and branches == 1:
                                    branch_step -= 1 # This will be necessary for finding the next unit in the sequence.
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
            pre_op = cycle_connection[2]
            
            # Search for the cycle destination ('<#' or '<_#') and add connection to unit operation that <# refers to.
            if "_" in cycle_connection[0]:
                number = re.findall(r"\d+", cycle_connection[0])
                cycle_tgt = self.sfiles_list.index("<_" + number[0])
                for k in range(0, cycle_tgt):
                    if bool(re.match(pattern_node, self.sfiles_list[cycle_tgt - k])):
                        cycle_op = self.sfiles_list[cycle_tgt - k]
                        edges_wo_tags = [x[0:2] for x in edges]
                        if (pre_op[1:-1], cycle_op[1:-1]) in edges_wo_tags:
                            if not self.use_single_signal_stream_old:
                                # > New default behaviour:
                                edges.append((pre_op[1:-1], cycle_op[1:-1], {"tags": "next_unitop"}))
                            else:
                                # > Backwards compatibility:
                                index = edges_wo_tags.index((pre_op[1:-1], cycle_op[1:-1]))
                                edges[index] = (pre_op[1:-1], cycle_op[1:-1], {"tags": "next_unitop"})
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

    @staticmethod
    def convert_to_multidigraph(initial_flowsheet: nx.DiGraph) -> nx.MultiDiGraph:
        if not isinstance(initial_flowsheet, nx.MultiDiGraph):
            try:
                og_type = type(initial_flowsheet)
                initial_flowsheet = nx.MultiDiGraph(initial_flowsheet)
                warnings.warn(f"CONVERTED initial_flowsheet TO nx.MultiDiGraph (original type: {og_type}). Attention: this conversion was done inplace!")
            except Exception as e:
                print(
                    f"Tried to create_from_nx with invalid type: {type(initial_flowsheet)}\n"
                    f"Flowsheet graphs are of nx.MultiDiGraph (at least nx.DiGraph must be passed)."
                )
                raise e
        return initial_flowsheet

    def create_from_nx(self, initial_flowsheet: nx.MultiDiGraph):
        """Method to initialize the flowsheet from an already existing nx-Graph.

        Parameters
        ----------
        initial_flowsheet: networkx graph
            Already existing networkx-Graph, default case: initialized with one feed-node ('IO-1'),
            an unprocessed-node ('X-1') and a connecting edge with stream data.
        """
        self.state = Flowsheet.convert_to_multidigraph(initial_flowsheet)
        self.signal_connectivity_backwards_compatibility()

    def signal_connectivity_backwards_compatibility(self):
        """Checks if the Flowsheet's Graph was *initialized* using the old formatting
        for signal connections, and adds extra edges if necessary (not self.use_single_signal_stream_old).

        Originally, if a control unit (e.g. C-1) had its material outlet stream connected to 
        another unit (e.g. v-1) but ALSO had a signal connection to that same unit (v-1), this
        had to be specified as a single networkx edge, like so:
        
        ``('C-2/FC', 'v-2', {'tags': {'signal': ['next_unitop']}})``

        Now, this limitation has been solved, and the two edges should be specified
        distinctively:
        
        ``('C-2/FC', 'v-2') # Material stream``

        ``('C-2/FC', 'v-2', {'tags': {'signal': ['next_unitop']}}) # Signal connection``
        
        For backwards compatibility, this function checks if only the signal stream has
        been specified, and adds the material stream. 
        """
        if self.use_single_signal_stream_old:
            return # Nothing to do
        # > If we are NOT using the old_signal_format, then
        # > we want to have two separate streams for material and signal connections.
        # > In this case, let's check if the flowsheet was specified according to the
        # > old format and adapt the state accordingly.

        edge_tag_dict = nx.get_edge_attributes(self.state, "tags") # {(n1, n2, key): {"he": [], ... "signal": [...]}}
        # > Get edges with the next_unitop signal:
        edges_w_next_unitop_signal = []
        for edge, tags in edge_tag_dict.items():
            if "signal" in tags:
                if len(tags["signal"]) > 0:
                    if not len(tags["signal"]) == 1:
                        raise AssertionError(f"> Unexpected: edge {edge} has more than 1 signal tag: {tags['signal']}")
                    if tags["signal"][0] == "next_unitop":
                        edges_w_next_unitop_signal.append(edge)
        # > Check if it is the only edge:
        for edge in edges_w_next_unitop_signal:
            n1, n2, key = edge
            if len(self.state[n1][n2]) == 1:
                # It is, let's add another one:
                self.state.add_edge(n1, n2, key = None)
                warnings.warn(
                    f"Fixed graph: added one extra (material) edge between nodes {n1} and {n2}.\n"
                    f"If you would like to only have one graph edge between {n1} and {n2}"
                    f" (associated to both material and signal streams), initialize the"
                    f" Flowsheet object with use_single_signal_stream_old=True."
                )
    
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
        # > Next line avoids issues in case state was set manually as a DiGraph:
        self.create_from_nx(self.state)

        if self.OntoCapeConform:
            self.map_Ontocape_to_SFILES()  # sets self.flowsheet_SFILES_names
        else:
            # Does not modify self.state in case there are no multi-stream hex nodes, but already HI nodes
            # in hex-#/# notation
            self.split_HI_nodes()
            self.flowsheet_SFILES_names = self.state.copy()
        self.sfiles_list, self.sfiles = nx_to_SFILES(
            self.flowsheet_SFILES_names, version, remove_hex_tags, canonical,
            use_single_signal_stream_old=self.use_single_signal_stream_old
        )

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
        # > Next line avoids issues in case state was set manually as a DiGraph:
        self.create_from_nx(self.state)

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
        # > Next line avoids issues in case state was set manually as a DiGraph:
        self.create_from_nx(self.state)

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
    
    @staticmethod
    def is_decoupled_hex(node_name: str) -> bool:
        """Quick check for whether a node is a decoupled integration heat exchanger (by only checking its name).
        
        Simply:
        
        .. code-block:: python

            return \
                (("hex" in node_name) or ("HeatExchanger" in node_name)) \
            and "/" in node_name \
            and not bool(re.match(r".*/[A-Z]+", node_name))  # 1. is hex?, 2. potentially decoupled? 3. confirmed decoupled.

        Parameters
        ----------
        node_name: str
            The name of the node.
        
        Returns
        -------
        True if it is, False otherwise.

        """
        return \
            (("hex" in node_name) or ("HeatExchanger" in node_name)) \
        and "/" in node_name \
        and not bool(re.match(r".*/[A-Z]+", node_name))  # 1. is hex?, 2. potentially decoupled? 3. confirmed decoupled.

    def merge_HI_nodes(self):
        """For non-ontocape conform SFILES merge heat integrated hex nodes into one node and creating connectivity tags,
        so it is possible to split nodes again later.
        """

        def check_and_add_tag(edge_attrs: Dict, port: int, edge_type: Literal["in", "out"]) -> bool:
            # > Sanity checks: Check whether we don't have invalid in-tags:
            tags = [tag for tag in edge_attrs["tags"]["he"] if edge_type in tag]
            if len(tags) > 1:
                raise AssertionError(f'Too many HEX tags of type "{edge_type}" in this edge (edge attributes: {edge_attrs}).')
            if len(tags) == 1 and tags[0] != f"{port}_{edge_type}":
                raise AssertionError(f'Unexpected HEX tag: {tags[0]}, expected {port}_{edge_type} (edge attributes: {edge_attrs}).')
            # > Add tag to edge_attrs if it is not there:
            if f"{port}_{edge_type}" not in edge_attrs["tags"]["he"]:
                edge_attrs["tags"]["he"].append(f"{port}_{edge_type}")
            return edge_attrs

        relabel_mapping = dict()
        create_tags_map = dict()
        node_attrs_map = dict()
        state_copy = self.state.copy()      # > So we don't alter the state if an error happens.
        # > List nodes which we want to merge:
        for node_name, node_attrs in state_copy.nodes(data=True):
            if Flowsheet.is_decoupled_hex(node_name):
                relabel_mapping[node_name] = node_name.split(sep="/")[0]    # > {"hex-1/2": "hex-1"}
                create_tags_map[node_name] = node_name.split(sep="/")[1]    # > {"hex-1/2": "2"}
                node_attrs_map[node_name]  = node_attrs                     # > {"hex-1/2": {...}}
        
        nodes_to_remove = list(relabel_mapping.keys())      # > ["hex-1/1", "hex-1/2", ...]
        edge_dict = dict()                          # > Will be useful for handling edge attributes and repeated entries 
        for n1, n2 in relabel_mapping.items():      # > n1 = "hex-1/2", n2 = "hex-1"
            port = create_tags_map[n1]              # > port = "2"
            
            # > Verify that each node only has one in edge and get its attributes:
            edges_in = list(state_copy.in_edges(n1, keys=True, data=True))
            if len(edges_in) != 1:
                raise AssertionError(f"Decoupled hex {n1} has more than one in_edge: {edges_in}.\nCannot merge HI nodes.")
            edge_in = edges_in[0]
            upstream_unit, _, edge_key, edge_in_attrs = edge_in
            # > Sanity checks: Check whether we don't have invalid in-tags and add tag if necessary:
            # > NOTE: If upstream_unit is also a decoupled HEX, its tag will be added to the same
            # > dict later in the loop. This is possible because we will be touching a reference to
            # > the same python object. 
            edge_in_attrs = check_and_add_tag(edge_in_attrs, port, "in")
            # > Add entry to edge_dict dictionary. This is useful for avoiding adding the same edge twice
            # > (which could happend using list.append(). No need to check if it already exists as the
            # > dictionary size won't change and we won't be changing the entry since the edge_attrs will
            # > be pointing to the same python object:
            dict_entry = (upstream_unit, n1, edge_key)
            edge_dict[dict_entry] = edge_in_attrs

            # > Analogous for out_edges:
            edges_out = list(state_copy.out_edges(n1, keys=True, data=True))
            if len(edges_out) != 1:
                raise AssertionError(f"Decoupled hex {n1} has more than one out_edge: {edges_out}.\nCannot merge HI nodes.")
            edge_out = edges_out[0]
            _, downstream_unit, edge_key, edge_out_attrs = edge_out
            edge_out_attrs = check_and_add_tag(edge_out_attrs, port, "out")
            dict_entry = (n1, downstream_unit, edge_key)
            edge_dict[dict_entry] = edge_out_attrs
            
            # > Flag new node for creation if not yet in the list.
            # > Must also handle NODE attributes, in case the user has
            # > created the decoupled HEXs manually, rather than with split_HI_nodes:
            if n2 not in node_attrs_map:    
                node_attrs_map[n2] = {n1: node_attrs_map[n1]} # node_attrs_map["hex-1"] = {"hex-1/2": {...}}
                del node_attrs_map[n1] # > This will simplify our life later
            else:
                node_attrs_map[n2][n1] = node_attrs_map[n1]
                del node_attrs_map[n1] # > This will simplify our life later
        
        # > Now handle node attributes if they are different:
        new_nodes = list()
        for new_node_name, node_attr_dict in node_attrs_map.items():
            # Let's check if the node attributes match:
            node_attrs = dict()
            for key, value in node_attr_dict.items():
                if len(node_attrs) == 0: # First node, initialize node_attrs:
                    node_attrs.update(value)
                    continue
                if value != node_attrs:
                    # In this case, the decoupled HEX's had different node attributes.
                    # To avoid loss of information, we'll add them all (node_attrs = {"hex-1/1": {...(hex-1/1 attrs)}, "hex-1/2": {...(hex-1/2 attrs)}})
                    node_attrs = node_attr_dict
                    break
            new_nodes.append((new_node_name, node_attrs))

        # > Create list of new edges from edge_dict, taking care of decoupled hex names:
        new_edges = []
        for key, value in edge_dict.items():
            n1, n2, _ = key
            if Flowsheet.is_decoupled_hex(n1): n1 = n1.split("/")[0]
            if Flowsheet.is_decoupled_hex(n2): n2 = n2.split("/")[0]
            new_edges.append((n1, n2, value)) # > No need to enforce the edge_key 

        # > First remove old nodes (which will already get rid of associated edges): 
        state_copy.remove_nodes_from(nodes_to_remove)
        # > Add new nodes and edges:
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
        edge_information = nx.get_edge_attributes(self.state, "tags") # > With MultiDiGraph change, edge_information is now {(node1, node2, key): tags}
        edge_information_signal = {k: self.flatten(v["signal"]) for k, v in edge_information.items() if
                                   "signal" in v.keys() if v["signal"]} # > alright, we don't play with the keys here
        edges_to_remove = [k for k, v in edge_information_signal.items() if v != []]  # > same
        if self.use_single_signal_stream_old:
            edges_to_remove = [k for k, v in edge_information_signal.items() if v != ["next_unitop"]]  # > same
        flowsheet_wo_signals.remove_edges_from(edges_to_remove) # > alright, it is good that the MultiDiGraph keys are present here.

        # First get the names of the HEX we actually have to split:
        hex_to_split = []
        for node_name, node_attrs in flowsheet_wo_signals.nodes(data=True):
            if heatexchanger in node_name and flowsheet_wo_signals.in_degree(node_name) > 1:  # Heat exchangers with more than 1 streams
                edges_in = flowsheet_wo_signals.in_edges(node_name, keys=True, data=True)
                edges_out = flowsheet_wo_signals.out_edges(node_name, keys=True, data=True)
                if len(edges_in) != len(edges_out):
                    # > Warning suppressed because this is the desired behaviour.
                    # warnings.warn(
                    #     f"Skipping decoupling of heat exchanger {node_name}: Number of in_edges != out_edges."
                    #     f"in_edges: {edges_in};"
                    #     f"out_edges: {edges_out}."
                    # )
                    continue
                hex_to_split.append(node_name)

        # First get the names of the HEX we actually have to split:
        hex_to_split = {}
        for node_name, node_attrs in flowsheet_wo_signals.nodes(data=True):
            if heatexchanger in node_name and flowsheet_wo_signals.in_degree(node_name) > 1:  # Heat exchangers with more than 1 streams
                edges_in = flowsheet_wo_signals.in_edges(node_name, data=True)
                edges_out = flowsheet_wo_signals.out_edges(node_name, data=True)
                if len(edges_in) != len(edges_out):
                    # > Warning suppressed because this is the desired behaviour.
                    # warnings.warn(
                    #     f"Skipping decoupling of heat exchanger {node_name}: Number of in_edges != out_edges."
                    #     f"in_edges: {edges_in};"
                    #     f"out_edges: {edges_out}."
                    # )
                    continue
                hex_to_split[node_name] = node_attrs

        nodes_to_remove = []    # > We'll remove nodes only at the end, to avoid issues with changing the size of the graph during iterations
        new_nodes = []
        new_edges = []
        new_edge_names = [] # Will be used to avoid adding the same edge twice.
        for node_name, node_attrs in hex_to_split.items():
            nodes_to_remove.append(node_name)   # > We'll make all changes at the very end.
            edges_in = flowsheet_wo_signals.in_edges(node_name, keys=True, data=True)
            edges_out = flowsheet_wo_signals.out_edges(node_name, keys=True, data=True)
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
                    # > This means we didn't break from the for loop:
                    raise RuntimeError(f"> Couldn't find out tag {in_tag}_out for heat exchanger {node_name}!\nin_edges: {edges_in},\nout_edges:{edges_out}")
                
                # > Ok, so we've found the associated out_edge to the in_edge!
                # > Let's add the new edges and nodes:
                new_nodes.append((f"{node_name}/{in_tag}", node_attrs))             # hex-1 --> hex-1/1
                
                # > ATTENTION WHEN CREATING NEW EDGES !
                # > Possible issue if the hex is connected to another hex or itself!
                if in_edge[0] in hex_to_split:
                    extra_tag = Flowsheet.get_he_tag(in_edge, "out")
                    # We'll create the new edge depending on f"{in_edge[0]}/{extra_tag}"
                    # even though we haven't yet created that new node:
                    if f"{in_edge[0]}/{extra_tag} + {in_edge[1]}/{in_tag}" not in new_edge_names:
                        # Only adding edge once to list (avoiding adding it twice as we have a MultiDiGraph):
                        new_edge_names.append(f"{in_edge[0]}/{extra_tag} + {in_edge[1]}/{in_tag}")
                        new_edges.append(
                            (f"{in_edge[0]}/{extra_tag}", f"{in_edge[1]}/{in_tag}", in_edge[-1]))
                else:
                    new_edges.append(
                        (in_edge[0], f"{in_edge[1]}/{in_tag}", in_edge[-1]))
                
                # > Analogously for out_edges:
                if out_edge[1] in hex_to_split:
                    extra_tag = Flowsheet.get_he_tag(out_edge, "in")
                    if f"{out_edge[0]}/{out_tag} + {out_edge[1]}/{extra_tag}" not in new_edge_names:
                        new_edge_names.append(f"{out_edge[0]}/{out_tag} + {out_edge[1]}/{extra_tag}")
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
        # > Next line avoids issues in case state was set manually as a DiGraph:
        self.create_from_nx(self.state)
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
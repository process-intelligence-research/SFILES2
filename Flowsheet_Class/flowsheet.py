import warnings
from Flowsheet_Class.OntoCape_SFILES_mapping import OntoCape_SFILES_map
from Flowsheet_Class.RandomFlowsheetGen_OC.random_flowsheet_generator import Generate_flowsheet
import networkx as nx
from Flowsheet_Class.utils_visualization import create_stream_table, create_unit_table, plot_flowsheet_nx, plot_flowsheet_pyflowsheet
import re
from Flowsheet_Class.nx_to_sfiles import nx_to_SFILES

class Flowsheet:
    """
    This is a class to create flowsheets represented as a graphs.

    Attributes:
        self.state (nx graph): Stores the flowsheet represented as networkx graph
        self.sfiles (string): String representation of the graph
        self.sfiles_list (list): List of sfiles tokens (parsed string)
        OntoCapeConformity (bool): Specify as True when using OntoCape vocabulary (Should be the standard in future), defaults to False
        sfiles_in (string): SFILES string input
        sfiles_list_in (list): SFILES parsed string input
        xml_file (string): Path to xml file that can be read with nx.read_graphml method
    """

    def __init__(self, OntoCapeConformity= False, sfiles_in=None, sfiles_list_in=None, xml_file=None):
        self.OntoCapeConform = OntoCapeConformity
        self.sfiles = sfiles_in
        self.sfiles_list = sfiles_list_in
        self.state = nx.DiGraph()  # Default initialization of the flowsheet as a nx Graph
        if xml_file:  # ToDo mapping xml digitization group -> OntoCape vocab
            self.state = nx.read_graphml(xml_file)
        elif sfiles_in:
            self.create_from_sfiles()
        elif sfiles_list_in:
            self.create_from_sfiles()
              
    def add_unit(self, unique_name=None):
        """This method adds a new unit as a new node to the existing flowsheet-graph.

        Args:
            unique_name (string): Unique name of the unit, e.g. 'hex-1'
        """

        self.state.add_node(unique_name)

    def add_stream(self, node1, node2, tags={'he':[],'col':[]}):
        """Method adds a stream as an edge to the existing flowsheet graph, thereby connecting two unit operations
        (nodes).
        
        Args:
            node1 (string): Unique name of the node with the unit where the stream origins
            node2 (string): Unique name of the node with the unit where the stream is fed into
            tags (dict): Tags for that stream, of following form: {'he':[],'col':[]}, i.e heat exchanger related tags
                (hot_in,cold_out, ...) and column related tags (t_out,b_out, ...)

        Returns:
            Adjust the attribute self.state by updating the graph.
        """

        self.state.add_edge(node1, node2, tags = tags)

    def create_from_sfiles(self, sfiles_in="", override_nx=False, merge_HI_nodes=True):
        """
        Function to read SFILES (parsed or unparsed) and creates Units (without child objects) and Streams.
        Result is a flowsheet with Units with categories and specific categories.
        Convert the SFILES string to a graph.
        
        Parameters
        ----------
        sfiles_in (str), optional: SFILES string

        Returns
        ----------
        Adjusts the flowsheet self.state 
        """

        " Error handling "
        if not self.sfiles_list:  # Should be empty
            if self.sfiles:
                self.sfiles_list = self.SFILES_parser()
            else: 
                if sfiles_in:
                    self.sfiles = sfiles_in
                    self.sfiles_list = self.SFILES_parser()
                else:
                    raise ValueError('Empty SFILES string! Set the attribute self.sfiles or specify input argument '
                                     '\'sfiles_in\' or \'sfiles_list_in\' before using this method')
        else: 
            if self.sfiles:
                print('Overwriting the current self.sfiles_list')
                self.sfiles_list = self.SFILES_parser()
            else:
                if sfiles_in:
                    self.sfiles = sfiles_in
                    self.sfiles_list = self.SFILES_parser()
                else:  # SFILES list already set
                    pass 
                
        # Make sure we start with an empty graph, overriding possible.
        if not nx.classes.is_empty(self.state):
            if override_nx:
                self.state = nx.DiGraph()
            else:
                raise ValueError('There already exists a nx graph. If you wish to override it, '
                                 'specify \'override_nx=True\'')

        " Converting SFILES to graph "
        edges = []
        missing_circles = []
        tags = []

        " First loop through SFILES (generalized) and renumber the nodes so the graph construction works. "
        nodes = self.renumber_generalized_SFILES()

        " Loop through sfiles list and create the graph. "
        # Initialize some variables
        last_ops = []  # Already visited operations
        pattern_node = r'\(.*?\)'  # Regex pattern for a node
        last_index = len(self.sfiles_list) - 1

        for token_idx, token in enumerate(self.sfiles_list):
            # Append token to visited operations.
            last_ops.append(token)

            # If current token is a node, search the connections that are associated with the node.
            if bool(re.match(pattern_node, token)):
                step = 0
                branches = 0

                while not (token_idx + step) == last_index:
                    step += 1
                    
                    # Next list element is node, normal connection (no branches)
                    if not branches and bool(re.match(pattern_node, self.sfiles_list[token_idx+step])):
                        edges.append((token[1:-1], self.sfiles_list[token_idx+step][1:-1], {'tags': tags}))
                        tags = []
                        break
                    
                    # Next list element is node, open branch
                    elif branches and bool(re.match(pattern_node, self.sfiles_list[token_idx+step])):
                        edges.append((token[1:-1], self.sfiles_list[token_idx+step][1:-1], {'tags': tags}))
                        tags = []
                        branches -= 1

                    # Cycle: next list element is a single digit or a multiple digit number of form %##
                    # TODO: introduce cycles always with %-sign. Then the elif criterium
                    #  self.sfiles_list[token_idx+step][0] == '%' would be sufficient.
                    # TODO: Do this step afterwards, when every node is known all cycles can be connected
                    elif self.sfiles_list[token_idx+step].isdecimal() or\
                            (self.sfiles_list[token_idx+step][0] == '%' and
                             self.sfiles_list[token_idx+step][1:].isdecimal()):
                        # Previous unit operation
                        pre_op = list(filter(re.compile(pattern_node).match, last_ops))[-1]
                        # search for <# and add connection to unit operation that <# refers to
                        try:
                            # first make sure we remove the % sign in case the cycle number is >9
                            cyc_nr = re.findall(r'\d+', self.sfiles_list[token_idx+step])[0]
                            i = last_ops.index('<'+cyc_nr)
                            for ii in range(0, i+1):
                                if bool(re.match(pattern_node, last_ops[i-ii])):
                                    cycle_op = last_ops[i-ii]
                                    edges.append((pre_op[1:-1], cycle_op[1:-1], {'tags': tags}))
                                    tags = []
                                    break
                        # if the <# operator is not in the last operations we need to add the connection later
                        except ValueError: 
                            missing_circles.append((cyc_nr, tags))
                            tags = []
                    
                    # Branch opens. Looping through the branch until it is terminated.
                    elif self.sfiles_list[token_idx+step] == '[':
                        branches = 1
                        # TODO: What does variable found mean? Maybe also calculate len(self.sfiles_list)-1 in extra line to get rid of this ominous +1
                        # TODO: Why is this looping required? Only next node is added to edges? Why not break if found=true?
                        found = False
                        while not (token_idx + step) == last_index:
                            step += 1
                            if not found and bool(re.match(pattern_node, self.sfiles_list[token_idx+step])):
                                edges.append((token[1:-1], self.sfiles_list[token_idx+step][1:-1], {'tags': tags}))
                                tags = []
                                found = True
                            # If next token in sfiles_list is '[', a branch inside a branch is present.
                            if self.sfiles_list[token_idx+step] == '[':
                                branches += 1
                            # A branch inside a branch closes.
                            elif branches > 1 and self.sfiles_list[token_idx+step] == ']':
                                branches -= 1
                            # The first opened branch (==1) closes and will cause the exit of the while loop of branch.
                            elif branches == 1 and self.sfiles_list[token_idx+step] == ']':
                                branches -= 1
                                tags = []
                                break
                            # Tags in SFILES v2 in branch (usually the first token after branching)
                            elif bool(re.match(r'\{.*?\}', self.sfiles_list[token_idx+step])):
                                # Tags that are used for heat integration are not required
                                # (those are incorporated in node names)
                                # Branches needs to be 1 otherwise the tags of subbranches might be added
                                if not bool(re.match(r'^[0-9]+$', self.sfiles_list[token_idx+step][1:-1])) \
                                        and branches == 1:
                                    tags.append(self.sfiles_list[token_idx+step][1:-1])
                    
                    # New incoming branch
                    elif self.sfiles_list[token_idx+step] == '<&|':
                        # Increase steps until the corresponding | or &| is reached and continue looking for
                        # connections of node.
                        _continue = 1
                        while _continue:
                            step += 1
                            if self.sfiles_list[token_idx+step] == '<&|':
                                _continue += 1
                            if self.sfiles_list[token_idx+step] == '|' or self.sfiles_list[token_idx+step] == '&|':
                                _continue -= 1
                    
                    # Inside an incoming branch |, &| can occur on this level of if clauses.
                    # Find the node the incoming branch is leading to and add the connection.
                    elif self.sfiles_list[token_idx+step] == '&' or self.sfiles_list[token_idx+step] == '&|':
                        # Run backwards through last operations, search for unit operations, 
                        # but ignore everything if its token in this or another incoming branch
                        break_while = False
                        if self.sfiles_list[token_idx+step] == '&|':
                            # Only break searching for connections, when the incoming branch has no branches itself.
                            break_while = True
                        _ignore = 1
                        for e in reversed(last_ops):
                            if e == '<&|':
                                _ignore -= 1
                            if e == '|' or e == '&|':
                                _ignore += 1
                            if not _ignore and bool(re.match(pattern_node, e)):
                                edges.append((token[1:-1], e[1:-1], {'tags': tags}))
                                tags = []
                                break
                        # break while loop
                        if break_while:
                            break

                    # Tags in SFILES v2
                    elif bool(re.match(r'\{.*?\}', self.sfiles_list[token_idx+step])):
                        # Tags that are used for heat integration are not required
                        # (those are incorporated in node names)
                        if not bool(re.match(r'^[0-9]+$', self.sfiles_list[token_idx+step][1:-1])):
                            tags.append(self.sfiles_list[token_idx+step][1:-1])
                    
                    elif self.sfiles_list[token_idx+step] == '|':
                        break
                    elif self.sfiles_list[token_idx+step] == ']':
                        break
                    elif self.sfiles_list[token_idx+step] == 'n|':
                        break

            # append the current string to already visited operations
        for missing in missing_circles:
            # previous unit operation
            if bool(re.match(r'^[0-9]$', missing[0])): 
                circle_pos = self.sfiles_list.index(missing[0])
            else:  # % sign for cyc_nr>9
                circle_pos = self.sfiles_list.index('%'+missing[0])
            pre_op = list(filter(re.compile(pattern_node).match, self.sfiles_list[0: circle_pos+1]))[-1]
            # search for <# and add connection to unit operation that <# refers to
            if '<' + missing[0] in self.sfiles_list:
                i = self.sfiles_list.index('<' + missing[0])
                for ii in range(0, i):
                    if bool(re.match(pattern_node, self.sfiles_list[i-ii])):
                        cycle_op = self.sfiles_list[i-ii]
                        edges.append((pre_op[1:-1], cycle_op[1:-1], {'tags': missing[1]}))
                        tags = []
                        break
            elif '<_' + missing[0] in self.sfiles_list:
                i = self.sfiles_list.index('<_' + missing[0])
                for ii in range(0, i):
                    if bool(re.match(pattern_node, self.sfiles_list[i-ii])):
                        cycle_op = self.sfiles_list[i-ii]
                        edges.append((pre_op[1:-1], cycle_op[1:-1], {'tags': 'signal'}))
                        tags = []
                        break
        
        """ In this next section we loop through the nodes and edges lists and create the flowsheet with all unit and 
        stream objects. Please note that add_unit should not be called with initialize_child=True 
        because self.map_SFILES_to_Ontocape() only changes the state attribute but not the child objects"""
        for node in nodes:
            name = node[1:-1]
            self.add_unit(unique_name=name)

        for connection in edges:
            # adjust tags: tags:[..] to tags:{'he':[..],'col':[..]}
            regex_he = re.compile(r"(hot.*|cold.*|[0-9].*|Null)") # Null at the moment is used in Aspen/DWSim graphs for missing hex tags
            regex_col = re.compile(r"(^t.*|^b.*)")
            regex_signal = re.compile(r"(^T.*)")
            old_tags = connection[2]['tags']
            # TODO: Fix this! What are old tags? Why is this step necessary?
            tags = {'he': [m.group(0) for k in old_tags for m in [regex_he.search(k)] if m],
                    'col': [m.group(0) for k in old_tags for m in [regex_col.search(k)] if m],
                    'signal2unitop': [True if old_tags == 'signal' else False]}
            self.add_stream(connection[0], connection[1], tags=tags)

        """ Finally, the current self.state is not according to the OntoCape naming conventions so we map it back """
        if self.OntoCapeConform: 
            self.map_SFILES_to_Ontocape(merge_HI_nodes)
        elif merge_HI_nodes: 
            self.merge_HI_nodes()
        
    def create_from_nx(self, initial_flowsheet):
        """Methods to initialize the flowsheet from an already existing nx-Graph.

        Args:
            initial_flowsheet (nx graph): Already existing networkx-Graph, default case:
                                    initialized with one feed-node ('IO-1'), an unprocessed-node ('X-1')
                                    and a connecting edge with stream data

        Returns:
            sets the flowsheet's attribute "state" and replaces the default with the argument initial_flowsheet
        """
        self.state = initial_flowsheet


    def convert_to_sfiles(self, version='v2', remove_hex_tags=True):
        """
        Method to convert the flowsheet nx graph to string representation SFILES
        Yields both an SFILES string and a parsed list of the SFILES tokens 
        
        
        Parameters:
        ----------
        version (str): either v1 or v2. SFILES v2 contains more information regarding connectivity, default is v2
        OntoCape_mapping (bool): Specify as False if the input graph is according to SFILES standards (abbreviations, heat integration conventions in graph), defaults to True
        remove_hex_tags (bool): Whether to show heat exchanger tags in SFILES v2
        
        Returns:
        ----------
            sets the flowsheet's attribute "sfiles" and "sfiles_list"

        """
        if self.OntoCapeConform: 
            self.map_Ontocape_to_SFILES() # sets self.flowsheet_SFILES_names
        else: 
            self.split_HI_nodes() # does not modify self.state in case there are no multi-stream hex nodes, but already HI nodes in hex-#/# notation
            self.flowsheet_SFILES_names = self.state.copy()
        self.sfiles_list, self.sfiles = nx_to_SFILES(self.flowsheet_SFILES_names, version, remove_hex_tags)

    def create_random_flowsheet(self, add_sfiles=True):
        """This methods creates a random flowsheet
            The specification for the random flowsheet is created
            in a seperate class in the folder RandomFlowsheetGen

        Args:
            add_sfiles (boolean): True if SFILES representation should be added, default True

        Returns:
            None, adjustment of self.state (and self.sfiles)
        """
        random_flowsheet = Generate_flowsheet()
        
        for name in random_flowsheet.nodes:
            self.add_unit(unique_name=name)

        for connection in random_flowsheet.edges:
            # adjust tags: tags:[..] to tags:{'he':[..],'col':[..]}
            regex_he = re.compile(r"(hot.*|cold.*|[0-9].*)") # matches everything starting with 'hot', 'cold', or a number
            regex_col = re.compile(r"(^t.*|^b.*)") # matches e.g. 'b_out' or 'bout' 
            old_tags = connection[2]['tags']
            tags = {'he':[m.group(0) for l in old_tags for m in [regex_he.search(l)] if m],'col':[m.group(0) for l in old_tags for m in [regex_col.search(l)] if m]}
            self.add_stream(connection[0], connection[1], tags=tags)
        if add_sfiles:
            self.convert_to_sfiles(version='v2')

    def visualize_flowsheet(self, figure=True, plot_with_stream_labels=True,  table=True, plot_as_pfd=True,
                            pfd_block=True, decimals=3, pfd_path='plots/flowsheet', chemicalspecies=None,
                            add_positions=True):
        """This methods visualizes the process as a flowsheet and/or a streamtable.

        Args:
            figure (boolean): True if flowsheet should be showed, otherwise False.
            table (boolean): True if streamtable and unittable should be showed, otherwise False.
            decimals (int): Amount of decimals showed in the streamtable.
            plot_with_stream_labels (boolean): True if labels should be shown in the flowsheet (otherwise just a simple
                                graph visualization)
            plot_as_pfd (boolean): True if the flowsheet is plotted using the pyflowsheet package. Otherwise, it is
                                   plotted using the networkx package.
            pfd_block (boolean): True: creates a block-flowsheet, False: creates a flowsheet with unit-figures.
            pfd_path (string): Path to save the pfd as svg.
            chemicalspecies: List with string names of chemical species considered in the process
            add_positions: boolean telling whether a position attribute already exists

        Returns:
            fig: Figure showing the flowsheet
            table_streams: table with all stream information
            table_units: table with all unit information
        """
        fig = None
        table_streams = None
        table_units = None

        if table:
            # Shows the streamtable for the process including the stream name, corresponding edge, amount of moles,
            # temperature, pressure and molefractions.
            table_streams = create_stream_table(self.state, chemicalspecies, decimals)
            # Shows the unit table for the process including the unit name, unit type, and continuous decision
            table_units = create_unit_table(self.state, decimals)

        if figure:
            # Plot the nx-graph
            fig = plot_flowsheet_nx(self.state, plot_with_stream_labels, add_positions)

        if plot_as_pfd:
            # Create a flowsheet
            plot_flowsheet_pyflowsheet(self.state, block=pfd_block, imagepath=pfd_path, add_positions=add_positions)
            # No return, is directly saved as svg using the imagepath

        return fig, table_streams, table_units


    """ Helper functions SFILES related """

    def flatten(self, l):
        """
        Helper function that returns a flattened list

        Parameters
        ----------
        l (list): nested list
        
        Returns
        ----------
        l_flat (list): flat list
        """
        l_flat = []
        for i in l:
            if isinstance(i, list): l_flat.extend(self.flatten(i))
            else: l_flat.append(i)
        return l_flat

    def split_dictionary(self, input_dict, chunk_size):
        """
        Helper function that returns sliced dictionaries

        Parameters
        ----------
        input_dict (dict): dictionary to be chunked
        chunk_size (int): chunk size
        
        Returns
        ----------
        res (list): list of chunked dictionaries
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
        """
        Parses a SFILES string and returns a list with SFILES elements
        ! At the moment assumes that there are less than 100 cycles !
        
        Returns
        ----------
        sfiles_list (list): SFILES as list
        """

        # First convert string to list
        sfiles_regex_pattern = r"(\(.*?\)|\{.*?\}|\%\([0-9]{3}\)|\%[0-9]{2}|\]|\[|\<.?[0-9]|\<\&\||(?<!\<)\&\||n\||(?<!\&)(?<!n)\||\&(?!\|)|\/[0-9]|[0-9])"
        regex = re.compile(sfiles_regex_pattern)
        sfiles_list = [token for token in regex.findall(self.sfiles)]
        # TODO: Remove lines below if not used!
        r = re.compile(r"(\(.*?\))")
        nodes = list(filter(r.match, sfiles_list))
        
        return sfiles_list
    
    def map_SFILES_to_Ontocape(self, merge_HI_nodes):
        """
        Current self.state is according to SFILES abbreviations.
        This function maps the SFILES abbreviations back to OntoCape vocabulary. 
        Uses the Ontocape_SFILES_mapping to modify self.state. The previous self.state is copied to the attribute self.flowsheet_SFILES_names
        Additionally, the 

        """
        SFILES_node_names = list(self.state.nodes)
        relabel_mapping = {}
        for n in SFILES_node_names:
            _name = n.split(sep='-')[0] # name without number
            _num = n.split(sep='-')[1]
            _OC_term = list(OntoCape_SFILES_map.keys())[list(OntoCape_SFILES_map.values()).index(_name)]
            relabel_mapping[n] = _OC_term +'-'+ _num

        flowsheet_SFILES = self.state.copy()
        self.state = nx.relabel_nodes(self.state, relabel_mapping)

        " Merge heat integrated hex nodes into one node using tags for edges again."
        """ " This parameter is set to False at the moment, because it might result in unwanted behavior: 
        Assume a heat exchanger that takes both top and bottom product of column -> network x cannot have 2 edges with the same in and out node but different tags :( """
        if merge_HI_nodes:
            self.merge_HI_nodes()

        self.flowsheet_SFILES_names = flowsheet_SFILES

    def merge_HI_nodes(self):
        """
        For non-ontocape conform SFILES
        Merge heat integrated hex nodes into one node and creating connectivity tags, so it is possible to split nodes
        again later.
        """
        relabel_mapping = {}
        create_tags_map = {}
        state_copy = self.state.copy()
        for n in list(state_copy.nodes): 
            if '/' in n and not bool(re.match(r'.*/[A-Z]+', n)):
                relabel_mapping[n] = n.split(sep='/')[0]
                create_tags_map[n] = n.split(sep='/')[1]
    
        for n1, n2 in relabel_mapping.items():
            counter = create_tags_map[n1]
            edge_infos = nx.get_edge_attributes(state_copy, "tags")
            edge_in = list(state_copy.in_edges(n1))
            edge_out = list(state_copy.out_edges(n1))
            edge_infos_in = [v for k, v in edge_infos.items() if k in edge_in][0]  # only one item
            edge_infos_in['he'].append('%s_in'%counter)
            edge_infos_out = [v for k, v in edge_infos.items() if k in edge_out][0]  # only one item
            edge_infos_out['he'].append('%s_out'%counter)
            
            #remove old node and delete old edges + create new node if it does not exist and edges
            state_copy.remove_node(n1)
            if not n2 in list(state_copy.nodes):
                state_copy.add_node(n2)
            state_copy.add_edges_from([(edge_in[0][0],n2,{'tags':edge_infos_in}),(n2,edge_out[0][1],{'tags':edge_infos_out})])
        
        if len(state_copy.edges) == len(self.state.edges): # this has to be still equal, otherwise merge failed
            self.state = state_copy
        else: 
            print('Warning: seems like two streams of heat exchanger are connected to same unit operation and in have same edge directions. No merging in NetworkX possible')

    def split_HI_nodes(self, OntoCapeNames=False):
        """ 
        Heat integrated heat exchanger nodes are splitted.
        (Only if there is a multistream heat exchanger node with corresponding he tags)
        """
        if OntoCapeNames:
            heatexchanger = 'HeatExchanger'
        else:
            heatexchanger = 'hex'
        for n in list(self.state.nodes):
            if heatexchanger in n and self.state.in_degree(n) > 1:  # Heat exchangers with more than 1 streams
                assert(self.state.out_degree(n) == self.state.in_degree(n))
                edge_infos = nx.get_edge_attributes(self.state, "tags")
                edges_in = list(self.state.in_edges(n))
                edges_out = list(self.state.out_edges(n))
                # Edges with infos only for that heat exchanger
                edge_infos_he_in = {k: v for k, v in edge_infos.items() if k in edges_in}
                # Edges with infos only for that heat exchanger
                edge_infos_he_out = {k: v for k, v in edge_infos.items() if k in edges_out}

                # Here we try to match the inlet with their corresponding outlet streams using the tags
                # (This works for tags of the form hot_in,hot_out,cold_in,cold_out,1_in,1_out, ...)
                try:
                    assert(len(edge_infos_he_in.keys()) == len(edges_in))
                    assert(len(edge_infos_he_out.keys()) == len(edges_out))
                    # Sort by he_tags -> cold and hot substring is used for sorting
                    edges_in_sorted = dict(sorted(edge_infos_he_in.items(),
                                                  key=lambda item: [s for s in item[1]['he'] if 'in' in s][0]))
                    # Sort by he_tags -> cold and hot string is used
                    edges_out_sorted = dict(sorted(edge_infos_he_out.items(),
                                                   key=lambda item: [s for s in item[1]['he'] if 'out' in s][0]))
                    heat_exchanger_subs_in = self.split_dictionary(edges_in_sorted, 1)  # Splits for each stream
                    heat_exchanger_subs_out = self.split_dictionary(edges_out_sorted, 1)  # Splits for each stream
                    heat_exchanger_subs = [{**heat_exchanger_subs_in[i], **heat_exchanger_subs_out[i]}
                                           for i in range(0, len(heat_exchanger_subs_in))]
                    new_nodes = []
                    new_edges = []

                    # TODO: Test if this is correct.
                    hex_sub_temp = False
                    for i, hex_sub in enumerate(heat_exchanger_subs):
                        new_node = n+'/%d' % (i+1)
                        new_nodes.append(new_node)  # Nodes

                        for old_edge, attributes in hex_sub.items():
                            if hex_sub_temp == hex_sub.get(old_edge):
                                continue
                            else:
                                # Check if heat exchanger is connected to itself.
                                if old_edge[0] == old_edge[1]:
                                    new_node_2 = n+'/%d' % (i+2)
                                    new_edge = (new_node, new_node_2)
                                    hex_sub_temp = hex_sub.get(old_edge)
                                else:
                                    new_edge = tuple(s if s != n else new_node for s in old_edge)
                                    #new_edge = tuple(map(lambda i: str.replace(i, n,new_node), old_edge))

                                new_edges.append((new_edge[0], new_edge[1], {'tags': attributes}))  # edges with attributes
                    "Delete old node and associated edges first"
                    self.state.remove_node(n)
                    self.state.add_nodes_from(new_nodes)
                    self.state.add_edges_from(new_edges)
                except Exception:
                    warnings.warn("Warning: No he tags (or not of all connected edges) found for this multistream "
                                  "heat exchanger. The multi-stream heat exchanger will be represented as one node.",
                                  DeprecationWarning)
    
    def map_Ontocape_to_SFILES(self):
        """
        Function that returns a graph with the node names according to SFILES abbreviations for OntoCape unit operation names.
        Additionally, the heat exchanger nodes (with more than 1 stream) are split up for each stream according to the he tags (edge attribute tags:{he:[]}).
        Uses the Ontocape_SFILES_mapping to set self.flowsheet_SFILES_names.
        
        """
        self.split_HI_nodes(OntoCapeNames = True)

        " Relabel from OntoCape to SFILES abbreviations"
        relabel_mapping = {}
        for n in list(self.state.nodes):
            _name = n.split(sep='-')[0] # name without number
            _num = n.split(sep='-')[1]
            _abbrev = OntoCape_SFILES_map[_name]
            relabel_mapping[n] = _abbrev +'-'+ _num

        flowsheet_SFILES = self.state.copy()
        flowsheet_SFILES = nx.relabel_nodes(flowsheet_SFILES, relabel_mapping)

        self.flowsheet_SFILES_names = flowsheet_SFILES

    def add_edge_tags(self, edges, nodes):
        """
        Helper function that assigns tags in SFILES (node related) to corresponding edges in graph

        Parameters
        ----------
        edges (list): list of edges without tags
        nodes (dict): Mapping of nodes and in and out tags
        
        Returns
        ----------
        edges (list): list of edges with tags
        """
        for i, edge in enumerate(edges):
            e1 = edge[0]
            e2 = edge[1]
            out_con = nodes[e1]['out_connect']
            in_con = nodes[e2]['in_connect']
            common_tags = list(set(out_con).intersection(in_con))
            if len(common_tags) > 1:
                raise Exception('The used tags are not unambigous. '
                                'The edge of nodes %s and %s has two common tags in the SFILES.' % (e1, e2))
            elif len(common_tags) == 1:  # only one tag per edge!
                edges[i] = (e1, e2, {'tags': [common_tags[0]]})
            else: 
                edges[i] = (e1, e2, {'tags': []})
        return edges

    def renumber_generalized_SFILES(self):
        """
        Helper function that renumbers the generalized SFILES, in specific the unit operations
        Modifies the attribute self.sfiles_list and returns list of node names.

        Returns
        ----------
        nodes (list): list of numbered node names
        """
        unit_counting = {}
        HI_hex = {}
        for s_idx, s in enumerate(self.sfiles_list):

            if bool(re.match(r'\(.*?\)', s)):  # Current s is a unit operation
                unit_cat = s[1:-1]
                if unit_cat not in unit_counting:  # First unit in SFILES of that category
                    unit_counting[unit_cat] = 1
                    unit_name = unit_cat + '-' + '1'
                    # Check if the current unit is a hex unit with heat integration -> Special node name
                    # Only if it's not the last token
                    if s_idx < len(self.sfiles_list)-1:
                        if bool(re.match(r'\{[0-9]+\}', self.sfiles_list[s_idx+1])):
                            _HI_number = self.sfiles_list[s_idx+1][1:-1]
                            HI_hex[_HI_number] = (unit_name, 1)
                            # Add HI notation to hex node name
                            unit_name = unit_name + '/1'
                        elif bool(re.match(r'\{[A-Z]+\}', self.sfiles_list[s_idx + 1])):
                            unit_name = unit_name + '/' + self.sfiles_list[s_idx + 1][1:-1]
                else: 
                    # Check if the current unit is a unit with heat integration -> Special node name
                    # Only possible if it's not the last token
                    if s_idx < len(self.sfiles_list)-1:
                        if bool(re.match(r'\{[0-9]+\}', self.sfiles_list[s_idx+1])):
                            _HI_number = self.sfiles_list[s_idx+1][1:-1]
                            # Check if _HI_number is already in HI_hex dict keys
                            if _HI_number in HI_hex: 
                                _occurrence = HI_hex[_HI_number][1]+1
                                # TODO: Modify line to  HI_hex[_HI_number][1] = _occurrence ??
                                HI_hex[_HI_number] = (HI_hex[_HI_number][0], _occurrence)
                                unit_name = HI_hex[_HI_number][0]+'/'+str(_occurrence)
                            else: 
                                # TODO: Line below is redundant?
                                _HI_number = self.sfiles_list[s_idx+1][1:-1]
                                unit_counting[unit_cat] += 1
                                unit_name = unit_cat + '-' + str(unit_counting[unit_cat])
                                HI_hex[_HI_number] = (unit_name, 1)
                                unit_name = unit_name + '/1'

                        elif bool(re.match(r'\{[A-Z]+\}', self.sfiles_list[s_idx + 1])):
                            unit_counting[unit_cat] += 1
                            unit_name = unit_cat + '-' + str(unit_counting[unit_cat]) + '/' + \
                                        self.sfiles_list[s_idx + 1][1:-1]
                        else:
                            # TODO: Introduce a separate function for these two lines of code?
                            unit_counting[unit_cat] += 1
                            unit_name = unit_cat + '-' + str(unit_counting[unit_cat])
                    else:
                        unit_counting[unit_cat] += 1
                        unit_name = unit_cat + '-' + str(unit_counting[unit_cat])
                
                # Modify the token in sfiles list
                self.sfiles_list[s_idx] = '('+unit_name+')'
        
        # node names from sfiles list
        r = re.compile(r"(\(.*?\))")
        nodes = list(filter(r.match, self.sfiles_list))

        return nodes
from Flowsheet_Class.RandomFlowsheetGen_OC.patterns import *
from Flowsheet_Class.RandomFlowsheetGen_OC.unit_operations import unit_ops, unit_ops_probabilities
import sys
import os
import random


"""
This Python class creates a random flowsheet graph
using several random sequences (markov chain like). 
Some of the process patterns are derived from the pattern recognition paper: 
Zhang, T., Sahinidis, N. V., & Siirola, J. J. (2019). Pattern recognition in chemical process flowsheets. AIChE Journal, 65(2), 592-603.
"""
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class Generate_flowsheet:
    """
    Creates an object with nodes and edges specification of random flowsheet
    """

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.unit_ops = unit_ops
        _detailed_ops = self.flatten(list(unit_ops.values()))
        self.operation_counter = {s: 1 for s in _detailed_ops}
        self.HI_hex_stream_counter = {}
        self.include_controls = False

        # 1. Initializing step determine the number of raw materials
        self.raw_materials()
        # 2. Choose first type of unit operation:
        self.next_operation(connect_info=[], first_operation=True)
        # 3. Restructure the edge list -> conformity with flowsheet class representation
        self.edges = [(e[0][0], e[0][1], {'tags': e[1]['in_connect']+e[1]['out_connect']}) for e in self.edges]

    def raw_materials(self):
        """ The raw materials part of the process 
            - up to 3 raw materials
            - random heat exchangers and pumps
            - mix the streams with mixers 'mix-#'
        """
        
        #self.number_raw = random.choice([1, 2, 3])  # chose the first node randomly, each node with equal probability
        # TODO: for now only two raw material streams are allowed!
        self.number_raw = random.choice([1, 2])  # chose the first node randomly, each node with equal probability
        for n in range(1, self.number_raw+1):

            _current_node = 'RawMaterial-%d' % self.operation_counter['RawMaterial']
            self.nodes.append(_current_node)
            self.operation_counter['RawMaterial'] += 1

            # Two raw materials
            if self.number_raw == 2:
                while True:  # break when mixer is reached
                    _next_op_cat = random.choices(['Mixing', 'TemperatureChange', 'PressureChange'],
                                                  [0.7, 0.2, 0.1])[0]
                    _next_op = random.choices(unit_ops_probabilities[_next_op_cat][0],
                                              unit_ops_probabilities[_next_op_cat][1])[0]
                    _next_op_name = _next_op + '-' + str(self.operation_counter[_next_op])

                    if _next_op_cat == 'Mixing':
                        # Mixer of material 1 and 2
                        if n == 1:
                            self.nodes.append(_next_op_name)
                            node1 = self.nodes[-2]
                            mixing = self.nodes[-1]
                            if not self.include_controls:
                                self.edges.append(
                                    ((_current_node, _next_op_name), {'in_connect': [], 'out_connect': []}))
                                _current_node = _next_op_name
                        elif n == 2:
                            # Node already exists
                            node2 = self.nodes[-1]
                            self.operation_counter[_next_op] += 1
                            if self.include_controls:
                                self.mixing_ctrl_pattern(node1, node2, mixing)
                                _current_node = _next_op_name
                            else:
                                self.edges.append(
                                    ((_current_node, _next_op_name), {'in_connect': [], 'out_connect': []}))
                                _current_node = _next_op_name
                        break

                    else:
                        if _next_op_cat == 'TemperatureChange' and self.include_controls:
                            _current_node = self.temperature_ctrl_pattern(_current_node)
                        elif _next_op_cat == 'PressureChange' and self.include_controls:
                            _current_node = self.pressure_ctrl_pattern(_current_node, _next_op)
                        else:
                            self.operation_counter[_next_op] += 1
                            self.nodes.append(_next_op_name)
                            self.edges.append(((_current_node, _next_op_name), {'in_connect': [], 'out_connect': []}))
                            _current_node = _next_op_name



            # Three raw materials
            elif self.number_raw == 3:
                while True:  # break when mixer is reached
                    _next_op_cat = random.choices(['Mixing', 'TemperatureChange', 'PressureChange'],
                                                  [0.7, 0.2, 0.1])[0]
                    _next_op = random.choices(unit_ops_probabilities[_next_op_cat][0],
                                              unit_ops_probabilities[_next_op_cat][1])[0]
                    _next_op_name = _next_op + '-' + str(self.operation_counter[_next_op])
                    if _next_op_name not in self.nodes:
                        self.nodes.append(_next_op_name)
                    self.edges.append(((_current_node, _next_op_name), {'in_connect': [], 'out_connect': []}))
                    _current_node = _next_op_name

                    if _next_op_cat == 'Mixing':
                        if n == 1:
                            break
                        # Mixer of material 1 and 2
                        elif n == 2 and self.operation_counter[_next_op] == 1:
                            self.operation_counter[_next_op] += 1
                        # Mixer of material 2 and 3
                        elif n == 2 and self.operation_counter[_next_op] == 2:
                            break
                        # Mixer of material 2 and 3
                        elif n == 3:
                            # do not add unit, it's the previous mixer
                            self.operation_counter[_next_op] += 1
                            break
                    else:
                        self.operation_counter[_next_op] += 1

        self.last_node = _current_node  # last node (MixingUnit-1, MixingUnit-2 or RawMaterial-1)


    def next_operation(self, connect_info=[], first_operation=False):
        """ The choice of first pattern/operation
            - random choice between different operations:
                - 'Reactor','Column','Separator','Vessel'
            - for the first operation 'Purification' is not possible
        """
        if first_operation:
            # first Choice after the raw materials
            _next_op_cat = random.choices(['Reaction', 'ThermalSeparation', 'CountercurrentSeparation', 'Filtration',
                                           'CentrifugalSeparation'], [0.25, 0.4, 0.25, 0.05, 0.05])[0]
        else:
            _next_op_cat = random.choices(['Purification', 'Reaction', 'ThermalSeparation', 'CountercurrentSeparation',
                                           'Filtration', 'CentrifugalSeparation'],
                                          [0.5, 0.125, 0.2, 0.125, 0.025, 0.025])[0]

        if _next_op_cat == 'Reaction':
            self.reaction(connect_info)
            
        elif _next_op_cat == 'ThermalSeparation':
            self.separation_thermal(connect_info)

        elif _next_op_cat == 'CountercurrentSeparation':
            self.separation_sep(connect_info)
        
        elif _next_op_cat == 'Filtration':
            self.separation_filt(connect_info)

        elif _next_op_cat == 'CentrifugalSeparation':
            self.separation_centr(connect_info)

        elif _next_op_cat == 'Purification':
            self.purification(connect_info)

    def reaction(self, connect_info):
        """ 
        - The following lines randomly (with probabilities, see Patterns.py) picks a pattern containing a reactor
        - afterwards we go back to further_operation()
        - additionally special operations: recycling stream, heat integration, additional reactants
        """
        _current_node = self.last_node

        pattern = random.choices(list(reactor_patterns.keys()), [i[1][0] for i in list(reactor_patterns.values())])[0]
        
        # Connect the last node to first of this pattern
        for _next_op_cat in reactor_patterns[pattern][0]:
            _next_op_name, _ = self.select_unit_name(_next_op_cat)
            self.nodes.append(_next_op_name)
            self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
            connect_info = []  # Reset connect_info after first edge in this function.
            # Reset the current node
            _current_node = _next_op_name
        
        # Save reactor node name. Reactor always last element of reactor pattern.
        _reac_node = _current_node
        
        # Recycling, Heat integration, additional reactants, and None
        if 'TemperatureChange' in reactor_patterns[pattern][0]:
            special_op = random.choices(['Rec', 'HI', 'AddR', 'None'], [0.35, 0.25, 0.2, 0.2])[0]
        else:
            special_op = random.choices(['Rec', 'AddR', 'None'], [0.35, 0.2, 0.45])[0]

        """
        ----------
        Recycling:
        We need to insert a mixer before the reactor node, a splitter after the reactor node and adjust the edges
        ----------
        """ 
        if special_op == 'Rec':
            # Mixer
            _mixer_name, _ = self.select_unit_name('Mixing')
            # Adjust the edges
            _last_edge = self.edges.pop()
            _presuc = _last_edge[0][0]  # e.g. heat exchanger
            _suc = _last_edge[0][1]  # Reactor
            _presuc_info = _last_edge[1]['in_connect']
            _suc_info = _last_edge[1]['out_connect']
            # new mixer node
            self.nodes.insert(-1, _mixer_name)

            # two new edges needed
            # e.g. heat exchanger to mixer
            self.edges.append(((_presuc, _mixer_name), {'in_connect': _presuc_info, 'out_connect': []}))
            self.edges.append(((_mixer_name, _suc), {'in_connect': [], 'out_connect': _suc_info}))  # mixer to reactor
            # splitter
            _splitter_name, _ = self.select_unit_name('Splitting')
            self.nodes.append(_splitter_name)
            # adjust the edges
            # splitter to mixer
            self.edges.append(((_splitter_name, _mixer_name), {'in_connect': [], 'out_connect': []}))
            self.edges.append(((_suc, _splitter_name), {'in_connect': [], 'out_connect': []}))  # reactor to splitter

            # splitter is the node where to continue from
            _current_node = _splitter_name
        
        """
        ----------
        Heat integration:
        We use the heat exchanger in the reactor pattern as node after reactor 
        According to the description in the SFILES Paper we create a second node hex-#/2 for the second stream that 
        enters the Hex
        And adjust the node for the first stream: hex-#/1
        By default the first heat exchanger (2 possible) is used for HI
        ----------
        """ 
        if special_op == 'HI':
            # nodes[nodepos] where nodepos =-len(pattern)+pos(1.heat exchanger)
            _nodepos = - len(reactor_patterns[pattern][0]) + reactor_patterns[pattern][0].index('TemperatureChange')
            _heat_ex_HI = self.nodes[_nodepos] # node name of hex
            if '/' in _heat_ex_HI:  # already heat integration
                _stream_nr_HI = _heat_ex_HI.split(sep='/')[1]
                _hex_name_HI = _heat_ex_HI.split(sep='/')[0]
                _next_stream_HI_node = _hex_name_HI + '/%s' % (self.HI_hex_stream_counter[_hex_name_HI]+1)
                # node and edge for new stream
                self.nodes.append(_next_stream_HI_node)
                self.HI_hex_stream_counter[_hex_name_HI] += 1
                self.edges.append(((_current_node, _next_stream_HI_node), {'in_connect': connect_info,
                                                                           'out_connect': []}))
            else: # newly added heat integration
                # Adjust hex node name and the edges of original node
                # overwrite hex-# with hex-#/1
                _new_name = _heat_ex_HI + '/1'
                self.nodes[_nodepos] = _new_name
                # adjust edges
                self.adjust_HI_edges(_heat_ex_HI, _new_name, 'in')
                self.adjust_HI_edges(_heat_ex_HI, _new_name, 'out')
                # node and edge for second stream
                _next_stream_HI_node = _heat_ex_HI + '/2'
                self.nodes.append(_next_stream_HI_node)
                self.edges.append(((_current_node, _next_stream_HI_node),
                                   {'in_connect': connect_info, 'out_connect': []}))
                self.HI_hex_stream_counter[_heat_ex_HI] = 2  # 2 nodes
            
            # set current node to new hex node
            _current_node = _next_stream_HI_node
            connect_info = []

        """
        ----------
        Add reactants:
        The only thing to do is to add one new input stream that ends in the reactor
        ----------
        """ 
        if special_op == 'AddR':
            pattern = random.choices(list(addR_patterns.keys()), [i[1][0] for i in list(addR_patterns.values())])[0]
            for i, _next_op_cat in enumerate(addR_patterns[pattern][0]):
                if i == 0:  # i=0 is the start of the incoming detergent branch -> only node no edge
                    _next_op_name, _next_op = self.select_unit_name(_next_op_cat)
                    self.nodes.append(_next_op_name)
                else:
                    # no new node (already created _reac_node) and out_connect info, and reduce operation counter
                    if _next_op_cat == 'Reaction':
                        self.edges.append(((_current_node, _reac_node),
                                           {'in_connect': connect_info, 'out_connect': []}))
                    else: 
                        # detergent preprocessing with node and edge for instance hex in Feed-hex-sep sequence
                        _next_op_name, _next_op = self.select_unit_name(_next_op_cat)
                        self.nodes.append(_next_op_name)
                        self.edges.append(((_current_node, _next_op_name),
                                           {'in_connect': connect_info, 'out_connect': []}))
                connect_info = []  # reset connect_info
                # reset the current node
                _current_node = _next_op_name

            # Set current node to reactor node -> where we want to continue
            _current_node = _reac_node
                
        # reset the last node to current_node -> Where we continue
        # (AddR: _reac_node, HI: _next_stream_HI_node, Rec: _splitter_name)
        self.last_node = _current_node

        # Next subprocess
        self.next_operation(connect_info)

    def separation_col(self, connect_info):
        """ 
        - !!! Currently not used (in DistillationSystem and RectificationSystem reboilers and condensers are included) !!!
        - The following lines randomly (with probabilities, see Patterns.py) picks a pattern containing a column
        - start of branches (1 feed stream -> two seperated streams)
        - afterwards we go back to next_operation()
        - special operations: reflux stream
        """
        _current_node = self.last_node
        pattern = random.choices(list(thermal_sep_patterns.keys()),
                                 [i[1][0] for i in list(thermal_sep_patterns.values())])[0]
        
        # Connect the last node to first of this pattern
        for _next_op_cat in thermal_sep_patterns[pattern][0]:
            _next_op_name, _ = self.select_unit_name(_next_op_cat)
            self.nodes.append(_next_op_name)
            self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
            connect_info = []  # Reset connect_info after first node in this function
            # Reset the current node
            _current_node = _next_op_name
        
        """
        ----------
        Refluxes
        Branches
        ----------
        """ 
        # 1. Adjust column node with top and bottom connections
        
        _branches = ['tout', 'bout']
        for b in _branches:
            if b == 'bout' and random.choices(['reb', 'noreb'], [0.5, 0.5])[0] == 'reb':
                _reb_lower, _ = self.select_unit_name('Reboiler')
                self.nodes.append(_reb_lower)
                # Edges in both directions
                self.edges.append(((_current_node, _reb_lower), {'in_connect': [b], 'out_connect': []}))
                self.edges.append(((_reb_lower, _current_node), {'in_connect': [], 'out_connect': []}))
                # last node is reboiler
                self.last_node = _reb_lower

                # Next operation of branch
                self.next_operation(connect_info=[])

            else:  # Top or bottom and no reboiler
                # heat exchanger 
                _hex, _ = self.select_unit_name('TemperatureChange')
                self.nodes.append(_hex)
                self.edges.append(((_current_node, _hex), {'in_connect': [b], 'out_connect': []}))
                _split_op_cat = random.choices(['Splitter', 'Tank', 'Vessel'], [0.5, 0.25, 0.25])[0]
                _split_op_name, _ = self.select_unit_name(_split_op_cat)
                self.nodes.append(_split_op_name)
                # edge from hex to split operation and edge from split operation back to column
                self.edges.append(((_hex, _split_op_name), {'in_connect': [], 'out_connect': []}))
                self.edges.append(((_split_op_name, _current_node), {'in_connect': [], 'out_connect': []}))
                # last node is the splitter
                self.last_node = _split_op_name

                # Next operation of branch
                self.next_operation(connect_info=[])

    def separation_sep(self, connect_info):
        """ 
        - Can either be an absorption (g,l) or extraction (l,l) operation 
        - We assume counter current for those kind of separations
        - The following lines randomly (with probabilities, see Patterns.py) picks a pattern containing a separator
        - branching
        - for each branch continue to next_operation()
        """

        """ Setup either extraction or absorption """
        _current_node = self.last_node
        extraction = random.choices([1, 0], [0.5, 0.5])[0]  # 0 is absorption
        if extraction:  # detergent can be either streaming up or down (density dependent)
            _branches = ['t', 'b']
            random.shuffle(_branches)
        else:
            # absorption: detergent is always streaming down (higher density than gas) -> no shuffling
            _branches = ['t', 'b']

        """ Pattern for main inlet stream """
        if extraction:
            pattern = random.choices(list(CC_sep_patterns.keys()), [i[1][0] for i in list(CC_sep_patterns.values())])[0]

            "Pattern for main stream preprocessing"
            for _next_op_cat in CC_sep_patterns[pattern][0]:
                _next_op_name, _ = self.select_unit_name(_next_op_cat)
                self.nodes.append(_next_op_name)
                if _next_op_cat == 'CountercurrentSeparation':
                    # main stream is second item in _branches list (assert absorption inlet of main stream is bottom)
                    self.edges.append(((_current_node, _next_op_name),
                                       {'in_connect': connect_info, 'out_connect': ['%sin' % _branches[1]]}))
                else:
                    self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
                connect_info = []  # Reset connect_info after first edge in this function
                # Reset the current node
                _current_node = _next_op_name
                _sep_node = _next_op_name

        else:  # Absorption, stripping, scrubbing
            pattern = random.choices(list(CC_sep_patterns.keys()), [i[1][0] for i in list(CC_sep_patterns.values())])[0]

            "Pattern for main stream preprocessing"
            for _next_op_cat in CC_sep_patterns[pattern][0]:
                _next_op_name, _ = self.select_unit_name(_next_op_cat)
                self.nodes.append(_next_op_name)
                if _next_op_cat == 'CountercurrentSeparation':
                    # main stream is second item in _branches list (assert absorption inlet of main stream is bottom)
                    self.edges.append(((_current_node, _next_op_name),
                                       {'in_connect': connect_info, 'out_connect': ['%sin' % _branches[1]]}))
                else:
                    self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
                connect_info=[] # reset connect_info after first edge in this function
                # Reset the current node
                _current_node = _next_op_name
                _sep_node = _next_op_name
        """
        ----------
        Detergent
        Branches
        ----------
        """
        for i, b in enumerate(_branches):
            if i == 0:  # First branch with inlet pattern for detergent
                pattern = random.choices(list(detergent_patterns.keys()),
                                         [i[1][0] for i in list(detergent_patterns.values())])[0]

                # Connect the last node to first of this pattern
                for i, _next_op_cat in enumerate(detergent_patterns[pattern][0]):
                    _next_op_name, _next_op = self.select_unit_name(_next_op_cat)
                    if i == 0:  # i=0 is the start of the incoming detergent branch -> only node no edge
                        self.nodes.append(_next_op_name)
                    else:
                        # no new node (already created _sep_node) and out_connect info
                        if _next_op_cat == 'CountercurrentSeparation':
                            self.operation_counter[_next_op] -= 1  # reduce operation counter
                            self.edges.append(((_current_node, _sep_node),
                                               {'in_connect': connect_info, 'out_connect': ['%sin' % b]}))
                        else:
                            # detergent preprocessing with node and edge for instance hex in Feed-hex-sep sequence 
                            self.nodes.append(_next_op_name)
                            self.edges.append(((_current_node, _next_op_name),
                                               {'in_connect': connect_info, 'out_connect': []}))
                    connect_info = []  # Reset connect_info
                    # Reset the current node
                    _current_node = _next_op_name

                # Connect info for the outlet branch and further operation
                connect_info = ['%sout' % b]
                self.last_node = _sep_node
                self.next_operation(connect_info)

            # second branch with inlet pattern for main stream (already generated in beginning of this function)
            elif i == 1:
                # Connect info for the outlet branch and further operation
                connect_info = ['%sout' % b]
                self.last_node = _sep_node
                self.next_operation(connect_info)

    def separation_thermal(self, connect_info):
        """ 
        - The following lines randomly (with probabilities, see Patterns.py) picks a pattern containing a vessel
        - start of branches (1 feed stream -> two seperated streams)
        - afterwards we go back to further_operation()
        """
        _current_node = self.last_node
        pattern = random.choices(list(thermal_sep_patterns.keys()),
                                 [i[1][0] for i in list(thermal_sep_patterns.values())])[0]
        # Connect the last node to first of this pattern
        for _next_op_cat in thermal_sep_patterns[pattern][0]:
            _next_op_name, _ = self.select_unit_name(_next_op_cat)
            self.nodes.append(_next_op_name)
            self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
            connect_info = []  # Reset connect_info after first edge in this function
            # Reset the current node
            _current_node = _next_op_name
        
        """
        ----------
        Branches
        ----------
        """ 
        _branches = ['bout', 'tout']
        for b in _branches:
            self.last_node = _current_node
            # Next operation of branch
            connect_info = [b]
            self.next_operation(connect_info)


    def separation_filt(self, connect_info):
        """ 
        - The following lines randomly (with probabilities, see Patterns.py) picks a pattern containing a vessel
        - start of branches (1 feed stream -> two seperated streams)
        - afterwards we go back to further_operation()
        """
        _current_node = self.last_node
        pattern = random.choices(list(filtration_patterns.keys()),
                                 [i[1][0] for i in list(filtration_patterns.values())])[0]
        # Connect the last node to first of this pattern
        for _next_op_cat in filtration_patterns[pattern][0]:
            _next_op_name, _category = self.select_unit_name(_next_op_cat)
            self.nodes.append(_next_op_name)
            self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
            connect_info = []  # Reset connect_info after first edge in this function
            # Reset the current node
            _current_node = _next_op_name
        
        """
        ----------
        Branches
        ----------
        """ 
        _branches = ['bout', 'tout']
        for b in _branches:
            self.last_node = _current_node
            # Next operation of branch
            connect_info = [b]
            # by definition we say that the top outlet is the filtrated one, bout directly to OutputProduct
            if (b == 'bout' and _category == 'GasFilter') or (b == 'tout' and _category == 'LiquidFilter'):
                outlet_node = 'OutputProduct-%d' % self.operation_counter['OutputProduct']
                self.nodes.append(outlet_node)
                self.edges.append(((_current_node, outlet_node), {'in_connect': connect_info, 'out_connect': []}))
                self.operation_counter['OutputProduct'] += 1
            else:
                self.next_operation(connect_info)
    
    def separation_centr(self, connect_info):
        """ 
        - The following lines randomly (with probabilities, see Patterns.py) picks a pattern containing a vessel
        - start of branches (1 feed stream -> two seperated streams)
        - afterwards we go back to further_operation()
        """
        _current_node = self.last_node
        pattern = random.choices(list(centr_patterns.keys()), [i[1][0] for i in list(centr_patterns.values())])[0]
        # Connect the last node to first of this pattern
        for _next_op_cat in centr_patterns[pattern][0]:
            _next_op_name, _ = self.select_unit_name(_next_op_cat)
            self.nodes.append(_next_op_name)
            self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
            connect_info = []  # Reset connect_info after first edge in this function
            # Reset the current node
            _current_node = _next_op_name
        
        """
        ----------
        Branches
        ----------
        """ 
        _branches = ['bout', 'tout']
        for b in _branches:
            self.last_node = _current_node
            # Next operation of branch
            connect_info = [b]
            # by definition we say that the top outlet is the filtrated one, bout directly to OutputProduct
            if b == 'bout':
                outlet_node = 'OutputProduct-%d' % self.operation_counter['OutputProduct']
                self.nodes.append(outlet_node)
                self.edges.append(((_current_node, outlet_node), {'in_connect': connect_info, 'out_connect': []}))
                self.operation_counter['OutputProduct'] += 1
            else:
                self.next_operation(connect_info)

    def purification(self, connect_info):
        """ 
        - The following lines randomly (with probabilities, see Patterns.py) picks a pattern containing an outlet stream
        - no operation afterwards; branch or last process stream reaches an end
        """
        _current_node = self.last_node
        pattern = random.choices(list(purification_patterns.keys()),
                                 [i[1][0] for i in list(purification_patterns.values())])[0]
        # Connect the last node to first of this pattern
        for _next_op_cat in purification_patterns[pattern][0]:
            _next_op_name, _ = self.select_unit_name(_next_op_cat)
            # before the last node and edge is created, we go to special operations
            if _next_op_cat == 'OutputProduct':
                break
            else:
                self.nodes.append(_next_op_name)
                self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
                connect_info = []  # Reset connect_info after first edge in this function
                # Reset the current node
                _current_node = _next_op_name
            
        """ Random special operations to increase variety """
        # Check for heat exchangers in nodes
        _hexs = []
        for i, n in enumerate(list(self.nodes)):
            if 'HeatExchanger' in n: 
                if not n == _current_node:
                    _hexs.append((i, n))
        if len(list(self.edges)) > 1 and len(_hexs) > 0:
            # TODO: Rec special op deactivated for now. Otherwise a mixer could be randomly inserted between ctrl and
            # valve.
            #special_op = random.choices(['Rec', 'HI', 'None'], [0.15, 0.05, 0.8])[0]
            special_op = random.choices(['HI', 'None'], [0.1, 0.9])[0]
        elif len(list(self.edges)) > 1:
            #special_op = random.choices(['Rec', 'None'], [0.15, 0.85])[0]
            special_op = random.choices(['None'], [1])[0]
        else:
            special_op = 'None'

        if special_op == 'Rec':
            """
            ----------
            Recycling:
            Insert a mixer somewhere and a splitter before the IO node
            ----------
            """ 
            # mixer
            _mixer_name, _ = self.select_unit_name('Mixing')

            # Select one random edge_old (except for the last edge) which needs to be replaced by 
            # two edges and new mixer node in between edge_old[0] and edge_old[1]
            _nr_edges = len(list(self.edges))
            _edge_pos = random.choices(range(0, _nr_edges-1))[0]
            _edge_old = self.edges[_edge_pos]
            _pre_node = _edge_old[0][0]  # e.g. heat exchanger
            _suc_node = _edge_old[0][1]  # reactor
            _presuc_info = _edge_old[1]['in_connect']
            _suc_info = _edge_old[1]['out_connect']

            _new_pos = self.nodes.index(_suc_node)
            self.nodes.insert(_new_pos, _mixer_name)

            # two new edges needed
            self.edges.append(((_pre_node, _mixer_name), {'in_connect': _presuc_info, 'out_connect': []}))
            self.edges.append(((_mixer_name, _suc_node), {'in_connect': [], 'out_connect': _suc_info}))
            del self.edges[_edge_pos]  # delete old edge
            
            # splitter
            _splitter_name, _ = self.select_unit_name('Splitting')
            self.nodes.append(_splitter_name) 
            self.edges.append(((_current_node, _splitter_name), {'in_connect': connect_info, 'out_connect': []})) # current to spltiter; here we need possible connection information
            connect_info = []  # Reset connect_info after first edge in this function
            self.edges.append(((_splitter_name, _mixer_name), {'in_connect': [], 'out_connect': []}))  # splitter to mixer
            self.nodes.append(_next_op_name) # the IO node
            self.edges.append(((_splitter_name, _next_op_name), {'in_connect': [], 'out_connect': []}))  # splitter to IO
            _current_node = _next_op_name  # Reset the current node

        """
        ----------
        Heat integration:
        According to the description in the SFILES Paper we create a second node hex-#/2 for the second stream that enters the Hex
        And adjust the node for the first stream: hex-#/1
        In rare cases we select a heat exchanger that is already used for heat integration. 
        ----------
        """ 
        if special_op == 'HI':

            _item = random.choices(_hexs)[0]
            _heat_ex_HI = _item[1]
            _nodepos = _item[0]

            # Heat integration adjustments
            if '/' in _heat_ex_HI: # already heat integration
                _hex_name_HI = _heat_ex_HI.split(sep='/')[0]
                _next_stream_HI_node = _hex_name_HI + '/%s' % (self.HI_hex_stream_counter[_hex_name_HI]+1)
                # node and edge for new stream
                self.nodes.append(_next_stream_HI_node)
                self.HI_hex_stream_counter[_hex_name_HI] += 1
                self.edges.append(((_current_node, _next_stream_HI_node),
                                   {'in_connect': connect_info, 'out_connect': []}))
            else:  # newly added heat integration
                # Adjust hex node name and the edges of original node
                # overwrite hex-# with hex-#/1
                _new_name = _heat_ex_HI + '/1'
                self.nodes[_nodepos] = _new_name
                # adjust edges
                self.adjust_HI_edges(_heat_ex_HI, _new_name, 'in')
                self.adjust_HI_edges(_heat_ex_HI, _new_name, 'out')
                # node and edge for second stream
                _next_stream_HI_node = _heat_ex_HI + '/2'
                self.nodes.append(_next_stream_HI_node)
                self.edges.append(((_current_node, _next_stream_HI_node),
                                   {'in_connect': connect_info, 'out_connect': []}))
                self.HI_hex_stream_counter[_heat_ex_HI] = 2  # 2 nodes
            
            # set current node to new hex node
            _current_node = _next_stream_HI_node
            connect_info = []
            # HI hex to IO
            self.nodes.append(_next_op_name) # the IO node
            self.edges.append(((_current_node, _next_op_name), {'in_connect': [], 'out_connect': []}))
            _current_node = _next_op_name
            

        elif special_op == 'None':
            self.nodes.append(_next_op_name)
            self.edges.append(((_current_node, _next_op_name), {'in_connect': connect_info, 'out_connect': []}))
            connect_info = []  # reset connect_info after first edge in this function
            # reset the current node
            _current_node = _next_op_name

    def flatten(self, k):
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
        for i in k:
            if isinstance(i, list):
                l_flat.extend(self.flatten(i))
            else:
                l_flat.append(i)
        return l_flat

    def find_edges(self, node, _type='incoming'):
        """ Function to find edges for node 

        Parameters
        ----------
        node (str): node name to search edges for
        type (str): \'incoming\' or \'outgoing\'
        
        Returns
        ----------
        _edges (list): list of edges including the node together with the position (in a tuple)

        """
        if _type == 'outgoing':
            _edges = [(i, item) for i, item in enumerate(self.edges) if item[0][0] == node]
        if _type == 'incoming':
            _edges = [(i, item) for i, item in enumerate(self.edges) if item[0][1] == node]
        return _edges

    def select_unit_name(self, main_category):
        """ 
        Selects specific unit operation (e.g. hex_cool) for a main_category (e.g. Heat_exchanger).
        Assigns a numbered name and changes attribute self.operation_counter.

        Parameters
        ----------
        main_category (str): Main category name according to file unit_operations.py
        
        Returns
        ----------
        _unit_name (str): Numbered name for specific unit operation

        """
        _category = random.choices(unit_ops_probabilities[main_category][0],
                                   unit_ops_probabilities[main_category][1])[0]
        _unit_name = _category + '-' + str(self.operation_counter[_category])
        self.operation_counter[_category] += 1

        return _unit_name, _category
    
    def adjust_HI_edges(self, old_node_name, new_node_name, in_out):
        """ Function to adjust edges according to new hex name (heat integration) 

        Parameters
        ----------
        old_node_name (str): node name to search edges for
        new_node_name (str): node name that is used when overwriting the edges
        in_out (str): 'in' or 'out' edges
        
        Returns
        ----------
        None

        """
        if in_out == 'in':
            _incoming = self.find_edges(old_node_name, _type='incoming')[0]  # only one edge possible
            _edge_pos = _incoming[0]
            _connection_info = _incoming[1][1]  # dict with connection information
            _in_node = _incoming[1][0][0]
            _out_node = _incoming[1][0][1]  # should equal the old_node_name
            assert(_out_node == old_node_name)
            # Overwrite old edge with new edge with new hex name
            self.edges[_edge_pos] = ((_in_node, new_node_name), _connection_info)
        elif in_out == 'out':
            _outgoing = self.find_edges(old_node_name, _type='outgoing')[0]  # only one edge possible
            _edge_pos = _outgoing[0]
            _connection_info = _outgoing[1][1]  # dict with connection information
            _in_node = _outgoing[1][0][0]  # should equal the old_node_name
            _out_node = _outgoing[1][0][1] 
            assert(_in_node == old_node_name)
            self.edges[_edge_pos] = ((new_node_name, _out_node), _connection_info)

    def mixing_ctrl_pattern(self, node1, node2, mixing):
        # TODO: It has to be checked if raw material stream includes already FC through other unitop.
        #  Material stream cannot be controlled by two or more FC!
        mixing_pattern = random.choices(['Pattern_1', 'Pattern_2'], [0.7, 0.3])[0]

        if mixing_pattern == 'Pattern_1':
            ctrl_1 = 'Control' + '-' + str(self.operation_counter['Control']) + '/FC'
            self.operation_counter['Control'] += 1
            ctrl_2 = 'Control' + '-' + str(self.operation_counter['Control']) + '/FC'
            self.operation_counter['Control'] += 1
            valve_1 = 'Valve' + '-' + str(self.operation_counter['Valve'])
            self.operation_counter['Valve'] += 1
            valve_2 = 'Valve' + '-' + str(self.operation_counter['Valve'])
            self.operation_counter['Valve'] += 1

            self.nodes.extend([ctrl_1, ctrl_2, valve_1, valve_2])
            self.edges.extend([((node1, ctrl_1), {'in_connect': [], 'out_connect': []}),
                               ((ctrl_1, valve_1), {'in_connect': ['next_unitop'], 'out_connect': []}),
                               ((valve_1, mixing), {'in_connect': [], 'out_connect': []}),
                               ((node2, ctrl_2), {'in_connect': [], 'out_connect': []}),
                               ((ctrl_2, valve_2), {'in_connect': ['next_unitop'], 'out_connect': []}),
                               ((valve_2, mixing), {'in_connect': [], 'out_connect': []})])

        elif mixing_pattern == 'Pattern_2':
            ctrl_1 = 'Control' + '-' + str(self.operation_counter['Control']) + '/FT'
            self.operation_counter['Control'] += 1
            ctrl_2 = 'Control' + '-' + str(self.operation_counter['Control']) + '/FFC'
            self.operation_counter['Control'] += 1
            valve_1 = 'Valve' + '-' + str(self.operation_counter['Valve'])
            self.operation_counter['Valve'] += 1

            self.nodes.extend([ctrl_1, ctrl_2, valve_1])
            self.edges.extend([((node1, ctrl_1), {'in_connect': [], 'out_connect': []}),
                               ((ctrl_1, mixing), {'in_connect': [], 'out_connect': []}),
                               ((node2, ctrl_2), {'in_connect': [], 'out_connect': []}),
                               ((ctrl_2, valve_1), {'in_connect': ['next_unitop'], 'out_connect': []}),
                               ((valve_1, mixing), {'in_connect': [], 'out_connect': []}),
                               ((ctrl_1, ctrl_2), {'in_connect': ['not_next_unitop'], 'out_connect': []})])

    def temperature_ctrl_pattern(self, node):

        temperature_ctrl_pattern = random.choices(['Pattern_1', 'Pattern_2'], [0.2, 0.8])[0]

        if temperature_ctrl_pattern == 'Pattern_1':
            ctrl = 'Control' + '-' + str(self.operation_counter['Control']) + '/TC'
            self.operation_counter['Control'] += 1
            heatexchanger = 'HeatExchanger' + '-' + str(self.operation_counter['HeatExchanger'])
            self.operation_counter['HeatExchanger'] += 1
            self.nodes.extend([heatexchanger, ctrl])
            self.edges.extend([((node, heatexchanger), {'in_connect': [], 'out_connect': []}),
                               ((ctrl, heatexchanger), {'in_connect': ['not_next_unitop'], 'out_connect': []}),
                               ((heatexchanger, ctrl), {'in_connect': [], 'out_connect': []})])
            return ctrl
        elif temperature_ctrl_pattern == 'Pattern_2':
            ctrl = 'Control' + '-' + str(self.operation_counter['Control']) + '/TC'
            self.operation_counter['Control'] += 1
            valve = 'Valve' + '-' + str(self.operation_counter['Valve'])
            self.operation_counter['Valve'] += 1
            heatexchanger = 'HeatExchanger' + '-' + str(self.operation_counter['HeatExchanger'])
            self.operation_counter['HeatExchanger'] += 1
            utility_in = 'RawMaterial-%d' % self.operation_counter['RawMaterial']
            self.operation_counter['RawMaterial'] += 1
            utility_out = 'OutputProduct-%d' % self.operation_counter['OutputProduct']
            self.operation_counter['OutputProduct'] += 1
            self.nodes.extend([ctrl, heatexchanger, utility_in, utility_out])
            self.edges.extend([((node, heatexchanger), {'in_connect': ['1_in'], 'out_connect': []}),
                               ((heatexchanger, ctrl), {'in_connect': [], 'out_connect': ['1_out']}),
                               ((utility_in, heatexchanger), {'in_connect': ['2_in'], 'out_connect': []}),
                               ((heatexchanger, valve), {'in_connect': [], 'out_connect': ['2_out']}),
                               ((valve, utility_out), {'in_connect': [], 'out_connect': []}),
                               ((ctrl, valve), {'in_connect': ['not_next_unitop'], 'out_connect': []})])
            return ctrl

    def pressure_ctrl_pattern(self, node, _next_op):

        if _next_op == 'Pump':
            pressure_ctrl_patter = random.choices(['Pattern_1', 'Pattern_2', 'Pattern_3'], [0.2, 0.5, 0.3])[0]

            if pressure_ctrl_patter == 'Pattern_1':
                mixing = 'MixingUnit' + '-' + str(self.operation_counter['MixingUnit'])
                self.operation_counter['MixingUnit'] += 1
                pump = 'Pump' + '-' + str(self.operation_counter['Pump'])
                self.operation_counter['Pump'] += 1
                splt = 'SplittingUnit' + '-' + str(self.operation_counter['SplittingUnit'])
                self.operation_counter['SplittingUnit'] += 1
                ctrl_1 = 'Control' + '-' + str(self.operation_counter['Control']) + '/PI'
                self.operation_counter['Control'] += 1
                ctrl_2 = 'Control' + '-' + str(self.operation_counter['Control']) + '/FC'
                self.operation_counter['Control'] += 1
                ctrl_3 = 'Control' + '-' + str(self.operation_counter['Control']) + '/M'
                self.operation_counter['Control'] += 1
                valve = 'Valve' + '-' + str(self.operation_counter['Valve'])
                self.operation_counter['Valve'] += 1

                self.nodes.extend([mixing, pump, splt, ctrl_1, ctrl_2, ctrl_3, valve])
                self.edges.extend([((node, mixing), {'in_connect': [], 'out_connect': []}),
                                   ((mixing, pump), {'in_connect': [], 'out_connect': []}),
                                   ((pump, splt), {'in_connect': [], 'out_connect': []}),
                                   ((splt, ctrl_1), {'in_connect': [], 'out_connect': []}),
                                   ((ctrl_1, ctrl_2), {'in_connect': [], 'out_connect': []}),
                                   ((ctrl_2, valve), {'in_connect': ['not_next_unitop'], 'out_connect': []}),
                                   ((splt, valve), {'in_connect': [], 'out_connect': []}),
                                   ((valve, mixing), {'in_connect': [], 'out_connect': []}),
                                   ((pump, ctrl_3), {'in_connect': [], 'out_connect': []})])
                return ctrl_2

            elif pressure_ctrl_patter == 'Pattern_2':
                pump = 'Pump' + '-' + str(self.operation_counter['Pump'])
                self.operation_counter['Pump'] += 1
                ctrl_1 = 'Control' + '-' + str(self.operation_counter['Control']) + '/PI'
                self.operation_counter['Control'] += 1
                ctrl_2 = 'Control' + '-' + str(self.operation_counter['Control']) + '/FC'
                self.operation_counter['Control'] += 1
                ctrl_3 = 'Control' + '-' + str(self.operation_counter['Control']) + '/M'
                self.operation_counter['Control'] += 1
                valve = 'Valve' + '-' + str(self.operation_counter['Valve'])
                self.operation_counter['Valve'] += 1

                self.nodes.extend([pump, ctrl_1, ctrl_2, ctrl_3, valve])
                self.edges.extend([((node, pump), {'in_connect': [], 'out_connect': []}),
                                   ((pump, ctrl_1), {'in_connect': [], 'out_connect': []}),
                                   ((ctrl_1, ctrl_2), {'in_connect': [], 'out_connect': []}),
                                   ((ctrl_2, valve), {'in_connect': ['next_unitop'], 'out_connect': []}),
                                   ((pump, ctrl_3), {'in_connect': [], 'out_connect': []})])
                return ctrl_2

            elif pressure_ctrl_patter == 'Pattern_3':
                pump = 'Pump' + '-' + str(self.operation_counter['Pump'])
                self.operation_counter['Pump'] += 1
                ctrl_1 = 'Control' + '-' + str(self.operation_counter['Control']) + '/PI'
                self.operation_counter['Control'] += 1
                ctrl_2 = 'Control' + '-' + str(self.operation_counter['Control']) + '/FC'
                self.operation_counter['Control'] += 1
                ctrl_3 = 'Control' + '-' + str(self.operation_counter['Control']) + '/M'
                self.operation_counter['Control'] += 1

                self.nodes.extend([pump, ctrl_1, ctrl_2, ctrl_3])
                self.edges.extend([((node, pump), {'in_connect': [], 'out_connect': []}),
                                   ((pump, ctrl_1), {'in_connect': [], 'out_connect': []}),
                                   ((ctrl_1, ctrl_2), {'in_connect': [], 'out_connect': []}),
                                   ((pump, ctrl_3), {'in_connect': [], 'out_connect': []}),
                                   ((ctrl_2, ctrl_3), {'in_connect': ['not_next_unitop'], 'out_connect': []})])
                return ctrl_2

        else:
            pressure_ctrl_patter = random.choices(['Pattern_1', 'Pattern_2', 'Pattern_3'], [1, 0, 0])[0]

            if pressure_ctrl_patter == 'Pattern_1':
                compressor = _next_op + '-' + str(self.operation_counter[_next_op])
                self.operation_counter[_next_op] += 1
                self.nodes.extend([compressor])
                self.edges.extend([((node, compressor), {'in_connect': [], 'out_connect': []})])
                return compressor


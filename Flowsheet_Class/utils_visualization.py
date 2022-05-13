from tabulate import tabulate
import networkx as nx
import matplotlib.pyplot as plt
from pyflowsheet import Flowsheet, BlackBox, StreamFlag, SvgContext, VerticalLabelAlignment, \
        HorizontalLabelAlignment, HeatExchanger, Vessel, Distillation
from IPython.core.display import SVG


def create_stream_table(graph, chemicalspecies, decimals):
    """Function to return a table with all information about the streams in the flowsheet.

    Args:
        graph: nx-Graph representation of the flowsheet
        chemicalspecies: List with string names of chemical species considered in the process
        decimals: number of decimals showed int the table

    Returns:
        table_streams: table with all streams
    """
    if chemicalspecies is None:
        chemicalspecies = ['x_A', 'x_B', 'x_C']

    header = ['Stream name', 'Edge', 'Moles(mol/s)', 'Temperature(Kelvin)', 'Pressure(Pa)']
    header.extend(chemicalspecies)

    table_data = [header]
    for edge in graph.edges:
        stream_list = []
        stream_list.append(graph.get_edge_data(*edge)['processstream_name'])
        stream_data = graph.get_edge_data(*edge)['processstream_data']
        stream_list.append(edge)
        for i in range(len(stream_data[0:3])):
            stream_list.append(round(stream_data[i], decimals))
        for i in range(len(stream_data[-1])):
            stream_list.append(round(stream_data[-1][i], decimals))
        table_data.append(stream_list)
    table_streams = tabulate(table_data, headers='firstrow', tablefmt='grid')
    print(table_streams)
    return table_streams


def create_unit_table(graph, decimals):
    """Function to return a table with all information about the units in the flowsheet.

    Args:
        graph: nx-Graph representation of the flowsheet
        decimals: number of decimals showed int the table

    Returns:
        table_units: table with all units
    """
    unit_table_data = [
        ['Unit name', 'Unit type', 'Condition description', 'Condition']]
    for node in graph.nodes:
        node_list = []
        node_list.append(node)
        node_list.append(graph.nodes(data=True)[node]['unit_type_specific'])
        unit = graph.nodes(data=True)[node]['unit']
        if graph.nodes(data=True)[node]['unit_type'] == 'hex':
            node_list.append('water inlet temperature')
            node_list.append(round(unit.water_temp_in, decimals))
        elif graph.nodes(data=True)[node]['unit_type'] == 'r':
            node_list.append('length')
            node_list.append(round(unit.length, decimals))
        elif graph.nodes(data=True)[node]['unit_type'] == 'col':
            node_list.append('distillation to feed ratio')
            node_list.append(round(unit.has_distillation_to_feed_ratio, decimals))
        elif graph.nodes(data=True)[node]['unit_type'] == 'splt':
            node_list.append('split ratio')
            node_list.append(round(unit.split_ratio, decimals))
        else:
            node_list.append('N/A')
            node_list.append(0)
        unit_table_data.append(node_list)
    table_units = tabulate(unit_table_data, headers='firstrow', tablefmt='grid')
    print(table_units)
    return table_units


def _add_positions(graph, flowsheet_size):
    """Function to assign positions to each node of a flowsheet graph.

    Args:
        graph: nx-graph representation of the flowsheet
        flowsheet_size: number of nodes in the flowsheet

    Returns:
        graph with updated node attributes
    """
    # Fist set position of feed(s)

    # Save all feed nodes in a list (reason: the following algorithm always checks for all outgoing edges
    # and their successor nodes, starting with the first feeds. To come back to those later, they and their
    # position are saved in lists
    save_nodes = [feed for feed in graph.nodes if graph.in_degree(feed) == 0]
    save_pos = []
    y_coordinates = []  # List to save all y coordinates --> no nodes above each other
    # Initialize a list for saving all nodes that have been updated
    updated_nodes = []
    i=0
    for _, feed in enumerate(save_nodes):
        # Update positions of all feeds
        nx.set_node_attributes(graph, {feed: {'pos': [0, i]}})
        y_coordinates.append(i)
        # Save position of all feeds
        save_pos.append([0, i])
        # Write feeds in updated_nodes list to check later, if they already have a position attribute
        # (necessary when dealing with recycles!)
        updated_nodes.append(feed)
        i += 150

    # For the following loop, start from the first feed
    node = save_nodes[0]
    pos = save_pos[0]
    # Initialize a counter (set to one because the first feed is already in use)
    counter = 1

    while len(updated_nodes) < flowsheet_size:
        # While loop for as long as not all units have been updated with a position
        # Find all edges that leave the previously set node
        original_edges = list(graph.out_edges(node))
        # FOR RECYCLES: only considere edges that lead to nodes that don't have a position yet!
        # Copy all relevant edges to the list edges
        edges = []
        for k in range(len(original_edges)):
            if original_edges[k][1] not in updated_nodes:
                edges.append(original_edges[k])

        # Set position of the following node(s) depending on their number
        if len(edges) == 1:
            # Only one next node
            next_node = edges[0][1]
            # Set position to the right
            pos = pos[:]
            pos[0] += 150
            nx.set_node_attributes(graph, {next_node: {'pos': pos}})
            # Write updated node into list to check later, if this node has already been updated
            updated_nodes.append(next_node)
            # Use the new node as the source-node for the next iteration
            node = next_node

        elif len(edges) == 2:
            # Two successor nodes: Positions are set to the right and up / down
            next_node = edges[0][1]
            pos = pos[:]
            pos_x = pos[0]
            pos_y = pos[1]
            pos[0] = pos_x + 200
            pos[1] = pos_y + 100
            multiplier = 0.5

            while pos[1] in y_coordinates:
                # Quick fix to prevent multiple nodes directly above each other --> for side-streams a new y-coordinate
                # is chosen that has not been used before
                pos[1] = pos_y + 100 * multiplier
                multiplier = multiplier * 0.5

            y_coordinates.append(pos[1])
            nx.set_node_attributes(graph, {next_node: {'pos': pos}})
            updated_nodes.append(next_node)
            # Save the first of the two nodes and its position in the save lists in order to come back to
            # them later
            save_nodes.append(next_node)
            save_pos.append(pos)

            # Update the second node just like in the case with only one successor node
            next_node = edges[1][1]
            pos = pos[:]
            pos[1] -= 200
            multiplier = 0.5

            while pos[1] in y_coordinates:
                pos[1] = pos_y - 150 * multiplier
                multiplier = multiplier * 0.5

            y_coordinates.append(pos[1])
            nx.set_node_attributes(graph, {next_node: {'pos': pos}})
            updated_nodes.append(next_node)
            node = next_node

        elif len(edges) == 0:
            # If no edge is coming out of the node --> go on with the nodes that have been saved in the
            # save list and use them for the next iteration.
            node = save_nodes[counter]
            pos = save_pos[counter]
            counter += 1

        else:
            raise Exception('There are no units with more than two outlets so far')

    return graph


def plot_flowsheet_nx(graph, plot_with_stream_labels, add_positions=True):
    """Function to return a plot of a flowsheet represented as nx-graph. The visualization of the nodes is oriented on
    real flowsheets (start at the left side with the feed and move towards the products on the right).

    Args:
        graph: nx-Graph representation of the flowsheet
        plot_with_stream_labels: boolean telling whether stream data should be plotted or not
        add_positions: boolean telling whether a position attribute already exists

    Returns:
        table_streams: table with all streams
    """
    # Plots the flowsheet using matplotlib and shows the moles, temperature and pressure for each stream.
    # Update position attribute of nodes
    flowsheet_size = graph.number_of_nodes()

    if add_positions:
        graph = _add_positions(graph, flowsheet_size)

    # Plot
    fig = plt.figure(figsize=(flowsheet_size * 10. / 6., flowsheet_size * 5. / 6.))
    pos = nx.get_node_attributes(graph, 'pos')
    if plot_with_stream_labels:
        nx.draw(graph, pos, with_labels=True, node_size=1600, font_size=13, node_color='#00b4d9')
        try:
            labels = dict([((n1, n2),
                            ''.join([d['processstream_name'], '\n N=', str(round(d['processstream_data'][0])),
                                     ' mol/s\nT=', str(round(d['processstream_data'][1])), ' K\nP=',
                                     str(round(d['processstream_data'][2])), ' Pa']))
                           for n1, n2, d in graph.edges(data=True)])
            nx.draw_networkx_edge_labels(graph, pos, edge_labels=labels, rotate=False, font_size=10)

        except KeyError:
            print("Key error! stream does not have all attributes")
        except IndexError:
            print("Index error! stream does not have all attributes")

    else:
        nx.draw(graph, pos, with_labels=True, node_size=1600, font_size=13, node_color='#00b4d9')
    plt.show()
    return fig


def plot_flowsheet_pyflowsheet(graph, block=False, imagepath='flowsheet',  pfd_id='PFD',
                               pfd_name='process flow diagram', pfd_description='created with pyflowsheet',
                               add_positions=True):
    """Function to plot a flowsheet-graph using the package pyflowsheet.

    Args:
        graph: nx-graph representation of the flowsheet
        block (boolean): True: plot a block flowsheet, False: plot a "normal" flowsheet with images as units
        imagepath (string): path where the svg is saved, e.g. plots/blockflowprocess
        pfd_id (string): ID of the flowsheet
        pfd_name (string): Name of the flowsheet
        pfd_description (string): Description of the flowsheet
        add_positions: boolean telling whether a position attribute already exists
    """
    # First assign a position to every node
    flowsheet_size = graph.number_of_nodes()

    if add_positions:
        graph = _add_positions(graph, flowsheet_size)

    # create a flowsheet
    pfd = Flowsheet(pfd_id, pfd_name, pfd_description)  # id, name, description

    # Intialize a dict to store all unit operations using the node-ids as keys
    unit_dict = dict.fromkeys(list(graph.nodes))

    # Loop over all nodes in the graph to create UnitOperation objects with the pyflowsheet package
    feed_count = 1
    product_count = 1
    for node_id, node in graph.nodes(data=True):
        # Find all feeds and assign them to a StreamFlag unit
        if graph.in_degree(node_id) == 0:
            feed_name = 'Feed ' + str(feed_count)
            feed = StreamFlag(node_id, name=feed_name, position=node['pos'])
            feed.setTextAnchor(HorizontalLabelAlignment.Center, VerticalLabelAlignment.Center, (0, 5))  # Text in image
            feed_count += 1
            unit_dict[node_id] = feed

        # Find all products and assign them to a StreamFlag unit
        elif graph.out_degree(node_id) == 0 and node_id[0] == 'I':
            # Second condition in case a flowsheet does not end with IO unit but e.g. with 'X' (qick fix, there must be
            # a better way)
            product_name = 'Product ' + str(product_count)
            product = StreamFlag(node_id, name=product_name, position=node['pos'])
            product.setTextAnchor(HorizontalLabelAlignment.Center, VerticalLabelAlignment.Center, (0, 5))
            product_count += 1
            unit_dict[node_id] = product

        else:  # Unit operations
            if block:  # In a block-flowsheet all units are represented by a box
                unit = BlackBox(node_id, name=node_id, size=(80, 60), position=node['pos'])
                unit.setTextAnchor(HorizontalLabelAlignment.Center, VerticalLabelAlignment.Center, (0, 5))
            else:  # Use images for units
                # Todo: is there a way to work around the if-else statement?
                if node['unit_type'] == 'hex':
                    unit = HeatExchanger(node_id, name=node_id, position=node['pos'])
                elif node['unit_type'] == 'r':
                    unit = Vessel(node_id, name=node_id, position=node['pos'], angle=90)
                    unit.setTextAnchor(HorizontalLabelAlignment.Center, VerticalLabelAlignment.Center, (0, 5))
                elif node['unit_type'] == 'col':
                    unit = Distillation(node_id, name=node_id, position=node['pos'], hasReboiler=False,
                                        hasCondenser=False)
                    unit.setTextAnchor(HorizontalLabelAlignment.Center, VerticalLabelAlignment.Center, (0, 5))
                else:
                    unit = BlackBox(node_id, name=node_id, position=node['pos'], size=(80, 60))
                    unit.setTextAnchor(HorizontalLabelAlignment.Center, VerticalLabelAlignment.Center, (0, 5))
            unit_dict[node_id] = unit

    # Connect all units
    if block:  # All ports are called 'In' or 'Out' --> makes it easier
        count = 1  # Count all streams for identifier
        for edge in graph.out_edges(data=True):
            unit_1 = unit_dict[edge[0]]
            unit_2 = unit_dict[edge[1]]
            stream_id = 'stream-'+str(count)
            pfd.connect(stream_id, unit_1['Out'], unit_2['In'])

            # Set stream name position
            pos0 = graph.nodes(data=True)[edge[0]]['pos']
            pos1 = graph.nodes(data=True)[edge[1]]['pos']
            if pos0[1] > pos1[1]:
                pfd.streams[stream_id].labelOffset = (15, 10)
            else:
                pfd.streams[stream_id].labelOffset = (15, -10)
            count += 1

    else:  # If other UnitOperation objects than "BlackBox" are used, all ports have different names
        count = 1
        for edge in graph.out_edges(data=True):
            unit_1 = unit_dict[edge[0]]
            unit_2 = unit_dict[edge[1]]
            stream_id = 'stream-' + str(count)
            pos0 = graph.nodes(data=True)[edge[0]]['pos']
            pos1 = graph.nodes(data=True)[edge[1]]['pos']

            # Save names of ports of each specific unit
            # Todo: is there a way to work around the if-else statement?
            if graph.nodes(data=True)[edge[0]]['unit_type'] == 'hex':
                port1 = 'TOut'
            elif graph.nodes(data=True)[edge[0]]['unit_type'] == 'col':
                if pos0[1] > pos1[1]:
                    port1 = 'LOut'
                else:
                    port1 = 'VOut'
            else:
                port1 = 'Out'
            if graph.nodes(data=True)[edge[1]]['unit_type'] == 'hex':
                port2 = 'TIn'
            elif graph.nodes(data=True)[edge[1]]['unit_type'] == 'col':
                port2 = 'Feed'
            else:
                port2 = 'In'

            pfd.connect(stream_id, unit_1[port1], unit_2[port2])

            # Set stream name position
            if pos0[1] > pos1[1]:
                pfd.streams[stream_id].labelOffset = (25, 20)
            else:
                pfd.streams[stream_id].labelOffset = (25, -20)
            count += 1

    # Add units to pfd
    pfd.addUnits(unit_dict.values())

    # store the flowsheet as svg
    filename = imagepath + ".svg"
    ctx = SvgContext(filename)
    img = pfd.draw(ctx)
    SVG(img.render(scale=1))

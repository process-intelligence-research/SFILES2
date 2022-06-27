import json
import os


def json_extract(obj, key):
    """Recursively fetch values from nested JSON.
    https://hackersandslackers.com/extract-data-from-complex-json-python/"""

    arr = []

    def extract(obj, arr, key):
        """Recursively search for values of key in JSON tree."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    extract(v, arr, key)
                elif k == key:
                    arr.append(v)
        elif isinstance(obj, list):
            for item in obj:
                extract(item, arr, key)
        return arr

    values = extract(obj, arr, key)
    return values


def read_ctrl_pattern(self, pattern, last_node):
    # Load patterns from file.
    current_path = os.path.dirname(__file__)
    rel_path = ''.join(['ControlPatterns\\', pattern, '.json'])
    path = os.path.join(current_path, rel_path)
    with open(path) as f:
        data = json.load(f)

    #print(json.dumps(data, indent=4))
    nodes = json_extract(data, 'caption')
    for k, v in enumerate(nodes):
        unit_name = v.split(sep='-')[0]
        ctrl = None
        if '/' in v:
            ctrl = v.split(sep='/')[1]
            ctrl = '/' + ctrl
        nodes[k] = ''.join(filter(None, [unit_name, '-', str(self.operation_counter[unit_name]), ctrl]))
        self.operation_counter[unit_name] += 1

    nodes_id = json_extract(data['nodes'], 'id')
    from_id = json_extract(data, 'fromId')
    to_id = json_extract(data, 'toId')

    # special edges
    # TODO: Revise filter lists also for 3_in, 3_out etc.
    special_edges = json_extract(data, 'type')
    lst = ['next_unitop', 'not_next_unitop', 'tin', 'bin', '1_in', '2_in']
    lst2 = ['tout', 'bout', '1_out', '2_out']
    special_edges = [{'in_connect': [k], 'out_connect': []} if k in lst
                     else {'in_connect': [], 'out_connect': [k]} if k in lst2
                     else {'in_connect': [], 'out_connect': []} for k in special_edges]

    # Mapping
    mapping = dict(zip(nodes_id, nodes))
    from_id = [mapping[k] for k in from_id]
    to_id = [mapping[k] for k in to_id]
    edges = list(zip(from_id, to_id))
    edges = list(zip(edges, special_edges))

    # TODO: Include automatic recognition of start and end nodes
    nodetype = {}
    for k in range(len(data['nodes'])):
        if data['nodes'][k]['labels']:
            nodetype.update({data['nodes'][k]['id']: data['nodes'][k]['labels']})
    nodetype = {mapping[k]: v for k, v in nodetype.items()}

    end_nodes = []
    start_node = []
    for k, v in nodetype.items():
        for m in v:
            if m == 'start_node':
                start_node.append(k)
            elif m == 'end_node':
                end_nodes.append(k)

    if isinstance(last_node, str):
        last_node = [last_node]

    if len(start_node) != len(last_node) and not 'mixing' in pattern:
        print('Error. Too many start nodes!')

    for k in range(len(start_node)):
        if 'heatexchanger' in pattern:
            self.edges.extend([((last_node[k], start_node[k]), {'in_connect': ['1_in'], 'out_connect': []})])
        elif 'mixing' in pattern:
            self.edges.extend([((last_node[-k], start_node[k]), {'in_connect': ['1_in'], 'out_connect': []})])
        #elif 'add_reactor_feed' in pattern:
        #    self.edges.extend([((end_nodes[k], last_node[0]), {'in_connect': ['1_in'], 'out_connect': []})])
        #    end_nodes = last_node
        else:
            self.edges.extend([((last_node[k], start_node[k]), {'in_connect': [], 'out_connect': []})])

    self.nodes.extend(nodes)
    self.edges.extend(edges)

    return end_nodes

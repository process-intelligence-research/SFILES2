import json
from Flowsheet_Class.RandomFlowsheetGen_OC.unit_operations import unit_ops, unit_ops_probabilities

"""Extract nested values from a JSON tree."""
# https://hackersandslackers.com/extract-data-from-complex-json-python/
def json_extract(obj, key):
    """Recursively fetch values from nested JSON."""
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


def read_ctrl_pattern(operation_counter):
    # TODO: Replace static link with relative path to pattern.
    f = open(r'C:\Users\hirtr\OneDrive - TUM\Dokumente\PI Research\SFILES2_0\ControlPatterns\column_pattern_1.json')
    data = json.load(f)

    # unitop counter
    #flat_list = [x for xs in list(unit_ops.values()) for x in xs]
    #operation_counter = {s: 1 for s in flat_list}

    #print(json.dumps(data, indent=4))
    nodes = json_extract(data, 'caption')
    for k, v in enumerate(nodes):
        unit_name = v.split(sep='-')[0]
        ctrl = None
        if '/' in v:
            ctrl = v.split(sep='/')[1]
            ctrl = '/' + ctrl
        nodes[k] = ''.join(filter(None, [unit_name, '-', str(operation_counter[unit_name]), ctrl]))
        operation_counter[unit_name] += 1

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
    start_node = nodes[0]
    end_nodes = [nodes[19], nodes[20]]
    f.close()
    return nodes, edges, start_node, end_nodes

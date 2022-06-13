from Flowsheet_Class.flowsheet import Flowsheet
import networkx as nx


def testSFILESctrl(test_case, edges):
    graph_one = nx.DiGraph()
    graph_one.add_edges_from(edges)

    flowsheet = Flowsheet()
    flowsheet.state = graph_one
    flowsheet.convert_to_sfiles()
    sfilesctrl1 = flowsheet.sfiles
    flowsheet.create_from_sfiles(sfilesctrl1, override_nx=True)
    flowsheet.convert_to_sfiles()
    sfilesctrl2 = flowsheet.sfiles

    sfiles = flowsheet.convert_sfilesctrl_to_sfiles()
    flowsheet.sfiles = sfiles
    flowsheet.create_from_sfiles(sfiles, override_nx=True)
    flowsheet.convert_to_sfiles()
    sfiles2 = flowsheet.sfiles

    if sfilesctrl1 == sfilesctrl2 and sfiles == sfiles2:
        print('-------------------------------------------------------------------------------------------------------')
        print('Test case ', test_case)
        print('Conversion back successful')
        print('SFILESctrl: ', sfilesctrl1)
        print('SFILES: ', sfiles)
    else:
        print('-------------------------------------------------------------------------------------------------------')
        print('Test case ', test_case)
        print('Conversion back produced a different SFILES string. Input:', sfilesctrl1, 'Output:', sfilesctrl2)
        print('Conversion back produced a different SFILES string. Input:', sfiles, 'Output:', sfiles2)

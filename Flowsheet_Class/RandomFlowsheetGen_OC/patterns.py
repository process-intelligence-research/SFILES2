"""
---------
Dicts with different process flowsheet patterns and their probabilities
Some of the patterns can be found in the pattern recognition paper: 
Zhang, T., Sahinidis, N. V., & Siirola, J. J. (2019). Pattern recognition in chemical process flowsheets. AIChE Journal, 65(2), 592-603.
---------
"""
reactor_patterns={
    'p1': [['TemperatureChange', 'Reaction'], [0.2]],
    'p2': [['TemperatureChange', 'TemperatureChange','Reaction'], [0.2]],
    'p3': [['TemperatureChange', 'PressureChange', 'Reaction'], [0.2]],
    'p4': [['PressureChange', 'Reaction'], [0.2]],
    'p5': [['Reaction'], [0.2]]
}
""" For thermal separation the feed preparation mostly are operations to produce a two phase mixture -> separation """
thermal_sep_patterns={
    'p1': [['TemperatureChange', 'ThermalSeparation'], [0.2]],
    'p2': [['ThermalSeparation'], [0.4]],
    'p3': [['Valve', 'ThermalSeparation'], [0.2]],
    'p4': [['PressureChange', 'ThermalSeparation'], [0.2]]
}
purification_patterns={
    'p1': [['TemperatureChange', 'OutputProduct'], [0.25]],
    'p2': [['OutputProduct'], [0.5]],
    'p3': [['PressureChange', 'OutputProduct'], [0.25]],
}
CC_sep_patterns={
    'p1': [['TemperatureChange', 'CountercurrentSeparation'],[0.2]],
    'p2': [['CountercurrentSeparation'], [0.4]],
    'p3': [['PressureChange', 'CountercurrentSeparation'], [0.2]],#liquid
    'p4': [['Valve', 'CountercurrentSeparation'], [0.2]]
}
filtration_patterns={
    'p1': [['TemperatureChange', 'Filtration'],[0.2]],
    'p2': [['Filtration'], [0.6]],
    'p3': [['PressureChange', 'Filtration'], [0.2]],#liquid
}
centr_patterns={
    'p1': [['TemperatureChange', 'CentrifugalSeparation'],[0.2]],
    'p2': [['CentrifugalSeparation'], [0.6]],
    'p3': [['PressureChange', 'CentrifugalSeparation'], [0.2]],#liquid
}
detergent_patterns={
    'p1': [['RawMaterial', 'Storage', 'PressureChange', 'CountercurrentSeparation'], [0.4]],
    'p2': [['RawMaterial', 'CountercurrentSeparation'], [0.2]],
    'p3': [['RawMaterial', 'PressureChange', 'CountercurrentSeparation'], [0.2]],
    'p4': [['RawMaterial', 'Storage', 'TemperatureChange', 'CountercurrentSeparation'], [0.2]]
}
addR_patterns={
    'p1': [['RawMaterial', 'Storage', 'PressureChange', 'Reaction'], [0.4]],
    'p2': [['RawMaterial', 'Reaction'], [0.2]],
    'p3': [['RawMaterial', 'PressureChange', 'Reaction'], [0.2]],
    'p4': [['RawMaterial', 'Storage', 'TemperatureChange', 'Reaction'], [0.2]]
}
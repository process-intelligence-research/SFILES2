unit_ops = {
    'RawMaterial': ['RawMaterial'],
    'OutputProduct': ['OutputProduct'],
    'TemperatureChange': ['HeatExchanger'],
    'PhaseChange': ['Reboiler', 'Condenser'],
    'PressureChange': ['Pump', 'Blower', 'Compressor', 'Expander', 'OrificePlate'],
    'Reaction': ['ChemicalReactor'],
    'Splitting': ['SplittingUnit'],
    'Mixing': ['MixingUnit'],
    'Storage': ['StorageUnit'],
    'Separation': ['SeparationUnit'],  # general separation without further specification
    'ThermalSeparation': ['DistillationSystem', 'FlashUnit', 'RectificationSystem'],
    'CountercurrentSeparation': ['ExtractionUnit', 'StrippingSystem', 'AbsorptionColumn', 'Scrubber'],
    'Filtration': ['LiquidFilter', 'GasFilter'],
    'CentrifugalSeparation': ['CentrifugationUnit', 'Cyclone', 'Hydrocyclone'],
    'ElectricalGasCleaning': ['ElectricalGasCleaningUnit'],
    'Valve': ['Valve'],
    'UnitOperation': ['ProcessUnit'],
    'Control': ['Control']
}
unit_ops_probabilities = {
    'RawMaterial': [['RawMaterial'], [1]],
    'OutputProduct': [['OutputProduct'], [1]],
    'TemperatureChange': [['HeatExchanger'], [1]],
    'PhaseChange': [['Reboiler', 'Condenser'], [0.5, 0.5]],
    'PressureChange': [['Pump', 'Blower', 'Compressor', 'Expander', 'OrificePlate'], [0.7, 0.05, 0.15, 0.05, 0.05]],
    'Reaction': [['ChemicalReactor'], [1]],
    'Splitting': [['SplittingUnit'], [1]],
    'Mixing': [['MixingUnit'], [1]],
    'Storage': [['StorageUnit'], [1]],
    'Separation': [['SeparationUnit'], [1]],  # general separation without further specification
    #'ThermalSeparation': [['DistillationSystem', 'FlashUnit', 'RectificationSystem'], [0.33, 0.33, 0.34]],
    'ThermalSeparation': [['RectificationSystem'], [1]],
    'CountercurrentSeparation': [['ExtractionUnit', 'StrippingSystem', 'AbsorptionColumn', 'Scrubber'],
                                 [0.3, 0.2, 0.3, 0.2]],
    'Filtration': [['LiquidFilter', 'GasFilter'], [0.5, 0.5]],
    'CentrifugalSeparation': [['CentrifugationUnit', 'Cyclone', 'Hydrocyclone'], [0.4, 0.4, 0.2]],
    'ElectricalGasCleaning': [['ElectricalGasCleaningUnit'], [1]],
    'Valve': [['Valve'], [1]],
    'UnitOperation': [['ProcessUnit'], [1]]
}

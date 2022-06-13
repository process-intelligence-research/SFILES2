from TestSFILESctrl import testSFILESctrl

# 1) Measuring point in/at unit operation
test_case = '1a'
edges = [('IO-1', 'tank-1'), ('tank-1', 'IO-2'), ('tank-1', 'C-1/TIR'), ('tank-1', 'C-2/LIR')]
testSFILESctrl(test_case, edges)

test_case = '1b'
edges = [('IO-1', 'tank-1'), ('C-1/LIR', 'v-1', {'tags': {'signal': ['not_next_unitop']}}), ('tank-1', 'C-1/LIR'),
         ('v-1', 'IO-2'), ('tank-1', 'v-1')]
testSFILESctrl(test_case, edges)

# 2) Measuring point at material stream
test_case = '2'
edges = [('IO-1', 'C-1/FC'), ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2')]
testSFILESctrl(test_case, edges)

# 3) Cascade control
test_case = '3'
edges = [('IO-1', 'tank-1'), ('tank-1', 'C-1/LC'), ('C-1/LC', 'C-2/FC', {'tags': {'signal': ['next_signal']}}),
         ('tank-1', 'C-2/FC'), ('C-2/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2')]
testSFILESctrl(test_case, edges)

# A)
test_case = 'A'
edges = [('IO-1', 'C-1/FC'), ('C-1/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2')]
testSFILESctrl(test_case, edges)

# B)
test_case = 'B'
edges = [('IO-1', 'C-1/F'), ('C-1/F', 'C-2/FFC', {'tags': {'signal': ['next_signal']}}),
         ('C-2/FFC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-2'), ('IO-3', 'C-3/F'),
         ('C-3/F', 'C-2/FFC'), ('C-3/F', 'IO-4')]
testSFILESctrl(test_case, edges)

# C)
test_case = 'C'
edges = [('IO-1', 'C-1/T'), ('C-1/T', 'IO-2'), ('IO-3', 'C-2/FQC'),
         ('C-1/T', 'C-2/FQC', {'tags': {'signal': ['next_signal']}}),
         ('C-2/FQC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'IO-4')]
testSFILESctrl(test_case, edges)

# D)
test_case = 'D'
edges = [('IO-1', 'hex-1/1'), ('hex-1/1', 'C-1/TC'), ('C-1/TC', 'IO-2'), ('IO-3', 'C-2/FC'),
         ('C-2/FC', 'v-1', {'tags': {'signal': ['next_unitop']}}), ('v-1', 'hex-1/2'),
         ('hex-1/2', 'IO-4'), ('C-1/TC', 'C-2/FC', {'tags': {'signal': ['next_signal']}})]
testSFILESctrl(test_case, edges)

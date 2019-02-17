import time
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sGraph.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sNode.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sEdge.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

# parameters
layer_name = 'oproads_lon'
layer_name = 'osm_lon'
layer = getLayerByName(layer_name)
crs = layer.crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()


getUnlinks = True
snap_threshold = 5
merge_type = 'intersections'
merge_type = ('angle', 45)

# 1. LOAD
_time = time.time()
pseudo_graph = sGraph({},{})
pseudo_graph.load_edges_w_o_topology(clean_features_iter(layer, snap_threshold))
print time.time() - _time

pseudo_layer = to_layer(map(lambda e: e.feature, pseudo_graph.sEdges.values()), crs, encoding, geom_type, 'memory', None, 'pseudo_layer')
QgsMapLayerRegistry.instance().addMapLayer(pseudo_layer)

# 2. BREAK
_time = time.time()
graph = sGraph({},{})
graph.load_edges(pseudo_graph.break_features_iter(getUnlinks))
print time.time() - _time

broken_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, geom_type, 'memory', None, 'broken_layer')
QgsMapLayerRegistry.instance().addMapLayer(broken_layer)

nodes = to_layer(map(lambda n: n.feature, graph.sNodes.values()), crs, encoding, 1, 'memory', None, 'nodes')
QgsMapLayerRegistry.instance().addMapLayer(nodes)

# 3. SNAP
_time = time.time()
graph.snap(snap_threshold)
print time.time() - _time

# 4. CLEAN
_time = time.time()
graph.clean_dupl_orphans()
print time.time() - _time

# 5. MERGE
_time = time.time()
graph.merge(merge_type)
print time.time() - _time

# 6. CLEAN
_time = time.time()
graph.clean_dupl_orphans()
print time.time() - _time

# simplify angle
route_graph = graph.merge(('route hierarchy', 45))
angle_column = route_graph.applyAngularCost({'class':'value'})
route_graph.simplifyAngle('angle_column')
graph = route_graph.break_graph(unlinks)

# collapse to node rb, short
graph.simplify_circles('length_column', {'rb_column': 'rb_value'})

# collapse to medial axis
graph.simplify_parallel_lines('dc column':'dc_value', distance)

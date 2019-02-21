import time
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sGraph.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sNode.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sEdge.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

# parameters
layer_name = 'oproads_lon'
# time with previous version: ~ 16 minutes
# time with new      version:
# reduction:

layer_name = 'osm_lon'
layer = getLayerByName(layer_name)
crs = layer.crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()
getUnlinks = True
snap_threshold = 5
angle_threshold = 15
merge_type = 'intersections' # 'angle'
orphans = True
fix_unlinks = False
collinear_threshold = None

# 1. LOAD
_time = time.time()
pseudo_graph = sGraph({},{})
pseudo_graph.load_edges_w_o_topology(clean_features_iter(layer))
print time.time() - _time

pseudo_layer = to_layer(map(lambda e: e.feature, pseudo_graph.sEdges.values()), crs, encoding, geom_type, 'memory', None, 'pseudo_layer')
QgsMapLayerRegistry.instance().addMapLayer(pseudo_layer)

# 2. BREAK
_time = time.time()
graph = sGraph({},{})
graph.load_edges(pseudo_graph.break_features_iter(getUnlinks, angle_threshold, fix_unlinks))
print time.time() - _time

broken_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, geom_type, 'memory', None, 'broken_layer')
QgsMapLayerRegistry.instance().addMapLayer(broken_layer)

# nodes
nodes = to_layer(map(lambda n: n.getFeature(), graph.sNodes.values()), crs, encoding, 1, 'memory', None, 'nodes')
QgsMapLayerRegistry.instance().addMapLayer(nodes)

# TODO: should happen after merge
# 4. SNAP
_time = time.time()
graph.snap_endpoints(snap_threshold)
print time.time() - _time

snapped_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, geom_type, 'memory', None, 'snapped_layer')
QgsMapLayerRegistry.instance().addMapLayer(snapped_layer)

# nodes
nodes = to_layer(map(lambda n: n.getFeature(), graph.sNodes.values()), crs, encoding, 1, 'memory', None, 'nodes')
QgsMapLayerRegistry.instance().addMapLayer(nodes)

# 3. CLEAN DUPLICATES
_time = time.time()
graph.clean_dupl_orphans(orphans, snap_threshold)
print time.time() - _time

cleaned_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, geom_type, 'memory', None, 'cleaned_layer')
QgsMapLayerRegistry.instance().addMapLayer(cleaned_layer)

# nodes
nodes = to_layer(map(lambda n: n.getFeature(), graph.sNodes.values()), crs, encoding, 1, 'memory', None, 'nodes')
QgsMapLayerRegistry.instance().addMapLayer(nodes)

# 3. MERGE
_time = time.time()
graph.merge(merge_type, collinear_threshold)
print time.time() - _time

# 6. CLEAN DUPLICATES & ORPHANS
_time = time.time()
graph.clean_dupl_orphans(orphans, snap_threshold)
print time.time() - _time

cleaned_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, geom_type, 'memory', None, 'cleaned_layer')
QgsMapLayerRegistry.instance().addMapLayer(cleaned_layer)

# simplify angle
route_graph = graph.merge(('route hierarchy', 45))
angle_column = route_graph.applyAngularCost({'class':'value'})
route_graph.simplifyAngle('angle_column')
graph = route_graph.break_graph(unlinks)

# collapse to node rb, short
graph.simplify_circles('length_column', {'rb_column': 'rb_value'})

# collapse to medial axis
graph.simplify_parallel_lines('dc column':'dc_value', distance)

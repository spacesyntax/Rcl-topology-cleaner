import time
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sGraph.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sNode.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/sEdge.py'.encode('utf-8'))
execfile(u'/Users/i.kolovou/Documents/Github/Rcl-topology-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

# parameters
layer_name = 'oproads_lon'
# time with previous version: ~ 16 minutes
# time with new      version: ~ 3 minutes
# reduction: 80%

layer_name = 'oproads_lon_small'
layer_name = 'Bhubneshwar'
layer_name = 'Diss_Hyd_Meso_HS_trails_small'

layer = getLayerByName(layer_name)
crs = layer.crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()
getUnlinks = True
snap_threshold = 10
angle_threshold = 15
merge_type = 'intersections'
#merge_type = 'collinear'
orphans = True
fix_unlinks = False
collinear_threshold = 5
duplicates = True
path = None

# 1. LOAD
_time = time.time()
pseudo_graph = sGraph({},{})
pseudo_graph.step = layer.featureCount()/ float(10)
pseudo_graph.load_edges_w_o_topology(clean_features_iter(layer.getFeatures()))
print time.time() - _time

#pseudo_layer = to_layer(map(lambda e: e.feature, pseudo_graph.sEdges.values()), crs, encoding, geom_type, 'memory', None, 'pseudo_layer')
#QgsMapLayerRegistry.instance().addMapLayer(pseudo_layer)

# 2. BREAK
_time = time.time()
graph = sGraph({},{})
pseudo_graph.step = len(pseudo_graph.sEdges)/ float(20)
graph.load_edges(pseudo_graph.break_features_iter(getUnlinks, angle_threshold, fix_unlinks))
#graph.load_edges(clean_features_iter(layer.getFeatures()))

print time.time() - _time

broken_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, 'Linestring', 'memory', path, 'broken_layer')
QgsMapLayerRegistry.instance().addMapLayer(broken_layer)

# nodes
# nodes = to_layer(map(lambda n: n.getFeature(), graph.sNodes.values()), crs, encoding, 'Point', 'memory', None, 'nodes')
# QgsMapLayerRegistry.instance().addMapLayer(nodes)

# 2. CLEAN || & CLOSED POLYLINES
_time = time.time()
graph.clean(True, False, snap_threshold, True)
print time.time() - _time

# 5. SNAP
_time = time.time()
graph.snap_endpoints(snap_threshold)






snapped_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, 'Linestring', 'memory', None, 'snapped_layer')
QgsMapLayerRegistry.instance().addMapLayer(snapped_layer)

# 4. CLEAN || & CLOSED POLYLINES
_time = time.time()
graph.clean(True, False, snap_threshold, True)
print time.time() - _time

#_time = time.time()
#graph.merge_collinear(collinear_threshold, angle_threshold)
#print time.time() - _time

# 3. MERGE
_time = time.time()
graph.merge_b_intersections(angle_threshold)
print time.time() - _time

merged_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, 'Linestring', 'memory', None, 'merged_layer')
QgsMapLayerRegistry.instance().addMapLayer(merged_layer)

# nodes
#nodes = to_layer(map(lambda n: n.getFeature(), graph.sNodes.values()), crs, encoding, 1, 'memory', None, 'nodes')
#QgsMapLayerRegistry.instance().addMapLayer(nodes)

# 6. CLEAN ALL
_time = time.time()
graph.clean(True, True, snap_threshold, False)
print time.time() - _time

# simplify angle
route_graph = graph.merge(('route hierarchy', 45))
angle_column = route_graph.applyAngularCost({'class':'value'})
route_graph.simplifyAngle('angle_column')
graph = route_graph.break_graph(graph.unlinks)

# collapse to node rb, short (has happened)
graph.simplify_roundabouts({'rb_column': 'rb_value'})

# collapse to medial axis
graph.simplify_parallel_lines({'dc column':'dc_value'}, {'dc column_distance':'dc_distance_value'})

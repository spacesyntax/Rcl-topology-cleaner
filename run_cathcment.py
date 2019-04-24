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

layer_name = 'r_osm_simpl_cl'
origins_name = 'pt_network_w_o_times_nodes'
origins_name = 'origins_test'

layer = getLayerByName(layer_name)
origins_layer = getLayerByName(origins_name)
crs = layer.crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()
path = None

# 1. LOAD
_time = time.time()
graph = sGraph({}, {})
graph.load_edges(clean_features_iter(layer.getFeatures()))
print time.time() - _time
_layer = to_layer(map(lambda e: e.feature, graph.sEdges.values()), crs, encoding, 'Linestring', 'memory', path, 'loaded_layer')
QgsMapLayerRegistry.instance().addMapLayer(_layer)

# 2. LOAD SPINDEX
graph.edgeSpIndex = QgsSpatialIndex()
res = map(lambda sedge: graph.edgeSpIndex.insertFeature(sedge.feature), graph.sEdges.values())

_time = time.time()
for k, v in graph.sEdges.items():
    v.len = v.feature.geometry().length()


_time = time.time()
# START

for o in origins_layer.getFeatures():
    # break
    origin_name = str(o.id())
    #print origin_name
    origin_geom = o.geometry()
    closest_edge = graph.edgeSpIndex.nearestNeighbor(origin_geom.asPoint(), 1)[0]
    edge_geom = graph.sEdges[closest_edge].feature.geometry()
    nodes = set(graph.sEdges[closest_edge].nodes)
    graph.cost_limit = 600
    graph.origin_name = origin_name
    # endpoints
    branches = []
    shortest_line = o.geometry().shortestLine(edge_geom)
    point_on_line = shortest_line.intersection(edge_geom)
    fraction = edge_geom.lineLocatePoint(point_on_line)
    fractions = [fraction, 1 - fraction]
    degree = 0
    for node, fraction in zip(nodes, fractions):
        branches.append(([node, graph.sNodes[node].feature.geometry().distance(point_on_line)))
    for k in graph.sEdges.keys():
        graph.sEdges[k].visited[origin_name] = None
    graph.sEdges[closest_edge].visited[origin_name] = True
    graph.sEdges[closest_edge].agg_cost[origin_name] = -1
    while len(branches) > 0:
        branches = map(lambda (dest, agg_cost): graph.get_next_edges(dest, agg_cost), branches)
        branches = list(itertools.chain.from_iterable(branches))
    break

print time.time() - _time
print time.time() - _time

### TEST 1
#  1 origin - 600  -
#  1 origin - 1200 - 0.09 - interpolate for 10.000 - 20 min

### TEST 2
#  1 origin - 1200 - 0.021 - interpolate for 10.000 - 3.5 min

# for 2000 - 0.7 min
# NON LINEAR - 10 min






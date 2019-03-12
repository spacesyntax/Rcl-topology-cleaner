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
#for j in range(1, 100):

for o in origins_layer.getFeatures():
    break

origin_geom = o.geometry()
closest_edge = graph.edgeSpIndex.nearestNeighbor(origin_geom.asPoint(), 1)[0]
graph.sEdges[closest_edge].visited = True
for (n, agg_cost, edge, fr) in graph.catchment_iterator(origin_geom, closest_edge, 600):
    pass
    #print (n, agg_cost, edge, fr, degree)
    #break


        #try:
        #    graph.sEdges.catchment[str(o.id())] = min([graph.sEdges.catchment['origin1'], agg_cost])
        #except KeyError:
        #    graph.sEdges.catchment[str(o.id())] = agg_cost

print time.time() - _time
print time.time() - _time


1 origin - 600  -
1 origin - 1200 - 0.09 - interpolate for 10.000 - 20 min - wish

600m - 1000 - 1.53 sec
1200m




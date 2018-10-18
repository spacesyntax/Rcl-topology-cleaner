
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/clean_tool.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/sNode.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/sEdge.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

#execfile(u'/Users/I.Kolovou/Documents/GitHub/Road-network-cleaner/sGraph/clean_tool.py'.encode('utf-8'))

# SETTINGS _______________________________________________________________________
import time
start_time = time.time()

# input settings
layer_name = 'road_small2'
#layer_name = 'madagascar'
#layer_name = 'comp_model_cr_cl_simpl10'
layer = getLayerByName(layer_name)

# cleaning settings
Snap = 1
Break = True
Merge = 'between intersections'
Errors = True
Unlinks = True

# output settings
path = None

# RUN____________________________________________________________________________

clean_tool = cleanTool(Snap, Break, Merge, Errors, Unlinks)

"""0.LOAD"""
res = map(lambda f:clean_tool.sEdgesSpIndex.insertFeature(f), clean_tool.features_iter(layer))

"""1.BREAK"""
# TODO: speed up
broken_edges = map(lambda (sedge, vertices): clean_tool.breakAtVertices(sedge, vertices), clean_tool.breakFeaturesIter())
res = map(lambda edge_id: clean_tool.del_edge(edge_id), filter(lambda edge_id: edge_id is not None, broken_edges))

# create topology
res = map(lambda (edgeid, qgspoint): clean_tool.createTopology(qgspoint, edgeid), clean_tool.endpointsIter())

subgraph_nodes = clean_tool.subgraph_nodes()
subgraph_nodes_layer = to_layer([clean_tool.sNodes[n].getFeature() for n in subgraph_nodes], layer.crs(), layer.dataProvider().encoding(), 1, 'memory', None, 'closest_nodes')
QgsMapLayerRegistry.instance().addMapLayer(subgraph_nodes_layer)

res = map(lambda nodes: clean_tool.mergeNodes(nodes), clean_tool.con_comp_iter(clean_tool.subgraph_nodes()))

edges_layer = to_layer([sedge.feature for sedge in clean_tool.sEdges.values()], layer.crs(), layer.dataProvider().encoding(), 2, 'memory', None, 'edges')
QgsMapLayerRegistry.instance().addMapLayer(edges_layer)

nodes_layer = to_layer([n.getFeature() for n in clean_tool.sNodes.values()], layer.crs(), layer.dataProvider().encoding(), 1, 'memory', None, 'closest_nodes')
QgsMapLayerRegistry.instance().addMapLayer(nodes_layer)


all_pairs = map(lambda sedge: [frozenset([sedge.getStartNode(), sedge.getEndNode()]), sedge.id], clean_tool.sEdges.values())
clean_tool.sNodeNode = dict(map(lambda (k, g): (k, [x[1] for x in g]), itertools.groupby(sorted(all_pairs), operator.itemgetter(0))))
res = map(lambda group_edges: clean_tool.merge_edges(group_edges), clean_tool.con_comp_con_2_iter())


components_passed = set([])
for (ndid, node) in filter(lambda (_id, _node): _node.getConnectivity() != 2, clean_tool.sNodes.items()):
    break

for id in node.topology:
    startnode = ndid
    endnode = [i for i in clean_tool.sEdges[id].nodes if i !=ndid].pop()
    if {endnode}.isdisjoint(components_passed):
        group = [startnode, [endnode]]
        candidates = ['dummy']
        while len(candidates) == 1:
            flat_group = group[:-1] + group[-1]
            last_visited = group[-1][0]
            candidates = itertools.chain.from_iterable(
                map(lambda edge: clean_tool.sEdges[edge].nodes, clean_tool.sNodes[last_visited].topology))
            group = flat_group + [list(set(candidates).difference(set(flat_group)))]
        components_passed.update(set(group[1:-1]))

        yield group[:-1]

print 'process time', time.time() - start_time
print 'finished'











# project settings
crs = layer.dataProvider().crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()

errors = True

# break features
br = breakTool(layer, tolerance, None, True, True)
br.add_edges()
fields = br.layer_fields

broken_features = br.break_features()

unlinks = to_shp(None, br.unlinked_features, [QgsField('id', QVariant.Int), QgsField('line_id1', QVariant.String), QgsField('line_id2', QVariant.String), QgsField('x', QVariant.Double), QgsField('y', QVariant.Double)], crs,'unlinks', encoding, 0)
QgsMapLayerRegistry.instance().addMapLayer(unlinks)

#broken_network = br.to_shp(broken_features, crs, 'broken')
#QgsMapLayerRegistry.instance().addMapLayer(broken_network)

mrg = mergeTool(broken_features, None, True)

#fields = br.layer_fields
#to_merge = to_shp(feat_to_merge, fields, crs, 'to_merge')
#QgsMapLayerRegistry.instance().addMapLayer(to_merge)

#to_start = to_shp(edges_to_start, fields, crs, 'to_start')
#QgsMapLayerRegistry.instance().addMapLayer(to_start)

result = mrg.merge()

to_dblayer('geodb', 'postgres', '192.168.1.10', '5432', 'spaces2017', 'gbr_exeter', 'cleaned',  br.layer_fields, result, crs)

final = to_shp(path, result, fields, crs, 'f', encoding, geom_type )
QgsMapLayerRegistry.instance().addMapLayer(final)


layer = iface.mapCanvas().currentLayer()
qgs_flds = [QgsField(i.name(), i.type()) for i in layer.dataProvider().fields()]
postgis_flds = qgs_to_postgis_fields(qgs_flds, arrays = False)




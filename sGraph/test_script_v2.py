
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

"""2.SNAP"""

subgraph_nodes = clean_tool.subgraph_nodes()
subgraph_nodes_layer = to_layer([clean_tool.sNodes[n].getFeature() for n in subgraph_nodes], layer.crs(), layer.dataProvider().encoding(), 1, 'memory', None, 'closest_nodes')
QgsMapLayerRegistry.instance().addMapLayer(subgraph_nodes_layer)

res = map(lambda nodes: clean_tool.mergeNodes(nodes), clean_tool.con_comp_iter(clean_tool.subgraph_nodes()))

edges_layer = to_layer([sedge.feature for sedge in clean_tool.sEdges.values()], layer.crs(), layer.dataProvider().encoding(), 2, 'shapefile', '/Users/joe/Downloads/sedges.shp', 'edges')
QgsMapLayerRegistry.instance().addMapLayer(edges_layer)

nodes_layer = to_layer([n.getFeature() for n in clean_tool.sNodes.values()], layer.crs(), layer.dataProvider().encoding(), 1, 'shapefile', '/Users/joe/Downloads/snodes.shp', 'closest_nodes')
QgsMapLayerRegistry.instance().addMapLayer(nodes_layer)


"""3.MERGE"""
#pseudo_nodes = clean_tool.subgraph_con2_nodes()
#pseudo_nodes_layer = to_layer([clean_tool.sEdges[e].feature for e in pseudo_nodes], layer.crs(), layer.dataProvider().encoding(), 2, 'memory', None, 'pseudo nodes')
#QgsMapLayerRegistry.instance().addMapLayer(pseudo_nodes_layer)
#pseudo_nodes_layer = to_layer([snode.getFeature() for n, snode in pseudo_nodes.items()], layer.crs(), layer.dataProvider().encoding(), 1, 'memory', None, 'pseudo nodes')
#QgsMapLayerRegistry.instance().addMapLayer(pseudo_nodes_layer)

edges_to_rem = map(lambda (group_edges): clean_tool.merge_edges(group_edges), clean_tool.con_comp_iter(clean_tool.subgraph_con2_nodes()))
res = map(lambda edge_id: clean_tool.del_edge(edge_id), itertools.chain.from_itearble(edges_to_rem))

edges_layer = to_layer([sedge.feature for sedge in clean_tool.sEdges.values()], layer.crs(), layer.dataProvider().encoding(), 2, 'shapefile', '/Users/joe/Downloads/sedges.shp', 'edges')
QgsMapLayerRegistry.instance().addMapLayer(edges_layer)
















for (group_edges, group_nodes) in clean_tool.con_comp_con_2_iter():
    res = clean_tool.merge_edges(group_edges, group_nodes)



components_passed = set([])
for (edge_id, edge) in filter(lambda (_id, _edge): clean_tool.getConnectivity(_edge) != 2 and len(set(_edge.nodes)) != 1,
                              clean_tool.sEdges.items()):
    # statedge should not be a selfloop
    if {edge_id}.isdisjoint(components_passed):
        startnode, endnode = edge.nodes
        if clean_tool.sNodes[endnode].getConnectivity() != 2:
            startnode, endnode = edge.nodes[::-1]
        #if startnode > endnode:  # prevent 2 ways
        group_nodes = [startnode, endnode]
        group_edges = [edge_id]
        if clean_tool.sNodes[endnode].getConnectivity() == 2:
            edge_id


        while clean_tool.sNodes[endnode].getConnectivity() == 2:
            candidates = [edge for edge in clean_tool.sNodes[endnode].topology if edge not in group_edges]
            group_edges += candidates  # selfloop/ parallels disregarded
            endnode = (set(clean_tool.sEdges[candidates[0]].nodes).difference({endnode})).pop()
            group_nodes += [endnode]
        components_passed.update(set(group_edges))
        if len(group_edges) > 1:
            yield group_edges, group_nodes









pseudo_edges = []
for i in clean_tool.con_comp_con_2_iter():
    pseudo_edges+= [i[0]]


pseudo_edges = [clean_tool.sEdges[e].feature  for edg in pseudo_edges for e in edg]

pseudo_edges_layer = to_layer(pseudo_edges, layer.crs(), layer.dataProvider().encoding(), 2, 'shapefile', '/Users/joe/Downloads/pseudoedges.shp', 'pseudo_edges_layer')
QgsMapLayerRegistry.instance().addMapLayer(pseudo_edges_layer)




pseudo_nodes = {}
for nid, node in clean_tool.sNodes.items():
    if node.getConnectivity() == 2:
        bool = True
        for i in node.topology:
            if len(set(clean_tool.sEdges[i].nodes)) == 1:
                bool = False
        if bool:
            pseudo_nodes[nid] = node

pseudo_nodes_layer = to_layer([n.getFeature() for n in pseudo_nodes.values()], layer.crs(),
                                layer.dataProvider().encoding(), 1, 'shapefile', '/Users/joe/Downloads/pseudo.shp', 'pseudo_nodes')
QgsMapLayerRegistry.instance().addMapLayer(pseudo_nodes_layer)












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




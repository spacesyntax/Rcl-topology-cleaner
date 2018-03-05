
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/break_tools.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/merge_tools.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

#execfile(u'/Users/I.Kolovou/Documents/GitHub/Road-network-cleaner/sGraph/break_tools.py'.encode('utf-8'))
#execfile(u'/Users/I.Kolovou/Documents/GitHub/Road-network-cleaner/sGraph/merge_tools.py'.encode('utf-8'))
#execfile(u'/Users/I.Kolovou/Documents/GitHub/Road-network-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

# _______________________________________________________________________________
layer_name = 'comp_model'

# cleaning settings
path = None
tolerance = None

# project settings
layer = getLayerByName(layer_name)
crs = layer.dataProvider().crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()

# break features
br = breakTool(layer.fields())
br.add_links(layer.getFeatures(), layer.featureCount(), 30)

layer = to_shp(path, br.links.values(), br.linksFields, crs, 'layer', encoding, geom_type )
QgsMapLayerRegistry.instance().addMapLayer(layer)

nodes = to_shp(path, br.nodes.values(), [QgsField('id', QVariant.Int)], crs, 'nodes', encoding, 0 )
QgsMapLayerRegistry.instance().addMapLayer(nodes)

snap_threshold = 5
if snap_threshold:
    br.add_short_links(snap_threshold)


short_layer = to_shp(path, br.shortLinks.values(), br.linksFields, crs, 'short_layer', encoding, geom_type )
QgsMapLayerRegistry.instance().addMapLayer(short_layer)

only_short = False
broken_features = br.break_links(only_short)

import time
start = time.time()

x = 0

for link_id, link in br.links.items():
    x += 1
    if x< 1000:
        intersecting_vertices, self_intersections = br.get_breakages(link, link_id, only_short)
        print intersecting_vertices

end = time.time()
print 'Graph build', end - start




broken_layer = to_shp(path, list(broken_features), br.linksFields, crs, 'broken_layer', encoding, geom_type )
QgsMapLayerRegistry.instance().addMapLayer(broken_layer)

#broken_network = br.to_shp(broken_features, crs, 'broken')
#QgsMapLayerRegistry.instance().addMapLayer(broken_network)

mrg = mergeTool(broken_features + br.shortLinks.values(), br.linksFields)

#fields = br.layer_fields
#to_merge = to_shp(feat_to_merge, fields, crs, 'to_merge')
#QgsMapLayerRegistry.instance().addMapLayer(to_merge)

#to_start = to_shp(edges_to_start, fields, crs, 'to_start')
#QgsMapLayerRegistry.instance().addMapLayer(to_start)

colinear_threshold = None
result = mrg.merge(colinear_threshold)

to_dblayer('geodb', 'postgres', '192.168.1.10', '5432', 'spaces2017', 'gbr_exeter', 'cleaned',  br.layer_fields, result, crs)

final = to_shp(path, result, fields, crs, 'f', encoding, geom_type )
QgsMapLayerRegistry.instance().addMapLayer(final)


layer = iface.mapCanvas().currentLayer()
qgs_flds = [QgsField(i.name(), i.type()) for i in layer.dataProvider().fields()]
postgis_flds = qgs_to_postgis_fields(qgs_flds, arrays = False)





execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/break_tools.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/merge_tools.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

execfile(u'/Users/I.Kolovou/Documents/GitHub/Road-network-cleaner/sGraph/break_tools.py'.encode('utf-8'))
execfile(u'/Users/I.Kolovou/Documents/GitHub/Road-network-cleaner/sGraph/merge_tools.py'.encode('utf-8'))
execfile(u'/Users/I.Kolovou/Documents/GitHub/Road-network-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

# _________________________ TRANSFORMATIONS ______________________________

# transform shapefile to primal graph

#layer_name = 'london_ax_ex'
#layer_name = 'New scratch layer'
#layer_name = 'Netwrok_small'
#layer_name = 'madagascar'
layer_name = 'comp_model_cr_cl_simpl10'

# cleaning settings
path = None
tolerance = None

# project settings
layer = getLayerByName(layer_name)
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





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
layer_name = 'Barnsbury_OpenStreetMap'

dbname = 'nyc'
user = 'postgres'
host = 'localhost'
port = 5432
password = 'spaces01'
schema = '"public"'
table_name = '"1 test"'
connstring = "dbname=%s user=%s host=%s port=%s password=%s" % (dbname, user, host, port, password)

# cleaning settings

path = None
tolerance = 6

# project settings
layer = getLayerByName(layer_name)
crs = layer.dataProvider().crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()

errors = True

# break features
br = breakTool(layer, tolerance, None, True)
br.add_edges()

broken_features = br.break_features()

to_dblayer(dbname, user, host, port, password, schema, table_name, br.layer_fields, broken_features, crs, arrays=False)

#broken_network = br.to_shp(broken_features, crs, 'broken')
#QgsMapLayerRegistry.instance().addMapLayer(broken_network)

mrg = mergeTool(broken_features, None, True)

#fields = br.layer_fields
#to_merge = to_shp(feat_to_merge, fields, crs, 'to_merge')
#QgsMapLayerRegistry.instance().addMapLayer(to_merge)

#to_start = to_shp(edges_to_start, fields, crs, 'to_start')
#QgsMapLayerRegistry.instance().addMapLayer(to_start)

result = mrg.merge()

to_dblayer(dbname, user, host, port, password, schema, table_name, br.layer_fields, result, crs, arrays=True)


fields = br.layer_fields
final = to_shp(path, result, fields, crs, 'f', encoding, geom_type )
QgsMapLayerRegistry.instance().addMapLayer(final)


layer = iface.mapCanvas().currentLayer()
qgs_flds = [QgsField(i.name(), i.type()) for i in layer.dataProvider().fields()]
postgis_flds = qgs_to_postgis_fields(qgs_flds, arrays = False)




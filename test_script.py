
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/break_tools.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/merge_tools.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))

# _________________________ TRANSFORMATIONS ______________________________

# transform shapefile to primal graph

#layer_name = 'london_ax_ex'
#layer_name = 'New scratch layer'
#layer_name = 'Netwrok_small'
#layer_name = 'madagascar'
layer_name = 'nyc_streets'

# cleaning settings

path = None
tolerance = 6

# project settings
layer = getLayerByName(layer_name)
crs = layer.dataProvider().crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()
user_id = 'id'
errors = True

# break features
br = breakTool(layer, tolerance, user_id, True)
input_geometries = br.geometries
input_fid_to_id = br.fid_to_uid

broken_features, breakages, overlaps, orphans, closed_polylines, self_intersecting, duplicates = br.break_features()

#broken_network = br.to_shp(broken_features, crs, 'broken')
#QgsMapLayerRegistry.instance().addMapLayer(broken_network)

mrg = mergeTool(broken_features, user_id, True)
all_con, con_1, f_dict, feat_to_copy, feat_to_merge, edges_to_start = mrg.prepare()

#fields = br.layer_fields
#to_merge = to_shp(feat_to_merge, fields, crs, 'to_merge')
#QgsMapLayerRegistry.instance().addMapLayer(to_merge)

#to_start = to_shp(edges_to_start, fields, crs, 'to_start')
#QgsMapLayerRegistry.instance().addMapLayer(to_start)

result = mrg.merge()

fields = br.layer_fields
final = to_shp(result, fields, crs, 'f' )
QgsMapLayerRegistry.instance().addMapLayer(final)




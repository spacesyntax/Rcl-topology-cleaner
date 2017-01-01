
# imports
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/utilityFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/shpFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/primal_graph.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/plFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/generalFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/dual_graph.py'.encode('utf-8'))


# _________________________ TRANSFORMATIONS ______________________________

# transform shapefile to primal graph

from PyQt4.QtCore import QVariant
qgsflds_types = {u'Real': QVariant.Double, u'String': QVariant.String}

layer_name = 'ttt1'

# cleaning settings

path = None
tolerance = 6
base_id = 'id_in'

# project settings
n = getLayerByName(layer_name)
crs = n.dataProvider().crs()
encoding = n.dataProvider().encoding()
geom_type = n.dataProvider().geometryType()
qgsflds = get_field_types(layer_name)


# shp/postgis to prGraph instance
simplify = True
user_id = 'osm_id'
parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify, 'id_column': base_id, 'user_id':user_id, 'get_invalids':True, 'get_multiparts':True}

# error cat: invalids, multiparts
primal_graph, invalids, multiparts = transformer(parameters).read_shp_to_multi_graph()
any_primal_graph = prGraph(primal_graph, True)
primal_cleaned, duplicates, parallel_con, parallel_nodes = any_primal_graph.rmv_dupl_overlaps(user_id, False)

QgsMapLayerRegistry.instance().addMapLayer(primal_cleaned.to_shp(None, 't', crs, encoding, geom_type, qgsflds))

# break at intersections and overlaping geometries
# error cat: to_break
broken_primal, to_break, overlaps, orphans, closed_polylines = primal_cleaned.break_graph(tolerance, simplify, user_id)

# error cat: duplicates
broken_clean_primal, duplicates_br, parallel_con2, parallel_nodes2 = broken_primal.rmv_dupl_overlaps(user_id, True)

QgsMapLayerRegistry.instance().addMapLayer(broken_clean_primal.to_shp(None, 'br', crs, encoding, geom_type, qgsflds))


# transform primal graph to dual graph
centroids = broken_clean_primal.get_centroids_dict()
broken_dual = dlGraph(broken_clean_primal.to_dual(True, parallel_nodes2, tolerance, False, False), centroids, True)

# Merge between intersections
# error cat: to_merge
merged_primal, to_merge = broken_dual.merge(broken_clean_primal, tolerance, simplify, user_id)


QgsMapLayerRegistry.instance().addMapLayer(broken_dual.to_shp(None, 'dual', crs, encoding, geom_type))

# error cat: duplicates
merged_clean_primal, duplicates_m,  parallel_con3, parallel_nodes3 = merged_primal.rmv_dupl_overlaps(None, False)

name = layer_name + '_cleaned'


centroids = merged_clean_primal.get_centroids_dict()
merged_dual = dlGraph(merged_clean_primal.to_dual(False, parallel_nodes3, tolerance, False, False), centroids,
		  True)


error_list = [['invalid', invalids], ['multipart', multiparts],
                                      ['intersecting at vertex', to_break],
                                      ['overlaping', overlaps],
                                      ['duplicate', duplicates],
                                      ['continuous line', to_merge],
                                      # ['islands', islands],
                                      ['orphans', orphans], ['closed_polyline', closed_polylines]
          ]
e_path = None
input_layer = getLayerByName(parameters['layer_name'])
QgsMapLayerRegistry.instance().addMapLayer(errors_to_shp(input_layer, parameters['user_id'], error_list, e_path, 'errors', crs, encoding, geom_type))

# return cleaned shapefile and errors
QgsMapLayerRegistry.instance().addMapLayer(merged_clean_primal.to_shp(path, name, crs, encoding, geom_type, qgsflds))

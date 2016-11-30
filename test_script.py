
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

layer_name = 'nyc_streets_small'

# cleaning settings

path = None
tolerance = 3
base_id = 'id_in'

# project settings
n = getLayerByName(layer_name)
crs = n.dataProvider().crs()
encoding = n.dataProvider().encoding()
geom_type = n.dataProvider().geometryType()
qgsflds = get_field_types(layer_name)


# shp/postgis to prGraph instance
simplify = True
user_id = 'gid'
parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify, 'id_column': base_id, 'user_id':user_id, 'get_invalids':False, 'get_multiparts':False}

# error cat: invalids, multiparts
primal_graph, invalids, multiparts = transformer(parameters).run()
any_primal_graph = prGraph(primal_graph, base_id, True)

# break at intersections and overlaping geometries
# error cat: to_break
broken_primal, to_break = any_primal_graph.break_graph(tolerance, simplify)

# error cat: duplicates
broken_clean_primal, duplicates_br = broken_primal.rmv_dupl_overlaps()

# transform primal graph to dual graph
centroids = broken_clean_primal.get_centroids_dict()
broken_dual = dlGraph(broken_clean_primal.to_dual(True, False, False), broken_clean_primal.uid, centroids, True)

# Merge between intersections
# error cat: to_merge
merged_primal, to_merge = broken_dual.merge(broken_clean_primal, tolerance, simplify)


# error cat: duplicates
merged_clean_primal, duplicates_m = merged_primal.rmv_dupl_overlaps()

name = layer_name + '_cleaned'


centroids = merged_clean_primal.get_centroids_dict()
merged_dual = dlGraph(merged_clean_primal.to_dual(False, False, False), merged_clean_primal.uid, centroids,
		  True)

# error cat: islands, orphans
islands, orphans = merged_dual.find_islands_orphans(merged_clean_primal)


# combine all errors
error_list = [['invalids', invalids], ['multiparts', multiparts], ['intersections/overlaps', to_break],
  ['duplicates', duplicates_br], ['chains', to_merge],
  ['islands', islands], ['orphans', orphans]]
e_path = None
errors = errors_to_shp(error_list, e_path, 'errors', crs, encoding, geom_type)


# return cleaned shapefile and errors
cleaned = merged_clean_primal.to_shp(path, name, crs, encoding, geom_type, qgsflds)
ret = (errors, cleaned,)
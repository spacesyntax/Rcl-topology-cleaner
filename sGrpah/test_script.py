# imports
execfile(u'/Users/joe/Rcl-topology-validation/geometryFunctions/wktFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/otherFunctions/utilityFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/otherFunctions/shpFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGrpah/sGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGrpah/prGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/geometryFunctions/plFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/otherFunctions/generalFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGrpah/dlGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGraphFunctions/transformer.py'.encode('utf-8'))

# _________________________ TRANSFORMATIONS ______________________________

# transform shapefile to primal graph

from PyQt4.QtCore import QVariant
qgsflds_types = {u'Real': QVariant.Double , u'String': QVariant.String}

layer_name = 'nyc_streets_shp'

transformation_type = 'shp_to_pgr'
base_id = 'id_in'
tolerance = 3
simplify = True
parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify, 'id_column': base_id}
primal_graph = transformer(parameters, transformation_type).result

any_primal_graph = prGraph(primal_graph, base_id, True)
print any_primal_graph.obj.size()
print any_primal_graph.obj.__len__()


# _________________________ DIAGNOSIS ______________________________

# identify multiparts invalids from shpefile

invalids, multiparts = inv_mlParts(layer_name, base_id)

# clean duplicates, overlaps

clean_graph = any_primal_graph.rmv_dupl_overlaps()

# TODO: setup constants of project
n = getLayerByName(layer_name)
crs = n.dataProvider().crs()
encoding = n.dataProvider().encoding()
geom_type = n.dataProvider().geometryType()
name = 'network'
path = None
qgsflds = get_field_types(layer_name)

clean_shp = clean_graph.to_shp(path, name, crs, encoding, geom_type, qgsflds)

# TODO Add change coordinate reference system

# Break at intersections

broken_primal = clean_graph.break_at_intersections(tolerance, simplify)
broken_clean_primal = broken_primal.rmv_dupl_overlaps()

name = 'broken_network'
broken_clean_primal.to_shp(path, name, crs, encoding, geom_type, qgsflds)

# transform primal graph to dual graph

centroids = broken_clean_primal.get_centroids_dict()
broken_dual = dlGraph(broken_primal.to_dual(True), broken_primal.uid, centroids, True)

print broken_dual.obj.size()
print broken_dual.obj.__len__()

name = 'dual_network'
broken_dual.to_shp(path, name, crs, encoding, geom_type)

#broken_dual_all = dlGraph(broken_primal.to_dual(False), broken_primal.uid, centroids, True)
#print broken_dual_all.obj.size()
#print broken_dual_all.obj.__len__()

#name = 'dual_network_all'
#broken_dual_all.to_shp(path, name, crs, encoding, geom_type)

sets = broken_dual.find_cont_lines()


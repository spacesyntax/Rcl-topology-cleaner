
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

layer_name = 'Netwrok_small'

tolerance = 3
simplify = True
parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify}
primal_graph = transformer(parameters).run()
base_id = 'id_in'

any_primal_graph = prGraph(primal_graph, base_id, True)
print any_primal_graph.obj.size()
print any_primal_graph.obj.__len__()

# identify multiparts invalids from shpefile

# invalids, multiparts = inv_mlParts(layer_name, base_id)

# TODO: setup constants of project
n = getLayerByName(layer_name)
crs = n.dataProvider().crs()
encoding = n.dataProvider().encoding()
geom_type = n.dataProvider().geometryType()
qgsflds = get_field_types(layer_name)

# Break at intersections

broken_primal, to_break = any_primal_graph.break_graph(tolerance, simplify)
path=None
name = 'network'
any_primal_graph.to_shp(path, name, crs, encoding, geom_type, any_primal_graph.get_qgs_fields(qgsflds))
br = any_primal_graph.find_breakages()
x=0
for i in br:
	x+=1

broken_clean_primal = broken_primal.rmv_dupl_overlaps()

name = 'broken_network'
broken_clean_primal.to_shp(path, name, crs, encoding, geom_type, qgsflds)

# transform primal graph to dual graph

centroids = broken_clean_primal.get_centroids_dict()
broken_dual = dlGraph(broken_clean_primal.to_dual(True,False,False), broken_clean_primal.uid, centroids, True)

print broken_dual.obj.size()
print broken_dual.obj.__len__()

name = 'dual_network'
broken_dual.to_shp(path, name, crs, encoding, geom_type)

# Merge between intersections
# sets = broken_dual.find_cont_lines()

merged_primal = broken_dual.merge(broken_clean_primal, tolerance, simplify)
merged_clean_primal = merged_primal.rmv_dupl_overlaps()

name = 'merged_network'
merged_clean_primal.to_shp(path, name, crs, encoding, geom_type, qgsflds)

centroids = merged_clean_primal.get_centroids_dict()

merged_dual_all = dlGraph(merged_clean_primal.to_dual(False,True,True), merged_clean_primal.uid, centroids, True)
print merged_dual_all.obj.size()
print merged_dual_all.obj.__len__()

name = 'dual'
merged_dual_all.to_shp(path, name, crs, encoding, geom_type)
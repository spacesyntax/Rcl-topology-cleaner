# imports
execfile(u'/Users/joe/Rcl-topology-validation/geometryFunctions/wktFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/otherFunctions/utilityFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGraphFunctions/analyser.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/otherFunctions/shpFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGrpah/sGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGrpah/prGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/geometryFunctions/plFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/otherFunctions/generalFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGrpah/fMap.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGrpah/dlGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGraphFunctions/transformer.py'.encode('utf-8'))
execfile(u'/Users/joe/Rcl-topology-validation/sGraphFunctions/cleaner.py'.encode('utf-8'))



# _________________________ TRANSFORMATIONS ______________________________

# transform shapefile to primal graph

from PyQt4.QtCore import QVariant
qgsflds_types = {u'Real': QVariant.Double , u'String': QVariant.String}

layer_name = 'nyc_streets_shp'

transformation_type = 'shp_to_pgr'
base_id = 'id_in'
parameters = {'layer_name': layer_name, 'tolerance': 3, 'simplify': True, 'id_column': base_id}
primal_graph = transformer(parameters, transformation_type).result

any_primal_graph = prGraph(primal_graph, base_id)
print any_primal_graph.obj.size()
print any_primal_graph.obj.__len__()


# match qgs fields to primal graph fields

transformation_type = 'prflds_to_qgsfields'
base_id = 'id_in'
prflds = any_primal_graph.get_fields()
qgsflds = get_field_types(layer_name)
parameters = {'layer_name': layer_name, 'prfields': prflds, 'qgsfields': qgsflds, 'id_column': base_id, 'qvariant_types': qgsflds_types}
flds = transformer(parameters, transformation_type).result

# transform primal graph to qfeatures

transformation_type = 'prg_to_qf'
parameters = {'prGraph': any_primal_graph, 'id_column': base_id, 'fields': flds, 'count':0}
base_id = 'id_in'
# no fields set up, no fid in the result of the transformation
qf = fMap(transformer(parameters, transformation_type).result, parameters['count'])
print qf.obj[0].id(), qf.obj[1].id()

# write qfeatures to shapefile

transformation_type = 'fm_to_shp'
# TODO: setup constants of project
n = iface.mapCanvas().currentLayer()
crs = n.dataProvider().crs()
encoding = n.dataProvider().encoding()
geom_type = n.dataProvider().geometryType()
layer_name = 'network'

parameters = {'fields': flds, 'fMap': qf, 'name': layer_name, 'path': None, 'encoding': encoding, 'geom_type': geom_type, 'crs': crs, 'id_column': base_id}
shp = transformer(parameters, transformation_type).result

# transform primal graph to dual graph

transformation_type ='prg_to_dlgr'
parameters = {'prGraph': any_primal_graph, 'break_at_intersections': False,'id_column': base_id}
dual_g = dlGraph(transformer(parameters,transformation_type).result,parameters['id_column'])
print dual_g.obj.size()
print dual_g.obj.__len__()

# transform dual graph to qfeatures

transformation_type = 'dlgr_to_qf'
attr_index = 1
parameters = {'fMap': qf,'attr_index': attr_index, 'dlGraph': dual_g, 'id_column': base_id, 'count':0}
dl_qf = fMap(transformer(parameters, transformation_type).result, parameters['count'])

# write dual graph qfeatures to shapefile

transformation_type = 'fm_to_shp'
layer_name = 'dual_network'
dl_flds = [QgsField("line1", QVariant.String), QgsField("line2", QVariant.String), QgsField("cost", QVariant.Int)]
parameters = {'fields': dl_flds, 'fMap': dl_qf, 'name': layer_name, 'path': None, 'encoding': encoding, 'geom_type': geom_type, 'crs': crs, 'id_column': base_id}
dl_shp = transformer(parameters, transformation_type).result


# _________________________ DIAGNOSIS ______________________________


# TODO Add identify invalids and multiparts
# TODO Add change coordinate reference system

# Break at intersections

analysis_type = 'break_at_intersections'
settings = {'fMap': qf, 'attr_index': attr_index, 'id_column': base_id}
analysis = analyser(settings, analysis_type)
breakages_iter = analysis.find_breakages()


parameters = {'wkt_index': 6, 'fMap': qf, 'breakages': breakages_iter, 'attr_index': attr_index, 'id_column': base_id, 'clean_type': 'break_at_intersections'}
broken_feat, new_field = cleaner(parameters).result

transformation_type = 'fm_to_shp'
# TODO: setup constants of project
layer_name = 'network_broken'
broken_flds = flds + [new_field]
base_id = 'broken_id'
brfMap = fMap(broken_feat, 19092)
parameters = {'wkt_index': 6, 'fields': broken_flds, 'fMap': brfMap, 'name': layer_name, 'path': None, 'encoding': encoding, 'geom_type': geom_type, 'crs': crs, 'id_column': base_id}
shp_broken = transformer(parameters, transformation_type).result


# TODO: identify duplicates
# TODO: idenify overlaps
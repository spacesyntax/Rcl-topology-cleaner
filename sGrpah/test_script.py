# imports
execfile(u'/Users/joe/Snippets/sGrpah/wktFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/utilityFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/transformer.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/shpFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/sGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/prGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/plFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/generalFunctions.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/fMap.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/dlGraph.py'.encode('utf-8'))
execfile(u'/Users/joe/Snippets/sGrpah/transformer.py'.encode('utf-8'))

from PyQt4.QtCore import QVariant
qgsflds_types = {6: QVariant.Double , 10: QVariant.String}


layer_name = 'nyc_streets_shp'

transformation_type = 'shp_to_pgr'
base_id = 'id_in'
parameters = {'layer_name': layer_name, 'tolerance': 3, 'simplify': True, 'id_column': base_id}
primal_graph = transformer(parameters, transformation_type).result

# test initialise every object of super glass separately and test their methods
any_primal_graph = prGraph(primal_graph, base_id)

transformation_type = 'prflds_to_qgsfields'
base_id = 'id_in'
prflds = any_primal_graph.get_fields()
qgsflds = get_field_types(layer_name, qgsflds_types)
parameters = {'layer_name': layer_name, 'prfields': prflds, 'qgsfields': qgsflds, 'id_column': base_id, 'qvariant_types': qgsflds_types}
flds = transformer(parameters,transformation_type).result


transformation_type = 'prg_to_qf'
parameters = {'prGraph': any_primal_graph, 'id_column': base_id}
base_id = 'id_in'
print any_primal_graph.obj.size()
print any_primal_graph.obj.__len__()
# no fields set up, no fid in the result of the transformation
qf = fMap(transformer(parameters, transformation_type).result, fields, count)


# TODO Add identify invalids and multiparts
# change id columns
# TODO Add change coordinate reference system

# Break at intersections

analysis_type = 'break_at_intersections'
parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify}

primal_graph = read_shp_to_multi_graph(layer_name, tolerance, simplify)

pg = prGraph(primal_graph, id_column)

pg.get_fields()

n = iface.mapCanvas().currentLayer()

make_shp(sg, n.crs())

flds = n.dataProvider().fields()

sg.getfGraph.set_fields(flds)


sg.getfGraph.make_centroids_dict(id_column)

dl = graph_to_dual(sg, False)

dual_to_shp(n.crs(), sg, dl )


x=0

#for comb in find_breakages(sg.features):
#	x+=1

x

new_broken_feat = []
feat_to_del_ids = []
id_column = sg.id_column
features = Features(sg.features).make_feat_dict('feature_id')
attributes = Features(sg.features).make_attr_dict(id_column)
uid = Features(sg.features).fid_to_uid(id_column)
uid_rev = {v: k for k, v in uid.items()}



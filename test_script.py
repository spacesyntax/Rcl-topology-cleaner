
execfile(u'/Users/joe/Rcl-topology-cleaner/sGraph/break_tools.py'.encode('utf-8'))


# _________________________ TRANSFORMATIONS ______________________________

# transform shapefile to primal graph

from PyQt4.QtCore import QVariant
qgsflds_types = {u'Real': QVariant.Double, u'String': QVariant.String}

layer_name = 'london_ax_ex'
#layer_name = 'New scratch layer'
#layer_name = 'Netwrok_small'
#layer_name = 'madagascar'

def getLayerByName(name):
    layer = None
    for i in QgsMapLayerRegistry.instance().mapLayers().values():
        if i.name() == name:
            layer = i
    return layer

# cleaning settings

path = None
tolerance = 6

# project settings
layer = getLayerByName(layer_name)
crs = layer.dataProvider().crs()
encoding = layer.dataProvider().encoding()
geom_type = layer.dataProvider().geometryType()
user_id = 'id'

# break features

br = breakTool(layer, tolerance, user_id, True)
input_geometries = br.geometries
input_fid_to_id = br.fid_to_uid

broken_features, breakages, overlaps, orphans, closed_polylines, self_intersecting, duplicates = br.break_features()

broken_network = br.to_shp(broken_features, crs, 'broken')
QgsMapLayerRegistry.instance().addMapLayer(broken_network)

mrg = mergeTool(broken_features, user_id, True)
all_con, con_1, f_dict, feat_to_copy = mrg.prepare()

result = mrg.merge()


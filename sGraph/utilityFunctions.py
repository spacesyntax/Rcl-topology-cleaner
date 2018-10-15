from qgis.core import QgsFeature, QgsMapLayerRegistry

def copy_feature(prototype_feat, geom, id):
    f = QgsFeature(prototype_feat)
    f.setFeatureId(id)
    f.setGeometry(geom)
    return f

def getLayerByName(name):
    layer = None
    for i in QgsMapLayerRegistry.instance().mapLayers().values():
        if i.name() == name:
            layer = i
    return layer
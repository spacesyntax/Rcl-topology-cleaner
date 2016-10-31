# general imports
from os.path import expanduser

# plugin module imports


# source: ess utility functions


def getLayerByName(name):
    layer = None
    for i in QgsMapLayerRegistry.instance().mapLayers().values():
        if i.name() == name:
            layer = i
    return layer

def copy_shp(temp_layer, path):
    features_to_copy = getAllFeatures(temp_layer)
    provider = temp_layer.dataProvider()
    writer = QgsVectorFileWriter(path, provider.encoding(), provider.fields(), provider.geometryType(), provider.crs(),
                                 "ESRI Shapefile")

    # TODO: push message
    if writer.hasError() != QgsVectorFileWriter.NoError:
        print "Error when creating shapefile: ", writer.errorMessage()

    for fet in features_to_copy.values():
        writer.addFeature(fet)

    del writer
    layer = QgsVectorLayer(path, temp_layer.name(), "ogr")
    return layer

# source: ess utility functions


def getLayerPath4ogr(layer):
    path = ''
    provider = layer.dataProvider()
    provider_type = provider.name()
    # TODO: if provider_type == 'spatialite'
    if provider_type == 'postgres':
        uri = QgsDataSourceURI(provider.dataSourceUri())
        databaseName = uri.database().encode('utf-8')
        databaseServer = uri.host().encode('utf-8')
        databaseUser = uri.username().encode('utf-8')
        databasePW = uri.password().encode('utf-8')
        path = "PG: host=%s dbname=%s user=%s password=%s" % (
            databaseServer, databaseName, databaseUser, databasePW)
    elif provider_type == 'ogr':
        uri = provider.dataSourceUri()
        path = uri.split("|")[0]
    elif provider_type == 'memory':
        # save temp file in home directory
        home = expanduser("~")
        path = home + '/' + layer.name() + '.shp'
        copied_layer = copy_shp(layer, path)
    return path, provider_type


# update unique id column on a network
# limitation: works only with shapefiles
# TODO: add function for postgres provider


def update_unqid(layer_name, attr_column, prfx):
    network = getLayerByName(layer_name)
    pr = network.dataProvider()
    fieldIdx = pr.fields().indexFromName(attr_column)
    if fieldIdx == -1:
        pr.addAttributes([QgsField(attr_column, QVariant.String)])
        fieldIdx = pr.fields().indexFromName(attr_column)
    fid = 0
    updateMap = {}
    for f in network.dataProvider().getFeatures():
        updateMap[f.id()] = {fieldIdx: prfx + '_' + str(fid)}
        fid += 1
    pr.changeAttributeValues(updateMap)
    return network


def getAllFeatures(layer):
    allfeatures = {}
    if layer:
        features = layer.getFeatures()
        allfeatures = {feature.id(): feature for feature in features}
    return allfeatures


def add_column(v_layer, col_name, col_type):
    pr = v_layer.dataProvider()
    v_layer.startEditing()
    pr.addAttributes([QgsField(col_name, col_type)])
    v_layer.commitChanges()

def add_field_to_fields(fields,field_name,field_type):
    return [QgsField(fld.name,fld.type) for fld in fields] + [QgsField(field_name,field_type)]



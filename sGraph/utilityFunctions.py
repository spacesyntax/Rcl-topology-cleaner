import collections
import math
from collections import defaultdict

# FEATURES -----------------------------------------------------------------

# detecting errors:
# (NULL), point, (invalids), multipart geometries, snap (will be added later)
points = []
multiparts = []
def clean_features_iter(layer, snap):
    id = 0
    for f in layer.getFeatures():

        # dropZValue if geometry is 3D
        if f.geometry().geometry().is3D():
                f.geometry().geometry().dropZValue()

        f_geom = f.geometry()

        # point
        if f_geom.length() <= 0:
            points.append(f_geom.asPoint())
        # short line (when snap != -1)
        elif f_geom.wkbType() == 2:
            # if self.Snap == -1 never valid
            f.setFeatureId(id)
            id += 1
            if f_geom.length() > snap: # do not add as error, it will be added later
                yield f
        # empty geometry
        elif f_geom is NULL:
            #self.empty_geometries.append()
            pass
        # invalid geometry
        elif not f_geom.isGeosValid():
            #self.invalids.append(copy_feature(f, QgsGeometry(), f.id()))
            pass
        # multilinestring
        elif f_geom.wkbType() == 5:
            ml_segms = f_geom.asMultiPolyline()
            for ml in ml_segms:
                ml_geom = QgsGeometry(ml)
                # if self.Snap == -1 never valid
                if ml_geom.length() > snap:  # do not add as error, it will be added later
                    ml_feat = QgsFeature(f)
                    ml_feat.setFeatureId(id)
                    id += 1
                    ml_feat.setGeometry(ml_geom)
                    multiparts.append(ml_geom.asPolyline()[0])
                    multiparts.append(ml_geom.asPolyline()[-1])
                    yield ml_feat

# GEOMETRY -----------------------------------------------------------------

def getSelfIntersections(polyline):
    return [item for item, count in collections.Counter(polyline).items() if count > 1] # points


def find_vertex_indices(polyline, points):
    indices = defaultdict(list)
    for idx, vertex in enumerate(polyline):
        indices[vertex].append(idx)
    break_indices = [indices[v] for v in set(points)] + [[0, (len(polyline) - 1)]]
    break_indices = [item for sublist in break_indices for item in sublist]
    return sorted(list(set(break_indices)))


def break_feat(polyline, vertices_indices):
    vertices_indices = sorted(vertices_indices)
    for start, end in zip(vertices_indices[:-1], vertices_indices[1:]):
        yield start, end

# ITERATORS -----------------------------------------------------------------

# connected components iterator from group_dictionary e.g. { A: [B,C,D], B: [D,E,F], ...}
def con_comp_iter(group_dictionary):
    components_passed = set([])
    for id in group_dictionary.keys():
        if {id}.isdisjoint(components_passed):
            group = [[id]]
            candidates = ['dummy', 'dummy']
            while len(candidates) > 0:
                flat_group = group[:-1] + group[-1]
                candidates = map(lambda last_visited_node: set(group_dictionary[last_visited_node]).difference(set(flat_group)), group[-1])
                candidates = list(set(itertools.chain.from_iterable(candidates)))
                group = flat_group + [candidates]
                components_passed.update(set(candidates))
            yield group[:-1]

# WRITE -----------------------------------------------------------------

def to_layer(features, crs, encoding, geom_type, layer_type, path, name):

    first_feat = features[0]
    fields = first_feat.fields()
    layer = None
    if layer_type == 'memory':
        geom_types = {1: 'Point', 2: 'Linestring', 3:'Polygon'}
        layer = QgsVectorLayer(geom_types[geom_type] + '?crs=' + crs.authid(), name, "memory")
        pr = layer.dataProvider()
        pr.addAttributes(fields.toList())
        layer.updateFields()
        layer.startEditing()
        pr.addFeatures(features)
        layer.commitChanges()

    elif layer_type == 'shapefile':
        file_writer = QgsVectorFileWriter(path, encoding, fields, geom_type, crs, "ESRI Shapefile")
        print path, encoding, fields, geom_type, crs
        if file_writer.hasError() != QgsVectorFileWriter.NoError:
            print "Error when creating shapefile: ", file_writer.errorMessage()
        del file_writer
        # TODO: get name from path
        layer = QgsVectorLayer(path, name, "ogr")
        pr = layer.dataProvider()
        layer.startEditing()
        pr.addFeatures(features)
        layer.commitChanges()

    return layer


# LAYER -----------------------------------------------------------------

def getLayerByName(name):
    layer = None
    for i in QgsMapLayerRegistry.instance().mapLayers().values():
        if i.name() == name:
            layer = i
    return layer
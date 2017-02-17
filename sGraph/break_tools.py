
# general imports
from qgis.core import QgsFeature, QgsGeometry, QgsSpatialIndex, QgsPoint, QgsVectorFileWriter, QgsField
from PyQt4.QtCore import QObject, pyqtSignal, QVariant

# plugin module imports
from utilityFunctions import *

class breakTool(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)

    def __init__(self,layer, tolerance, uid, errors):
        QObject.__init__(self)
        self.layer = layer
        self.feat_count = self.layer.featureCount()
        self.tolerance = tolerance
        self.uid = uid

        self.errors = errors
        self.multiparts = []
        self.points = []
        self.invalids = []

        self.features = []
        self.attributes = {}
        self.geometries = {}
        self.geometries_wkt = {}
        self.geometries_vertices = {}
        # create spatial index object
        self.spIndex = QgsSpatialIndex()
        self.layer_fields = [QgsField(i.name(), i.type()) for i in self.layer.dataProvider().fields()]
        if self.uid is not None:
            self.uid_index = [index for index,field in enumerate(self.layer_fields) if field.name() == self.uid].pop()
        self.fid_to_uid = {}
        self.uid_to_fid = {}
        new_key_count = 0
        f_count = 1
        for f in self.layer.getFeatures():

            self.progress.emit(45 * f_count / self.feat_count)
            f_count += 1

            attr = f.attributes()
            if f.geometry().wkbType() == 5 :
                attr = f.attributes()
                if self.errors and self.uid is not None:
                    self.multiparts.append(attr[self.uid_index])
                    self.uid_to_fid[attr[self.uid_index]] = f.id()
                for multipart in f.geometry().asGeometryCollection():
                    new_key_count += 1
                    if self.uid is not None:
                        self.fid_to_uid[new_key_count] = attr[self.uid_index]
                    attr = f.attributes()
                    new_feat = QgsFeature()
                    new_feat.setAttributes(attr)
                    new_feat.setFeatureId(new_key_count)
                    if self.tolerance:
                        snapped_wkt = make_snapped_wkt(multipart.exportToWkt(), self.tolerance)
                    else:
                        snapped_wkt = multipart.exportToWkt()
                    snapped_geom = QgsGeometry.fromWkt(snapped_wkt)
                    new_feat.setGeometry(snapped_geom)
                    self.features.append(new_feat)
                    self.attributes[new_key_count] = attr
                    self.geometries[new_key_count] = new_feat.geometryAndOwnership()
                    self.geometries_wkt[new_key_count] = snapped_wkt
                    self.geometries_vertices[new_key_count] = [vertex for vertex in vertices_from_wkt_2(snapped_wkt)]
                    # insert features to index
                    self.spIndex.insertFeature(new_feat)
            elif f.geometry().wkbType() == 1:
                if self.errors and self.uid is not None:
                    self.points.append(attr[self.uid_index])
            elif not f.geometry().isGeosValid():
                if self.errors and self.uid is not None:
                    self.invalids.append(attr[self.uid_index])
            elif f.geometry().wkbType() == 2:
                attr = f.attributes()
                if self.tolerance:
                    snapped_wkt = make_snapped_wkt(f.geometry().exportToWkt(), self.tolerance)
                else:
                    snapped_wkt = f.geometry().exportToWkt()
                snapped_geom = QgsGeometry.fromWkt(snapped_wkt)
                f.setGeometry(snapped_geom)
                new_key_count += 1
                f.setFeatureId(new_key_count)
                self.features.append(f)
                self.attributes[f.id()] = attr
                self.geometries[f.id()] = f.geometryAndOwnership()
                self.geometries_wkt[f.id()] = snapped_wkt
                self.geometries_vertices[f.id()] = [vertex for vertex in vertices_from_wkt_2(snapped_wkt)]
                # insert features to index
                self.spIndex.insertFeature(f)
                if self.uid is not None:
                    self.fid_to_uid[f.id()] = attr[self.uid_index]
                    self.uid_to_fid[attr[self.uid_index]] = f.id()

    def break_features(self):

        broken_features = []

        f_count = 1

        breakages = []
        overlaps = []
        orphans = []
        closed_polylines = []
        self_intersecting = []
        duplicates = []

        for fid in self.geometries.keys():

            f_geom = self.geometries[fid]
            f_attrs = self.attributes[fid]

            # intersecting lines
            gids = self.spIndex.intersects(f_geom.boundingBox())

            self.progress.emit((45 * f_count / self.feat_count) + 5)
            f_count += 1

            f_errors, vertices = self.find_breakages(fid, gids)

            if self.errors is True:
                if f_errors == ['br', 'ovrlp']:
                    breakages.append(self.fid_to_uid[fid])
                    overlaps.append(self.fid_to_uid[fid])
                elif f_errors == 'br':
                    breakages.append(self.fid_to_uid[fid])
                elif f_errors == 'ovrlp':
                    overlaps.append(self.fid_to_uid[fid])
                elif f_errors == 'orphan':
                    orphans.append(self.fid_to_uid[fid])
                elif f_errors == 'closed polyline':
                    closed_polylines.append(self.fid_to_uid[fid])
                elif f_errors == 'duplicate':
                    duplicates.append(self.fid_to_uid[fid])

            if f_errors is None:
                vertices = [0, len(f_geom.asPolyline()) - 1 ]

            if f_errors in [['br', 'ovrlp'], 'br', 'ovrlp', None]:
                for ind, index in enumerate(vertices):
                    if ind != len(vertices) - 1:
                        points = [self.geometries_vertices[fid][i] for i in range(index, vertices[ind + 1] + 1)]
                        p = ''
                        for point in points:
                            p += point[0] + ' ' + point[1] + ', '
                        wkt = 'LINESTRING(' + p[:-2] + ')'
                        self.feat_count += 1
                        new_fid = self.feat_count
                        new_feat = [new_fid, f_attrs, wkt]
                        broken_features.append(new_feat)

        return broken_features, breakages, overlaps, orphans, closed_polylines, self_intersecting, duplicates

    def find_breakages(self, fid, gids):

        f_geom = self.geometries[fid]

        # errors checks
        must_break = False
        is_closed = False
        if f_geom.asPolyline()[0] == f_geom.asPolyline()[-1]:
            is_closed = True
        is_orphan = True
        is_duplicate = False
        has_overlaps = False

        # get breaking points
        breakages = []

        # is self intersecting
        is_self_intersersecting = False
        for i in f_geom.asPolyline():
            if f_geom.asPolyline().count(i) > 1:
                point = QgsGeometry().fromPoint(QgsPoint(i[0], i[1]))
                breakages.append(point)
                is_self_intersersecting = True
                must_break = True

        for gid in gids:

            g_geom = self.geometries[gid]

            if gid < fid:
                # duplicate geometry
                if f_geom.isGeosEqual(g_geom):
                    is_duplicate = True
                    #break

            if is_duplicate is False:
                intersection = f_geom.intersection(g_geom)
                # intersecting geometries at point
                if intersection.wkbType() == 1 and point_is_vertex(intersection, f_geom):
                    breakages.append(intersection)
                    is_orphan = False
                    must_break = True

                # intersecting geometries at multiple points
                elif intersection.wkbType() == 4:
                    for point in intersection.asGeometryCollection():
                        if point_is_vertex(point, f_geom):
                            breakages.append(point)
                            is_orphan = False
                            must_break = True

                # overalpping geometries
                elif intersection.wkbType() == 2 and intersection.length() != f_geom.length():
                    point1 = QgsGeometry.fromPoint(QgsPoint(intersection.asPolyline()[0]))
                    point2 = QgsGeometry.fromPoint(QgsPoint(intersection.asPolyline()[-1]))
                    if point_is_vertex(point1, f_geom):
                        breakages.append(point1)
                        is_orphan = False
                        must_break = True
                    if point_is_vertex(point2, f_geom):
                        breakages.append(point2)
                        is_orphan = False
                        must_break = True

                # overalpping multi-geometries
                # every feature overlaps with itself as a multilinestring
                elif intersection.wkbType() == 5 and intersection.length() != f_geom.length():
                    point1 = QgsGeometry.fromPoint(QgsPoint(intersection.asGeometryCollection()[0].asPolyline()[0]))
                    point2 = QgsGeometry.fromPoint(QgsPoint(intersection.asGeometryCollection()[-1].asPolyline()[-1]))
                    if point_is_vertex(point1, f_geom):
                        is_orphan = False
                        has_overlaps = True
                        breakages.append(point1)
                    if point_is_vertex(point2, f_geom):
                        is_orphan = False
                        has_overlaps = True
                        breakages.append(point2)

        if is_duplicate is True:
            return 'duplicate', []
        else:
            # add first and last vertex
            vertices = set([vertex for vertex in find_vertex_index(breakages, f_geom)])
            vertices = list(vertices) + [0] + [len(f_geom.asPolyline()) - 1]
            vertices = list(set(vertices))
            vertices.sort()
            if is_orphan:
                if is_closed is True:
                    return 'closed polyline', []
                else:
                    return 'orphan', []
            elif is_self_intersersecting:
                if has_overlaps:
                    return ['br', 'ovrlp'], vertices
                else:
                    return 'br', vertices
            elif has_overlaps or must_break:
                if has_overlaps is True and must_break is True:
                    return ['br', 'ovrlp'], vertices
                elif has_overlaps is True and must_break is False:
                    return 'ovrlp', vertices
                elif has_overlaps is False and must_break is True:
                    if len(vertices) > 2:
                        return 'br', vertices
                    else:
                        return None, []
                else:
                    return None, []
            else:
                return None, []



    def to_shp(self, any_features_list, crs, name ):
        network = QgsVectorLayer('LineString?crs=' + crs.toWkt(), name, "memory")
        pr = network.dataProvider()

        pr.addAttributes(self.layer_fields)

        new_features = []

        for i in any_features_list:
            new_feat = QgsFeature()
            new_feat.setFeatureId(i[0])
            new_feat.setAttributes(i[1])
            new_feat.setGeometry(QgsGeometry.fromWkt(i[2]))
            new_features.append(new_feat)

        network.startEditing()
        pr.addFeatures(new_features)
        network.commitChanges()
        return network


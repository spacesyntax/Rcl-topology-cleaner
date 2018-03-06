
# general imports
from PyQt4.QtCore import QObject, pyqtSignal, QVariant
from qgis.core import QgsGeometry, QgsSpatialIndex, QgsField, QgsDistanceArea, QgsFeature

# plugin module imports
try:
    from utilityFunctions import *
except ImportError:
    pass

class breakTool(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)
    killed = pyqtSignal(bool)

    #TODO:
    def __init__(self, linksFields):
        QObject.__init__(self)
        self.links = {} # id: feat
        self.nodes = {} # id: feat
        self.nodesMemory = {} # xy: id
        self.linksMemory = {} # (node_id, node_id): [link_id1, ...]  - excluding duplicates

        # fields
        self.linksFields = linksFields # list of QGgsfield objects
        self.linksFields.append(QgsField('original_id', QVariant.Int)) # TODO what if attr already in fields ?

        # spatial indices
        self.linksSpIndex = QgsSpatialIndex()
        self.ndSpIndex = QgsSpatialIndex()
        self.shortSpIndex = QgsSpatialIndex()

        # feature counter
        self.linksCounter = 0
        self.nodesCounter = 0

        # errors
        self.shortLinks = {}
        self.points = {}
        self.invalids = {}
        self.mlstrings = {}
        self.duplicates = {}
        self.empty = {}
        self.breakages = set([])
        self.orphans = {}
        self.overlaps = {}

    def add_nodes(self, f_nodes):
        node_ids = []
        for nd in f_nodes:
            try:
                ex_node_id = self.nodesMemory[nd]
                node_ids.append(ex_node_id)
            except KeyError:
                self.nodesCounter += 1
                nd_f = QgsFeature()
                nd_f.setFeatureId(self.nodesCounter)
                nd_f.setGeometry(QgsGeometry.fromPoint(nd))
                nd_f.setAttributes([self.nodesCounter])
                self.nodesMemory[nd] = self.nodesCounter
                self.nodes[self.nodesCounter] = nd_f
                self.ndSpIndex.insertFeature(nd_f)
                node_ids.append(self.nodesCounter)
        return node_ids

    def check_for_duplicate(self, node_ids, f_geom, f_id, f):
        try:  # if duplicate
            dummy = self.linksMemory[frozenset(node_ids)]
            if f_geom.isGeosEqual(self.links[dummy].geometry()):
                self.duplicates[f_id] = f
            else:
                dummy = self.linksMemory['invalid_key']
        except KeyError:
            self.linksMemory[frozenset(node_ids)] = self.linksCounter

        return

    def add_links(self, feat_iter, feat_count, simpl_threshold):

        f_count = 1

        for f in feat_iter:

            self.progress.emit(30 * f_count / feat_count)
            f_count += 1

            if self.killed is True: break

            # geometry and attributes
            f_geom = f.geometry()
            f_id = f.id()

            #f_geom.geometry().dropZValue() # drop 3rd dimension # if f_geom.geometry().is3D(): # geom_type not in [5, 2, 1]

            # linestrings
            if f_geom.wkbType() == 2:
                self.linksCounter += 1
                f.setFeatureId(self.linksCounter)
                f_pl = f_geom.asPolyline()
                f_nodes = {f_pl[0], f_pl[-1]}
                node_ids = self.add_nodes(f_nodes)
                self.check_for_duplicate(node_ids, f_geom, f_id, f)
                f_copy = QgsFeature(f)
                f_copy.setFeatureId(self.linksCounter)
                if simpl_threshold:
                    f_geom = f_geom.simplify(simpl_threshold)
                f_copy.setGeometry(f_geom)
                f_copy.setFields(self.linksFields)
                f_copy['original_id'] = f_id
                self.links[self.linksCounter] = f
                self.linksSpIndex.insertFeature(f)
            # multilinestrings
            elif f_geom.wkbType() == 4:
                self.mlstrings[f_id] = f
                for f_geom_part in f_geom.asMultiPolyline():
                    self.linksCounter += 1
                    f_nodes = {f_geom_part[0].asPoint(), f_geom_part[-1].asPoint()}
                    node_ids = self.add_nodes(f_nodes)
                    self.check_for_duplicate(node_ids, f_geom, f_id, f)
                    f_copy = QgsFeature(f)
                    f_copy.setFeatureId(self.linksCounter)
                    if simpl_threshold:
                        f_geom_part = f_geom_part.simplify(simpl_threshold)
                    f_copy.setGeometry(f_geom_part)
                    f_copy.setFields(self.linksFields)
                    f_copy['original_id'] = f_id
                    self.links[self.linksCounter] = f
                    self.linksSpIndex.insertFeature(f)
            # points
            elif f_geom.wkbType() == 1 or f_geom.length() == 0:  # TODO test 2nd condition
                self.points[f_id] = f
            # invalids
            elif not f_geom.isGeosValid():
                self.invalids[f_id] = f
            # empty geometries
            elif f_geom.isEmpty() or f_geom is NULL:
                self.empty[f_id] = f

        return

    def add_short_links(self, snap_threshold):
        for nd_id, nd_f in self.nodes.items():
            # buffer radar
            node_geom = nd_f.geometry()
            radar_geom = node_geom.buffer(snap_threshold, 25)

            # search if another node within snap_threshold
            closest_nodes = self.ndSpIndex.intersects(radar_geom.boundingBox())
            closest_nodes = [nd for nd in closest_nodes if self.nodes[nd].geometry().intersects(radar_geom)
                                    and nd != nd_id]
            closest_nodes = [nd for nd in closest_nodes if self.nodes[nd].geometry().distance(node_geom) != 0]

            if len(closest_nodes) > 0:

                # to ensure no duplicates are created
                closest_nodes = [nd for nd in closest_nodes if nd_id > nd]

                for node in closest_nodes:
                    # if edge not exists
                    try:
                        ex_link = self.linksMemory[frozenset({nd_id, node})]
                    except KeyError: # no check for duplicates needed - no action to add node is needed - nodes exist
                        shortest_geom = node_geom.shortestLine(self.nodes[node].geometry())
                        self.linksCounter += 1
                        f = QgsFeature()
                        f.setFeatureId(self.linksCounter)
                        f.setGeometry(shortest_geom)
                        f.setFields(self.linksFields)
                        f.setAttributes([NULL for i in self.linksFields])
                        self.shortLinks[self.linksCounter] = f
                        self.shortSpIndex.insertFeature(f)
            # search if another edge within snap_threshold
            else:
                closest_links = self.linksSpIndex.intersects(radar_geom.boundingBox())
                closest_links = [link for link in closest_links if self.links[link].geometry().intersects(radar_geom)]
                closest_links = [link for link in closest_links if self.links[link].geometry().distance(node_geom) != 0]
                for link in closest_links:
                    shortest_geom = self.links[link].geometry().shortestLine(nd_f.geometry())
                    self.linksCounter += 1
                    f = QgsFeature()
                    f.setFeatureId(self.linksCounter)
                    f.setGeometry(shortest_geom)
                    f.setFields(self.linksFields)
                    f.setAttributes([NULL for i in self.linksFields])
                    self.shortLinks[self.linksCounter] = f
                    self.shortSpIndex.insertFeature(f)
        return

    def get_breakages(self, link,  link_id, only_short=False):

        link_geom = link.geometry()
        link_geom_pl = link_geom.asPolyline()
        candidate_points = []  # list of QgsPoints
        intersecting_vertices = []

        # intersecting lines
        if only_short:
            gids = []
        else:
            gids = self.linksSpIndex.intersects(link_geom.boundingBox())
            gids.remove(link_id)

        # filter intersections
        for gid in gids:
            g_geom = self.links[gid].geometry()
            intersection = link_geom.intersection(g_geom)
            # multipoint
            if intersection.wkbType() == 4:
                candidate_points.extend(intersection.asMultiPoint())
            # point
            elif intersection.wkbType() == 1:
                candidate_points.append(intersection.asPoint())
            # line - overlaps
            elif intersection.wkbType() == 2:
                self.overlaps[link_id] = link
                inter_pl = intersection.asPolyline()
                candidate_points.extend([inter_pl[0], inter_pl[-1]])
            # multiline - overlaps
            elif intersection.wkbType() == 5:
                self.overlaps[link_id] = link
                inter_ml_pl = intersection.asMultiPolyline()
                candidate_points.extend([inter_ml_pl[0][0], inter_ml_pl[-1][-1]])

        # intersecting short lines

        gids = self.shortSpIndex.intersects(link_geom.boundingBox())
        for gid in gids:
            g_geom = self.shortLinks[gid].geometry()
            intersection = link_geom.intersection(g_geom)
            try:
                nd = intersection.asPoint()
                # add vertex to link geom
                # check if point is vertex
                if point_is_vertex(nd, link_geom):
                    intersecting_vertices.append(nd)
                else:
                    (closest_point, atVertex, befVertex, afterVertex, dist) = link_geom.closestVertex(nd)
                    if befVertex == -1:
                        befVertex = len(link_geom_pl) - 1
                    bool = link_geom.insertVertex(nd.x(), nd.y(), befVertex)
                    #print bool, link_id
                    del closest_point, atVertex, afterVertex, dist
                    intersecting_vertices.append(nd)
                    # update link and copy geom otherwise C++ error object has been deleted
                    link_geom = QgsGeometry(link_geom)
                    link_geom_pl = link_geom.asPolyline()
                    self.links[link_id].setGeometry(link_geom)
            except AttributeError:
                pass

        # filter only sharing vertices
        for point in candidate_points:
            if point_is_vertex(point, link_geom):
                intersecting_vertices.append(point)

        # check if self intersects
        self_intersections = self_intersects(link_geom_pl)
        if len(intersecting_vertices) > 0:
            intersecting_vertices.extend(self_intersections)
            self.breakages.update(set(intersecting_vertices))
            intersecting_vertices = list(set([0, len(link_geom_pl) - 1] + [link_geom_pl.index(x) for x in intersecting_vertices]))
            intersecting_vertices.sort()
        # check if is orphan (can be closed polyline - self intersects)
        else:
            self.orphans[link_id] = link

        return intersecting_vertices, self_intersections

    def break_links(self, only_short=False):

        broken_features = []
        f_count = 1

        # TODO what if attr already in fields?
        self.linksFields.append(QgsField('broken_id', QVariant.Int))
        broken_counter = 0

        for link_id, link in self.links.items():

            if self.killed is True: break
            self.progress.emit((60 * f_count / max(self.links.keys())) + 30)
            f_count += 1
            link_geom = link.geometry()
            link_geom_pl = link_geom.asPolyline()
            intersecting_vertices, self_intersections = self.get_breakages(link, link_id, only_short)

            if len(intersecting_vertices) == 2:  # and len(self_intersections) == 0

                # copy feature

                broken_counter += 1

                link_copy = QgsFeature(link)
                link_copy.setFields(self.linksFields)
                link_copy['broken_id'] = broken_counter
                broken_features.append(link_copy)

            elif len(intersecting_vertices) > 2:
                # print intersecting_vertices

                # if no crossing points
                for i, vrtx_idx in enumerate(intersecting_vertices[1:]):
                    new_geom = QgsGeometry.fromPolyline(link_geom_pl[intersecting_vertices[i]:vrtx_idx])
                    # new_feat
                    broken_counter += 1

                    broken_feat = QgsFeature(link)
                    broken_feat.setGeometry(new_geom)
                    broken_feat.setFeatureId(broken_counter)
                    broken_feat.setFields(self.linksFields)
                    broken_feat['broken_id'] = broken_counter
                    broken_features.append(broken_feat)

        return broken_features

    def kill(self):
        self.killed = True

# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RoadNetworkCleaner
                                 A QGIS plugin
 This plugin clean a road centre line map.
                              -------------------
        begin                : 2016-11-10
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Space SyntaxLtd
        email                : i.kolovou@spacesyntax.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import traceback
from PyQt4.QtCore import QThread, QSettings, QObject, pyqtSignal, QVariant
from qgis.core import *
from qgis.gui import *
from qgis.utils import *

from road_network_cleaner_dialog import RoadNetworkCleanerDialog
from sGraph.clean_tool import *  # better give these a name to make it explicit to which module the methods belong
from sGraph.utilityFunctions import *

# Import the debug library - required for the cleaning class in separate thread
# set is_debug to False in release version
is_debug = False
try:
    import pydevd
    has_pydevd = True
except ImportError, e:
    has_pydevd = False
    is_debug = False


class NetworkCleanerTool(QObject):

    # initialise class with self and iface
    def __init__(self, iface):
        QObject.__init__(self)

        self.iface=iface
        self.legend = self.iface.legendInterface()

        # load the dialog from the run method otherwise the objects gets created multiple times
        self.dlg = None

        # some globals
        self.cleaning = None
        self.thread = None

    def loadGUI(self):
        # create the dialog objects
        self.dlg = RoadNetworkCleanerDialog(self.getQGISDbs())

        # setup GUI signals
        self.dlg.closingPlugin.connect(self.unloadGUI)
        self.dlg.cleanButton.clicked.connect(self.startWorker)
        self.dlg.cancelButton.clicked.connect(self.killWorker)

        # add layers to dialog
        self.updateLayers()

        self.dlg.outputCleaned.setText(self.dlg.inputCombo.currentText() + "_cl")
        self.dlg.inputCombo.currentIndexChanged.connect(self.updateOutputName)

        # setup legend interface signals
        self.legend.itemAdded.connect(self.updateLayers)
        self.legend.itemRemoved.connect(self.updateLayers)

        self.settings = None

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

    def unloadGUI(self):
        if self.dlg:
            self.dlg.closingPlugin.disconnect(self.unloadGUI)
            self.dlg.cleanButton.clicked.disconnect(self.startWorker)
            self.dlg.cancelButton.clicked.disconnect(self.killWorker)
            self.settings = None
        self.legend.itemAdded.disconnect(self.updateLayers)
        self.legend.itemRemoved.disconnect(self.updateLayers)

        self.dlg = None

    def getQGISDbs(self):
        """Return all PostGIS connection settings stored in QGIS
        :return: connection dict() with name and other settings
        """
        settings = QSettings()
        settings.beginGroup('/PostgreSQL/connections')
        named_dbs = settings.childGroups()
        all_info = [i.split("/") + [unicode(settings.value(i))] for i in settings.allKeys() if
                    settings.value(i) != NULL and settings.value(i) != '']
        all_info = [i for i in all_info if
                    i[0] in named_dbs and i[2] != NULL and i[1] in ['name', 'host', 'service', 'password', 'username',
                                                                    'port']]
        dbs = dict(
            [k, dict([i[1:] for i in list(g)])] for k, g in itertools.groupby(sorted(all_info), operator.itemgetter(0)))
        settings.endGroup()
        return dbs

    def getActiveLayers(self):
        layers_list = []
        for layer in self.iface.legendInterface().layers():
            if layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
                if layer.hasGeometryType() and (layer.geometryType() == 1):
                    layers_list.append(layer.name())
        return layers_list

    def updateLayers(self):
        layers = self.getActiveLayers()
        self.dlg.popActiveLayers(layers)

    # SOURCE: Network Segmenter https://github.com/OpenDigitalWorks/NetworkSegmenter
    # SOURCE: https://snorfalorpagus.net/blog/2013/12/07/multithreading-in-qgis-python-plugins/

    def updateOutputName(self):
        self.dlg.outputCleaned.setText(self.dlg.inputCombo.currentText() + "_cl")

    def giveMessage(self, message, level):
        # Gives warning according to message
        self.iface.messageBar().pushMessage("Road network cleaner: ", "%s" % (message), level, duration=5)

    def workerError(self, exception_string):
        # Gives error according to message
        QgsMessageLog.logMessage('Cleaning thread raised an exception: %s' % exception_string, level=QgsMessageLog.CRITICAL)
        self.dlg.close()

    def startWorker(self):
        self.dlg.cleaningProgress.reset()
        self.settings = self.dlg.get_settings()
        if self.settings['output_type'] == 'postgis':
            db_settings = self.dlg.get_dbsettings()
            self.settings.update(db_settings)

        if self.settings['input']:

            cleaning = self.Worker(self.settings, self.iface)
            print self.settings
            # start the cleaning in a new thread
            thread = QThread()
            cleaning.moveToThread(thread)
            cleaning.finished.connect(self.workerFinished)
            cleaning.error.connect(self.workerError)
            cleaning.warning.connect(self.giveMessage)
            cleaning.cl_progress.connect(self.dlg.cleaningProgress.setValue)

            thread.started.connect(cleaning.run)

            thread.start()

            self.thread = thread
            self.cleaning = cleaning

            #if is_debug:
            print 'started'
        else:
            self.giveMessage('Missing user input!', QgsMessageBar.INFO)
            return

    def workerFinished(self, ret):
        #if is_debug:
        print 'trying to finish'
        # get cleaning settings
        layer_name = self.settings['input']
        path = self.settings['output']
        output_type = self.settings['output_type']
        if output_type == 'postgis':
            (dbname, schema_name, table_name) = path.split(':')
            path = (self.dlg.dbsettings_dlg.connstring, schema_name, table_name)
        #  get settings from layer
        layer = getLayerByName(layer_name)

        if self.cleaning:
            # clean up the worker and thread
            self.cleaning.finished.disconnect(self.workerFinished)
            self.cleaning.error.disconnect(self.workerError)
            self.cleaning.warning.disconnect(self.giveMessage)
            self.cleaning.cl_progress.disconnect(self.dlg.cleaningProgress.setValue)

        # clean up the worker and thread
        self.thread.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()

        if ret:

            cleaned_features, errors, unlinks = ret
            cleaned = to_layer(cleaned_features, layer.crs(), layer.dataProvider().encoding(),
                                 layer.dataProvider().geometryType(), output_type, path,
                                 layer_name + '_cl')
            QgsMapLayerRegistry.instance().addMapLayer(cleaned)
            cleaned.updateExtents()
            if self.settings['errors']:
                errors = to_layer(errors, layer.crs(), layer.dataProvider().encoding(), 1, output_type,
                                  (path[0], path[1], path[2] + "_cl_errors"), path[2] + "_cl_errors")
                QgsMapLayerRegistry.instance().addMapLayer(errors)

            if self.settings['unlinks']:
                unlinks = to_layer(unlinks, layer.crs(), layer.dataProvider().encoding(), 1, output_type,
                                  (path[0], path[1], path[2] + "_u"), path[2] + "_u")
                QgsMapLayerRegistry.instance().addMapLayer(unlinks)

            self.giveMessage('Process ended successfully!', QgsMessageBar.INFO)

        else:
            # notify the user that sth went wrong
            self.giveMessage('Something went wrong! See the message log for more information', QgsMessageBar.CRITICAL)


        if is_debug: print 'thread running ', self.thread.isRunning()
        if is_debug: print 'has finished ', self.thread.isFinished()

        self.thread = None
        self.cleaning = None

        if self.dlg:
            self.dlg.cleaningProgress.reset()
            self.dlg.close()

    def killWorker(self):
        if is_debug: print 'trying to cancel'
        # add emit signal to breakTool or mergeTool only to stop the loop
        if self.cleaning:
            # Disconnect signals
            self.cleaning.finished.disconnect(self.workerFinished)
            self.cleaning.error.disconnect(self.workerError)
            self.cleaning.warning.disconnect(self.giveMessage)
            self.cleaning.cl_progress.disconnect(self.dlg.cleaningProgress.setValue)
            try: # it might not have been connected already
                self.cleaning.progress.disconnect(self.dlg.cleaningProgress.setValue)
            except TypeError:
                pass
            # Clean up thread and analysis
            self.cleaning.kill()
            self.cleaning.clean_tool.kill()
            self.cleaning.deleteLater()
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
            self.cleaning = None
            self.dlg.cleaningProgress.reset()
            self.dlg.close()
        else:
            self.dlg.close()


    # SOURCE: https://snorfalorpagus.net/blog/2013/12/07/multithreading-in-qgis-python-plugins/
    class Worker(QObject):

        # Setup signals
        finished = pyqtSignal(object)
        error = pyqtSignal(Exception, basestring)
        cl_progress = pyqtSignal(float)
        warning = pyqtSignal(str)
        cl_killed = pyqtSignal(bool)

        def __init__(self, settings, iface):
            QObject.__init__(self)
            self.settings = settings
            self.cl_killed = False
            self.iface = iface
            self.clean_tool = None

        def run(self):
            if has_pydevd and is_debug:
                pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True, suspend=False)
            ret = None
            if self.settings:
                try:
                    # cleaning settings
                    layer_name = self.settings['input']
                    layer = getLayerByName(layer_name)
                    Snap = self.settings['snap']
                    Break = self.settings['break']
                    # Merge = 'between intersections'
                    Merge = self.settings['merge']
                    Orphans = self.settings['orphans']

                    Errors = self.settings['errors']
                    Unlinks = self.settings['unlinks']

                    self.clean_tool = cleanTool(Snap, Break, Merge, Errors, Unlinks, Orphans)
                    self.cl_progress.emit(0)
                    self.clean_tool.progress.connect(self.cl_progress.emit)

                    # 0. LOAD GRAPH # errors: points, invalids, null, multiparts
                    self.clean_tool.step = self.clean_tool.range/ float(layer.featureCount())

                    res = map(lambda f: self.clean_tool.sEdgesSpIndex.insertFeature(f), self.clean_tool.features_iter(layer))

                    # 1. BREAK AT COMMON VERTICES # errors: duplicates, broken, self_intersecting (overlapping detected as broken)
                    if self.clean_tool.Break:
                        print 'break'
                        self.clean_tool.step = self.clean_tool.range / float(len(self.clean_tool.sEdges))
                        broken_edges = map(lambda (sedge, vertices): self.clean_tool.breakAtVertices(sedge, vertices),
                                           self.clean_tool.breakFeaturesIter())
                        res = map(lambda edge_id: self.clean_tool.del_edge(edge_id), filter(lambda edge_id: edge_id is not None, broken_edges))

                    # 2. SNAP # errors: snapped
                    self.clean_tool.step = self.clean_tool.range/ float(len(self.clean_tool.sEdges))
                    res = map(lambda (edgeid, qgspoint): self.clean_tool.createTopology(qgspoint, edgeid), self.clean_tool.endpointsIter())
                    if self.clean_tool.Snap != -1:
                        # group based on distance - create subgraph
                        self.clean_tool.step = (self.clean_tool.range/ float(len(self.clean_tool.sNodes))) / float(2)
                        subgraph_nodes = self.clean_tool.subgraph_nodes()
                        self.clean_tool.step = (self.clean_tool.range/ float(len(subgraph_nodes))) / float(2)
                        res = map(lambda nodes: self.clean_tool.mergeNodes(nodes), self.clean_tool.con_comp_iter(subgraph_nodes))

                    # 3. MERGE # errors merged
                    if self.clean_tool.Merge:
                        if self.clean_tool.Merge == 'between_intersections':
                            self.clean_tool.step = (self.clean_tool.range / float(len(self.clean_tool.sNodes))) / float(2)
                            subgraph_nodes = self.clean_tool.subgraph_con2_nodes()
                            self.clean_tool.step = (self.clean_tool.range / float(len(subgraph_nodes))) / float(2)
                            res = map(lambda group_edges: self.clean_tool.merge_edges(group_edges),
                                      self.clean_tool.con_comp_iter(subgraph_nodes))
                        elif self.clean_tool.Merge[0] == 'collinear':
                            self.clean_tool.step = (self.clean_tool.range / float(len(self.clean_tool.sNodes))) / float(2)
                            subgraph_nodes = self.clean_tool.subgraph_collinear_nodes()
                            self.clean_tool.step = (self.clean_tool.range / float(len(subgraph_nodes))) / float(2)
                            res = map(lambda (group_edges): self.clean_tool.merge_edges(group_edges),
                                      self.con_comp_iter(subgraph_nodes))

                    # 4. ORPHANS
                    # errors orphans, closed polylines
                    if self.clean_tool.Orphans:
                        self.clean_tool.step = len(self.clean_tool.sEdges) / float(self.clean_tool.range)
                        res = map(
                            lambda sedge: self.clean_tool.del_edge_w_nodes(sedge.id, sedge.getStartNode(), sedge.getEndNode()),
                            filter(lambda edge: self.clean_tool.sNodes[edge.getStartNode()].getConnectivity() ==
                                                self.clean_tool.sNodes[edge.getEndNode()].getConnectivity() == 1,
                                   self.clean_tool.sEdges.values()))

                    error_features = []
                    if self.clean_tool.Errors:
                        all_errors = []
                        all_errors += zip(self.clean_tool.multiparts, ['multipart'] * len(self.clean_tool.multiparts))
                        all_errors += zip(self.clean_tool.points, ['point'] * len(self.clean_tool.points))
                        all_errors += zip(self.clean_tool.orphans, ['orphan'] * len(self.clean_tool.orphans))
                        all_errors += zip(self.clean_tool.closed_polylines, ['closed polyline'] * len(self.clean_tool.closed_polylines))
                        all_errors += zip(self.clean_tool.duplicates, ['duplicate'] * len(self.clean_tool.duplicates))
                        all_errors += zip(self.clean_tool.broken, ['broken'] * len(self.clean_tool.broken))
                        all_errors += zip(self.clean_tool.merged, ['pseudo'] * len(self.clean_tool.merged))
                        all_errors += zip(self.clean_tool.self_intersecting, ['self intersection'] * len(self.clean_tool.self_intersecting))
                        all_errors += zip(self.clean_tool.snapped, ['snapped'] * len(self.clean_tool.snapped))
                        error_features = [self.clean_tool.create_error_feat(k, str([i[1] for i in list(g)])[1:-1]) for k, g in
                                          itertools.groupby(sorted(all_errors), operator.itemgetter(0))]

                    unlink_features = []
                    if self.clean_tool.Unlinks:
                        unlink_features = map(lambda p: self.clean_tool.create_unlink_feat(p), self.clean_tool.unlinks)

                    if is_debug: print "survived!"
                    self.clean_tool.progress.disconnect()
                    self.cl_progress.emit(100)
                    # return cleaned data, errors and unlinks

                    ret = map(lambda e: e.feature, self.clean_tool.sEdges.values()), error_features, unlink_features

                except Exception, e:
                    # forward the exception upstream
                    self.error.emit( traceback.format_exc())

            self.finished.emit(ret)

        def kill(self):
            self.cl_killed = True

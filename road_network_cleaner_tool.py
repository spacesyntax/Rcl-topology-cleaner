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
from PyQt4.QtCore import QThread, QSettings
from qgis.core import *
from qgis.gui import *
from qgis.utils import *
import operator

from road_network_cleaner_dialog import RoadNetworkCleanerDialog
from sGraph.sGraph import *  # better give these a name to make it explicit to which module the methods belong
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

        if self.dlg.getNetwork():
            self.dlg.outputCleaned.setText(self.dlg.inputCombo.currentText() + "_cl")
            self.dlg.dbsettings_dlg.nameLineEdit.setText(self.dlg.inputCombo.currentText() + "_cl")
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
        self.dlg.dbsettings_dlg.nameLineEdit.setText(self.dlg.inputCombo.currentText() + "_cl")

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
            # start the cleaning in a new thread
            self.dlg.lockGUI(True)
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

            if is_debug:
                print 'started'
            self.giveMessage('Process started..', QgsMessageBar.INFO)
        else:
            self.giveMessage('Missing user input!', QgsMessageBar.INFO)
            return

    def workerFinished(self, ret):
        if is_debug:
            print 'trying to finish'
        self.dlg.lockGUI(False)
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
            self.cleaning.graph.kill() #todo
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
            self.pseudo_graph = sGraph({}, {})
            self.graph = None

        def run(self):
            if has_pydevd and is_debug:
                pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True, suspend=False)
            ret = None
            #if self.settings:
            try:
                # cleaning settings
                layer_name = self.settings['input']
                layer = getLayerByName(layer_name)
                snap_threshold = self.settings['snap']
                break_at_vertices = self.settings['break']
                merge_type = self.settings['merge']
                collinear_threshold = self.settings['collinear_angle']
                angle_threshold = self.settings['simplification_threshold']
                fix_unlinks = self.settings['fix_unlinks']
                orphans = self.settings['orphans']
                errors = self.settings['errors']
                getUnlinks = self.settings['unlinks']


                self.cl_progress.emit(0)
                # self.pseudo_graph.step = layer.featureCount() / float(10)
                #self.pseudo_graph.progress.connect(self.cl_progress.emit)
                self.graph = sGraph({}, {})
                self.pseudo_graph.load_edges_w_o_topology(clean_features_iter(layer))
                QgsMessageLog.logMessage('pseudo_graph edges added', level=QgsMessageLog.CRITICAL)

                if break_at_vertices:
                    #self.pseudo_graph.step = len(self.pseudo_graph.sEdges) / float(20)
                    self.graph.load_edges(self.pseudo_graph.break_features_iter(getUnlinks, angle_threshold, fix_unlinks))
                    QgsMessageLog.logMessage('pseudo_graph edges broken', level=QgsMessageLog.CRITICAL)

                #self.pseudo_graph.progress.disconnect() # self.cl_progress.emit

                #self.graph.progress.connect(self.cl_progress.emit)
                #self.graph.total = self.pseudo_graph.total
                #self.graph.step = 0
                self.graph.clean(True, False, snap_threshold, True)
                QgsMessageLog.logMessage('graph clean parallel and closed pl', level=QgsMessageLog.CRITICAL)

                if merge_type:

                    self.graph.merge(merge_type, collinear_threshold)
                    self.graph.clean(True, False, snap_threshold, True)
                    QgsMessageLog.logMessage('merge and clean', level=QgsMessageLog.CRITICAL)

                if snap_threshold != 0:

                    self.graph.snap_endpoints(snap_threshold)
                    self.graph.clean(True, orphans, snap_threshold, False)
                    if merge_type:
                        self.graph.merge(merge_type, collinear_threshold)
                    QgsMessageLog.logMessage('snap, clean and merge', level=QgsMessageLog.CRITICAL)

                if getUnlinks:
                    unlink_features = map(lambda p: create_feat_from_point(p), zip(range(1, len(self.graph.unlinks)), self.graph.unlinks))
                    QgsMessageLog.logMessage('unlinks created', level=QgsMessageLog.CRITICAL)

                error_features = []
                if errors and False:
                    error_features = map(lambda p: create_feat_from_point(p), zip(range(1, len(self.graph.unlinks)), self.graph.errors))
                    QgsMessageLog.logMessage('errors created', level=QgsMessageLog.CRITICAL)

                if is_debug: print "survived!"
                #self.graph.progress.disconnect()
                self.cl_progress.emit(100)
                # return cleaned data, errors and unlinks
                ret = map(lambda e: e.feature, self.graph.sEdges.values()), error_features, unlink_features
                #ret = None

            except Exception, e:
                # forward the exception upstream
                # print e
                self.error.emit(e, traceback.format_exc() )

            self.finished.emit(ret)

        def kill(self):
            self.cl_killed = True

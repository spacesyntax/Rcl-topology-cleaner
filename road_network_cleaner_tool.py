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
from PyQt4.QtCore import Qt, QThread
from PyQt4 import QtGui

from qgis.core import *
from qgis.gui import *
from qgis.utils import *

#import db_manager.db_plugins.postgis.connector as con
import traceback

# Initialize Qt resources from file resources.py
import resources
# the dialog modules
from road_network_cleaner_dialog import RoadNetworkCleanerDialog

# additional modules
from sGraph.break_tools import *  # better give these a name to make it explicit to which module the methods belong
from sGraph.merge_tools import *
from sGraph.utilityFunctions import *

# Import the debug library - required for the cleaning class in separate thread
# set is_debug to False in release version
is_debug = True
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
        #self.dbsettings_dlg = None
        #self.clsettings_dlg = None

        # some globals
        self.cleaning = None
        self.thread = None

    def loadGUI(self):
        # create the dialog objects
        self.dlg = RoadNetworkCleanerDialog()

        # setup GUI signals
        self.dlg.closingPlugin.connect(self.unloadGUI)
        self.dlg.cleanButton.clicked.connect(self.startCleaning)
        self.dlg.cancelButton.clicked.connect(self.killCleaning)

        # add layers to dialog
        self.updateLayers()

        # setup legend interface signals
        self.legend.itemAdded.connect(self.updateLayers)
        self.legend.itemRemoved.connect(self.updateLayers)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

    def unloadGUI(self):
        if self.dlg:
            self.dlg.closingPlugin.disconnect(self.unloadGUI)
            self.dlg.cleanButton.clicked.disconnect(self.startCleaning)
            self.dlg.cancelButton.clicked.disconnect(self.killCleaning)

        try:
            self.legend.itemAdded.disconnect(self.updateLayers)
            self.legend.itemRemoved.disconnect(self.updateLayers)
        except TypeError:
            pass

        self.dlg = None

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

    def giveMessage(self, message, level):
        # Gives warning according to message
        self.iface.messageBar().pushMessage("Road network cleaner: ", "%s" % (message), level, duration=5)

    def cleaningError(self, e, exception_string):
        # Gives error according to message
        QgsMessageLog.logMessage('Cleaning thread raised an exception: %s' % exception_string, level=QgsMessageLog.CRITICAL)
        self.dlg.close()

    def startCleaning(self):
        self.dlg.cleaningProgress.reset()
        settings = self.dlg.get_settings()
        if settings['output_type'] == 'postgis':
            db_settings = self.dlg.get_dbsettings()
            settings.update(db_settings)

        if settings['input']:

            cleaning = self.clean(settings, self.iface)
            # start the cleaning in a new thread
            thread = QThread()
            cleaning.moveToThread(thread)
            cleaning.finished.connect(self.cleaningFinished)
            cleaning.error.connect(self.cleaningError)
            cleaning.warning.connect(self.giveMessage)
            cleaning.cl_progress.connect(self.dlg.cleaningProgress.setValue)

            thread.started.connect(cleaning.run)
            # thread.finished.connect(self.cleaningFinished)

            self.thread = thread
            self.cleaning = cleaning

            self.thread.start()

            if is_debug: print 'started'
        else:
            self.giveMessage('Missing user input!', QgsMessageBar.INFO)
            return

    def cleaningFinished(self, ret):
        if is_debug: print 'trying to finish'
        # load the cleaning results layer
        try:
            # report the result
            for layer in ret:
                if layer:
                    QgsMapLayerRegistry.instance().addMapLayer(layer)
                    layer.updateExtents()
                    self.iface.mapCanvas().refresh()

            self.giveMessage('Process ended successfully!', QgsMessageBar.INFO)

        except Exception, e:
            # notify the user that sth went wrong
            self.cleaning.error.emit(e, traceback.format_exc())
            self.giveMessage('Something went wrong! See the message log for more information', QgsMessageBar.CRITICAL)

        # clean up the worker and thread
        #self.cleaning.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()

        if is_debug: print 'thread running ', self.thread.isRunning()
        if is_debug: print 'has finished ', self.thread.isFinished()

        self.thread = None
        self.cleaning = None

        if self.dlg:
            self.dlg.cleaningProgress.reset()
            self.dlg.close()

    def killCleaning(self):
        if is_debug: print 'trying to cancel'
        # add emit signal to breakTool or mergeTool only to stop the loop
        if self.cleaning:

            try:
                dummy = self.cleaning.br
                del dummy
                self.cleaning.br.killed = True
            except AttributeError:
                pass
            try:
                dummy = self.cleaning.mrg
                del dummy
                self.cleaning.mrg.killed = True
            except AttributeError:
                pass
            # Disconnect signals
            self.cleaning.finished.disconnect(self.cleaningFinished)
            self.cleaning.error.disconnect(self.cleaningError)
            self.cleaning.warning.disconnect(self.giveMessage)
            self.cleaning.cl_progress.disconnect(self.dlg.cleaningProgress.setValue)
            # Clean up thread and analysis
            self.cleaning.kill()
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
    class clean(QObject):

        # Setup signals
        finished = pyqtSignal(object)
        error = pyqtSignal(Exception, basestring)
        cl_progress = pyqtSignal(float)
        warning = pyqtSignal(str)
        cl_killed = pyqtSignal(bool)

        def __init__(self, settings, iface):
            QObject.__init__(self)
            self.settings = settings
            self.iface = iface
            self.total =0

        def add_step(self,step):
            self.total += step
            return self.total

        def run(self):
            if has_pydevd and is_debug:
                pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True, suspend=False)
            ret = None
            if self.settings:
                try:
                    # cleaning settings
                    layer_name = self.settings['input']
                    path = self.settings['output']
                    tolerance = self.settings['tolerance']
                    output_type = self.settings['output_type']

                    # project settings
                    layer = getLayerByName(layer_name)
                    crs = layer.dataProvider().crs()
                    encoding = layer.dataProvider().encoding()
                    geom_type = layer.dataProvider().geometryType()

                    self.cl_progress.emit(2)

                    self.br = breakTool(layer, tolerance, None, self.settings['errors'], self.settings['unlinks'])

                    if self.cl_killed is True or self.br.killed is True: return

                    self.br.add_edges()

                    if self.cl_killed is True or self.br.killed is True: return

                    self.cl_progress.emit(5)
                    self.total = 5
                    step = 40/ self.br.feat_count
                    self.br.progress.connect(lambda incr=self.add_step(step): self.cl_progress.emit(incr))

                    broken_features = self.br.break_features()

                    if self.cl_killed is True or self.br.killed is True: return

                    self.cl_progress.emit(45)

                    self.mrg = mergeTool(broken_features, None, True)

                    # TODO test
                    try:
                        step = 40/ len(self.mrg.con_1)
                        self.mrg.progress.connect(lambda incr=self.add_step(step): self.cl_progress.emit(incr))
                    except ZeroDivisionError:
                        pass

                    merged_features = self.mrg.merge()

                    if self.cl_killed is True or self.mrg.killed is True: return

                    fields = self.br.layer_fields

                    (final, errors, unlinks) = (None, None, None)
                    if output_type in ['shp', 'memory']:
                        final = to_shp(path, merged_features, fields, crs, 'cleaned', encoding, geom_type)
                    else:
                        final = to_dblayer(self.settings['dbname'], self.settings['user'], self.settings['host'], self.settings['port'],self.settings['password'], self.settings['schema'], self.settings['table_name'], fields, merged_features, crs)
                        try:
                            # None will be emitted if db layer is not created
                            self.error.emit(final, traceback.format_exc())
                        except :
                            pass

                    if self.settings['errors']:
                        self.br.updateErrors(self.mrg.errors_features)
                        errors_list = [[k, [[k], [v[0]]], v[1]] for k, v in self.br.errors_features.items()]
                        errors = to_shp(None, errors_list, [QgsField('id_input', QVariant.Int), QgsField('errors', QVariant.String)], crs, 'errors', encoding, geom_type)

                    if self.settings['unlinks']:
                        unlinks = to_shp(None, self.br.unlinked_features, [QgsField('id', QVariant.Int), QgsField('line_id1', QVariant.Int), QgsField('line_id2', QVariant.Int), QgsField('x', QVariant.Double), QgsField('y', QVariant.Double)], crs,'unlinks', encoding, 0)

                    if is_debug: print "survived!"
                    self.cl_progress.emit(100)
                    # return cleaned shapefile and errors
                    ret = (errors, final, unlinks)

                except Exception, e:
                    # forward the exception upstream
                    self.error.emit(e, traceback.format_exc())

            self.finished.emit(ret)

        def kill(self):
            self.cl_killed = True

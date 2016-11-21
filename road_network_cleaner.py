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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QThread
from PyQt4.QtGui import QAction, QIcon
from qgis.core import QgsMapLayer, QgsMapLayerRegistry, QgsMessageLog
from PyQt4.QtCore import pyqtSlot
from qgis.gui import QgsMessageBar

from sGraph.dual_graph import *
from sGraph.shpFunctions import *


from qgis.utils import *
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from road_network_cleaner_dialog import RoadNetworkCleanerDialog
import os.path
import math

from periodic_worker import GenericWorker, ClassFactory

# Import the debug library
# set is_debug to False in release version
is_debug = False
try:
    import pydevd
    has_pydevd = True
except ImportError, e:
    has_pydevd = False
    is_debug = False

gl_res = None
progress_steps = 10
progress_point = 0

class RoadNetworkCleaner:
    """QGIS Plugin Implementation."""

    global gl_res
    global progress_steps
    global progress_point

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'RoadNetworkCleaner_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = RoadNetworkCleanerDialog()
        self.cleaning = None

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&RoadNetworkCleaner')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'RoadNetworkCleaner')
        self.toolbar.setObjectName(u'RoadNetworkCleaner')

        # Setup debugger
        if has_pydevd and is_debug:
            pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True, suspend=True)

        # setup GUI signals
        # self.dockwidget.cleanButton.clicked.connect(self.runCleaning)
        self.dlg.cleanButton.clicked.connect(self.clean)
        self.dlg.cancelButton.clicked.connect(self.killWorker)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('RoadNetworkCleaner', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/RoadNetworkCleaner/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Road network cleaner'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&RoadNetworkCleaner'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def getActiveLayers(self, iface):
        layers_list = []
        for layer in iface.legendInterface().layers():
            if layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
                if layer.hasGeometryType() and (layer.geometryType() == 1):
                    layers_list.append(layer.name())
        return layers_list

    def render(self,vector_layer):
        QgsMapLayerRegistry.instance().addMapLayer(vector_layer)

    # SOURCE: Network Segmenter https://github.com/OpenDigitalWorks/NetworkSegmenter
    # SOURCE: https://snorfalorpagus.net/blog/2013/12/07/multithreading-in-qgis-python-plugins/

    def giveMessage(self, message, level):
        # Gives warning according to message
        self.iface.messageBar().pushMessage("Road network cleaner: ", "%s" % (message), level, duration=5)

    def cleaningError(self, e, exception_string):
        # Gives error according to message
        QgsMessageLog.logMessage('Cleaning thread raised an exception: %s' % exception_string, level=QgsMessageLog.CRITICAL)


    def killWorker(self):
        if self.cleaning:
            # Disconnect signals
            self.any_worker.finished.disconnect(self.finishWorker)
            self.any_worker.error.disconnect(self.cleaningError)
            self.any_worker.warning.disconnect(self.giveMessage)
            self.any_worker.progress.disconnect(self.changePB)
            # Clean up thread and analysis
            self.any_worker.kill()
            self.any_worker.deleteLater()
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
            self.any_worker = None
            self.dlg.cleaningProgress.reset()

    def finishWorker(self, ret):

        print "job finished!"
        # clean up  the worker and thread
        self.any_worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.any_worker = None

        if ret:
            # report the result
            print ret
            gl_res = ret
            self.giveMessage('Process ended successfully!', QgsMessageBar.INFO)

        else:
            # notify the user that sth went wrong
            self.giveMessage('Something went wrong! See the message log for more information', QgsMessageBar.CRITICAL)

        self.dlg.cleaningProgress.reset()

    def startWorker(self,any_worker):
        print "new worker started"
        thread = QThread()
        thread.start()

        any_worker.moveToThread(thread)
        any_worker.start.connect(any_worker.any_run({}))

        any_worker.finished.connect(self.finishWorker)
        any_worker.error.connect(self.cleaningError)
        any_worker.warning.connect(self.giveMessage)
        any_worker.progress.connect(self.changePB)

        #thread.started.connect(any_worker.any_run)

        self.thread = thread
        self.any_worker = any_worker

    @pyqtSlot(int, int)
    def changePB(self,progress, progress_steps=progress_steps, progress_point=progress_point):
        self.dlg.cleaningProgress.setValue((progress/ progress_steps) + progress_point)

    def clean(self):
        settings = self.dlg.get_settings()
        if settings:
            # cleaning settings
            layer_name = settings['input']
            path = settings['output']
            tolerance = settings['tolerance']
            base_id = 'id_in'

            # project settings
            n = getLayerByName(layer_name)
            crs = n.dataProvider().crs()
            encoding = n.dataProvider().encoding()
            geom_type = n.dataProvider().geometryType()
            qgsflds = get_field_types(layer_name)

            simplify = True
            parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify, 'id_column': base_id}
            # BaseClass = transformer
            my_worker = GenericWorker(parameters,transformer(parameters).transform)
            #my_worker.any_run({})
            progress_steps = 10
            progress_point = 0
            self.startWorker(my_worker)

            print gl_res

            # error cat: invalids, multiparts
            #primal_graph, invalids, multiparts = transformer(parameters).run()
            #any_primal_graph = prGraph(primal_graph, base_id, True)

    def run(self):
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()

        self.dlg.popActiveLayers(self.getActiveLayers(self.iface))
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass





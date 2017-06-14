# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DbSettingsDialog
                                 A QGIS plugin
 This is to load the postgis db settings
                             -------------------
        begin                : 2017-06-12
        git sha              : $Format:%H$
        copyright            : (C) 2017 by Ioanna Kolovou
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

import os

from PyQt4.QtCore import pyqtSignal, QSettings
from PyQt4 import QtGui, uic

import db_manager.db_plugins.postgis.connector as con
from qgis.core import QgsDataSourceURI



FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'DbSettings_dialog_base.ui'))


class DbSettingsDialog(QtGui.QDialog, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(DbSettingsDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

    def getQGISDbs(self):
        from PyQt4.QtCore import QSettings
        qs = QSettings()
        available_dbs = {}
        for k in sorted(qs.allKeys()):
            if k[0:23] == 'PostgreSQL/connections/' and k[-9:] == '/database':
                available_dbs[k[23:].split('/')[0]] = {}

        for dbname, info in available_dbs.items():
            host = qs.value('PostgreSQL/connections/' + dbname + '/host')
            port = qs.value('PostgreSQL/connections/' + dbname + '/port')
            username = qs.value('PostgreSQL/connections/' + dbname + '/username')
            password = qs.value('PostgreSQL/connections/' + dbname + '/password')
            info['host'] = host
            info['port'] = port
            info['username'] = username
            info['password'] = password
            available_dbs[dbname] = dict(info)

        return available_dbs

    def popDbs(self, available_dbs):
        self.dbCombo.clear()
        self.dbCombo.addItems(available_dbs.keys())
        return

    def popSchemas(self, available_dbs, selected_db):
        uri = QgsDataSourceURI()
        db_info = available_dbs[selected_db]
        uri.setConnection(db_info['host'], db_info['port'], selected_db, db_info['username'], db_info['password'])
        c = con.PostGisDBConnector(uri)
        schemas = list(set([i[2] for i in c.getTables()]))
        self.schemaCombo.addItems(schemas)
        pass

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
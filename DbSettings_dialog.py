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

        self.nameLineEdit.setText("cleaned")
        self.okButton.clicked.connect(self.close)

    def getQGISDbs(self):
        """Return all PostGIS connection settings stored in QGIS
        :return: connection dict() with name and other settings
        """
        con_settings = []
        settings = QSettings()
        settings.beginGroup('/PostgreSQL/connections')
        for item in settings.childGroups():
            con = dict()
            con['name'] = unicode(item)
            con['host'] = unicode(settings.value(u'%s/host' % unicode(item)))
            con['port'] = unicode(settings.value(u'%s/port' % unicode(item)))
            con['database'] = unicode(settings.value(u'%s/database' % unicode(item)))
            con['username'] = unicode(settings.value(u'%s/username' % unicode(item)))
            con['password'] = unicode(settings.value(u'%s/password' % unicode(item)))
            con_settings.append(con)
        settings.endGroup()
        dbs = {}
        if len(con_settings) > 1:
            for conn in con_settings:
                dbs[conn['name']]= conn
        return dbs

    def popDbs(self, available_dbs):
        self.dbCombo.clear()
        self.dbCombo.addItems(sorted(available_dbs.keys()))
        return

    def getSelectedDb(self):
        return self.dbCombo.currentText()

    def getDbSettings(self, available_dbs):
        connection = self.dbCombo.currentText()
        return {'dbname': available_dbs[connection]['name'],
        'user': available_dbs[connection]['username'],
        'host': available_dbs[connection]['host'],
        'port': available_dbs[connection]['port'],
        'password': available_dbs[connection]['password'],
        'schema': self.schemaCombo.currentText(),
        'table_name': self.nameLineEdit.text()}

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
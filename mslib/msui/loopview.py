"""Module to display batch-generated images.

********************************************************************************

   Copyright 2008-2014 Deutsches Zentrum fuer Luft- und Raumfahrt e.V.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

********************************************************************************

This file is part of the Mission Support System User Interface (MSUI).

DESCRIPTION:
============

This module provides functionality to view batch generated images that are also
available from the Mission Support Website. The difference to the website is
that in this module the user can load up to four product categories and explore
the images time-synchronized. Also, all available vertical levels of the
products are loaded, so that the exploration of the vertical structure of the
atmosphere becomes easier.

Use the 'Layout' menu to select the number of displayed products. Depending on
the chosen layout, the window will be split into up to four areas (using the
QSplitter class), each containing an instance of the ImageLoopWidget class
contained in loopviewer_widget.py.

Use a double click on an ImageLoopWidget to load imagery into the widget. The
dialog that opens will offer the configuration defined in mss_settings.json.
Once the images have been loaded, use the mouse wheel on one of the images
to navigate forward and backward in time. Use the mouse wheel while the
<Shift> key is pressed to navigate up- and downward in vertical level.


AUTHORS:
========

* Marc Rautenhaus (mr)

"""

# standard library imports
import functools
import logging
import sys

# related third party imports
from PyQt4 import QtGui, QtCore  # Qt4 bindings
import numpy as np

# local application imports
from mslib.msui import ui_loopwindow as ui
from mslib.msui import loopviewer_widget as imw
from mslib.msui import mss_qt
from mslib.mss_util import config_loader

"""
CLASS MSSLoopWindow
"""


class MSSLoopWindow(mss_qt.MSSViewWindow, ui.Ui_ImageLoopWindow):
    """MSUI view that can load and display batch images. No interactive
       modification of the images is possible, the intent of this module
       is to let the user navigate comfortably in time and vertical level
       (using the mouse wheel) in up to max_views time synchronized
       views.

       Principle: This window uses QSplitter instances to divide the view
       area into up to max_views elements. In each element an ImageLoopWidget
       is loaded, which provides functionality to load and display batch
       images.
       The individual image widgets synchronize through the 'changeValidTime'
       signal, which is emitted by a widget whose time has been changed.
    """
    name = "Loop View"
    max_views = 4  # maximum number of views

    def __init__(self, config, *args):
        super(MSSLoopWindow, self).__init__(*args)
        self.setupUi(self)
        self.statusBar.addPermanentWidget(QtGui.QLabel(
            "Use wheel on image for time navigation, "
            "shift+wheel for level navigation."))

        # Create max_views image labels. The labels will exist
        # in memory, but they won't always be visible to the user.
        # Connect the changeValidTime signal of the widgets to the
        # changeValidTime() method of this class, which displays
        # the globally synchronized time.
        self.imageWidgets = []
        for i in xrange(self.max_views):
            widget = imw.ImageLoopWidget(config, self)
            self.imageWidgets.append(widget)
            self.connect(widget, QtCore.SIGNAL("changeValidTime(bool, PyQt_PyObject)"),
                         self.changeValidTime)

        # Create the splitter objects that are necessary to implement
        # the layouts.
        self.mainSplitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.rightSplitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.topSplitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.bottomSplitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.mainSplitter.addWidget(self.rightSplitter)
        self.mainSplitter.addWidget(self.topSplitter)
        self.mainSplitter.addWidget(self.bottomSplitter)

        # Set the initial layout (only one widget visible).
        layout = QtGui.QHBoxLayout()
        layout.addWidget(self.mainSplitter)
        self.centralFrame.setLayout(layout)
        self.setLayout(0)

        # This combobox provides time steps for the fwd/back buttons.
        self.cbVTStep.setCurrentIndex(5)

        # Connect slots and signals ("Layout" menu and global fwd/back
        # buttons).
        self.connect(self.actionSingleView,
                     QtCore.SIGNAL("triggered()"),
                     functools.partial(self.setLayout, 0))
        self.connect(self.actionDualView,
                     QtCore.SIGNAL("triggered()"),
                     functools.partial(self.setLayout, 1))
        self.connect(self.actionOneLargeTwoSmall,
                     QtCore.SIGNAL("triggered()"),
                     functools.partial(self.setLayout, 2))
        self.connect(self.actionOneLargeThreeSmall,
                     QtCore.SIGNAL("triggered()"),
                     functools.partial(self.setLayout, 3))
        self.connect(self.actionQuadView,
                     QtCore.SIGNAL("triggered()"),
                     functools.partial(self.setLayout, 4))

        self.connect(self.tbValidTime_fwd, QtCore.SIGNAL("clicked()"),
                     functools.partial(self.changeValidTime, True))
        self.connect(self.tbValidTime_back, QtCore.SIGNAL("clicked()"),
                     functools.partial(self.changeValidTime, False))

    def setLayout(self, index):
        """Set the layout of the displayed image labels. This slot is called
           whenever an antry from the Layout menu has been selected. It shows/
           hides the ImageLoopWidgets.
        """
        # print self.mainSplitter.width(), self.mainSplitter.height()
        # for i in xrange(self.mainSplitter.count()):
        #    print "main", i, self.mainSplitter.widget(i)

        # Hide everything.
        self.rightSplitter.hide()
        self.topSplitter.hide()
        self.bottomSplitter.hide()
        for widget in self.imageWidgets:
            widget.hide()
        # Determine the width of the main splitter widget (used below to
        # set the size of sub-splitters and labels).
        w = self.mainSplitter.width()

        if index == 0:
            # Single view: Hide all sub-splitters and display one label.
            self.mainSplitter.addWidget(self.imageWidgets[0])
            show_widgets = [0]

        elif index == 1:
            # Dual view: Hide all sub-splitters and show two labels
            # side by side.
            self.mainSplitter.setOrientation(QtCore.Qt.Horizontal)
            # Transfer ownership of the label widgets to the main splitter.
            # If the splitter already owns the labels, nothing will be
            # changed. Otherwise the labels will be removed from the
            # splitter objects that own the labels.
            self.mainSplitter.addWidget(self.imageWidgets[0])
            self.mainSplitter.addWidget(self.imageWidgets[1])
            show_widgets = [0, 1]
            # Distribute the available space evenly among the two labels.
            self.mainSplitter.setSizes(np.ones(self.mainSplitter.count()))

        elif index == 2:
            # One large and two small views.
            self.mainSplitter.setOrientation(QtCore.Qt.Horizontal)
            self.rightSplitter.addWidget(self.imageWidgets[1])
            self.rightSplitter.addWidget(self.imageWidgets[2])
            self.rightSplitter.show()
            self.mainSplitter.insertWidget(0, self.imageWidgets[0])
            show_widgets = [0, 1, 2]
            self.rightSplitter.setSizes(np.ones(self.rightSplitter.count()))
            self.mainSplitter.setSizes([2 * w / 3, w / 3])

        elif index == 3:
            # One large and three small views.
            self.mainSplitter.setOrientation(QtCore.Qt.Horizontal)
            self.rightSplitter.addWidget(self.imageWidgets[1])
            self.rightSplitter.addWidget(self.imageWidgets[2])
            self.rightSplitter.addWidget(self.imageWidgets[3])
            self.rightSplitter.show()
            self.mainSplitter.insertWidget(0, self.imageWidgets[0])
            show_widgets = [0, 1, 2, 3]
            self.rightSplitter.setSizes(np.ones(self.rightSplitter.count()))
            self.mainSplitter.setSizes([2 * w / 3, w / 3])

        elif index == 4:
            # Four equally sized views.
            self.topSplitter.addWidget(self.imageWidgets[0])
            self.topSplitter.addWidget(self.imageWidgets[1])
            self.bottomSplitter.addWidget(self.imageWidgets[2])
            self.bottomSplitter.addWidget(self.imageWidgets[3])
            self.mainSplitter.setOrientation(QtCore.Qt.Vertical)
            self.topSplitter.show()
            self.bottomSplitter.show()
            show_widgets = [0, 1, 2, 3]
            self.topSplitter.setSizes(np.ones(self.topSplitter.count()))
            self.bottomSplitter.setSizes(np.ones(self.bottomSplitter.count()))
            self.mainSplitter.setSizes(np.ones(self.mainSplitter.count()))

        # Show the labels that are visible in the new layout.
        for i in show_widgets:
            self.imageWidgets[i].show()

    def changeValidTime(self, forward, time=None):
        """Slot called when (a) one of the global time fwd/back buttons has
           been clicked, and (b) when a changeValidTime signal has been
           observed.

        Sets the global time display if a time has been passed (signal call)
        and emits changeValidTime to notify other observers.
        """
        if time:
            self.dteValidTime.setDateTime(time)
        else:
            multiplier = 1 if forward else -1
            timestep_sec = [300, 600, 900, 1800, 3600, 10800, 21600,
                            43200, 86400][self.cbVTStep.currentIndex()]
            # Get QDateTime object from QtDateTimeEdit field.
            d = self.dteValidTime.dateTime()
            # Add value from sbInitTime_step and set new date.
            self.dteValidTime.setDateTime(d.addSecs(multiplier * timestep_sec))
            time = self.dteValidTime.dateTime().toPyDateTime()

        # Notify the other widgets of the change.
        self.emit(QtCore.SIGNAL("changeValidTime(bool, PyQt_PyObject)"), forward, time)


################################################################################
################################################################################
# Module test.

if __name__ == "__main__":
    # Log everything, and send it to stderr.
    # See http://docs.python.org/library/logging.html for more information
    # on the Python logging module.
    # NOTE: http://docs.python.org/library/logging.html#formatter-objects
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s (%(module)s.%(funcName)s): %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    app = QtGui.QApplication(sys.argv)
    loop_configuration = {
        "ECMWF forecasts": {
            # URL to the Mission Support website at which the batch image
            # products are located.
            "url": "http://www.your-server.de/forecasts",
            # Initialisation times every init_timestep hours.
            "init_timestep": 12,
            # Products available on the webpage. Add new products here!
            # Each product listed here will be loaded as one group, so
            # that the defined times can be navigated with <wheel> and
            # the defined levels can be navigated with <shift+wheel>.
            # Times not found in the listed range of forecast_steps
            # are ignored, its hence save to define the entire forecast
            # range with the smalled available time step.
            "products": {
                "Geopotential and Wind": {
                    "abbrev": "geop",
                    "regions": {"Europe": "eur", "Germany": "de"},
                    "levels": [200, 250, 300, 500, 700, 850, 925],
                    "forecast_steps": range(0, 240, 3)},
            }
        }
    }
    loop_configuration = config_loader(dataset="loop_configuration", default=loop_configuration)
    win = MSSLoopWindow(loop_configuration)
    win.show()
    sys.exit(app.exec_())
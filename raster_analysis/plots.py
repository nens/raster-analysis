# -*- coding: utf-8 -*-
""" Find lowest upstream points. """

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

from pylab import imshow
from pylab import show
from pylab import plot
from pylab import axis


class Plot(object):
    def add_geometries(self, *geometries):
        for geometry in geometries:
            try:
                points = geometry.GetPoints()
            except RuntimeError:
                points = geometry.Boundary().GetPoints()
            plot(*zip(*points))

    def add_array(self, *args, **kwargs):
        imshow(*args, **kwargs)

    def show(self):
        axis('equal')
        show()

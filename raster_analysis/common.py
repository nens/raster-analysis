# -*- coding: utf-8 -*-
""" Find lowest upstream points. """

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import os

from pylab import imshow
from pylab import show
from pylab import plot
from pylab import axis

from osgeo import gdal
from osgeo import ogr

gdal.UseExceptions()
ogr.UseExceptions()


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


class Source(object):
    """ Wrap a shapefile. """
    def __init__(self, path):
        self.dataset = ogr.Open(path)
        self.layer = self.dataset[0]

    def __iter__(self):
        for feature in self.layer:
            yield(feature)

    def __len__(self):
        return self.layer.GetFeatureCount()

    def query(self, geometry):
        self.layer.SetSpatialFilter(geometry)
        for feature in self.layer:
            yield(feature)


class Target(object):
    """ Wrap a shapefile. """
    def __init__(self, path, template_path, attributes):
        # read template
        template_data_source = ogr.Open(template_path)
        template_layer = template_data_source[0]
        template_sr = template_layer.GetSpatialRef()

        # create or replace shape
        driver = ogr.GetDriverByName(b'ESRI Shapefile')
        #if os.path.exists(path):
            #driver.DeleteDataSource(str(path))
        self.dataset = driver.CreateDataSource(str(path))
        layer_name = os.path.basename(path)
        self.layer = self.dataset.CreateLayer(layer_name, template_sr)

        # Copy field definitions
        layer_defn = template_layer.GetLayerDefn()
        for i in range(layer_defn.GetFieldCount()):
            self.layer.CreateField(layer_defn.GetFieldDefn(i))

        # Add extra fields
        for attribute in attributes:
            self.layer.CreateField(ogr.FieldDefn(str(attribute), ogr.OFTReal))
        self.layer_defn = self.layer.GetLayerDefn()

    def append(self, geometry, attributes):
        """ Append geometry and attributes as new feature. """
        feature = ogr.Feature(self.layer_defn)
        feature.SetGeometry(geometry)
        for key, value in attributes.items():
            feature[str(key)] = value
        self.layer.CreateFeature(feature)

# -*- coding: utf-8 -*-
""" Find lowest upstream points. """

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import os

from osgeo import gdal
from osgeo import ogr

gdal.UseExceptions()
ogr.UseExceptions()


class Source(object):
    """ Wrap a shapefile. """
    def __init__(self, path):
        self.dataset = ogr.Open(path)
        self.layer = self.dataset[0]

    def __iter__(self):
        total = len(self)
        gdal.TermProgress_nocb(0)
        for count, feature in enumerate(self.layer, 1):
            yield feature
            gdal.TermProgress_nocb(count / total)

    def __len__(self):
        return self.layer.GetFeatureCount()

    def query(self, geometry):
        """ Return generator of features with geometry as spatial filter. """
        self.layer.SetSpatialFilter(geometry)
        for feature in self.layer:
            yield feature
        self.layer.SetSpatialFilter(None)

    def select(self, text):
        """ Return generator of features for text, e.g. '2/5' """
        selected, parts = map(int, text.split('/'))
        size = len(self) / parts
        start = int((selected - 1) * size)
        stop = len(self) if selected == parts else int(selected * size)
        total = stop - start
        gdal.TermProgress_nocb(0)
        for count, fid in enumerate(xrange(start, stop), 1):
            yield self.layer[fid]
            gdal.TermProgress_nocb(count / total)


class Target(object):
    """ Wrap a shapefile. """
    def __init__(self, path, template_path, attributes):
        # read template
        template_data_source = ogr.Open(template_path)
        template_layer = template_data_source[0]
        template_sr = template_layer.GetSpatialRef()

        # create or replace shape
        driver = ogr.GetDriverByName(b'ESRI Shapefile')
        self.dataset = driver.CreateDataSource(str(path))
        layer_name = os.path.basename(path)
        self.layer = self.dataset.CreateLayer(layer_name, template_sr)

        # Copy field definitions, remember names
        existing = []
        layer_defn = template_layer.GetLayerDefn()
        for i in range(layer_defn.GetFieldCount()):
            field_defn = layer_defn.GetFieldDefn(i)
            existing.append(field_defn.GetName().lower())
            self.layer.CreateField(field_defn)

        # Add extra fields
        for attribute in attributes:
            if attribute.lower() in existing:
                raise NameError(('field named "{}" already '
                                 'exists in template').format(attribute))

            self.layer.CreateField(ogr.FieldDefn(str(attribute), ogr.OFTReal))
        self.layer_defn = self.layer.GetLayerDefn()

    def append(self, geometry, attributes):
        """ Append geometry and attributes as new feature. """
        feature = ogr.Feature(self.layer_defn)
        feature.SetGeometry(geometry)
        for key, value in attributes.items():
            feature[str(key)] = value
        self.layer.CreateFeature(feature)

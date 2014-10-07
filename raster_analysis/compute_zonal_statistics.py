# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import argparse
import logging
import os
import sys

from osgeo import gdal
from osgeo import ogr
import numpy as np

from raster_store import stores

DRIVER_OGR_SHAPE = ogr.GetDriverByName(b'ESRI Shapefile')

logger = logging.getLogger(__name__)
gdal.UseExceptions()
ogr.UseExceptions()


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=(
        'Compute the max for geometries for data in a store'
    ))
    parser.add_argument('store_path',
                        metavar='STORE',
                        help='Path to raster store')
    parser.add_argument('source_path',
                        metavar='SOURCE',
                        help='Path to vector source')
    parser.add_argument('target_path',
                        metavar='TARGET',
                        help='Path to results shape')
    parser.add_argument('error_path',
                        metavar='ERROR',
                        help='Path to errors shape')
    return parser


def compute(store, geometry):
    """ Return max. """
    x1, x2, y1, y2 = geometry.GetEnvelope()
    width = int(round((x2 - x1) / 0.5))
    height = int(round((y2 - y1) / 0.5))
    datadict = store.get_data_for_polygon(
        projection='epsg:28992',
        geometry=geometry,
        height=height,
        width=width,
        select=None,
    )
    values = datadict['values']
    mask = np.equal(values, datadict['no_data_value'])
    max = np.max(values[~mask])
    return max


def command(store_path, source_path, target_path, error_path):
    """ Calculate max. """
    store = stores.Store(store_path)

    # source datasource
    source_datasource = ogr.Open(source_path)
    source_layer = source_datasource[0]

    # target datasource
    if os.path.exists(target_path):
        DRIVER_OGR_SHAPE.DeleteDataSource(target_path)
    target_datasource = DRIVER_OGR_SHAPE.CreateDataSource(target_path)
    target_layer = target_datasource.CreateLayer(b'max')
    target_layer.CreateField(ogr.FieldDefn(b'max', ogr.OFTReal))
    target_layer_defn = target_layer.GetLayerDefn()

    # error datasource
    if os.path.exists(error_path):
        DRIVER_OGR_SHAPE.DeleteDataSource(error_path)
    error_datasource = DRIVER_OGR_SHAPE.CreateDataSource(error_path)
    error_layer = error_datasource.CreateLayer(b'max')
    source_layer_defn = source_layer.GetLayerDefn()
    for i in range(source_layer_defn.GetFieldCount()):
        source_field_defn = source_layer_defn.GetFieldDefn(i)
        error_layer.CreateField(source_field_defn)

    # prepare for progress
    total = source_layer.GetFeatureCount()
    gdal.TermProgress_nocb(0)

    for count, source_feature in enumerate(source_layer, 1):
        source_geometry = source_feature.geometry()
        try:
            max = compute(geometry=source_geometry, store=store)
        except Exception as e:
            logger.exception(e)
            error_layer.CreateFeature(source_feature)
            gdal.TermProgress_nocb(count / total)
            continue
        if np.isnan(max):
            gdal.TermProgress_nocb(count / total)
            continue

        target_feature = ogr.Feature(target_layer_defn)
        target_feature[b'max'] = max
        target_feature.SetGeometry(source_geometry)
        target_layer.CreateFeature(target_feature)

        gdal.TermProgress_nocb(count / total)


def main():
    """ Call command with args from parser. """
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    return command(**vars(get_parser().parse_args()))

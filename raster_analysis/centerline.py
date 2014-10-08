# -*- coding: utf-8 -*-
""" Find lowest upstream points. """

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import argparse
import logging
import math
import sys

from osgeo import ogr
import numpy as np

from raster_store import stores
from pylab import imshow, show, plot

ogr.UseExceptions()
logger = logging.getLogger(__name__)


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        'polygon_path',
        metavar='POLYGONS',
    )
    parser.add_argument(
        'linestring_path',
        metavar='LINES',
    )
    parser.add_argument(
        'store_paths',
        metavar='STORE',
        nargs='+',
    )
    parser.add_argument(
        '-g', '--grow',
        type=float,
        default=0.5,
        metavar='',
    )
    parser.add_argument(
        '-d', '--distance',
        type=float,
        default=15.0,
        metavar='',
    )

    return parser


class Geometries():
    def __init__(self, path):
        self.dataset = ogr.Open(path)
        self.layer = self.dataset[0]

    def __iter__(self):
        for feature in self.layer:
            yield(feature)

    def query(self, feature):
        self.layer.SetSpatialFilter(feature.geometry())
        for feature in self.layer:
            yield(feature)


class MinimumStore(object):
    def __init__(self, paths):
        self.stores = [stores.get(path) for path in paths]

    def get_data(self, *args, **kwargs):
        data = [store.get_data(*args, **kwargs) for store in self.stores]
        array = np.ma.array(
            [np.ma.masked_equal(d['values'],
                                d['no_data_value']) for d in data],
        )
        no_data_value = data[0]['no_data_value']
        return {'no_data_value': no_data_value,
                'values': array.min(0).filled(no_data_value)}


def get_size(envelope):
    """ Return width, height tuple based on ahn2 resolution. """
    x1, x2, y1, y2 = envelope
    width = int(math.ceil((x2 - x1) / 0.5))
    height = int(math.ceil((y2 - y1) / 0.5))
    return width, height


def get_geotransform(size, envelope):
    """ Return appropriate geo-transform. """
    w, h = size
    x1, x2, y1, y2 = envelope
    return x1, (x2 - x1) / w, 0, y2, 0, (y1 - y2) / h


def command(polygon_path, linestring_path, store_paths, grow, distance):
    linestrings = Geometries(linestring_path)
    store = MinimumStore(store_paths)
    for i, polygon in enumerate(Geometries(polygon_path)):
        polygon.SetGeometry(polygon.geometry().Buffer(0.5))
        geometry = polygon.geometry()
        envelope = geometry.GetEnvelope()

        geom = geometry.ExportToWkt()
        sr = geometry.GetSpatialReference().ExportToWkt()
        width, height = get_size(envelope)
        data = (store.get_data(geom=geom, sr=sr, width=width, height=height))
        exit()

        # debug
        array = np.ma.masked_equal(data['values'], data['no_data_value'])[0]
        #imshow(array, extent=envelope)
        #plot(*zip(*geometry.Boundary().GetPoints()))
        #show()

        for linestring in linestrings.query(polygon):
            pass
            # split in meters
            # per point
    return 0


def main():
    """ Call command with args from parser. """
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    return command(**vars(get_parser().parse_args()))

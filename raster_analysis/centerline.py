# -*- coding: utf-8 -*-
""" TODO Docstring. """

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import argparse
import logging
import sys

from osgeo import ogr

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
        'store_path',
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


def command(polygon_path, linestring_path, store_path):
    linestrings = Geometries(linestring_path)
    for i, polygon in enumerate(Geometries(polygon_path)):

        polygon.SetGeometry(polygon.geometry().Buffer(0.5))
        for linestring in linestrings.query(polygon):
            exit()
    return 0


def main():
    """ Call command with args from parser. """
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    return command(**vars(get_parser().parse_args()))

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
from pylab import imshow, show, plot, axis

ogr.UseExceptions()
logger = logging.getLogger(__name__)


POINT = b'POINT({} {})'


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


def point2geometry(point, sr):
    """ Return ogr geometry. """
    return ogr.CreateGeometryFromWkt(POINT.format(*point), sr)


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


class Features():
    def __init__(self, path):
        self.dataset = ogr.Open(path)
        self.layer = self.dataset[0]

    def __iter__(self):
        for feature in self.layer:
            yield(feature)

    def query(self, geometry):
        self.layer.SetSpatialFilter(geometry)
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


class Case(object):
    def __init__(self, store, polygon, distance, linestring):
        self.store = store
        self.polygon = polygon
        self.distance = distance
        self.linestring = linestring
        self.sr = linestring.GetSpatialReference()

    def get_pairs(self, reverse):
        """ Return generator of point pairs. """
        linestring = self.linestring.Clone()
        linestring.Segmentize(1)
        points = linestring.GetPoints()
        if reverse:
            points.reverse()
        return zip(points[:-1], points[1:])

    def get_sites(self, reverse):
        """ Return generator of geometry, normal pairs. """
        for (x1, y1), (x2, y2) in self.get_pairs(reverse):
            dx, dy = x2 - x1, y2 - y1
            l = math.sqrt(dx ** 2 + dy ** 2)
            direction = dx / l, dy / l
            yield point2geometry((x1, y1), self.sr), direction
        # yield the last point with previous direction
        yield point2geometry((x2, y2), self.sr), direction

    def make_rectangle(self, point, radius, direction):
        """ Return ogr geometry of rectangle. """
        sr = point.GetSpatialReference()
        x, y = point.GetPoints()[0]
        points = []
        dx, dy = direction
        dx, dy = 2 * dx * radius, 2 * dy * radius  # scale
        dx, dy = dy, -dx  # right
        x, y = x + dx, y + dy  # move
        points.append('{} {}'.format(x, y))
        dx, dy = -dy, dx  # left
        x, y = x + dx, y + dy  # move
        points.append('{} {}'.format(x, y))
        dx, dy = -dy, dx  # left
        x, y = x + dx, y + dy  # move
        x, y = x + dx, y + dy  # move
        points.append('{} {}'.format(x, y))
        dx, dy = -dy, dx  # left
        x, y = x + dx, y + dy  # move
        points.append('{} {}'.format(x, y))
        points.append(points[0])
        wkt = 'POLYGON ((' + ','.join(points) + '))'
        return ogr.CreateGeometryFromWkt(wkt, sr)

    def get_areas(self, reverse):
        """ Return generator of point, area tuples. """
        for point, direction in self.get_sites(reverse):
            if not self.polygon.Contains(point):
                continue
            radius = max(self.distance, point.Distance(self.polygon))
            circle = point.Buffer(radius)
            rectangle = self.make_rectangle(point=point,
                                            radius=radius,
                                            direction=direction)
            intersection = circle.Intersection(rectangle)
            yield point, self.polygon.Intersection(intersection)

    def get_levels(self, reverse):
        for point, polygon in self.get_areas(reverse):
            envelope = polygon.GetEnvelope()
            width, height = get_size(envelope)

            # get data from store
            data = self.store.get_data(sr=self.sr,
                                       width=width,
                                       height=height,
                                       geom=polygon.ExportToWkt())
            array = np.ma.masked_equal(data['values'],
                                       data['no_data_value'])[0]

            # debug plotting
            plot = Plot()
            plot.add_geometries(
                point,
                polygon,
                self.polygon,
                self.linestring,
            )
            plot.add_array(array, extent=envelope)
            plot.show()
            exit()

            yield point[0], array.min().item()


def command(polygon_path, linestring_path, store_paths, grow, distance):
    linestring_features = Features(linestring_path)
    store = MinimumStore(store_paths)
    for i, polygon_feature in enumerate(Features(polygon_path)):
        # grow a little
        polygon = polygon_feature.geometry().Buffer(grow)

        # query the linestrings
        for linestring_feature in linestring_features.query(polygon):
            linestring = linestring_feature.geometry()

            case = Case(store=store,
                        polygon=polygon,
                        distance=distance,
                        linestring=linestring)

            forward = case.get_levels(Reverse).next()
            reverse = case.get_levels(True)
    return 0


def main():
    """ Call command with args from parser. """
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    return command(**vars(get_parser().parse_args()))

# -*- coding: utf-8 -*-
"""
Find lowest upstream points along a line within a polygon using
combined data from raster stores.
"""

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import argparse
import math

from osgeo import gdal
from osgeo import ogr
import numpy as np

from raster_store import load
from raster_analysis import common

gdal.UseExceptions()
ogr.UseExceptions()

POINT = b'POINT({} {})'
KEY = b'height'


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        'polygon_path',
        metavar='POLYGONS',
        help='Confine search to these polygons.',
    )
    parser.add_argument(
        'linestring_path',
        metavar='LINES',
        help='Assign height to points on these lines.',
    )
    parser.add_argument(
        'store_paths',
        metavar='STORE',
        nargs='+',
        help=('Get raster data from this raster '
              'store (multiple stores possible).'),
    )
    parser.add_argument(
        'path',
        metavar='POINTS',
        help='Path to output (point-)shapefile',
    )
    parser.add_argument(
        '-g', '--grow',
        type=float,
        default=0.5,
        metavar='',
        help='Initial buffer of input polygons (default 0.5).',
    )
    parser.add_argument(
        '-d', '--distance',
        type=float,
        default=15.0,
        metavar='',
        help='Minimum upstream search distance (default 15.0).',
    )
    parser.add_argument(
        '-m', '--multiplier',
        type=float,
        default=1.0,
        metavar='',
        help='Multiplier for distance to polygon (default 1.0).',
    )
    parser.add_argument(
        '-s', '--separation',
        type=float,
        default=1.0,
        metavar='',
        help='Separation between points (default 1.0)',
    )
    parser.add_argument(
        '-p', '--partial',
        help='Partial processing source, for example "2/3"',
    )
    return parser


def point2geometry(point, sr):
    """ Return ogr geometry. """
    return ogr.CreateGeometryFromWkt(POINT.format(*point), sr)


class MinimumStore(object):
    def __init__(self, paths):
        self.stores = [load(path) for path in paths]

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
    def __init__(self, store, polygon, distance,
                 multiplier, separation, linestring):
        self.store = store
        self.polygon = polygon
        self.distance = distance
        self.multiplier = multiplier
        self.linestring = linestring
        self.separation = separation
        self.sr = linestring.GetSpatialReference()

    def get_pairs(self, reverse):
        """ Return generator of point pairs. """
        linestring = self.linestring.Clone()
        linestring.Segmentize(self.separation)
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
            radius = max(
                self.distance,
                self.multiplier * point.Distance(self.polygon.Boundary()),
            )
            circle = point.Buffer(radius)
            rectangle = self.make_rectangle(point=point,
                                            radius=radius,
                                            direction=direction)
            intersection = circle.Intersection(rectangle)

            yield point, self.polygon.Intersection(intersection)

    def get_levels(self, reverse):
        """ Return generator point, level tuples. """
        for point, polygon in self.get_areas(reverse):
            envelope = polygon.GetEnvelope()
            width, height = get_size(envelope)

            if polygon.GetGeometryName() == 'MULTIPOLYGON':
                # keep reference to original collection or segfault
                collection = polygon
                polygon = min(collection, key=point.Distance)
                polygon.AssignSpatialReference(
                    collection.GetSpatialReference(),
                )

            # get data from store
            data = self.store.get_data(
                geom=polygon,
                width=width,
                height=height,
            )
            array = np.ma.masked_equal(
                data['values'], data['no_data_value'],
            ).ravel().compressed()

            # level = array.min().item()
            # print(level)
            # if level < -4.8:
            #     from raster_analysis import plots
            #     plot = plots.Plot()
            #     ma = np.ma.masked_equal(data['values'],
            #                             data['no_data_value'])
            #     plot.add_array(ma[0], extent=polygon.GetEnvelope())
            #     #plot.add_geometries(point, polygon, self.polygon)
            #     plot.add_geometries(point, polygon)
            #     plot.show()

            try:
                yield point, array[array.argsort()[1]].item()
            except IndexError:
                continue


def command(polygon_path, linestring_path, store_paths,
            grow, distance, multiplier, separation, path, partial):
    """ Main """
    linestring_features = common.Source(linestring_path)
    store = MinimumStore(store_paths)
    target = common.Target(
        path=path,
        template_path=linestring_path,
        attributes=[KEY],
    )

    # select some or all polygons
    if partial is None:
        polygon_features = common.Source(polygon_path)
    else:
        polygon_features = common.Source(polygon_path).select(partial)

    for polygon_feature in polygon_features:
        # grow a little
        polygon = polygon_feature.geometry().Buffer(grow)

        # query the linestrings
        for linestring_feature in linestring_features.query(polygon):
            linestring = linestring_feature.geometry()

            case = Case(store=store,
                        polygon=polygon,
                        distance=distance,
                        multiplier=multiplier,
                        separation=separation,
                        linestring=linestring)

            # do
            try:
                points, levels = zip(*list(case.get_levels(False)))
            except (TypeError, ValueError):
                # there are no levels for this case
                continue

            if len(levels) > 1:
                # check upstream
                index = int(len(levels) / 2)
                first = levels[:index]
                last = levels[index:]
                if sum(first) / len(first) > sum(last) / len(last):
                    # do reverse
                    try:
                        points, levels = zip(*list(case.get_levels(True)))
                    except (TypeError, ValueError):
                        # there are no levels for this case
                        continue

            # save
            attributes = dict(linestring_feature.items())
            for point, level in zip(points, levels):
                attributes[KEY] = level
                target.append(geometry=point, attributes=attributes)
    return 0


def main():
    """ Call command with args from parser. """
    return command(**vars(get_parser().parse_args()))

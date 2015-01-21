# -*- coding: utf-8 -*-
"""
Calculate zonal statistics of raster store for a shapefile.

Special stats worth mentioning are 'count' (the amount of pixels
with data), 'size' (the total amount of pixels) and 'p<n>' (the
n-percentile). If the statistic is unsuitable as field name in the target
shape, a different field name can be specified like "myfield:count"
instead of simply "count".
"""

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import argparse
import logging
import math
import re
import sys

from osgeo import gdal
from osgeo import ogr
import numpy as np

from raster_store import stores
from raster_analysis import common

gdal.UseExceptions()
ogr.UseExceptions()

logger = logging.getLogger(__name__)


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        'source_path',
        metavar='SOURCE',
        help='Path to shape with source features.',
    )
    parser.add_argument(
        'store_path',
        metavar='STORE',
        help='Path to raster store.',
    )
    parser.add_argument(
        'target_path',
        metavar='TARGET',
        help='Path to shape with target features.',
    )
    parser.add_argument(
        'statistics',
        metavar='STATISTIC',
        nargs='+',
        help='Stastics to compute, for example "value", "median", "p90".',
    )
    parser.add_argument(
        '-p', '--partial',
        help='Partial processing source, for example "2/3"',
    )
    return parser


def get_kwargs(geometry):
    """ Return get_data_kwargs based on ahn2 resolution. """
    name = geometry.GetGeometryName()
    if name == 'POINT':
        return {}
    if name == 'LINESTRING':
        size = int(math.ceil(geometry.Length() / 0.5))
        return {'size': size}
    if name == 'POLYGON':
        x1, x2, y1, y2 = geometry.GetEnvelope()
        width = int(math.ceil((x2 - x1) / 0.5))
        height = int(math.ceil((y2 - y1) / 0.5))
        return {'width': width, 'height': height}


def command(source_path, store_path, target_path, statistics, partial):
    """ Main """
    if partial is None:
        source_features = common.Source(source_path)
    else:
        source_features = common.Source(source_path).select(partial)

    store = stores.get(store_path)

    # prepare statistics gathering
    actions = {}  # column_name: func_name, args
    percentile = None
    pattern = re.compile('(p)([0-9]+)')
    for statistic in statistics:
        # allow for different column name
        try:
            column, statistic = statistic.split(':')
        except ValueError:
            column = statistic

        # determine the action
        match = pattern.match(statistic)
        if pattern.match(statistic):
            percentile = int(match.groups()[1])
            actions[column] = 'percentile', [percentile]
        elif statistic == 'value':
            actions[column] = 'item', []
        else:
            actions[column] = statistic, []

    target = common.Target(
        path=target_path,
        template_path=source_path,
        attributes=actions,
    )

    for source_feature in source_features:
        # retrieve raster data
        geometry = source_feature.geometry()
        kwargs = get_kwargs(geometry)
        data = store.get_data_direct(geometry, **kwargs)
        masked = np.ma.masked_equal(data['values'],
                                    data['no_data_value'])
        compressed = masked.compressed()

        # apppend statistics
        attributes = source_feature.items()
        for column, (action, args) in actions.items():
            try:
                if hasattr(np.ma, action):
                    value = getattr(np.ma, action)(masked, *args)
                else:
                    value = getattr(np, action)(compressed, *args)
                value = np.nan if np.ma.is_masked(value) else value
            except ValueError:
                value = np.nan
            attributes[column] = value

        target.append(geometry=geometry, attributes=attributes)
    return 0


def main():
    """ Call command with args from parser. """
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    return command(**vars(get_parser().parse_args()))

# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans, see LICENSE.rst.
"""
Extract layers from a raster store using a geometry. For instructions
to do this from a 3Di result, have a look at the README:

https://github.com/nens/raster-analysis/blob/master/README.rst
"""

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import argparse
import collections
import logging
import sys

from osgeo import gdal_array
import numpy as np

from raster_store import stores
from raster_store import datasets

from raster_analysis.common import gdal
from raster_analysis.common import ogr


DRIVER_OGR_MEMORY = ogr.GetDriverByName(str('Memory'))
DRIVER_GDAL_MEM = gdal.GetDriverByName(str('mem'))
DRIVER_GDAL_GTIFF = gdal.GetDriverByName(str('gtiff'))
POLYGON = 'POLYGON (({x1} {y1},{x2} {y1},{x2} {y2},{x1} {y2},{x1} {y1}))'

# argument defaults
CELLSIZE = 0.5, 0.5
TIME = '1970-01-01T00:00:00Z'

Tile = collections.namedtuple('Tile', ['width',
                                       'height',
                                       'origin',
                                       'polygon',
                                       'geo_transform'])


def get_projection(sr):
    """ Return simple userinput string for spatial reference, if any. """
    key = str('GEOGCS') if sr.IsGeographic() else str('PROJCS')
    return '{name}:{code}'.format(name=sr.GetAuthorityName(key),
                                  code=sr.GetAuthorityCode(key))


def create_dataset(geometry, cellsize, fillvalue, dtype, path):
        """ The big sparse target dateset"""
        # properties
        a, b, c, d = cellsize[0], 0.0, 0.0, -cellsize[1]
        x1, x2, y1, y2 = geometry.GetEnvelope()
        p, q = a * (x1 // a), d * (y2 // d)

        width = -int((p - x2) // a)
        height = -int((q - y1) // d)
        geo_transform = p, a, b, q, c, d
        projection = geometry.GetSpatialReference().ExportToWkt()

        # data type from store, no data value max of that type
        data_type = gdal_array.NumericTypeCodeToGDALTypeCode(dtype)
        no_data_value = fillvalue

        # create
        options = ['TILED=YES',
                   'BIGTIFF=YES',
                   'SPARSE_OK=TRUE',
                   'COMPRESS=DEFLATE']
        dataset = DRIVER_GDAL_GTIFF.Create(
            path, width, height, 1, data_type, options,
        )
        dataset.SetProjection(projection)
        dataset.SetGeoTransform(geo_transform)
        dataset.GetRasterBand(1).SetNoDataValue(no_data_value)

        return dataset


class Index(object):
    """
    Iterates the indices into the target dataset.
    """
    def __init__(self, dataset, geometry):
        """
        Rasterize geometry into target dataset extent to find relevant
        blocks.
        """
        # make a dataset
        w, h = dataset.GetRasterBand(1).GetBlockSize()
        p, a, b, q, c, d = dataset.GetGeoTransform()
        index = DRIVER_GDAL_MEM.Create(
            '',
            (dataset.RasterXSize - 1) // w + 1,
            (dataset.RasterYSize - 1) // h + 1,
            1,
            gdal.GDT_Byte,
        )

        geo_transform = p, a * w, b * h, q, c * w, d * h
        index.SetProjection(dataset.GetProjection())
        index.SetGeoTransform(geo_transform)

        # rasterize where geometry is
        datasource = DRIVER_OGR_MEMORY.CreateDataSource('')
        sr = geometry.GetSpatialReference()
        layer = datasource.CreateLayer(str('geometry'), sr)
        layer_defn = layer.GetLayerDefn()
        feature = ogr.Feature(layer_defn)
        feature.SetGeometry(geometry)
        layer.CreateFeature(feature)
        gdal.RasterizeLayer(
            index,
            [1],
            layer,
            burn_values=[1],
            options=['all_touched=true'],
        )

        # remember some of this
        self.dataset_size = dataset.RasterXSize, dataset.RasterYSize
        self.geo_transform = dataset.GetGeoTransform()
        self.indices = index.ReadAsArray().nonzero()
        self.block_size = w, h
        self.sr = sr

    def __len__(self):
        return len(self.indices[0])

    def _get_indices(self, serial):
        """ Return indices into dataset. """
        w, h = self.block_size
        W, H = self.dataset_size
        y, x = self.indices[0][serial].item(), self.indices[1][serial].item()
        x1 = w * x
        y1 = h * y
        x2 = min(W, (x + 1) * w)
        y2 = min(H, (y + 1) * h)
        return x1, y1, x2, y2

    def _get_extent(self, indices):
        """ Convert indices to extent. """
        u1, v1, u2, v2 = indices
        p, a, b, q, c, d = self.geo_transform
        x1 = p + a * u1 + b * v1
        y2 = q + c * u1 + d * v1
        x2 = p + a * u2 + b * v2
        y1 = q + c * u2 + d * v2
        return x1, y1, x2, y2

    def _get_polygon(self, extent):
        """ Return polygon for extent. """
        x1, y1, x2, y2 = extent
        wkt = POLYGON.format(x1=x1, y1=y1, x2=x2, y2=y2)
        return ogr.CreateGeometryFromWkt(wkt, self.sr)

    def _get_geo_transform(self, extent):
        """ Return geo tranform for extent. """
        x1, y1, x2, y2 = extent
        p, a, b, q, c, d = self.geo_transform
        return x1, a, b, y2, c, d

    def __iter__(self):
        for serial in range(len(self)):
            x1, y1, x2, y2 = indices = self._get_indices(serial)
            width, height, origin = x2 - x1, y2 - y1, (x1, y1)
            extent = self._get_extent(indices)
            polygon = self._get_polygon(extent)
            geo_transform = self._get_geo_transform(extent)
            yield Tile(width=width,
                       height=height,
                       origin=origin,
                       polygon=polygon,
                       geo_transform=geo_transform)


def burn(dataset, geometry, value):
    """ Burn value where geometry is into dataset. """
    sr = geometry.GetSpatialReference()

    # put geometry into temporary layer
    datasource = DRIVER_OGR_MEMORY.CreateDataSource('')
    layer = datasource.CreateLayer(str(''), sr)
    layer_defn = layer.GetLayerDefn()
    feature = ogr.Feature(layer_defn)
    feature.SetGeometry(geometry)
    layer.CreateFeature(feature)

    # burn no data
    burn_values = [value]
    gdal.RasterizeLayer(dataset, [1], layer, burn_values=burn_values)


def command(shape_path, store_path, target_path, cellsize, time):
    """
    Prepare and extract the first feature of the first layer.
    """
    # process store
    store = stores.get(store_path)
    dtype = np.dtype(store.dtype).type
    fillvalue = store.fillvalue

    # process shape
    datasource = ogr.Open(shape_path)
    layer = datasource[0]

    feature = layer[0]
    geometry = feature.geometry()

    # process target
    target = create_dataset(dtype=dtype,
                            path=target_path,
                            geometry=geometry,
                            cellsize=cellsize,
                            fillvalue=fillvalue)

    # prepare
    gdal.TermProgress_nocb(0)
    index = Index(target, geometry)
    sr = layer.GetSpatialRef()
    no_data_value = target.GetRasterBand(1).GetNoDataValue()

    # work
    total = len(index)
    for count, tile in enumerate(index, 1):
        # get data
        kwargs = {'sr': sr,
                  'start': time,
                  'width': tile.width,
                  'height': tile.height,
                  'geom': tile.polygon.ExportToWkt()}
        data = store.get_data(**kwargs)

        # make source
        array = data['values']
        kwargs = {'projection': sr.ExportToWkt(),
                  'geo_transform': tile.geo_transform,
                  'no_data_value': no_data_value}

        with datasets.Dataset(array, **kwargs) as source:

            # set pixels outside geometry to 'no data'
            outside = tile.polygon.Difference(geometry)
            burn(dataset=source, geometry=outside, value=no_data_value)

            # write to target
            p1, q1 = tile.origin
            DRIVER_GDAL_MEM.CreateCopy('', source)
            target.WriteRaster(
                p1, q1, tile.width, tile.height,
                source.ReadRaster(0, 0, tile.width, tile.height),
            )

        gdal.TermProgress_nocb(count / total)


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', '--verbose', action='store_true')
    # main
    parser.add_argument('shape_path',
                        metavar='SHAPE')
    parser.add_argument('store_path',
                        metavar='STORE')
    parser.add_argument('target_path',
                        metavar='OUTPUT')
    # options
    parser.add_argument('-c', '--cellsize',
                        nargs=2,
                        type=float,
                        default=CELLSIZE,
                        help='Cellsize. Default: {} {}'.format(*CELLSIZE))
    parser.add_argument('-t', '--time',
                        default=TIME, dest='time',
                        help='ISO-8601 time. Default: "{}"'.format(TIME))
    return parser


def main():
    """ Call command with args from parser. """
    # logging
    kwargs = vars(get_parser().parse_args())
    if kwargs.pop('verbose'):
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(stream=sys.stderr, level=level, format='%(message)s')

    # run
    command(**kwargs)


if __name__ == '__main__':
    exit(main())


if __name__ == '__main__':
    exit(main())

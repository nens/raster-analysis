# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans, see LICENSE.rst.
""" Extract layers from a raster store using a geometry. """

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import argparse
import collections

from osgeo import gdal
from osgeo import ogr
from osgeo import osr

from raster_store import stores

gdal.UseExceptions()
ogr.UseExceptions()
osr.UseExceptions()
operations = {}

# Version management for outdated warning
VERSION = 20

GITHUB_URL = ('https://raw.github.com/nens/'
              'raster-tools/master/raster_tools/extract.py')

DRIVER_OGR_MEMORY = ogr.GetDriverByName(str('Memory'))
DRIVER_OGR_SHAPE = ogr.GetDriverByName(str('ESRI Shapefile'))
DRIVER_GDAL_MEM = gdal.GetDriverByName(str('mem'))
DRIVER_GDAL_GTIFF = gdal.GetDriverByName(str('gtiff'))
DTYPES = {'u1': gdal.GDT_Byte,
          'u2': gdal.GDT_UInt16,
          'u4': gdal.GDT_UInt32,
          'i2': gdal.GDT_Int16,
          'i4': gdal.GDT_Int32,
          'f4': gdal.GDT_Float32}

POLYGON = 'POLYGON (({x1} {y1},{x2} {y1},{x2} {y2},{x1} {y2},{x1} {y1}))'

# argument defaults
CELLSIZE = 0.5, 0.5
DTYPE = 'f4'
PROJECTION = 'EPSG:28992'
TIMESTAMP = '1970-01-01T00:00:00Z'

Tile = collections.namedtuple('Tile', ['width',
                                       'height',
                                       'origin',
                                       'serial',
                                       'polygon'])


class Preparation(object):
    """
    Preparation.
    """
    def __init__(self, feature, layer, store, path, **kwargs):
        """ Prepare a lot. """
        self.projection = kwargs.pop('projection')
        self.cellsize = kwargs.pop('cellsize')

        self.wkt = osr.GetUserInputAsWKT(str(self.projection))
        self.sr = osr.SpatialReference(self.wkt)

        self.path = path
        self.geometry = self._prepare_geometry(feature)

        self.dataset = self._create_dataset()
        self.index = Index(self.dataset, self.geometry)

    def _prepare_geometry(self, feature):
        """ Transform geometry if necessary. """
        geometry = feature.geometry()
        sr = geometry.GetSpatialReference()
        if sr:
            geometry.Transform(osr.CoordinateTransformation(sr, self.sr))
        return geometry

    def _create_dataset(self, name, path):
        """ The big sparse target dateset"""
        # properties
        a, b, c, d = self.cellsize[0], 0.0, 0.0, -self.cellsize[1]
        x1, x2, y1, y2 = self.geometry.GetEnvelope()
        p, q = a * (x1 // a), d * (y2 // d)

        width = -int((p - x2) // a)
        height = -int((q - y1) // d)
        geo_transform = p, a, b, q, c, d
        projection = self.wkt

        # create
        options = ['TILED=YES',
                   'BIGTIFF=YES',
                   'SPARSE_OK=TRUE',
                   'COMPRESS=DEFLATE'],
        dataset = DRIVER_GDAL_GTIFF.Create(
            path, width, height, 1, self.store.dtype, options,
        )
        dataset.SetProjection(projection)
        dataset.SetGeoTransform(geo_transform)
        dataset.GetRasterBand(1).SetNoDataValue(self.store.fillvalue)
        return dataset

    def get_source(self):
        """ Return dictionary of source objects. """
        source = Source(time=self.time,
                        index=self.index,
                        store=self.store,
                        projection=self.projection)
        return source

    def get_target(self, source):
        """ Return target object. """
        target = Target(source=source,
                        index=self.index,
                        dataset=self.dataset,
                        geometry=self.geometry)
        return target


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
        self.block_size = w, h
        self.dataset_size = dataset.RasterXSize, dataset.RasterYSize
        self.geo_transform = dataset.GetGeoTransform()
        self.indices = index.ReadAsArray().nonzero()

    def get_indices(self, serial):
        """ Return indices into dataset. """
        w, h = self.block_size
        W, H = self.dataset_size
        y, x = self.indices[0][serial].item(), self.indices[1][serial].item()
        x1 = w * x
        y1 = h * y
        x2 = min(W, (x + 1) * w)
        y2 = min(H, (y + 1) * h)
        return x1, y1, x2, y2

    def get_polygon(self, indices):
        """ Return ogr wkb polygon for a rectangle. """
        u1, v1, u2, v2 = indices
        p, a, b, q, c, d = self.geo_transform
        x1 = p + a * u1 + b * v1
        y1 = q + c * u1 + d * v1
        x2 = p + a * u2 + b * v2
        y2 = q + c * u2 + d * v2
        return POLYGON.format(x1=x1, y1=y1, x2=x2, y2=y2)

    def __len__(self):
        return len(self.indices[0])

    def __nonzero__(self):
        return len(self) > self.resume

    def __iter__(self):
        for serial in range(self.resume, len(self)):
            x1, y1, x2, y2 = indices = self.get_indices(serial)
            width, height, origin = x2 - x1, y2 - y1, (x1, y1)
            polygon = self.get_polygon(indices)
            yield Tile(width=width,
                       height=height,
                       origin=origin,
                       serial=serial,
                       polygon=polygon)


class Source(object):
    """
    Factory of source chunks.
    """
    def __init__(self, projection, path, time, index):
        """  """
        self.projection = projection
        self.store = stores.get(path)
        self.time = time
        self.index = index

    def get_chunk(self, block):
        """ Return the target chunk for a source block. """
        kwargs = {'time': self.time, 'sr': self.projection}
        return Chunk(store=self.store, block=block, **kwargs)


class Chunk():
    """
    Represents a remote chunk of data.
    """
    def __init__(self, kwargs, block, store):
        """ Prepare url. """
        # extend kwargs with
        self.kwargs = {'geom': block.tile.polygon,
                       'width': block.tile.width,
                       'height': block.tile.height}
        self.kwargs.update(kwargs)

        # remember some
        self.block = block
        self.store = store

    def load(self):
        """ Query store using kwargs and keep the result. """
        self.block.input = self.store.get_data(**self.kwargs)

        # retrieve file into gdal vsimem system
        # vsi_path = '/vsimem/{}'.format(self.key)
        # vsi_file = gdal.VSIFOpenL(str(vsi_path), str('w'))
        # url_file = urlopen(self.url)
        # size = int(url_file.info().get('content-length'))
        # gdal.VSIFWriteL(url_file.read(), size, 1, vsi_file)
        # gdal.VSIFCloseL(vsi_file)

        # copy and remove
        # dataset = gdal.Open(vsi_path)
        # self.block.input = DRIVER_GDAL_MEM.CreateCopy('', dataset)
        # dataset = None
        # gdal.Unlink(vsi_path)


class Target(object):
    """
    Factory of target blocks.
    """
    def __init__(self, rpath, index, source, dataset, geometry, operation):
        self.index = index
        self.source = source
        self.dataset = dataset
        self.geometry = geometry

    def __len__(self):
        """ Returns the featurecount. """
        return len(self.index)

    def __iter__(self):
        """ Yields blocks. """
        for tile in self.index:
            block = Block(tile=tile,
                          source=self.source,
                          datasets=self.datasets,
                          geometry=self.geometry)
            yield block


class Block(object):
    """ Self saving local chunk of data. """
    def __init__(self, tile, rpath, source, dataset, geometry, operation):
        self.tile = tile
        self.rpath = rpath
        self.source = source
        self.dataset = dataset
        self.operation = operation
        self.geometry = self._create_geometry(tile=tile, geometry=geometry)
        self.chunks = self.source.get_chunks(self)
        self.input = None  # load method puts appropriate gdal dataset here

    def _create_geometry(self, tile, geometry):
        """
        Return ogr geometry that is the part of this block that's masked.
        """
        sr = geometry.GetSpatialReference()
        polygon = ogr.CreateGeometryFromWkt(tile.polygon, sr)
        difference = polygon.Difference(geometry)
        difference.AssignSpatialReference(sr)
        return difference

    def _mask(self, dataset):
        """ Mask dataset where outside geometry. """
        wkt = dataset.GetProjection()
        no_data_value = dataset.GetRasterBand(1).GetNoDataValue()
        datasource = DRIVER_OGR_MEMORY.CreateDataSource('')
        sr = osr.SpatialReference(wkt)
        layer = datasource.CreateLayer(str('blocks'), sr)
        layer_defn = layer.GetLayerDefn()
        feature = ogr.Feature(layer_defn)
        feature.SetGeometry(self.geometry)
        layer.CreateFeature(feature)
        gdal.RasterizeLayer(dataset, [1], layer, burn_values=[no_data_value])

    def _write(self, source, target):
        """ Write dataset into block. """
        p1, q1 = self.tile.origin
        target.WriteRaster(
            p1, q1, self.tile.width, self.tile.height,
            source.ReadRaster(0, 0, source.RasterXSize, source.RasterYSize),
        )

    def __iter__(self):
        """ Yield chunks. """
        for chunk in self.chunks.values():
            yield chunk

    def save(self):
        """
        Cut out and save block.
        """
        # turn self.input into some gdal dataset like self.output
        # create
        no_data_value = self.no_data_value[self.name]
        data_type = self.data_type[self.name]
        result = make_dataset(template=datasets[self.name],
                              data_type=data_type,
                              no_data_value=no_data_value)
        # read
        band = datasets[self.name].GetRasterBand(1)
        data = band.ReadAsArray().astype('f8')<F7>
        mask = ~band.GetMaskBand().ReadAsArray().astype('b1')
        data[mask] = no_data_value
        # write
        self.output.GetRasterBand(1).WriteArray(data)

        # mask
        self._mask(self.output)
        self._write(source=self.output,
                    target=self.dataset)

        with open(self.rpath, 'w') as resume_file:
            resume_file.write(str(self.tile.serial + 1))


def make_dataset(template, data_type, no_data_value):
    """
    Return dataset with dimensions, geo_transform and projection
    from template but data_type and no_data_value from arguments.
    """
    dataset = DRIVER_GDAL_MEM.Create(
        '',
        template.RasterXSize,
        template.RasterYSize,
        template.RasterCount,
        data_type,
    )
    dataset.SetProjection(template.GetProjection())
    dataset.SetGeoTransform(template.GetGeoTransform())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(no_data_value)
    band.Fill(no_data_value)
    return dataset


def make_polygon(x1, y2, x2, y1):
    """ Return ogr wkb polygon for a rectangle. """
    polygon = ogr.CreateGeometryFromWkt(
        POLYGON.format(x1=x1, y1=y1, x2=x2, y2=y2),
    )
    return polygon



def extract(preparation):
    """
    Extract for a single feature.
    """
    source = preparation.get_source()
    target = preparation.get_target(source)

    total = len(target)
    gdal.TermProgress_nocb(0)

    for block in target:
        for chunk in block:
            chunk.load()

        

    while True:
        # fetch loaded chunks
        try:
            chunk, thread2 = queue.get()
            thread2.join()  # this makes sure the chunk is laoded
        except TypeError:
            break

        # save complete blocks
        if len(chunk.block.chunks) == len(chunk.block.inputs):
            chunk.block.save()
            gdal.TermProgress_nocb((chunk.block.tile.serial + 1) / total)

    thread1.join()


def check_version():
    """
    Check if this is the highest available version of the script.
    """
    url_file = urlopen(GITHUB_URL)
    lines = url_file.read().decode('utf-8').split('\n')
    url_file.close()

    for l in lines:
        if str(l).startswith('VERSION ='):
            remote_version = int(l.split('=')[-1].strip())
            break
    if remote_version > VERSION:
        print('This script is outdated. Get the latest at:\n{}'.format(
            GITHUB_URL,
        ))
        exit()


def command(shape_path, store_path, output_path, **kwargs):
    """
    Prepare and extract the first feature of the first layer.
    """
    datasource = ogr.Open(shape_path)
    store = stores.get(store_path)
    layer = datasource[0]
    feature = layer[0]
    preparation = Preparation(layer=layer,
                              feature=feature,
                              store=store,
                              path=path, **kwargs)
    extract(preparation)


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    # main
    parser.add_argument('shape_path',
                        metavar='SHAPE')
    parser.add_argument('store_path',
                        metavar='STORE')
    parser.add_argument('output_path',
                        metavar='OUTPUT')
    # options
    parser.add_argument('-c', '--cellsize',
                        nargs=2,
                        type=float,
                        default=CELLSIZE,
                        help='Cellsize. Default: {} {}'.format(*CELLSIZE))
    parser.add_argument('-p', '--projection',
                        default=PROJECTION,
                        help='Projection. Default: "{}"'.format(PROJECTION))
    parser.add_argument('-t', '--timestamp',
                        default=TIMESTAMP, dest='time',
                        help='Timestamp. Default: "{}"'.format(TIMESTAMP))
    return parser


def main():
    """ Call command with args from parser. """
    kwargs = vars(get_parser().parse_args())
    command(**kwargs)


if __name__ == '__main__':
    exit(main())

How to calculate interpolated depth
===================================

1. Know your bathymetry resolution::

    $ gdalinfo dem.tif | grep 'Pixel Size'

2. Use it with the 'store-3di' command to build a special interplating
   raster-store-like object from the netcdf the at the correct resolution::

    $ mkdir raster
    $ store-3di -b raster/storage/bathymetry -c 2 2 subgrid_map.nc raster/storage raster/config

3. Build an ordinary raster-store for the bathymetry::

    $ store-put dem.tif raster/storage/bathymetry

4. Check available period and frames using 'store-info'::

    $ store-info raster/config/s1-dtri

5. Now you are ready to create (interpolated) geotiffs for 3Di result. For example::

    $ lextract -c 5 5 -t 2014-07-28T18:00:00 shape raster/config/s1-quad.json output/s1-quad.tif
    $ lextract -c 2 2 -t 2014-07-28T18:00:00 shape raster/config/s1-dtri.json output/s1-dtri.tif
    $ lextract -c 1 1 -t 2014-07-28T18:00:00 shape raster/config/depth-dtri.json output/depth-dtri.tif

A note on the available outputs:

- output/bathymetry: The bathymetry
- output/s1-quad:    the s1 variable per quad
- output/s1-dtri:    the s1 variable interpolated
- output/depth-quad: s1-minus-bathymetry, per quad, masked when less than zero.
- output/depth-dtri: s1-minus-bathymetry, inteprolated, masked when less than zero.

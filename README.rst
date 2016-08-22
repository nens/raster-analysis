How to calculate interpolated depth
===================================

1. Know your bathymetry resolution::

    $ gdalinfo dem.tif | grep 'Pixel Size'

2. Use it with the 'store-3di'\* command to build a special interpolating
   raster-store-like object from the netcdf the at the correct resolution::

    $ mkdir raster
    $ store-3di -b raster/storage/bathymetry -c 2 subgrid_map.nc raster/storage raster/config

3. Build an ordinary raster-store for the bathymetry using 'store-put'\*::

    $ store-put dem.tif raster/storage/bathymetry

4. Check the available period and frames using 'store-info'\*::

    $ store-info raster/config/s1-dtri

5. Now you are ready to create (interpolated) geotiffs for your 3Di
   result. You need a shapefile to provide the script with an area of
   interest. For example::

    $ mkdir output
    $ lextract -c 5 5 -t 2014-07-28T18:00:00 shape raster/config/s1-quad output/s1-quad.tif
    $ lextract -c 1 1 -t 2014-07-28T18:00:00 shape raster/config/depth-dtri output/depth-dtri.tif

A note on the available configurations:

- raster/config/bathymetry: The bathymetry
- raster/config/s1-quad:    the s1 variable per quad
- raster/config/s1-dtri:    the s1 variable interpolated
- raster/config/depth-quad: s1-minus-bathymetry, per quad, masked when less than zero.
- raster/config/depth-dtri: s1-minus-bathymetry, interpolated, masked when less than zero.

\*store-3di, store-put and store-info are commands from the nens/raster-store library.

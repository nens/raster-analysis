How to calculate interpolated depth
===================================

1. Know your bathymetry resolution::

    $ gdalinfo dem.tif | grep 'Pixel Size'

2. Build an ordinary raster-store for the bathymetry using 'store-put'\*::

    $ mkdir raster
    $ store-put dem.tif raster/bathymetry

3. Use it with the 'store-3di'\* command to build a special interpolating
   raster-store-like object from the netcdf the at the correct resolution::

    $ store-3di -b raster/bathymetry -c 2 subgrid_map.nc raster/storage raster/config dem.tif

4. Check the available period and frames using 'store-info'\*::

    $ store-info raster/config/s1-dtri

5. Now you are ready to create (interpolated) geotiffs for your 3Di
   result. You need a shapefile to provide the script with an area of
   interest. For example::

    $ mkdir output
    $ lextract -c 5 5 -t 2014-07-28T18:00:00 shape raster/config/s1-quad output/s1-quad.tif
    $ lextract -c 1 1 -t 2014-07-28T18:00:00 shape raster/config/depth-dtri output/depth-dtri.tif

A note on the available configurations:

- raster/config/bathymetry:     the bathymetry
- raster/config/s1-quad:        the waterlevel (s1) per quad
- raster/config/s1-dtri:        the waterlevel (s1) per quad, interpolated
- raster/config/depth-quad:     waterdepth (s1 - bathymetry) per quad
- raster/config/depth-dtri:     waterdepth (s1 - bathymetry) per quad, interpolated

Also available are the variables derived from the per-quad maxima of the waterlevel:

- raster/config/s1-max-quad:    maximum waterlevel (s1) per quad
- raster/config/s1-max-dtri:    maximum waterlevel (s1) per quad, interpolated
- raster/config/depth-max-quad: maximum waterdepth (s1 - bathymetry) per quad
- raster/config/depth-max-dtri: maximum waterdepth (s1 - bathymetry) per quad, interpolated

Here are some more exotic derivatives:

- raster/config/arrival:            Arrival time in seconds
- raster/config/rise-velocity-quad: Rise velocity in meters per second
- raster/config/ucr-max-quad:       Maximum flow velocity in meters per second
- raster/config/vol-first-quad:     Timestep(?) of arrival of first water in quad

\*store-3di, store-put and store-info are commands from the nens/raster-store library.

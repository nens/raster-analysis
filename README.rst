How to calculate interpolated depth
===================================

1. Know your bathymetry resolution::

    $ gdalinfo dem.tif | grep 'Pixel Size'

2. Use it with the 'store-3di'\* command to build a set of derived 3Di
   results, such as interpolated depth, maximum waterlevel, arrival times
   and many more::

    $ mkdir raster
    $ store-3di subgrid_map.nc dem.tif raster/storage raster/config -c 2 -a

   here optional parameter '-c 2' indicates a cellsize of 2 and '-a'
   enables the costly calculation of arrival times. Cellsize determines
   the level of detail for interpolated variables and the arrival times.

3. Check the available period and frames using 'store-info'\*::

    $ store-info raster/config/s1-dtri

4. Now you are ready to create geotiffs for your 3Di result. You need
   a shapefile to provide the script with an area of interest. For example::

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

- raster/config/arrival:            Arrival time in seconds\*\*
- raster/config/rise-velocity-quad: Rise velocity in meters per second
- raster/config/ucr-max-quad:       Maximum flow velocity in meters per second
- raster/config/vol-first-quad:     Timestep(?) of arrival of first water in quad

\*store-3di, store-put and store-info are commands from the nens/raster-store library.

\*\*only with the '-a' or '--arrival' option.

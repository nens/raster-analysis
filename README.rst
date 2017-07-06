How to calculate interpolated depth
===================================

1. Know your bathymetry resolution::

    $ gdalinfo dem.tif | grep 'Pixel Size'

2. Use it with the 'store-3di'\* command to build a set of derived 3Di
   results, such as interpolated depth, maximum waterlevel, arrival times
   and many more::

    $ mkdir raster
    $ store-3di subgrid_map.nc dem.tif raster/storage raster/config -c 2 -a -f flow_aggregate.nc

   here the optional parameter '-c 2' indicates a cellsize of 2 and '-a'
   enables the costly calculation of arrival times. Cellsize determines the
   level of detail for interpolated variables and the arrival times. Any time
   aggregations found in the optional flow_aggregate file will be available in
   the results as well.

3. Check the available period and frames using 'store-info'\*::

    $ store-info raster/config/s1-dtri

4. Now you are ready to create geotiffs for your 3Di result. You need
   a shapefile to provide the script with an area of interest. For example::

    $ mkdir output
    $ lextract -c 5 5 -t 2014-07-28T18:00:00 shape raster/config/s1-quad output/s1-quad.tif
    $ lextract -c 1 1 -t 2014-07-28T18:00:00 shape raster/config/depth-dtri output/depth-dtri.tif

A note on the available configurations:

- raster/config/bathymetry:     bathymetry
- raster/config/s1-quad:        waterlevel (s1) with original quad layout
- raster/config/s1-dtri:        waterlevel (s1) interpolated between quads
- raster/config/depth-quad:     s1-quad minus bathymetry
- raster/config/depth-dtri:     s1-dtri minus bathymetry

Also available are the variables derived from the per-quad maxima of the waterlevel:

- raster/config/s1-max-quad:    temporal maximum of s1-quad
- raster/config/s1-max-dtri:    temporal maximum of s1-max-dtri
- raster/config/depth-max-quad: temporal maximum of depth-quad
- raster/config/depth-max-dtri: temporal maximum of depth-dtri

Here are some more exotic derivatives:

- raster/config/depth-first-dtri:   Arrival time in seconds\*\*
- raster/config/rise-velocity-quad: Rise velocity in meters per second
- raster/config/ucr-max-quad:       Maximum flow velocity in meters per second
- raster/config/vol-first-quad:     Timestep(?) of arrival of first water in quad

Furthermore, when supplying a flow-aggregate.nc file\*\*\*, a numer of
extra wrappers will be made available, depending on the contents of that
file. These will be (where [stat] could be something like 'avg'):

- raster/config/s1_[stat]-max-quad:    maximum waterlevel (s1) per quad
- raster/config/s1_[stat]-max-dtri:    maximum waterlevel (s1) per quad, interpolated
- raster/config/depth_[stat]-max-quad: maximum waterdepth (s1 - bathymetry) per quad
- raster/config/depth_[stat]-max-dtri: maximum waterdepth (s1 - bathymetry) per quad, interpolated

\*store-3di and store-info are commands from the nens/raster-store library.

\*\*only with the '-a' or '--arrival' option.

\*\*\*with the '-f' or '--flow-aggregate' option.

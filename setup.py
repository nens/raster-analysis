from setuptools import setup

version = '0.2.dev0'

long_description = '\n\n'.join([
    open('README.rst').read(),
    open('CREDITS.rst').read(),
    open('CHANGES.rst').read(),
    ])

install_requires = [
    'gdal',
    'raster-store',
    'scipy',
    'setuptools',
    ],

tests_require = [
    'nose',
    'coverage',
    ]

setup(name='raster-analysis',
      version=version,
      description="Various routines for analysis of rasters in raster stores.",
      long_description=long_description,
      # Get strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[],
      keywords=[],
      author='Arjan Verkerk',
      author_email='arjan.verkerk@nelen-schuurmans.nl',
      url='',
      license='GPL',
      packages=['raster_analysis'],
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      tests_require=tests_require,
      extras_require={'test': tests_require},
      entry_points={
          'console_scripts': [
              'median = raster_analysis.median:main',
              'zonal = raster_analysis.zonal:main',
              'centroid = raster_analysis.centroid:main',
              'upstream = raster_analysis.upstream:main',
              'lextract = raster_analysis.lextract:main',
          ]},
      )

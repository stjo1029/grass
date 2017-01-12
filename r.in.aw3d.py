#!/usr/bin/env python
############################################################################
#
# MODULE:       r.in.aw3d
# AUTHOR(S):    Jonas Strobel, intern at mundialis and terrestris, Bonn
# PURPOSE:      r.in.aw3d
# COPYRIGHT:    (C) 2017 by stjo, and the GRASS Development Team
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
############################################################################

#%module
#% description: Creates a DEM from 1 arcsec Alos World 3D tiles.
#% keyword: Raster, Import
#%end
#%option G_OPT_F_INPUT
#% description: Name of input ALOS World 3D file
#%end
#%option G_OPT_R_OUTPUT
#% description: Name of output file
#%end
#%option
#% key: username_jaxa
#% type: string
#% required: no
#% multiple: no
#% description: Username for authentication at JAXA server
#%end
#%option
#% key: password_jaxa
#% type: string
#% required: no
#% multiple: no
#% description: Password for authentication at JAXA server
#%end
#%option
#% key: username_srtm
#% type: string
#% required: no
#% multiple: no
#% description: Username for authentication at SRTM server
#%end
#%option
#% key: password_srtm
#% type: string
#% required: no
#% multiple: no
#% description: Password for authentication at SRTM server
#%end
#%option
#% key: settings
#% type: string
#% required: no
#% multiple: no
#% label: Full path to settings file
#% description: Settings for authentication at JAXA server and SRTM server
#%end
#%option
#% key: memory
#% type: integer
#% required: no
#% multiple: no
#% description: Memory in MB for interpolation (values 0-2047)
#% answer: 300
#%end
#%option
#% key: random
#% type: integer
#% required: no
#% multiple: no
#% description: percentage of random points (values 0 - 100)
#% answer: 30
#%end
#%option
#% key: value
#% type: integer
#% required: no
#% multiple: no
#% description: value of dataholes
#% answer: -9999
#%end

proj = ''.join([
    'GEOGCS[',
    '"wgs84",',
    'DATUM["WGS_1984",SPHEROID["wgs84",6378137,298.257223563],TOWGS84[0.000000,0.000000,0.000000]],',
    'PRIMEM["Greenwich",0],',
    'UNIT["degree",0.0174532925199433]',
    ']'])


import sys
import grass.script as grass
import os
import atexit
import urllib
import urllib2
import time
from cookielib import CookieJar

global GDAL

try:
    import osgeo.gdal as gdal
    GDAL = True
except ImportError:
    try:
        import gdal
        GDAL = True
    except ImportError:
        GDAL = False
        print('WARNING: Python GDAL library not found, please install it')
        
def check(home):
    # check if the folder is writeable
    if os.access(home, os.W_OK):
        return True
    else:
        grass.fatal(_("Folder to write downloaded files does not "
                      "exist or is not writeable"))
            
        
def grass_commands(input, username_srtm, password_srtm, random, value, output, memory):
#run the grass commands
    grass.run_command("r.in.gdal", 
                      input = input, 
                      output = output, 
                      memory = memory)
    grass.run_command("g.rename",
                      raster = output,"jaxa_patch")

    grass.run_command("g.region",
                      raster = "jaxa_patch")

#TODO 2 passwoerter, kommandozeile nicht unbedingt sicher, optional siehe r.modis.download 
    grass.run_command("r.in.srtm.region",
                      user = username_srtm,
                      password = password_srtm,
                      flags = 1,
                      output = 'srtm_patch')

# mask calculation to show dataholes
    grass.run_command("r.mapcalc",
                      expression = "mask = if(jaxa_patch==-9999,1,null())")

    grass.run_command("g.region",
                      raster = "mask")

# buffer around mask (2 px)
    grass.run_command("r.buffer",
                      input = "mask",
                      output = "buffer_mask",
                      distances = 60,
                      units = "meters")

    grass.run_command("g.region",
                      raster = "buffer_mask")

# mapcalc for buffer fill with Values from jaxa data
    grass.run_command("r.mapcalc",
                      expression = "buffer_fill = if(buffer_mask==2,jaxa_patch,null())")

    grass.run_command("r.mask",
                      raster = "jaxa_patch",
                      maskcats = value)

#set region to srtm
    grass.run_command("g.region",
                      raster = "srtm_patch")

# random points from srtm data
#   DONE  TODO Werte oben definieren, das man sie als Variablen nutzen kann
    grass.run_command("r.random",
                      input = "srtm_patch",
                      npoints = random + "%",
                      raster = "random_points")

# deactivate mask
    grass.run_command("r.mask",
                      flags = 'r')

    grass.run_command("g.region",
                      raster = "random_points,buffer_fill")

# patch of random points with filled buffer zone
    grass.run_command("r.patch",
                      input = "random_points,buffer_fill",
                      output = "patch_random_buffer")

    grass.run_command("g.region",
                      raster = "jaxa_patch")
#  DONE  TODO Werte oben definieren, das man sie als Variablen nutzen kann
# generate mask again

    grass.run_command("r.mask",
                      raster = "jaxa_patch",
                      maskcats = value,
                      quiet = True)

    grass.run_command("g.region",
                      raster = "patch_random_buffer")

#fill nulls
    grass.run_command("r.fillnulls",
                      input = "patch_random_buffer",
                      output = "fill_data",
                      method = "bilinear",
                      quiet = True)
    grass.message(("filling null values of %s") % output)

# deactivate mask again
    grass.run_command("r.mask",
                      flags = 'r',
                      quiet = True)

    grass.run_command("g.region",
                      raster = "jaxa_patch")

# set values to null() to generate "real" holes
    grass.run_command("r.null",
                      map = "jaxa_patch",
                      setnull = value)

    grass.run_command("g.region",
                      raster = "jaxa_patch,fill_data")

# patch and finish
    grass.run_command("r.patch",
                      input = "jaxa_patch,fill_data",
                      output = output)

    grass.run_command("g.remove", flags = "f", type = "raster", name = "jaxa_patch,srtm_patch,mask,buffer_mask,buffer_fill,random_points,patch_random_buffer,fill_data")
      
def main():
    input = options['input']
    output = options['output']
    username_jaxa = options['username_jaxa']
    password_jaxa = options['password_jaxa']
    username_srtm = options['username_srtm']
    password_srtm = options['password_srtm']
    settings = options['settings']
    memory = options['memory']
    random = options['random']
    value = options['value']
    
    overwrite = grass.overwrite()
    
    # check the version
    version = grass.core.version()
    
    # check for GRASS 7 version
    if version['version'].find('7.') == -1:
        grass.fatal(_('GRASS GIS version 7 required'))
        return 0
    
    # make temporary directory 
    tmpdir = grass.tempfile()
    grass.try_remove(tmpdir)
    os.mkdir(tmpdir)
    currdir = os.getcwd()
    print (currdir)
    pid = os.getpid()
    print (pid)

    # change to temporary directory
    os.chdir(tmpdir)
    print ('changed to ' +  tmpdir)
    in_temp = True

    res = '00:00:01'

    # are we in LatLong location?
    s = grass.read_command("g.proj", flags='j')
    kv = grass.parse_key_val(s)
    if kv['+proj'] != 'longlat':
	grass.fatal(_("This module only operates in LatLong locations"))

 ###########################################

    if not options['settings']:
        try:
            username_jaxa != ''
            password_jaxa != ''
            username_srtm != ''
            password_srtm != ''
        except:
            grass.fatal(_("Even usernames and passwords or <%s> must be set") % options['settings'])

    # set username, password and folder if settings are insert by stdin
#    if options['settings'] == '-':
#        if options['folder'] != '':
#            if check(options['folder']):
#                fold = options['folder']
#            user = raw_input(_('Insert username: '))
#            passwd = raw_input(_('Insert password: '))
#        else:
#            grass.fatal(_("Set folder parameter when using stdin for passing "
#                          "the username and password"))
#            return 0
    # set username, password and folder by file
#    else:
        # open the file and read the username and password:
        # first line is username
        # second line is password
#        if check(options['settings']):
#            filesett = open(options['settings'], 'r')
#            fileread = filesett.readlines()
#            user = 'anonymous'
#            passwd = fileread[0].strip()
#            filesett.close()
#        else:
#            grass.fatal(_("File <%s> not found") % options['settings'])

        # set the folder by option folder
#        if options['folder'] != '':
#            if check(options['folder']):
#                fold = options['folder']

        # set the folder from path where settings file is stored
#        else:
#            path = os.path.split(options['settings'])[0]
#            if check(path):
#                fold = path
#################################################

    grass_commands(input, username_srtm, password_srtm, random, value, output, memory)


    return 0

if __name__ == "__main__":
    options, flags = grass.parser()
    sys.exit(main())

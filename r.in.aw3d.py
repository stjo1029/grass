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
#% description: Creates a void filled DEM from 1 arcsec Alos World 3D tiles and an auxiliary DEM.
#% keyword: Raster
#% keyword: Import
#%end
#%option G_OPT_F_BIN_INPUT
#% description: Name of input ALOS World 3D file
#%end
#%option G_OPT_F_BIN_INPUT
#% key: file
#% description: File to use for void filling (default is SRTM 1 arcsec)
#% required: no
#%end
#%option G_OPT_R_OUTPUT
#% required: no
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
#% key: machine
#% type: string
#% required: no
#% multiple: no
#% label: Name of machine in netrc file
#% description: Name of machine in the netrc file (SRTM data)
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
#% description: Percentage of random points (values 0 - 100)
#% answer: 30
#%end
#%option
#% key: value
#% type: integer
#% required: no
#% multiple: no
#% description: Value of dataholes
#% answer: -9999
#%end
#%option
#% key: method
#% type: string
#% required: yes
#% multiple: no
#% options: average, median
#% description: Choose average or median ALOS World 3D data product
#%end


# TODO option alternativ zu srtm daten eigene Daten eingeben, standart(falls nichts) srtm

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
import netrc
import tarfile
import tempfile
import shutil
import atexit

global GDAL

# check if gdal library is istalled
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


def grass_commands(input, file, username_srtm, password_srtm, random, value,
                   output, memory, machine, method, tmpdir):

    # run the grass commands
    # make sure every generated map before is removed
    try:
        grass.run_command("r.mask",
                          flags = "r",
                          quiet = True)
    except:
        print ''

    grass.run_command("g.remove",
                      flags = "f",
                      type = "raster",
                      name = "jaxa_patch,srtm_patch,mask,buffer_mask,buffer_fill,"
                      "random_points,patch_random_buffer,fill_data",
                      quiet = True)
    # change to temporary directory
    os.chdir(tmpdir)

    # import input data
    # if .tar.gz file
    ext = ".tar.gz"
#    infile = os.path.split(input)
    (fdir, tile) = os.path.split(input)
#    directory_list = os.listdir(fdir)

    if input.endswith(ext):
        grass.message(("Extracting data from %s ...") % tile)

        try:
            idx = tile.index('.tar.gz')
            grass.message('opening ' + tile + ' ...')
            t = tarfile.open(input)

            for name in t.getnames():
                    try:
                        if method == 'average' or method == 'median':
                            ave_med = method[:3].upper()
                            idx = name.index(ave_med + '_DSM.tif')
                            grass.message('extracting ' + name + ' ...')
                            t.extractall(tmpdir, members=[t.getmember(name)])

                            os.chdir(tmpdir)
                            grass.run_command("r.in.gdal",
                                              input = tmpdir + "/" + name,
                                              output = output,
                                              memory = memory)

                        else:
                            average = 'AVE'
                            median = 'MED'

                            idx = name.index(average + '_DSM.tif')
                            grass.message('extracting ' + name + ' ...')
                            t.extractall(tmpdir, members=[t.getmember(name)])

                            os.chdir(tmpdir)
                            grass.run_command("r.in.gdal",
                                              input = tmpdir + "/" + name,
                                              output = output,
                                              memory = memory)

                            idx = name.index(median + '_DSM.tif')
                            grass.message('extracting ' + name + ' ...')
                            t.extractall(tmpdir, members=[t.getmember(name)])

                            os.chdir(tmpdir)
                            grass.run_command("r.in.gdal",
                                              input = tmpdir + "/" + name,
                                              output = output,
                                              memory = memory)
                    except:
                        print ''
        except:
            print ''
    else:
        grass.run_command("r.in.gdal",
                          input = input,
                          output = output,
                          memory = memory)

    grass.run_command("g.rename",
                      raster = output + ",jaxa_patch",
                      quiet = True)

    grass.run_command("g.region",
                      raster = "jaxa_patch")

    # when file is set
    if file != '':
        try:
            grass.run_command("r.in.gdal",
                              input = file,
                              output = 'srtm_patch',
                              memory = memory)
        except:
            grass.fatal(_("An Error occured"))
    else:
    # credentials for authentication with r.in.srtm.region
    # take entries from gui
        if username_srtm != '' and password_srtm != '':
            grass.run_command("r.in.srtm.region",
                              user = username_srtm,
                              password = password_srtm,
                              flags = 1,
                              output = 'srtm_patch')

    # if username or password is missing
        elif username_srtm != '' and password_srtm == '':
            grass.fatal(_("Password for authentication must be set..."))

        elif username_srtm == '' and password_srtm != '':
            grass.fatal(_("Username for authentication must be set..."))

    # take credentials from netrc file
        else:
            nt = netrc.netrc()
            try:
                account = nt.hosts[machine]
            except:
                    grass.fatal(_("Please set username and password parameters "
                                "or enter a name for a netrc file "
                                "to authenticate at the NASA server"))

        # user for download
            user = account[0]
        # password for download
            password = account[2]

            grass.run_command("r.in.srtm.region",
                              user = user,
                              password = password,
                              flags = 1,
                              output = 'srtm_patch')

    # mask calculation to show dataholes
    grass.run_command("r.mapcalc",
                      expression = "mask = if(jaxa_patch==-9999,1,null())")

    grass.run_command("g.region",
                      raster = "mask",
                      zoom = "mask")

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
                      expression = "buffer_fill = if(buffer_mask==2,jaxa_patch"
                      ",null())")

    grass.run_command("r.mask",
                      raster = "jaxa_patch",
                      maskcats = value)

    #set region to srtm
    grass.run_command("g.region",
                      raster = "srtm_patch")

    # random points from srtm data
    grass.message("writing raster map <random_points> ...")

    grass.run_command("r.random",
                      input = "srtm_patch",
                      npoints = random + "%",
                      raster = "random_points",
                      quiet = True)

    # deactivate mask
    grass.run_command("r.mask",
                      flags = 'r',
                      quiet = True)

    # align pixel postion to map to be filled
    grass.run_command("g.region",
                      raster = "random_points,buffer_fill",
                      align = "jaxa_patch")

    # patch of random points with filled buffer zone
    grass.run_command("r.patch",
                      input = "random_points,buffer_fill",
                      output = "patch_random_buffer")

    grass.run_command("g.region",
                      raster = "jaxa_patch")

    # generate mask again
    grass.run_command("r.mask",
                      raster = "jaxa_patch",
                      maskcats = value,
                      quiet = True)

    grass.run_command("g.region",
                      raster = "patch_random_buffer")

    #fill null values
    grass.message(("filling null values of <%s>...") % output)

    try:
        grass.run_command("r.fillnulls",
                          input = "patch_random_buffer",
                          output = "fill_data",
                          method = "bilinear",
                          quiet = True)
    except:
        grass.message("Tile contains only No Data values...")

        grass.message("")

    # deactivate mask again
    grass.run_command("r.mask",
                      flags = 'r',
                      quiet = True)

    grass.run_command("g.region",
                      raster = "jaxa_patch")

    # set values to null() to generate "real" holes
    grass.run_command("r.null",
                      map = "jaxa_patch",
                      setnull = value,
                      quiet = True)

    # patch and finish
    grass.run_command("r.patch",
                      input = "jaxa_patch,fill_data",
                      output = output,
                      quiet = True)

    # remove generated maps
    # TODO move to temp environment
    grass.run_command("g.remove",
                      flags = "f",
                      type = "raster",
                      name = "jaxa_patch,srtm_patch,mask,buffer_mask,buffer_fill,"
                      "random_points,patch_random_buffer,fill_data",
                      quiet = True)

    # set color table to srtm
    grass.run_command("r.colors",
                      map = output,
                      color = "srtm",
                      quiet = True)

    #write metadata
    tmphist = grass.tempfile()
    f = open(tmphist, 'w+')
    f.write(os.environ['CMDLINE'])
    f.close

    grass.run_command('r.support', map = output,
                      description = 'generated by r.in.aw3d',
                      quiet = True)

    # write cmd history
#    grass.raster_history(output)

    # clean up the mess
#TODO check if it works    # remove temporary directory with extracted files
    grass.verbose("Removing temporary directory...")
    grass.try_remove(tmpdir)

    grass.message(("Done: generated map <%s>") % output)


def main():

    input = options['input']
    output = options['output']
    file = options['file']
    username_jaxa = options['username_jaxa']
    password_jaxa = options['password_jaxa']
    username_srtm = options['username_srtm']
    password_srtm = options['password_srtm']
    machine = options['machine']
    memory = options['memory']
    random = options['random']
    value = options['value']
    method = options['method']

#    TODO build in method (multiple)
#    TODO build in file with testing

#    TODO build in working like srtm.region (snap region)

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
    pid = os.getpid()

    grass.message(tmpdir)
    grass.message(currdir)
    grass.message(pid)

    # change to temporary directory
#    os.chdir(tmpdir)
#    in_temp = True

#    res = '00:00:01'

    # are we in LatLong location?
    s = grass.read_command("g.proj", flags='j')
    kv = grass.parse_key_val(s)
    if kv['+proj'] != 'longlat':
        grass.fatal(_("This module only operates in LatLong locations"))

    # if no output is set, take input
    infile = input
    while infile[-4:].lower() in ['.tif']:
        infile = infile[:-4]
    while infile[-7:].lower() in ['.tar.gz']:
        infile = infile[:-7]
    #fdir is head of directory, tile is tale of directory
    (fdir, tile) = os.path.split(infile)

    if not output:
        if input.endswith('.tar.gz'):
            if method == 'average':
                output = tile + '_AVE_DSM'
            else:
                output = tile + '_MED_DSM'
        else:
            output = tile
    else:
        output = output

    # run grass_commands
    grass_commands(input, file, username_srtm, password_srtm, random, value,
                   output, memory, machine, method, tmpdir)

    return 0

if __name__ == "__main__":
    options, flags = grass.parser()
    sys.exit(main())

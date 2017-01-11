#!/usr/bin/env python
#
############################################################################
#
# MODULE:    r.in.srtm.py
# AUTHOR(S): Markus Neteler 11/2003 neteler AT itc it
#            Hamish Bowman
#            Glynn Clements
#            Jonas Strobel
# PURPOSE:   import of SRTM hgt files or SRTM SWBD raw files into GRASS
#
# COPYRIGHT:    (C) 2004-2017 by the GRASS Development Team
#
#		This program is free software under the GNU General Public
#		License (>=v2). Read the file COPYING that comes with GRASS
#		for details.
#
# Dec 2004: merged with srtm_generate_hdr.sh (M. Neteler)
#           corrections and refinement (W. Kyngesburye)
# Aug 2004: modified to accept files from other directories
#           (by H. Bowman)
# June 2005: added flag to read in US 1-arcsec tiles (H. Bowman)
# April 2006: links updated from ftp://e0dps01u.ecs.nasa.gov/srtm/
#             to current links below
# October 2008: Converted to Python by Glynn Clements
# December 2016: Added flag to read SRTM SWBD (SRTM Water Body Dataset) raw binary files
#########################
# Derived from:
# ftp://e0srp01u.ecs.nasa.gov/srtm/version1/Documentation/Notes_for_ARCInfo_users.txt
#     (note: document was updated silently end of 2003)
#
# ftp://e0srp01u.ecs.nasa.gov/srtm/version1/Documentation/SRTM_Topo.txt
#  "3.0 Data Formats
#  [...]
#  To be more exact, these coordinates refer to the geometric center of
#  the lower left pixel, which in the case of SRTM-1 data will be about
#  30 meters in extent."
#
#- SRTM 90 Tiles are 1 degree by 1 degree
#- SRTM filename coordinates are said to be the *center* of the LL pixel.
#       N51E10 -> lower left cell center
#
#- BIL uses *center* of the UL (!) pixel:
#      http://downloads.esri.com/support/whitepapers/other_/eximgav.pdf
#
#- GDAL uses *corners* of pixels for its coordinates.
#
# NOTE: Even, if small difference: SRTM is referenced to EGM96, not WGS84 ellps
# http://earth-info.nga.mil/GandG/wgs84/gravitymod/egm96/intpt.html
#
#########################
# Test cases
# - SRTM HGT 1 arc second
# - SRTM HGT 3 arc second
# - SRTM HGT.zip 1 arc second
# - SRTM HGT.zip 3 arc second
# - SRTM SWBD 1 arc second
# - SRTM SWBD.zip 1 arc second
#########################

#%Module
#% description: Imports SRTM HGT or RAW files into raster map.
#% keyword: raster
#% keyword: import
#%End
#%option G_OPT_F_INPUT
#% description: Name of SRTM HGT / SRTM RAW input tile
#%end
#%option G_OPT_R_OUTPUT
#% description: Name for output raster map (default: input tile)
#% required : no
#%end
#%flag
#% key: 1
#% description: Input is a 1-arcsec tile (default: 3-arcsec)
#%end
#%flag
#% key: w
#% description: Import SRTM SWBD (SRTM Water Body Data)
#%end

tmpl1sec = """BYTEORDER M
LAYOUT BIL
NROWS 3601
NCOLS 3601
NBANDS 1
NBITS 16
BANDROWBYTES 7202
TOTALROWBYTES 7202
BANDGAPBYTES 0
PIXELTYPE SIGNEDINT
NODATA -32768
ULXMAP %s
ULYMAP %s
XDIM 0.000277777777777778
YDIM 0.000277777777777778
"""

tmpl3sec = """BYTEORDER M
LAYOUT BIL
NROWS 1201
NCOLS 1201
NBANDS 1
NBITS 16
BANDROWBYTES 2402
TOTALROWBYTES 2402
BANDGAPBYTES 0
PIXELTYPE SIGNEDINT
NODATA -32768
ULXMAP %s
ULYMAP %s
XDIM 0.000833333333333
YDIM 0.000833333333333
"""

proj = ''.join([
    'GEOGCS[',
    '"wgs84",',
    'DATUM["WGS_1984",SPHEROID["wgs84",6378137,298.257223563],TOWGS84[0.000000,0.000000,0.000000]],',
    'PRIMEM["Greenwich",0],',
    'UNIT["degree",0.0174532925199433]',
    ']'])

import os
import shutil
import atexit
import grass.script as grass
from grass.exceptions import CalledModuleError


def cleanup():
    if not in_temp:
        return
    for ext in ['.bil', '.hdr', '.prj', '.hgt.zip', '.raw', '.raw.zip']:
        grass.try_remove(tile + ext)
    os.chdir('..')
    grass.try_rmdir(tmpdir)


def main():
    global tile, tmpdir, in_temp

    in_temp = False

    input = options['input']
    output = options['output']
    one = flags['1']
    water = flags['w']

    # are we in LatLong location?
    s = grass.read_command("g.proj", flags='j')
    kv = grass.parse_key_val(s)
    if kv['+proj'] != 'longlat':
        grass.fatal(_("This module only operates in LatLong locations"))

    # use these from now on:
    infile = input
    while infile[-4:].lower() in ['.hgt', '.zip', '.raw']:
        infile = infile[:-4]
    (fdir, tile) = os.path.split(infile)

    if not output:
        tileout = tile
        grass.debug("No output set... using name: " + tileout)
    else:
        tileout = output

    if not water:
        zipfile = infile + ".hgt.zip"
        hgtfile = os.path.join(fdir, tile[:7] + ".hgt")
    else:
        zipfile = infile + ".raw.zip"
        rawfile = os.path.join(fdir, tile[:7] + ".raw")

    if os.path.isfile(zipfile):
        # check if we have unzip
        if not grass.find_program('unzip'):
            grass.fatal(_('The "unzip" program is required, please install it first'))

        # really a ZIP file?
        # make it quiet in a safe way (just in case -qq isn't portable)
        tenv = os.environ.copy()
        tenv['UNZIP'] = '-qq'
        if grass.call(['unzip', '-t', zipfile], env=tenv) != 0:
            grass.fatal(_("'%s' does not appear to be a valid zip file.") % zipfile)
        is_zip = True

    elif not water:
        os.path.isfile(hgtfile)
        # try and see if it's already unzipped
        is_zip = False

    elif os.path.isfile(rawfile):
        # try and see if it's already unzipped
        is_zip = False

    else:
        grass.fatal(_("File '%s' or '%s' or '%s' not found") % (zipfile, hgtfile, rawfile))

    # make a temporary directory
    tmpdir = grass.tempfile()
    grass.try_remove(tmpdir)
    os.mkdir(tmpdir)

    if is_zip:
        if not water:
            shutil.copyfile(zipfile, os.path.join(tmpdir, tile + ".hgt.zip"))
        else:
            shutil.copyfile(zipfile, os.path.join(tmpdir, tile + ".raw.zip"))

    else:
        if not water:
            shutil.copyfile(hgtfile, os.path.join(tmpdir, tile + ".hgt"))
        else:
            shutil.copyfile(rawfile, os.path.join(tmpdir, tile + ".raw"))

    # change to temporary directory
    os.chdir(tmpdir)
    in_temp = True

    if not water:
        zipfile = tile + ".hgt.zip"
    else:
        zipfile = tile + ".raw.zip"

    hgtfile = tile[:7] + ".hgt"
    bilfile = tile + ".bil"
    rawfile = tile[:7] + ".raw"

    if is_zip:
        # unzip & rename data file:
        grass.message(_("Extracting '%s'...") % zipfile)
        if grass.call(['unzip', zipfile], env=tenv) != 0:
            grass.fatal(_("Unable to unzip file."))

    if not water:
        grass.message(_("Converting input file to BIL..."))
        os.rename(hgtfile, bilfile)

    north = tile[0]
    ll_latitude = int(tile[1:3])
    east = tile[3]
    ll_longitude = int(tile[4:7])

    # are we on the southern hemisphere? If yes, make LATITUDE negative.
    if north == "S":
        ll_latitude *= -1

    # are we west of Greenwich? If yes, make LONGITUDE negative.
    if east == "W":
        ll_longitude *= -1

    if water:
        # Calculate Upper Left from Lower Left
        ulxmap = "%.1f" % (ll_longitude + 1)

        # SRTM90 tile size is 1 deg:
        ulymap = "%.1f" % (ll_latitude + 1)

    else:
        # Calculate Upper Left from Lower Left
        ulxmap = "%.1f" % ll_longitude

        # SRTM90 tile size is 1 deg:
        ulymap = "%.1f" % (ll_latitude + 1)

    if one or water:
        grass.message(_("Attempting to import 1-arcsec data."))
        tmpl = tmpl1sec

    else:
        tmpl = tmpl3sec

    header = tmpl % (ulxmap, ulymap)
    hdrfile = tile + '.hdr'
    outf = file(hdrfile, 'w')
    outf.write(header)
    outf.close()

    # create prj file: To be precise, we would need EGS96! But who really cares...
    prjfile = tile + '.prj'
    outf = file(prjfile, 'w')
    outf.write(proj)
    outf.close()

    if not water:
        try:
            grass.run_command('r.in.gdal', input=bilfile, output=tileout)
        except:
            grass.fatal("Unable to import data")

    else:
        # If water, these operations are required
        swbd_res = 0.000277777777777778  # 0:00:01

        n = float(ulymap) + (0.5 * swbd_res)
        s = float(ll_latitude) - (0.5 * swbd_res)
        e = float(ulxmap) + (0.5 * swbd_res)
        w = int(ll_longitude) - (0.5 * swbd_res)

        try:
            grass.run_command('r.in.bin', input=rawfile, output=tileout,
                              bytes=1, north=n, south=s, east=e, west=w,
                              rows=3601, cols=3601)
        except:
            grass.fatal(_("Unable to import data"))

    # nice color table
    grass.run_command('r.colors', map=tileout, color='srtm')

    # write cmd history:
    grass.raster_history(tileout)
    grass.message(_("Done: generated map ") + tileout)

    if not water:
        grass.message(_("(Note: Holes in the data can be closed with 'r.fillnulls' using splines)"))

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()

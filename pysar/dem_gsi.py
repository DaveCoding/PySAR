#!/usr/bin/env python3
############################################################
# Program is part of PySAR                                 #
# Copyright(c) 2019, Zhang Yunjun                          #
# Author:  Zhang Yunjun, Mar 2019                          #
############################################################


import os
import glob
import argparse
import numpy as np
from pysar.utils import readfile, writefile


# DEHM basic info
dehm = argparse.Namespace
dehm.step = 0.4 / 3600  #decimal degree
dehm.length = 6000      #40 mins in latitude per grid
dehm.width = 9000       #60 mins in longitude per grid
dehm.data_type = np.float32


##################################################################################################
EXAMPLE = """example:
  cd $KIRISHIMA/KirishimaAlosAT424/DEM
  dem_gsi.py -b 31.1 32.8 130.1 131.9
  dem_gsi.py -b 31.1 32.8 130.1 131.9 --grid-dir ~/insarlab/DEHM10m
"""

REFERENCE = """DEHM: Digital Ellipsoidal Height Model
yyxx.dehm with yy and xx indicating the coordinates of the upper left corner of the firt pixel.
where longitude = xx + 100
      latitude  = (yy + 1) / 1.5
"""

def create_parser():
    parser = argparse.ArgumentParser(description='Prepare DEM from GSI (Japan) DEHM grib files.',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=EXAMPLE)

    parser.add_argument('-b','--bbox', dest='SNWE', type=float, nargs=4, metavar=('S','N','W','E'), required=True,
                        help='Spatial region in the format south north west east.\n'
                             'The values should be from (-90,90) for latitudes and '
                             '(-180,180) for longitudes.')
    parser.add_argument('-o','--output', dest='outfile', default='gsi10m.dem',
                        help='output file name. Default: gsi10m.dem')
    parser.add_argument('-g','--grid-dir', dest='grid_dir', default='/famelung/data/gsi10m',
                        help='Directory of DEHM grib files. Default=/famelung/data/gsi10m')
    return parser


def cmd_line_parse(iargs=None):
    parser = create_parser()
    inps = parser.parse_args(args=iargs)

    inps.grid_dir = os.path.expanduser(inps.grid_dir)
    inps.grid_dir = os.path.expandvars(inps.grid_dir)
    inps.grid_dir = os.path.abspath(inps.grid_dir)
    if len(glob.glob(os.path.join(inps.grid_dir, '*.dehm'))) == 0:
        raise SystemExit('ERROR: no *.dehm file found in directory: {}'.format(inps.grid_dir))
    return inps


##################################################################################################
def write_dem_file(SNWE, dem_file, grid_dir):
    S, N, W, E = SNWE

    # get the min/max xx/yy number of the corresponding grid files
    yy_min = int(np.floor(S * 1.5 - 1) + 1)
    yy_max = int(np.ceil(N * 1.5 - 1))
    xx_min = int(np.floor(W - 100))
    xx_max = int(np.ceil(E - 100) - 1)
    num_grid_xx = int(xx_max - xx_min + 1)  #number of grids in x/longitude direction
    num_grid_yy = int(yy_max - yy_min + 1)  #number of grids in y/latitude direction
    print('number of grid files included: {} in lat direction and {} in lon direction'.format(
        num_grid_yy, num_grid_xx))

    print('stitching DEM from grid data ...')
    dem0 = np.zeros((num_grid_yy * dehm.length,
                     num_grid_xx * dehm.width), dtype=dehm.data_type)
    for yy in range(yy_max, yy_min-1, -1):
        r0 = (yy_max - yy) * dehm.length
        r1 = r0 + dehm.length
        for xx in range(xx_min, xx_max+1, 1):
            c0 = (xx - xx_min) * dehm.width
            c1 = c0 + dehm.width

            grid_file = os.path.join(grid_dir, '{}{}.dehm'.format(yy, xx))
            if os.path.isfile(grid_file):
                print('read', grid_file)
                data = np.fromfile(grid_file,
                                   dtype=dehm.data_type,
                                   count=dehm.length*dehm.width).reshape(dehm.length,
                                                                         dehm.width)
            else:
                print('warning: {} does not exists, filled with zero value and continue.')
                data = np.zeros(dehm.length, dehm.width, dtype=dehm.data_type)
            dem0[r0:r1, c0:c1] = data

    print('cropping based on the input SNWE: {} ...'.format(SNWE))
    grids_N = (yy_max + 1) / 1.5
    grids_W = xx_min + 100
    x_step = dehm.step
    y_step = -dehm.step
    
    r0 = round((N - grids_N) / y_step)
    r1 = round((S - grids_N) / y_step)
    c0 = round((W - grids_W) / x_step)
    c1 = round((E - grids_W) / x_step)
    dem = np.array(dem0[r0:r1, c0:c1], dtype=np.int16)
    print('file size in (row, col): {}'.format(dem.shape))

    # write to binary file
    print('writing {}'.format(dem_file))
    dem.tofile(dem_file)

    # generate meta namespace
    meta = argparse.Namespace
    meta.length, meta.width = dem.shape
    meta.south = S
    meta.north = N
    meta.west = W
    meta.east = E
    meta.lat_step = -1. * dehm.step
    meta.lon_step = dehm.step
    meta.file_path = os.path.abspath(dem_file)
    return meta


def write_rsc_file(meta, out_file):
    # initiate meta dict
    rsc = dict()
    rsc['FILE_LENGTH'] = meta.length
    rsc['WIDTH'] = meta.width
    rsc['XMIN'] = 0
    rsc['XMAX'] = meta.width - 1
    rsc['YMIN'] = 0
    rsc['YMAX'] = meta.length - 1
    rsc['X_FIRST'] = '{:.12f}'.format(meta.west)
    rsc['Y_FIRST'] = '{:.12f}'.format(meta.north)
    rsc['X_STEP'] = '{:.12f}'.format(meta.lon_step)
    rsc['Y_STEP'] = '{:.12f}'.format(meta.lat_step)
    rsc['X_UNIT'] = 'degrees'
    rsc['Y_UNIT'] = 'degrees'
    rsc['RLOOKS'] = 1
    rsc['ALOOKS'] = 1
    rsc['Z_OFFSET'] = 0
    rsc['Z_SCALE'] = 1
    rsc['PROJECTION'] = 'LATLON'
    rsc['DATE12'] = '111111-222222'
    rsc['DATA_TYPE'] = 'int16'
    # write rsc file
    writefile.write_roipac_rsc(rsc, out_file, print_msg=True)
    return out_file


def write_vrt_file(meta, out_file):
    # initiate vrt string
    vrt_str = """<VRTDataset rasterXSize="{w}" rasterYSize="{l}">
    <SRS>EPSG:4326</SRS>
    <GeoTransform>{x0}, {xs}, 0.0, {y0}, 0.0, {ys}</GeoTransform>
    <VRTRasterBand band="1" dataType="Int16" subClass="VRTRawRasterBand">
        <SourceFilename relativeToVRT="1">{f}</SourceFilename>
        <ByteOrder>LSB</ByteOrder>
        <ImageOffset>0</ImageOffset>
        <PixelOffset>2</PixelOffset>
        <LineOffset>{lo}</LineOffset>
    </VRTRasterBand>
</VRTDataset>
""".format(w=meta.width,
           l=meta.length,
           x0=meta.west,
           xs=meta.lon_step, 
           y0=meta.north,
           ys=meta.lat_step,
           f=meta.file_path,
           lo=2*meta.width)

    # write to vrt file
    with open(out_file, 'w') as f:
        f.write(vrt_str)
    print('write {}'.format(out_file))
    return out_file


##################################################################################################
def main(iargs=None):
    inps = cmd_line_parse(iargs)

    meta = write_dem_file(inps.SNWE,
                          dem_file=inps.outfile,
                          grid_dir=inps.grid_dir)

    write_rsc_file(meta, out_file='{}.rsc'.format(inps.outfile))

    write_vrt_file(meta, out_file='{}.vrt'.format(inps.outfile))

    if 'ISCE_STACK' in os.environ:
        print('generate {}.xml file using ISCE command'.format(inps.outfile))
        cmd = os.path.expandvars('${ISCE_STACK}/../../../applications/gdal2isce_xml.py')
        cmd += ' -i {}.vrt'.format(inps.outfile)
        print(cmd)
        os.system(cmd)

    return


###################################################################################################
if __name__ == '__main__':
    main()


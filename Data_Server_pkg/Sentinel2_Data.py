#@author Adrian Spork https://github.com/A-Spork
#@author Tatjana Melina Walter https://github.com/jana2308walter
#@author Maximilian Busch https://github.com/mabu1994

from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
import getpass
import numpy as np
import xarray as xr
import rasterio as rio
import os
import pandas as pd
import shutil
import stat
from rasterio.enums import Resampling
from datetime import datetime
from zipfile import ZipFile
from ftplib import FTP 



class NoPath(Exception):
    def init(self, message):
        self.message = message
    pass

class NoResolution(Exception):
    def init(self, message):
        self.message = message
    pass

class NoSafeFileError(Exception):
    def init(self,message):
        self.message = message
    pass 
    
    
'''Dask Cluster'''
from dask.distributed import Client, LocalCluster
'''Python 3.9.1 Workaround'''
#import multiprocessing.popen_spawn_posix#nonwindows#
#import multiprocessing.popen_spawn_win32#windows#
#from distributed import Client#
#Client()#
'''Server'''
#cluster = LocalCluster()
#client = Client(cluster)
#client


def downloadingData(aoi, collectionDate, plName, prLevel, clouds, username, password, directory):
    '''
    Downloads the Sentinel2 - Data with the given parameters

    Parameters:
        aoi (str): The type and the coordinates of the area of interest
        collectionDate datetime 64[ns]): The date of the data
        plName (str): The name of the platform
        prLevel (str): The name of the process
        clouds (tuple of ints): Min and max of cloudcoverpercentage
        username (str): The username of the Copernicus SciHub
        password (str): The password of the Copernicus SciHub
        directory (str): Pathlike string to the directory
    '''
    
    api = SentinelAPI(username, password, 'https://scihub.copernicus.eu/dhus')
    
    '''Choosing the data with bounding box (footprint), date, platformname, processinglevel and cloudcoverpercentage'''
    products = api.query(aoi, date = collectionDate, platformname = plName, processinglevel = prLevel, cloudcoverpercentage = clouds)

    '''Downloads the choosen files from Scihub'''
    if len(products)==0:
        raise Exception("No data for this params")
    print("Start downloading " + str(len(products)) + " product(s)")
    api.download_all(products, directory, max_attempts = 10, checksum = True)
    print("All necassary downloads done")





def unzipping(filename, directory):
    '''
    Unzips the file with the given filename
    Parameter:
        filename(str): Name of the .zip file
        directory (str): Pathlike string to the directory
    '''
    with ZipFile(os.path.join(directory, filename), 'r') as zipObj:
        zipObj.extractall(directory)





def unzip(directory):
    '''
    Unzips and deletes the .zip in the given directory

    Parameters:
        directory (str): Pathlike string to the directory
    '''

    for filename in os.listdir(directory):
        if filename.endswith(".zip"):
            if(filename[39:41]!="32"):
                print("CRS not supported! Only EPSG:32632 supported")
                delete(os.path.join(directory,filename))
            else:
                unzipping(filename, directory)
                delete(os.path.join(directory, filename))
                continue
        else:
            continue





def extractBands(filename, resolution, directory):
    '''
    Extracts bandpaths from the given .SAFE file
    Parameters:
        filename (str): Sentinel .SAFE file
        resolution (int): The resolution the datacube should have
        directory (str): Pathlike string to the directory
    Returns:
        bandPaths (str[]): An array of the paths for the red and nir band
    '''

    try:
        lTwoA = os.listdir(os.path.join(directory, filename, "GRANULE"))
        if resolution == 10:
            bandName = os.listdir (os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R10m"))
            pathRed = os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R10m", str(bandName[3]))
            pathNIR = os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R10m", str(bandName[4]))
            bandPaths = [pathRed, pathNIR]

        elif resolution == 20:
            bandName = os.listdir (os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R20m"))
            pathRed = os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R20m", str(bandName[3]))
            pathNIR = os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R20m", str(bandName[9]))
            bandPaths = [pathRed, pathNIR]

        elif resolution == 60:
            bandName = os.listdir (os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R60m"))
            pathRed = os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R60m", str(bandName[4]))
            pathNIR = os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R60m", str(bandName[11]))
            bandPaths = [pathRed, pathNIR]

        elif resolution == 100:
            bandName = os.listdir (os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R20m"))
            pathRed = os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R20m", str(bandName[3]))
            pathNIR = os.path.join(directory, filename, "GRANULE", str(lTwoA[0]), "IMG_DATA", "R20m", str(bandName[9]))
            bandPaths = [pathRed, pathNIR]

        else:
               raise NoResolution("Invalid Resolution, try 10, 20, 60 or 100")
    except FileNotFoundError:
        raise NoPath("No file in this path")
    return bandPaths





def loadBand (bandpath, date, tile, resolution, clouds, plName, prLevel, directory):
    '''
    Opens and reads the red and nir band, saves them as NetCDF file
    Parameters:
        bandPaths (str[]): Array with the paths to the red and nir band
        date (datetime 64[ns]): The collection date ("2020-12-31")
        tile (str): Bounding box of coordinates defined by Sentinel
        resolution (int): The resolution of the dataset
        clouds (tuple of ints): Min and max of cloudcoverpercentage
        plName (str): The name of the platform
        prLevel (str): The level of the process
        directory (str): Pathlike string to the directory
    Returns:
        dataset (xArray dataset): The result dataset as xArray dataset
    '''
    
    
    b4 = rio.open(bandpath[0])
    b8 = rio.open(bandpath[1])
    red = b4.read()
    nir = b8.read()

    if resolution == 10:
        res = 1830 * 3 * 2
    elif resolution == 20:
        res = 1830 * 3
    elif resolution == 60:
        res = 1830
    elif resolution == 100:
        res = 1098
    else:
        raise NoResolution("Invalid Resolution, try 10, 20, 60 or 100")

    j = res - 1
    i = 0
    lat = [0] * res
    lon = [0] * res
    while j >= 0:
        lon[i] = b4.bounds.left + i * resolution
        lat[i] = b4.bounds.bottom + j * resolution
        i = i + 1
        j = j - 1

    time = pd.date_range(date, periods = 1)

    if resolution == 100:
        upscale_factor = (1/5)
        nir = b8.read(
                out_shape = (
                    b8.count,
                    int(b8.height * upscale_factor),
                    int(b8.width * upscale_factor)
                ),
                resampling = Resampling.bilinear
        )
        transform = b8.transform * b8.transform.scale(
            (b8.width / nir.shape[-1]),
            (b8.height / nir.shape[-2])
        )
        red = b4.read(
            out_shape = (
                b4.count,
                int(b4.height * upscale_factor),
                int(b4.width * upscale_factor)
            ),
            resampling = Resampling.bilinear
        )

        transform = b4.transform * b4.transform.scale(
            (b4.width / red.shape[-1]),
            (b4.height / red.shape[-2])
        )

    dataset = xr.Dataset(
        {
            "red": (["time","lat", "lon"], red),
            "nir": (["time","lat", "lon"], nir)
        },
        coords = dict(
            time = time,
            lat = (["lat"], lat),
            lon = (["lon"], lon),
        ),
        attrs = dict(
            platform = plName,
            processingLevel = prLevel,
            source = "https://scihub.copernicus.eu/dhus",
            resolution = str(resolution) + " x " + str(resolution) + " m"
        ),
    )

    dataset.to_netcdf(directory + "datacube_" + str(date) + "_" + str(tile) + "_R" + str(resolution) + ".nc", 'w', format = 'NETCDF4')
    b4.close()
    b8.close()
    return dataset





def getDate(filename):
    '''
    Extracts the Date out of the Sentinelfilename
    Parameters:
        filename (str): Name of the file
    Returns:
        (str): Date of the File ("2020-12-31")
    '''

    return filename[11:15] + "-" + filename[15:17] + "-" + filename[17:19]





def getTile(filename):
    '''
    Extracts the UTM-tile of the Sentinelfilename
    Parameters:
        filename (str): Name of the file
    Returns:
        (str): UTM-tile of the File ("31UMC")
    '''
    return filename[38:44]





def on_rm_error(func, path, exc_info):
    '''
    Unlinks a read-only file
    '''

    os.chmod(path, stat.S_IWRITE)
    os.unlink(path)





def buildCube(directory, resolution, clouds, plName, prLevel):
    '''
    Builds a datacube in the given directory with coords, time as dimensions and the bands as datavariables
    Parameters:
        directory (str): Pathlike string to the directory
        resolution (int): The resolution of the dataset
        clouds (tuple of ints): Min and max of cloudcoverpercentage
        plName (str): The name of the platform
        prLevel (str): The level of the process
    '''
    
    i = 0
    for filename in os.listdir(directory):
        if filename.endswith(".SAFE"):
            i = i + 1
    if i == 0:
        raise NoSafeFileError ("In this directory is no SAFE file to build a cube")
    for filename in os.listdir(directory):
        if filename.endswith(".SAFE"):
            bandPath = extractBands(os.path.join(directory, filename), resolution, directory)
            band = loadBand(bandPath, getDate(filename), getTile(filename), resolution, clouds, plName, prLevel, directory)
            shutil.rmtree(os.path.join(directory, filename), onerror = on_rm_error)
            continue
        else:
            continue





def merge_Sentinel(directory, nameSentinel):
    '''
    Merges datacubes by coordinates and time

    Parameters:
        directory (str): Pathlike string where Data is stored
        nameSentinel (str): Filename for the datacube
    '''

    start = datetime.now()
    files = os.listdir(directory)
    for nc in files:
        if not nc.endswith(".nc"):
            raise TypeError("Wrong file in directory")
    if len(files) == 0:
        raise FileNotFoundError("Directory empty")
    elif len(files) == 1:
        print("Only one file in directory")
        os.rename(directory + (os.listdir(directory)[0]), directory + "merged_cube.nc")
        return
    else:
        print('Start merging')
        for file1 in files:
            for file2 in files:
                file1Date = file1[9:19]
                file1Tile = file1[20:26]
                file1Res = file1[27:31]
                file2Date = file2[9:19]
                file2Tile = file2[20:26]
                file2Res = file2[27:31]
                if file1[21:23] == "31":
                    delete(os.path.join(directory,file1))
                elif file2[21:23] == "31":
                    delete(os.path.join(directory,file2))
                elif file1Date == file2Date and file1Tile == file2Tile and file1Res == file2Res:
                    continue
                elif file1Date == file2Date and file1Tile == "T32ULC" and file2Tile == "T32UMC" and file1Res == file2Res:
                    fileLeft = xr.open_dataset(os.path.join(directory, file1))
                    fileRight = xr.open_dataset(os.path.join(directory, file2))
                    merge_coords(fileLeft, fileRight, file1[0:20] + "Merged" + file1[26:31], directory)
                    fileLeft.close()
                    fileRight.close()
                    delete(os.path.join(directory, file1))
                    delete(os.path.join(directory, file2))                   

    ds_merge = []
    files = []
    for f in os.listdir(directory):
        x = xr.open_dataset(os.path.join(directory, f))
        ds_merge.append(x)
        files.append(os.path.join(directory, f))
#   datacube = xr.open_mfdataset(files)#none dask
    datacube = xr.open_mfdataset(files, parallel=True, chunks={"time": "auto"})#with dask
    '''save datacube'''
    print("Start saving")
    datacube.to_netcdf(directory + nameSentinel + ".nc", compute = True)
    print("Done saving")
    datacube.close()

    for f in ds_merge:
        f.close()
    for f in files:
        delete(f)
        
    end = datetime.now()
    diff = end - start
    print('All cubes merged for ' + str(diff.seconds) + 's')



def safe_datacube(ds, name, directory):
    '''
    Saves the Datacube as NetCDF (.nc)
    Parameters:
        ds (xArray Dataset): Sourcedataset
        name (str): Name eg '2017', '2015_2019'
        directory (str): Pathlike string to the directory
    '''

    print("Start saving")
    start = datetime.now()
    ds.to_netcdf(directory + name + ".nc")
    diff = datetime.now() - start
    print("Done saving after "+ str(diff.seconds) + 's')





def merge_coords(ds_left, ds_right, name, directory):
    '''
    Merges two datasets by coordinates

    Parameters:
        ds_left (xArray dataset): Dataset to be merged
        ds_right (xArray dataset): Dataset to be merged
        name (str): Name of the new dataset
        directory (str): Pathlike string to the directory
    '''

    ds_selected = ds_left.sel(lon = slice(ds_left.lon[0], ds_right.lon[0]))
    ds_merge = [ds_selected, ds_right]
    merged = xr.combine_by_coords(ds_merge)
    safe_datacube(merged, name, directory)
    merged.close()





def delete(path):
    '''
    Deletes the file/directory with the given path
    Parameters:
        path (str): Path to the file/directory
    '''
    try: 
        os.remove(path)
        print("File was deleted")
    except FileNotFoundError:
        raise NoPath ("No file in this path")





def mainSentinel(resolution, directory, collectionDate, aoi, clouds, username, password, nameSentinel):
    '''
    Downloads, unzips, collects and merges Sentinel2 Satelliteimages to a single netCDF4 datacube

    Parameters:
        resolution (int): Resolution of the satelite image
        directory (str): Pathlike string to the workdirectory
        collectionDate (tuple of datetime 64[ns]): Start and end of the timeframe
        aoi (POLYGON): Area of interest
        clouds (tuple of ints): Min and max of cloudcoverpercentage
        username (str): Uername for the Copernicus Open Acess Hub
        password (str): Password for the Copernicus Open Acess Hub
        nameSentinel (str): Filename for the datacube
    '''
    if collectionDate[0]==collectionDate[1]:
        raise Exception("Start and end of collection can not be identical")
    plName = 'Sentinel-2'
    prLevel = 'Level-2A'
    downloadingData (aoi, collectionDate, plName, prLevel, clouds, username, password, directory)
    unzip(directory)
    buildCube(directory, resolution, clouds, plName, prLevel)
    merge_Sentinel(directory, nameSentinel)

	
	
##########################################Execution################################
#directory = 'F:/Data_Sentinel/WorkDir/'
#resolution = 100    #10, 20, 60, 100 possible

'''Parameters for the download'''
#aoi = 'POLYGON((7.52834379254901 52.01238155392252,7.71417925515199 52.01183230436206,7.705255583805303 51.9153349236737,7.521204845259327 51.90983021961716,7.52834379254901 52.01238155392252,7.52834379254901 52.01238155392252))'
#collectionDate = ('20200601', '20200615')
#clouds = (0, 30)
#username = getpass.getpass("user: ")
#password = getpass.getpass("password: ")

#mainSentinel(resolution, directory, collectionDate, aoi, clouds, username, password)

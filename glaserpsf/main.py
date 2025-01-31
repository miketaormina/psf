import numpy
from numpy import all, asarray, array, where, exp
import pandas as pd
from pandas import DataFrame
from skimage.filters import gaussian as gaussian_filter
from skimage.feature import peak_local_max
from scipy.stats import multivariate_normal
import matplotlib.pyplot as plt
import math
import scipy.optimize as opt
from numpy.random import default_rng
from tqdm.auto import tqdm
from time import time

max_bead_default=10000
# restricting rotation
rotation_bounds = [5.0*numpy.pi/180* i for i in [-1,1]]

def compute(im, options):

    im = im.astype(float)
    t0 = time()
    print(f'Finding beads in im ({im.shape})...')
    beads, maxima, centers, smoothed = getCenters(im, options)
    print(f'Found beads in {(time()-t0)/60} minute.')
    
    x = numpy.linspace(-beads[0].shape[2]/2.0, beads[0].shape[2]/2.0, beads[0].shape[2])
    y = numpy.linspace(-beads[0].shape[1]/2.0, beads[0].shape[1]/2.0, beads[0].shape[1])
    z = numpy.linspace(-beads[0].shape[0]/2.0, beads[0].shape[0]/2.0, beads[0].shape[0])

    initial_guess = (0,0,0,
        (options['wavelength']/1000.0/(2*options['NA']))*options['pxPerUmLat']/(4*numpy.sqrt(-0.5*numpy.log(0.5)))+options['bead_size'],
        (options['wavelength']/1000.0/(2*options['NA']))*options['pxPerUmLat']/(4*numpy.sqrt(-0.5*numpy.log(0.5)))+options['bead_size'],
        (options['wavelength']/1000.0/(2*options['NA']))*options['pxPerUmAx']/(4*numpy.sqrt(-0.5*numpy.log(0.5)))+options['bead_size'],
        1,0,
        0,0,0)

    lower_bounds = (-beads[0].shape[2]/2.0, -beads[0].shape[1]/2.0, -beads[0].shape[0]/2.0,
        0.1, 0.1, 0.1,
        0.5, -0.1,
        rotation_bounds[0],rotation_bounds[0],rotation_bounds[0])

    upper_bounds = (beads[0].shape[2]/2.0, beads[0].shape[1]/2.0, beads[0].shape[0]/2.0,
        beads[0].shape[2], beads[0].shape[1], beads[0].shape[0],
        1.1, 0.1,
        rotation_bounds[1], rotation_bounds[1], rotation_bounds[1])

    X, Z, Y = numpy.meshgrid(x, z, y)

    #data = [getPSF(i, numpy.array([X,Y,Z]), initial_guess, lower_bounds, upper_bounds, options) for i in beads]
    data = []
    for i in tqdm(beads, total=len(beads)):
        data.append(getPSF(i, numpy.array([X,Y,Z]), initial_guess, lower_bounds, upper_bounds, options))
    PSF = pd.concat([i for i in data])
    PSF['Max'] = maxima
    PSF['x_center'] = centers[:,2]
    PSF['y_center'] = centers[:,1]
    PSF['z_center'] = centers[:,0]
    PSF['bead'] = beads
    PSF = PSF.reset_index().drop(['index'],axis=1)
    
    return PSF, smoothed

def inside(shape, center, window):
    """
    Returns boolean if a center and its window is fully contained
    within the shape of the image on all three axes
    """
    return all([(center[i]-window[i] >= 0) & (center[i]+window[i] <= shape[i]) for i in range(0,3)])

def volume(im, center, window):
    if inside(im.shape, center, window):
        volume = im[(center[0]-window[0]):(center[0]+window[0]), (center[1]-window[1]):(center[1]+window[1]), (center[2]-window[2]):(center[2]+window[2])]
        volume = volume.astype('float64')
        baseline = volume[[0,-1],[0,-1],[0,-1]].mean()
        volume = volume - baseline
        volume = volume/volume.max()
        return volume

def findBeads(im, window, thresh):
    t0 = time()
    print(f'Applying smoothing filter and localizing beads...')
    smoothed = gaussian_filter(im, 1, output=None, mode='nearest', cval=0, multichannel=None)
    #print(f'Smoothed in {(time()-t0)/60} minutes. Now finding beads...')
    t0 = time()
    centers = peak_local_max(smoothed, min_distance=3, threshold_rel=thresh, exclude_border=True)
    print(f'Found beads in {(time()-t0)/60} minutes.')
    return centers, smoothed.max(axis=0)

def keepBeads(im, window, centers, options):
    print(f'Filtering found beads...')
    t0 = time()
    max_beads = options.get('maxBeads',max_bead_default)
    print(f'Found {len(centers)} beads, randomly choosing no more than {max_beads} and filtering on window. Default maxBeads currently set to {max_bead_default}.')
    if len(centers)>max_beads:
        rng = default_rng()
        bead_idx = rng.choice(len(centers), max_beads, replace=False)
        centers = asarray([centers[i] for i in bead_idx])
        
    centersM = asarray([[x[0]/options['pxPerUmAx'], x[1]/options['pxPerUmLat'], x[2]/options['pxPerUmLat']] for x in centers])
    centerDists = [nearest(x,centersM) for x in centersM]
    keep = where([x>3 for x in centerDists])
    centers = centers[keep[0],:]
    keep = where([inside(im.shape, x, window) for x in centers])
    print(f'Filtered to {len(centers[keep[0],:])} beads in {(time()-t0)/60} minutes.')
    return centers[keep[0],:]

def getCenters(im, options):
    window = [options['windowUm'][0]*options['pxPerUmAx'], options['windowUm'][1]*options['pxPerUmLat'], options['windowUm'][2]*options['pxPerUmLat']]
    window = [round(x) for x in window]
    centers, smoothed = findBeads(im, window, options['thresh'])
    centers = keepBeads(im, window, centers, options)
    beads = [volume(im, x, window) for x in centers]
    maxima = [im[x[0], x[1], x[2]] for x in centers]
    return beads, maxima, centers, smoothed

def getPSF(bead, XYZ, initial_guess, lower_bounds, upper_bounds, options):

    bead = bead/numpy.max(bead)
    
    #This doesn't seem to catch fit failures, not sure why
    try:
        popt, pcov = opt.curve_fit(gaussian_3D, XYZ, 
                                bead.ravel(), p0 = initial_guess,
                                bounds = (lower_bounds, upper_bounds))
    except RuntimeError:
        data = DataFrame([numpy.nan,]*6, index = ['FWHM_x', 'FWHM_y', 'FWHM_z', 'rotx', 'roty', 'rotz']).T    
        return data

    xo, yo, zo, sigma_x, sigma_y, sigma_z, amplitude, offset, rotx, roty, rotz = popt[0], popt[1], popt[2], popt[3], popt[4], popt[5], popt[6], popt[7], popt[8], popt[9], popt[10]

    FWHM_x = numpy.abs(4*sigma_x*numpy.sqrt(-0.5*numpy.log(0.5)))/options['pxPerUmLat']
    FWHM_y = numpy.abs(4*sigma_y*numpy.sqrt(-0.5*numpy.log(0.5)))/options['pxPerUmLat']
    FWHM_z = numpy.abs(4*sigma_z*numpy.sqrt(-0.5*numpy.log(0.5)))/options['pxPerUmAx']

    # are x_perr etc from pcov?
    #data = DataFrame([FWHM_x, FWHM_y, FWHM_z, rotx, roty, rotz], index = ['FWHM_x', 'FWHM_y', 'FWHM_z', 'x_perr', 'y_perr', 'z_perr', 'rotx', 'roty', 'rotz']).T
    data = DataFrame([FWHM_x, FWHM_y, FWHM_z, rotx, roty, rotz], index = ['FWHM_x', 'FWHM_y', 'FWHM_z', 'rotx', 'roty', 'rotz']).T

    return data
    
def dist(x,y):
    return ((x - y)**2)[1:].sum()**(.5)

def nearest(x,centers):
    z = [dist(x,y) for y in centers if not (x == y).all()]
    return abs(array(z)).min(axis=0)

def gaussian_3D(XYZ, xo, yo, zo, sigma_x, sigma_y, sigma_z, amplitude, offset, rotx, roty, rotz):

    # Function to fit, returns 2D gaussian function as 1D array

    XRot = numpy.array([[1, 0, 0], [0, numpy.cos(rotx),  numpy.sin(rotx)],[0, -numpy.sin(rotx), numpy.cos(rotx)]])

    YRot = numpy.array([[numpy.cos(roty), 0, -numpy.sin(roty)], [0, 1, 0],[numpy.sin(roty), 0, numpy.cos(roty)]])
    
    ZRot = numpy.array([[numpy.cos(rotz),  numpy.sin(rotz), 0],[-numpy.sin(rotz), numpy.cos(rotz), 0],[0, 0, 1]])

    XYZ = numpy.einsum('ij,jabc->iabc', XRot, XYZ)
    XYZ = numpy.einsum('ij,jabc->iabc', YRot, XYZ)
    XYZ = numpy.einsum('ij,jabc->iabc', ZRot, XYZ)

    g = offset + amplitude*numpy.exp(-(((XYZ[0]-xo)**2)/(2*sigma_x**2) + ((XYZ[1]-yo)**2)/(2*sigma_y**2) + ((XYZ[2]-zo)**2)/(2*sigma_z**2)))

    return g.ravel()
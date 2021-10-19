# psf
 A function for quantifying point spread functions in 3D. Based on Nick Sofroniew's [code](https://github.com/sofroniewn/psf/).

 ## Example usage

from skimage.io import imread
from skimage.io import imsave
from main import compute

sampling = 1.34 # um/px
wavelength = 638.0 # nm
NA = 0.7 # numerical aperture in sample
bead_size = 0.150 # um
windowUm = [5, 5, 5] # um
options = {'pxPerUmLat':1.0/sampling, 'pxPerUmAx':1.0/sampling, 'wavelength':wavelength, 'NA':NA, 'bead_size':bead_size, 'windowUm':windowUm}
options['thresh'] = 0.05

im = imread('./data/eci-beads-nodo-638.tif', plugin='tifffile')
data, smoothed = compute(im, options)
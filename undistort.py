import numarray as nx
import numarray.linear_algebra as linalg
from numarray.ieeespecial import inf, nan
import math

import matplotlib.mlab as mlab

def apply_distortion(x,k):
    if len(k) < 5:
        newk = [0]*5
        for i in range(len(k)):
            newk[i] = k[i]
        k = newk
    m,n = x.shape
    # Add distortion
    r2 = x[0,:]**2 + x[1,:]**2
    r4 = r2**2
    r6 = r2**3

    # Radial distortion:
    cdist = 1 + k[0]*r2 + k[1]*r4 + k[4]*r6

    #print 'cdist',cdist
    xd1 = x * nx.matrixmultiply(nx.ones((2,1)),cdist[nx.NewAxis,:])
    #print 'xd1',xd1

    coeff = nx.matrixmultiply(nx.reshape( nx.transpose(nx.array([ cdist, cdist])),(2*n,1)),
                              nx.ones((1,3)))
    #print 'coeff',coeff

    # tangential distortion:

    a1 = 2*x[0,:]*x[1,:]
    a2 = r2 + 2*x[0,:]**2
    a3 = r2 + 2*x[1,:]**2

    delta_x = nx.array([ k[2]*a1 + k[3]*a2,
                         k[2]*a3 + k[3]*a1])

    if 0:
        aa = nx.matrixmultiply((2*k[2]*x[1,:] + 6*k[3]*x[0,:])[:,nx.NewAxis], nx.ones((1,3)))
        bb = nx.matrixmultiply((2*k[2]*x[0,:] + 2*k[3]*x[1,:])[:,nx.NewAxis], nx.ones((1,3)))
        cc = nx.matrixmultiply((6*k[2]*x[1,:] + 2*k[3]*x[0,:])[:,nx.NewAxis], nx.ones((1,3)))
    #print 'aa',aa
    #print 'bb',bb
    #print 'cc',cc

    #print 'xd1.shape',xd1.shape
    #print 'delta_x.shape',delta_x.shape
    xd = xd1 + delta_x
    #print 'xd/1e3',xd/1e3
    return xd

def rect(I,R=None,f=None,c=None,k=None,alpha=None,KK_new=None):
    """

    arguments:
    
    I is image

    optional arguments:
    
    R is 3x3 rotation (of affine transformation) matrix, defaults to eye(3)
    f is focal length (horizontal and vertical), defaults to (1,1)
    c is image center (horizontal and vertical), defaults to (0,0)
    k is nonlinear parameters, defaults to (0,0,0,0,0)
    """
    if R is None:
        R = nx.array([[1,0,0],[0,1,0],[0,0,1]])
    if f is None:
        f = (1,1)
    if c is None:
        c = (0,0)
    if k is None:
        k = (0,0,0,0,0)
    if KK_new is None:
        KK_new = nx.array([[ f[0], 0, c[0]],
                           [ 0,  f[1], c[1]],
                           [ 0,    0,   1]])
    if alpha is None:
        alpha = 0
    

    # Note: R is the motion of the points in space
    # So: X2 = R*X where X: coord in the old reference frame, X2: coord in the new ref frame.

    
    nr, nc = I.shape # must be 2D (grayscale) image

    # put I in matlab uni-dimensional index format
    I = I.copy()
    I = nx.transpose(I).copy()
    I.ravel() 

    Irec = 255.0*nx.ones((nr*nc,))

    mx, my = mlab.meshgrid( nx.arange(nc), nx.arange(nr) )
    #print 'mx',mx
    px = nx.reshape( mx, (nc*nr,) )
    #print 'px',px
    py = nx.reshape( my, (nc*nr,) )

##    A = linalg.inverse(KK_new)
##    b = nx.array( [px,
##                   py,
##                   nx.ones(px.shape)])
    rays = nx.matrixmultiply(linalg.inverse(KK_new),nx.array( [px,
                                                               py,
                                                               nx.ones(px.shape)]))
    #print 'rays',rays

    # Rotation: (or affine transformation):
    rays2 = nx.matrixmultiply(nx.transpose(R),rays)
    #print 'rays2',rays2
    
    x = nx.array( [ rays2[0,:]/rays2[2,:], rays2[1,:]/rays2[2,] ] )
    #print 'x',x

    # Add distortion
    xd = apply_distortion(x, k)
    #print 'xd',xd

    # Reconvert in pixels:

    px2 = f[0]*(xd[0,:]+alpha*xd[1,:])+c[0]
    py2 = f[1]*xd[1,:]+c[1]
    #print 'px2',px2
    #print 'py2',py2

    
    # Interpolate between the closest pixels:

    px_0 = nx.floor(px2)
    
    
    py_0 = nx.floor(py2)
    if 0:
        py_1 = py_0 + 1;

    good_points = nx.where((px_0>=0) & (px_0 <= (nc-2)) & (py_0 >= 0) & (py_0 <= (nr-2)))[0]
    #print 'good_points',good_points

    px2 = px2[good_points]
    py2 = py2[good_points]
    px_0 = px_0[good_points]
    py_0 = py_0[good_points]
    
    alpha_x = px2 - px_0
    #print 'alpha_x',alpha_x
    alpha_y = py2 - py_0

    a1 = (1 - alpha_y)*(1 - alpha_x)
    a2 = (1 - alpha_y)*alpha_x
    a3 = alpha_y * (1 - alpha_x)
    a4 = alpha_y * alpha_x

    #print 'a2',a2

    ind_lu = px_0 * nr + py_0
    #print 'ind_lu',ind_lu
    ind_ru = (px_0 + 1) * nr + py_0
    ind_ld = px_0 * nr + (py_0 + 1)
    ind_rd = (px_0 + 1) * nr + (py_0 + 1)

    ind_new = (px[good_points])*nr + py[good_points]

    #print 'ind_new',ind_new
    #print 'I[ind_lu]',I[ind_lu]
    Irec[ind_new] = a1 * I[ind_lu] + a2 * I[ind_ru] + a3 * I[ind_ld] + a4 * I[ind_rd]

    # convert matlab unidimensional format into numarray format
    Irec = nx.reshape(Irec,(nc,nr))
    Irec = nx.transpose(Irec)
    
    return Irec

def undistort( reconstructor, distorted_image, cam_id ):
    intrin = reconstructor.get_intrinsic_linear(cam_id)
    k = reconstructor.get_intrinsic_nonlinear(cam_id)
    f = intrin[0,0], intrin[1,1] # focal length
    c = intrin[0,2], intrin[1,2] # camera center
    im = rect(distorted_image, f=f, c=c, k=k) # perform the undistortion
    im = im.astype(nx.UInt8)
    return im

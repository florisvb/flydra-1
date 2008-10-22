from __future__ import division
from __future__ import with_statement
import pkg_resources
if 1:
    # deal with old files, forcing to numpy
    import tables.flavor
    tables.flavor.restrict_flavors(keep=['numpy'])
import sets, os, sys, math, time, collections

import numpy
import numpy as np
from optparse import OptionParser
import flydra.a2.core_analysis as core_analysis
import flydra.a2.flypos
import flydra.a2.analysis_options as analysis_options

import flydra.a2.posts as posts
import flydra.a2.xml_stimulus as xml_stimulus

def angle_diff(ang1,ang2):
    return np.mod((ang1-ang2)+np.pi,2*np.pi)-np.pi

def test_angle_diff():
    ang1 = np.array([np.pi-0.001, -0.001,  0.001, np.pi+0.001])
    ang2 = np.array([np.pi+0.001,  0.001, -0.001, np.pi-0.001])
    actual = angle_diff(ang1,ang2)
    expected = np.array([-0.002, -0.002, 0.002, 0.002])
    #print 'actual',actual
    #print 'expected',expected

def get_horiz_turns( vx,vy, subsample_factor=None, frames_per_second=None):
    """return angular velocity of velocity direction in rad/sec"""
    N_observations = len(vx)//subsample_factor
    horiz_turns = []
    horiz_vel_angle = np.arctan2( vy, vx )
    d_angles = angle_diff(horiz_vel_angle[1:],horiz_vel_angle[:-1])
    for i in range( N_observations ):
        start = i*subsample_factor
        stop = (i+1)*subsample_factor
        total_angular_change = np.sum(  d_angles[start:stop] )
        whole_dt = 1.0/frames_per_second * subsample_factor
        vel_angular_rate = total_angular_change/whole_dt
        horiz_turns.append( vel_angular_rate ) # rad/sec
    horiz_turns = np.array( horiz_turns )
    return horiz_turns

def create_analysis_array( rec, subsample_factor=5, frames_per_second=None, skip_missing=True ):
    """from densely-spaced input data, create analysis array

    array has rows that are observations and columns that are features.

    Inputs
    ======
    rec - record array of densely-spaced input

    Outputs
    =======
    A - an MxN array of M observations over N features
    rowlabels - an array the length of rec labeling the corresponding row of A

    rough example:

    input

    a   b   c
    --- --- ---
    0   10  20
    1   11  30
    2   12  40
    3   13  50
    4   14  60

    output
    ------

    A = [[2,12,40]]
    rowlabls = [ -1, 0, 0, 0, -1 ]

    """
    rowlabels = np.nan*np.ones( (len(rec),))

    rowlabels_non_nan = np.arange( len(rec) // subsample_factor )
    rowlabels_non_nan = rowlabels_non_nan.repeat( subsample_factor )

    start_idx = 1 # skip nan at start
    stop_idx = len(rowlabels_non_nan)+1
    if stop_idx==len(rowlabels):
        stop_idx -= subsample_factor # skip nan at stop
    rowlabels[start_idx:stop_idx] = rowlabels_non_nan

    vx = rec['vel_x'][start_idx:stop_idx]
    vy = rec['vel_y'][start_idx:stop_idx]
    horizontal_angular_velocity = get_horiz_turns( vx,vy, subsample_factor=subsample_factor,
                                                   frames_per_second=frames_per_second)

    closest_dist = np.ma.array(rec[ 'closest_dist' ],mask=rec[ 'closest_dist_mask' ])
    angle_of_closest_dist = np.ma.array(rec[ 'angle_of_closest_dist' ],mask=rec[ 'closest_dist_mask' ])
    post_angle = angle_of_closest_dist[start_idx:stop_idx]
    try:
        sin_post_angle = np.sin( post_angle )
    except:
        print 'post_angle'
        print post_angle
        raise

    def downsamp(arr):
        N_observations = len(arr)//subsample_factor
        x = np.ma.reshape(arr, (N_observations,subsample_factor))
        x = np.ma.mean(x,axis=1)
        return x

    A = [ horizontal_angular_velocity,
          downsamp(rec['vel_horiz'][start_idx:stop_idx]),
          downsamp(rec['vel_z'][start_idx:stop_idx]),
          downsamp(closest_dist[start_idx:stop_idx]), # NL func or binarize on this?
          downsamp(post_angle),
          downsamp(sin_post_angle),
          ]
    A_names = ['angular velocity about Z axis (rad/sec)',
               'horizontal velocity (m/sec)',
               'vertical velocity (m/sec)',
               'distance to closest post (m)',
               'angle to post (rad)',
               'sin(angle to post)',
               ]
    A = [np.ma.array(ai,fill_value=np.nan) for ai in A]
    A = [ai.filled() for ai in A] # convert masked entries to nan
    if 1:
        shape = None
        for i,ai in enumerate(A):
            if shape is None:
                shape=ai.shape
            try:
                assert shape==ai.shape
            except:
                print 'assertion failed for row %d'%i
                raise
    DEBUG=False
    if DEBUG:
        N_observations = len(A[0])
        for i in range(N_observations):

            this_start_idx = start_idx + i*subsample_factor
            this_stop_idx = start_idx + (i+1)*subsample_factor
            if 1:
                # test indexing
                idx1 = np.nonzero(rowlabels == i)[0]
                idx2 = np.arange(this_start_idx,this_stop_idx)
                assert np.allclose(idx1,idx2)
            if 1:
                import pylab

                # make plot
                xi = rec['x'][this_start_idx:this_stop_idx]
                yi = rec['y'][this_start_idx:this_stop_idx]
                fig=pylab.figure(figsize=(3,3))
                ax=fig.add_subplot(1,1,1)
                ax.plot(xi,yi,'o-')
                ax.text(xi[0],yi[0],'i %d, turn: %.1f, dist %.1f'%(
                    i,horizontal_angular_velocity[i],A[3][i]))
                ax.set_aspect('equal')
                fig.savefig('debug%05d.png'%i)
                pylab.close(fig)
    A = np.array(A).T # observations = rows, attributes = columns
    if skip_missing:
        Anew = []
        inew = 0

        for i,ai in enumerate(A):
            this_start_idx = start_idx + i*subsample_factor
            this_stop_idx = start_idx + (i+1)*subsample_factor
            #print
            if np.any(~np.isfinite(ai)):
                ## #rowlabels[this_start_idx:] -= 1
                ## #rowlabels[rowlabels==i] = UNUSED_ROWLABEL

                ## #rowlabels = np.ma.masked_where(rowlabels==i, rowlabels) # mask these rows
                ## rowlabels.mask[rowlabels==i] = True
                ## rowlabels[this_start_idx:] -= 1
                rowlabel=np.nan
            else:
                Anew.append( ai )
                rowlabel=inew
                inew += 1

            rowlabels[this_start_idx:this_stop_idx] = rowlabel

            if 0 and i <=45:
                np.set_printoptions(linewidth=150,suppress=True)
                print 'i',i
                print 'np.any(~np.isfinite(ai))',np.any(~np.isfinite(ai))
                #print 'A[:i+1]'
                #print A[:i+1]
                print np.array(Anew)
                print
                print rowlabels[ : (start_idx + (i+1)*subsample_factor + 10) ]
                print
                if 0 and i==30:
                    sys.exit(0)
        A = np.array(Anew)

    return A, rowlabels, A_names

def normalize_array(A):
    column_means = np.mean(A,axis=0)
    column_std = np.std(A,axis=0)
    norm_info = {'means':column_means,
                 'std':column_std}
    normA = (A - column_means)/column_std
    return normA,norm_info

PICK=1
if PICK:
    global line2data
    global ax_xy, ax_xz
    global all_figs

    line2data = {}
    all_figs = []
    def onpick1(event):

        global line2data
        global ax_xy, ax_xz
        global all_figs

        import matplotlib.lines

        print 'onpick1 called:',event

        if isinstance(event.artist,matplotlib.lines.Line2D): # why is Line2D in the namespace??
            thisline = event.artist
            data,myax = line2data[thisline]
            # data is DataAssoc instance
            xdata = thisline.get_xdata()
            ydata = thisline.get_ydata()
            ind = event.ind

            rows_by_trace_id = data.elems_by_trace_id_for_Aidxs( ind )
            trace_ids = rows_by_trace_id.keys()
            for trace_id in trace_ids:
                rows = rows_by_trace_id[trace_id]

                ax_xy.plot( rows['x'], rows['y'], 'r.' )
                ax_xz.plot( rows['x'], rows['z'], 'r.' )

            for fig in all_figs:
                fig.canvas.draw()

class DataAssoc(object):
    def __init__(self, all_rowlabels, trace_ids, orig_data_by_trace_id, orig_row_offset_by_trace_id):
        self._all_rowlabels = np.ma.asarray(all_rowlabels)
        assert len(self._all_rowlabels.shape) == 1 # 1d array
        self._trace_ids = trace_ids
        self._orig_data_by_trace_id = orig_data_by_trace_id
        for value in self._orig_data_by_trace_id.itervalues():
            if not isinstance(value,np.ndarray):
                raise TypeError("original data must be numpy arrays!") # required for indexing

        self.orig_trace_id_and_idxs_from_A_row = []
        for i,trace_id in enumerate(self._trace_ids):
            cond = self._all_rowlabels==i
            cum_orig_idxs = np.nonzero(cond)[0]
            if len(cum_orig_idxs)==0:
                raise RuntimeError('the generated data must come from somewhere, but could not find it in rowlabels!')
            ## if i==27:
            ##     print 'self._all_rowlabels[130:150]',self._all_rowlabels[130:150]
            ##     print 'cond[130:150]',cond[130:150]
            ##     print 'cum_orig_idxs',cum_orig_idxs

            offset = orig_row_offset_by_trace_id[trace_id]
            orig_idxs = cum_orig_idxs - offset

            orig_idxs = orig_idxs.tolist()
            self.orig_trace_id_and_idxs_from_A_row.append( (trace_id, orig_idxs) )

    def idxs_by_trace_id_for_Aidxs(self,ind):
        x=collections.defaultdict(list)
        for ii in ind:
            trace_id, orig_idxs = self.orig_trace_id_and_idxs_from_A_row[ii]
            x[trace_id].extend( orig_idxs )

        # convert to numpy arrays (in normal dict) and return
        idxs_by_trace_id = {}
        for trace_id in x.keys():
            idxs_by_trace_id[trace_id] = np.array( x[trace_id] )

        return idxs_by_trace_id

    def elems_by_trace_id_for_Aidxs(self,ind):
        idxs_by_trace_id = self.idxs_by_trace_id_for_Aidxs(ind)
        results = {}
        for trace_id, orig_idxs in idxs_by_trace_id.iteritems():
            all_orig_elements = self._orig_data_by_trace_id[trace_id]
            try:
                selected_orig_elements = all_orig_elements[orig_idxs]
            except:
                print 'ind',ind
                print 'orig_idxs',orig_idxs
                raise
            results[trace_id] = selected_orig_elements
        return results

def test_data_assoc_1():
    # define the original data:
    a='trace A'
    b='trace B'
    orig_data_by_trace_id = {a:np.array([ 0.1, 0.2, 0.3, 0.4,   # becomes A row 0
                                          1.1, 1.2, ]),          # becomes A row 1
                             b:np.array([ 2.1,                  # becomes A row 2
                                          3.1, 3.2, 3,3,3,3,3])} # becomes A row 3

    # now A matrix is somehow generated from it:
    A = [[1,2], # from trace A rows 0,1,2,3
         [2,3], # from trace A rows 4,5
         [3,4], # from trace B rows 0
         [5,6]] # from trace B rows 1,2,3,4,5,6,7
    trace_ids = [a,a,b,b] # must be same length as A
    all_rowlabels = [ 0, 0, 0, 0, 1,1, 2, 3,3,3,3,3,3,3] # one element for every element of all orig_data
    orig_row_offset_by_trace_id = {a:0, # of all_rowlabels into trace_id specific elements
                                   b:6}
    d = DataAssoc(all_rowlabels, trace_ids, orig_data_by_trace_id, orig_row_offset_by_trace_id)

    # get all data from a
    results1 = d.idxs_by_trace_id_for_Aidxs( [0,1] )
    assert results1.keys() == [a]
    assert np.allclose(results1[a], [0,1,2,3, 4,5] )

    # check element view
    results1 = d.elems_by_trace_id_for_Aidxs( [0,1] )
    assert results1.keys() == [a]
    assert np.allclose(results1[a], [ 0.1, 0.2, 0.3, 0.4, 1.1, 1.2 ] )

    # get some data from a
    results1 = d.idxs_by_trace_id_for_Aidxs( [0] )
    assert results1.keys() == [a]
    assert np.allclose(results1[a], [0,1,2,3] )

    # get all data from a
    results1 = d.idxs_by_trace_id_for_Aidxs( [1] )
    assert results1.keys() == [a]
    assert np.allclose(results1[a], [4,5] )



    # get all data from b
    results2 = d.idxs_by_trace_id_for_Aidxs( [2,3] )
    assert results2.keys() == [b]
    assert np.allclose(results2[b], [0,1,2,3,4,5,6,7] )

    # check element view
    results2 = d.elems_by_trace_id_for_Aidxs( [2,3] )
    assert results2.keys() == [b]
    assert np.allclose(results2[b], [ 2.1, 3.1, 3.2, 3,3,3,3,3])

    # get some data from b
    results2 = d.idxs_by_trace_id_for_Aidxs( [2] )
    assert results2.keys() == [b]
    assert np.allclose(results2[b], [0])

    # get some data from b
    results2 = d.idxs_by_trace_id_for_Aidxs( [3] )
    assert results2.keys() == [b]
    assert np.allclose(results2[b], [1,2,3,4,5,6,7] )

    # get empty
    results3 = d.idxs_by_trace_id_for_Aidxs( [] )
    assert len(results3.keys())==0

def doit(options=None):
    if options.obj_only is not None:
        raise ValueError('obj_only is not a valid option for this function')

    kalman_rows, fps, stim_xml = posts.read_files_and_fuse_ids(options=options)
    trace_id = options.kalman_filename
    results_recarray = posts.calc_retinal_coord_array(kalman_rows, fps, stim_xml)

    # pretend (for now) that we have lots of data files:
    orig_data_by_trace_id = {trace_id:results_recarray} # keep organized

    ## results_recarrays = [results_recarray]
    ## unique_trace_ids = [trace_id]

    all_A = []
    all_rowlabels = []
    trace_ids = []
    rowlabels_inc = 0
    orig_row_offset_by_trace_id = {}
    #for trace_id,results_recarray in zip(unique_trace_ids,results_recarrays):
    for trace_id,results_recarray in orig_data_by_trace_id.iteritems():
        print 'trace_id',trace_id

        A, rowlabels, A_names = create_analysis_array( results_recarray,
                                                       frames_per_second=fps,
                                                       skip_missing=True, # temporary
                                                       )
        all_A.append(A)
        #rowlabels = np.ma.masked_where( np.isnan(rowlabels), rowlabels )
        rowlabels += rowlabels_inc
        all_rowlabels.append(rowlabels)
        orig_row_offset_by_trace_id[trace_id] = rowlabels_inc
        rowlabels_inc += len(A)
        trace_ids.extend( [trace_id]*len(A) )

    # combine all observations into one giant array
    A=np.vstack(all_A)
    #all_rowlabels = np.ma.hstack(all_rowlabels)
    all_rowlabels = np.hstack(all_rowlabels)
    #print 'all_rowlabels[:140]',all_rowlabels[:140]
    del rowlabels

    data = DataAssoc(all_rowlabels, trace_ids, orig_data_by_trace_id, orig_row_offset_by_trace_id)

    normA,norm_info = normalize_array(A)
    U,s,Vh = np.linalg.svd(normA,full_matrices=False)


    if 1:
        print np.set_printoptions(linewidth=150,suppress=True)
        print 'array size',normA.shape
        print 'U.shape',U.shape
        print 'U[:10]'
        print U[:10]
        print 's'
        print s
        print 'Vh.shape',Vh.shape
        print 'Vh'
        print Vh

    if 1:
        import matplotlib.pyplot as plt

        ax = None
        for j in range(3):
            col = U[:,j]
            all_rows_idx = np.arange(len(col))

            x = []
            y = []
            z = []
            c = []
            for i in range(len(col)):
                rows_by_trace_id = data.elems_by_trace_id_for_Aidxs( [i] )
                for trace_id, rows in rows_by_trace_id.iteritems():
                    x.append( rows['x'] )
                    y.append( rows['y'] )
                    z.append( rows['z'] )
                    c.append( [U[i,j]]*len(rows) )
                    break # only first trace_id

            x = np.hstack(x)
            y = np.hstack(y)
            z = np.hstack(z)
            c = np.hstack(c)

            fig = plt.figure()
            ax = fig.add_subplot(2,1,1,sharex=ax)
            ax.scatter(x,y,c=c,edgecolors='none',s=5)
            stim_xml.plot_stim(ax, projection=xml_stimulus.SimpleOrthographicXYProjection() )
            #ax.plot(x,c)
            ax.set_aspect('equal')
            ax.set_title('U%d'%j)

            ax = fig.add_subplot(2,1,2,sharex=ax)
            ax.set_aspect('equal')
            ax.scatter(x,z,c=c,edgecolors='none',s=5)
            stim_xml.plot_stim(ax, projection=xml_stimulus.SimpleOrthographicXZProjection() )

            if 0:
                rows_by_trace_id = data.elems_by_trace_id_for_Aidxs( all_rows_idx )
                for trace_id, rows in rows_by_trace_id.iteritems():
                    fig=plt.figure()
                    ax = fig.add_subplot(2,1,1)
                    ax.scatter(rows['x'],rows['y'],c=col)
                    ax.set_aspect('equal')
                    ax.set_title('U%d'%j)

                    ax = fig.add_subplot(2,1,2)
                    ax.scatter(rows['x'],rows['z'],c=col)
                    ax.set_aspect('equal')
        plt.show()


    if PICK:
        global line2data
        global ax_xy, ax_xz
        global all_figs

        import matplotlib.pyplot as plt

        fig=plt.figure()
        all_figs.append(fig)

        ax_xy = fig.add_subplot(2,1,1)
        ax_xy.plot(kalman_rows['x'],kalman_rows['y'],'b.',ms=.5)
        ax_xy.set_aspect('equal')

        ax_xz = fig.add_subplot(2,1,2)
        ax_xz.plot(kalman_rows['x'],kalman_rows['z'],'b.',ms=.5)
        ax_xz.set_aspect('equal')

        if 1:
            fig=plt.figure()
            all_figs.append(fig)

            ax = fig.add_subplot(2,2,1)
            line,=ax.plot( U[:,0], U[:,1], '.', picker=5)
            line2data[line]=data,ax
            ax.set_aspect('equal')
            plt.xlabel('U0')
            plt.ylabel('U1')

            ax = fig.add_subplot(2,2,2)
            line,=ax.plot( U[:,2], U[:,1], '.', picker=5)
            line2data[line]=data,ax
            ax.set_aspect('equal')
            plt.xlabel('U2')
            plt.ylabel('U1')

            ax = fig.add_subplot(2,2,3)
            line,=ax.plot( U[:,0], U[:,2], '.', picker=5)
            line2data[line]=data,ax
            ax.set_aspect('equal')
            plt.xlabel('U0')
            plt.ylabel('U2')
            fig.canvas.mpl_connect('pick_event', onpick1)
            print 'connected events'

        if 1:
            N = Vh.shape[1]
            fig=plt.figure()
            all_figs.append(fig)

            ind = np.arange(N)
            width = 0.2
            if 1:
                Vh = Vh.T
                print 'plotting columns of Vh'
            rects1 = plt.bar(ind, Vh[0,:], width, color='r')
            rects2 = plt.bar(ind+width, Vh[1,:], width, color='y')
            rects3 = plt.bar(ind+2*width, Vh[2,:], width, color='g')

            plt.ylabel('Factor')
            locs, labels = plt.xticks(ind+width, A_names )
            plt.setp(labels, 'rotation', 'vertical')
            plt.legend( (rects1[0], rects2[0], rects3[0]), ('Vh0 (s %.1f)'%s[0],
                                                            'Vh1 (s %.1f)'%s[1],
                                                            'Vh2 (s %.1f)'%s[2]) )

        plt.show()
    return A, normA, U,s,Vh

def main():
    usage = '%prog [options]'

    parser = OptionParser(usage)

    analysis_options.add_common_options( parser )
    (options, args) = parser.parse_args()

    if len(args):
        parser.print_help()
        return

    return doit( options=options,
                 )

if __name__=='__main__':
    results = main()

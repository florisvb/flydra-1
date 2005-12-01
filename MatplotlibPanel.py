# $Id$
ENABLED = True

if ENABLED:
    import matplotlib
    matplotlib.use('WXAgg')
    import matplotlib.numerix as nx
    import matplotlib.numerix.mlab as mlab
    import pylab
    import matplotlib.cm
    import matplotlib.figure
    from matplotlib.backends.backend_wx import NavigationToolbar2Wx
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
    from matplotlib.mlab import meshgrid
    
from wxPython.wx import *

#origin = 'lower' # will have to change extent?
origin = 'upper'

class PlotPanel(wxPanel):

    def __init__(self, parent):
        wxPanel.__init__(self, parent, -1)
        self.cmap_is_fixed = True
        if ENABLED:
            self.fig = matplotlib.figure.Figure(figsize=(5,4), dpi=75)
            self.canvas = FigureCanvasWxAgg(self, -1, self.fig)
            self.toolbar = NavigationToolbar2Wx(self.canvas) #matplotlib toolbar
            self.toolbar.Realize()
            #self.toolbar.set_active([0,1])

            # Now put all into a sizer
            sizer = wxBoxSizer(wxVERTICAL)
            # This way of adding to sizer allows resizing
            sizer.Add(self.canvas, 1, wxLEFT|wxTOP|wxGROW)
            # Best to allow the toolbar to resize!
            sizer.Add(self.toolbar, 0, wxGROW)
            self.SetSizer(sizer)
            self.Fit()

    def init_plot_data(self):
        if ENABLED:
            a = self.fig.add_axes([0.075,0.1,0.75,0.85])

            start_size=656,491
            x = nx.arange(start_size[0])
            y = nx.arange(start_size[1])
            pylab.setp(a,'xlim',[0,start_size[0]])
            pylab.setp(a,'xticks',range(0,start_size[0],100))
            pylab.setp(a,'ylim',[0,start_size[1]])
            pylab.setp(a,'yticks',range(0,start_size[1],100))
            x, y = meshgrid(x, y)
            z = nx.zeros(x.shape)
            frame = z
            extent = 0, frame.shape[1]-1, frame.shape[0]-1, 0
            self.im = a.imshow( z,
                                cmap=matplotlib.cm.pink,
                                #cmap=matplotlib.cm.hsv,
                                origin=origin,
                                interpolation='nearest',
                                extent=extent,
                                )
            self.im.set_clim(0,255)

            self.cax = self.fig.add_axes([0.85,0.1,0.075,0.85])
            self.fig.colorbar( self.im, cax=self.cax, orientation='vertical')
            
            self.lines = a.plot([0],[0],'o') 	 
            pylab.setp(self.lines[0],'markerfacecolor',None) 	 
            white = (1.0,1.0,1.0) 	 
            blue = (0.0,0.0,1.0)
            #pylab.setp(self.lines[0],'color',white) 	 
            #pylab.setp(self.lines[0],'linewidth',2.0) 	 
            pylab.setp(self.lines[0],'markeredgecolor',blue) 	 
            pylab.setp(self.lines[0],'markeredgewidth',2)
            a.grid('on')
            self.toolbar.update() # Not sure why this is needed - ADS

    def set_colormap(self,cmap_str):
        cmap = getattr( matplotlib.cm, cmap_str)
        self.im.set_cmap( cmap )
        # XXX probably a hack, because it generates a new instance
        self.fig.colorbar( self.im, cax=self.cax, orientation='vertical') 

    def set_fixed_color_range(self,is_fixed):
        self.cmap_is_fixed = is_fixed

    def GetToolBar(self):
        if ENABLED:
            # You will need to override GetToolBar if you are using an 
            # unmanaged toolbar in your frame
            return self.toolbar

    def set_image(self,image,image_coords):
        if ENABLED:
            orig_shape = self.im.get_size()
            if image.shape[0] != orig_shape[0] or image.shape[1] != orig_shape[1]:
                print "main_brain WARNING: size changed to %s, don't know how to re-adjust"%str(image.shape)
                return
            if not self.cmap_is_fixed:
                rval = nx.ravel(image)
                vmin = mlab.amin(rval)
                vmax = mlab.amax(rval)
                if vmin==vmax:
                    vmax=vmin+1
                self.im.set_clim(vmin,vmax)
                
                # XXX probably a hack, because it generates a new
                # instance.
                # It seems to be necessary, though, because colorbar
                # doesn't get notified of clim changes.
                self.fig.colorbar( self.im, cax=self.cax, orientation='vertical')
                
            self.im.set_array(image)
        
    def set_points(self,points):
        if ENABLED:
            xs = []
            ys = []
            for pt in points:
                if pt[9]: # if found_anything:
                    xs.append( pt[0] )
                    ys.append( pt[1] )
            self.lines[0].set_data(xs,ys)

    def draw(self):
        if ENABLED:
            self.canvas.draw()
		
    def onEraseBackground(self, evt):
        # this is supposed to prevent redraw flicker on some X servers...
        pass


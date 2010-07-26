__author__ = 'Richard Lincoln, r.w.lincoln@gmail.com'

""" This example demonstrates how to produce a publication plot of generator
costs using matplotlib. """

import matplotlib
#matplotlib.use('WXAgg')#'TkAgg')

#matplotlib.rc('font', **{'family': 'sans-serif',
#                         'sans-serif': ['Computer Modern Sans serif']})
matplotlib.rc('font', **{'family': 'serif', 'serif': ['Computer Modern Roman']})
matplotlib.rc('text', usetex=True)

from os.path import join, dirname

import scipy
import pylab
import pylon

DATA_DIR = join(dirname(pylon.case.__file__), "test", "data")
CASE = join(DATA_DIR, "case24_ieee_rts", "case24_ieee_rts.pkl")

# Set up publication quality graphs.
#fig_width_pt = 246.0  # Get this from LaTeX using \showthe\columnwidth
#inches_per_pt = 1.0 / 72.27               # Convert pt to inch
golden_mean = (pylab.sqrt(5) - 1.0) / 2.0 # Aesthetic ratio
fig_width = 5.5#fig_width_pt * inches_per_pt  # width in inches
fig_height = fig_width * golden_mean      # height in inches
fig_size = [fig_width, fig_height]
params = {'backend': 'ps',
          'axes.labelsize': 10,
          'text.fontsize': 10,
          'legend.fontsize': 8,
          'xtick.labelsize': 8,
          'ytick.labelsize': 8,
          'text.usetex': True,
#          'markup': 'tex',
#          'text.latex.unicode': True,
          'figure.figsize': fig_size}
pylab.rcParams.update(params)

case = pylon.Case.load(CASE)

#g = [0,2,8,11,15,20,22,24,32]
g = [15,0,24,2,8,20,11,32,22]

style = [('black', '-'), ('0.5', '-'), ('black', ':'), ('0.5', ':'),
    ('black', '--'), ('0.5', '--'), ('black', '-.'), ('0.5', '-.'), ('0.8', '-')]
ns = len(style)

pylab.figure()
plots = []
for i, gi in enumerate(g):
    generator = case.generators[gi]
    if generator.pcost_model == pylon.PW_LINEAR:
        x = [x for x, _ in generator.p_cost]
        y = [y for _, y in generator.p_cost]
    elif generator.pcost_model == pylon.POLYNOMIAL:
        x = scipy.arange(generator.p_min, generator.p_max, 0.1)
        y = scipy.polyval(scipy.array(generator.p_cost), x)
    else:
        raise
    clr, ls = style[i]
    plots.append(pylab.plot(x, y, linestyle=ls, color=clr))
    pylab.xlabel("P (MW)")
    pylab.ylabel("Cost (USD/h)")
pylab.legend(plots, ["U%.0f" % case.generators[i].p_max for i in g])

pylab.annotate("Oil", (90, 7000))
pylab.annotate("Coal", (170, 3600))
pylab.annotate("Nuclear", (210, 1800))

#pylab.show()

pylab.savefig('/tmp/fig1.pdf')

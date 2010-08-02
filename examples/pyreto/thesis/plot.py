__author__ = 'Richard Lincoln, r.w.lincoln@gmail.com'

""" This script creates the plots published in Learning to Trade Power by
Richard Lincoln. """

import matplotlib
#matplotlib.use('WXAgg')#'TkAgg')

#matplotlib.rc('font', **{'family': 'sans-serif',
#                         'sans-serif': ['Computer Modern Sans serif']})
matplotlib.rc('font', **{'family': 'serif', 'serif': ['Computer Modern Roman']})
matplotlib.rc('text', usetex=True)

from pylab import \
    figure, plot, xlabel, ylabel, legend, savefig, rcParams, clf, title, grid

from scipy import arange, sqrt
from scipy.io import mmread

# Set up publication quality graphs.
#fig_width_pt = 246.0  # Get this from LaTeX using \showthe\columnwidth
#inches_per_pt = 1.0 / 72.27               # Convert pt to inch
golden_mean = (sqrt(5) - 1.0) / 2.0 # Aesthetic ratio
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
rcParams.update(params)


clr = ["black", "0.5", "0.8"]
ls = ["-"]#, ":", "--", "-."]
nc, ns = len(clr), len(ls)


def plot_results(results, gi, ylab, xlab="Time (h)"):
    figure()
    clf()
    for (result, lab) in results:
        x = arange(0.0, result.shape[1], 1.0)
        plot(x, result[gi, :],
#             color=clr[gi % nc],
#             linestyle=ls[gi % ns],
             label=lab)
    xlabel(xlab)
    ylabel(ylab)
    legend()
#    grid()


def plot5_1():
    re_action = mmread("./out/ex5_1_re_action.mtx")
    q_action = mmread("./out/ex5_1_q_action.mtx")
    enac_action = mmread("./out/ex5_1_enac_action.mtx")

    actions = [(re_action, "Roth-Erev"), (q_action, "Q-Learning"),
               (enac_action, "ENAC")]

    plot_results(actions, 0, "Action (\%)")
    title("Generator 1 Action")
    savefig('./out/fig5_1_g1_action.pdf')
    plot_results(actions, 2, "Action (\%)")
    title("Generator 2 Action")
    savefig('./out/fig5_1_g3_action.pdf')


    re_reward = mmread("./out/ex5_1_re_reward.mtx")
    q_reward = mmread("./out/ex5_1_q_reward.mtx")
    enac_reward = mmread("./out/ex5_1_enac_reward.mtx")

    rewards = [(re_reward, "Roth-Erev"), (q_reward, "Q-Learning"),
               (enac_reward, "ENAC")]

    plot_results(rewards, 0, r"Reward (\verb+$+)")
    title("Generator 1 Reward")
    savefig('./out/fig5_1_g1_reward.pdf')
    plot_results(rewards, 2, r"Reward (\verb+$+)")
    title("Generator 2 Reward")
    savefig('./out/fig5_1_g3_reward.pdf')


if __name__ == "__main__":
    plot5_1()

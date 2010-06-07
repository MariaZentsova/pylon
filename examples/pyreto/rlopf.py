__author__ = 'Richard Lincoln, r.w.lincoln@gmail.com'

""" This example demonstrates how optimise power flow with Pyreto. """

import sys
import logging
import numpy
import scipy.io
import pylab
import pylon
import pyreto

from pybrain.rl.agents import LearningAgent
from pybrain.rl.learners import ENAC
from pybrain.rl.experiments import EpisodicExperiment
from pybrain.tools.shortcuts import buildNetwork
from pybrain.tools.plotting import MultilinePlotter

logger = logging.getLogger()
for handler in logger.handlers: logger.removeHandler(handler) # rm pybrain
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG)
#logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

case = pylon.Case.load("../data/case6ww.pkl")

# Assume initial demand is peak demand and save it.
Pd0 = [b.p_demand for b in case.buses if b.type == pylon.PQ]

# Define a 24-hour load profile with hourly values.
p1h = [0.52, 0.54, 0.52, 0.50, 0.52, 0.57, 0.60, 0.71, 0.89, 0.85, 0.88, 0.94,
       0.90, 0.88, 0.88, 0.82, 0.80, 0.78, 0.76, 0.68, 0.68, 0.68, 0.65, 0.58]

p1h = [x + 0.7 * (1.0 - x) for x in p1h]

# Create an environment.
env = pyreto.CaseEnvironment(case, p1h)

# Create a task.
task = pyreto.MinimiseCostTask(env)

# Create a controller network.
nb = len([bus for bus in case.buses if bus.type == pylon.PQ])
ng = len([g for g in case.online_generators if g.bus.type != pylon.REFERENCE])
net = buildNetwork(nb, 5, ng, bias=False)

# Create an agent and select an episodic learner.
agent = LearningAgent(net, ENAC())

# Prepare for plotting.
pylab.figure()#figsize=(16,8))
pylab.ion()
plot = MultilinePlotter(autoscale=1.1, xlim=[0, len(p1h)], ylim=[0, 1])

f_dc = scipy.io.mmread("../data/fDC.mtx").flatten()
Pg_dc = scipy.io.mmread("../data/PgDC.mtx")
f_ac = scipy.io.mmread("../data/fAC.mtx").flatten()
Pg_ac = scipy.io.mmread("../data/PgAC.mtx")
Qg_ac = scipy.io.mmread("../data/QgAC.mtx")

rday = range(len(p1h))
plot.setData(0, rday, f_dc)
plot.setData(1, rday, f_ac)
plot.update()

# Create an experiment.
experiment = EpisodicExperiment(task, agent)

weeks = 52e6
days = 7
for year in range(weeks):
    all_rewards = experiment.doEpisodes(number=days)
    f_n = -1.0 * numpy.array( all_rewards[0][-len(p1h):] )
    plot.setData(2, rday, f_n)
    plot.update()


#pylab.figure()
#pylab.plot(f_dc, "g+-")
#pylab.plot(f_ac, "mx-")
#f_n = numpy.array( all_rewards[0][-len(p1h):] )
#pylab.plot(-1.0 * f_n, "ro-")
#pylab.show()

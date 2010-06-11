__author__ = 'Richard Lincoln, r.w.lincoln@gmail.com'

""" This example demonstrates how to use Pyreto to simulate an episodic power
exchange auction market. """

import sys
import logging
import pylab
import scipy

import pyreto.continuous

from pylon import Case, OPF

from pybrain.rl.agents import LearningAgent
from pybrain.rl.learners import ENAC
from pybrain.tools.shortcuts import buildNetwork
from pybrain.tools.plotting import MultilinePlotter

logger = logging.getLogger()
for handler in logger.handlers: logger.removeHandler(handler)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG)

# Saved case formats are recognised by file extension.
case = Case.load("../data/case6ww.pkl")
case.generators[0].p_cost = (0.0, 16.0, 200.0)
case.generators[1].p_cost = (0.0, 2.0, 200.0)
case.generators[2].p_cost = (0.0, 32.0, 200.0)
#pyreto.tools.plotGenCost(case.generators)

# Construct a market and specify any desired limits.
market = pyreto.SmartMarket(case, priceCap=100.0)

# Define a 24-hour load profile with hourly values.
p1h = [0.52, 0.54, 0.52, 0.50, 0.52, 0.57, 0.60, 0.71, 0.89, 0.85, 0.88, 0.94,
       0.90, 0.88, 0.88, 0.82, 0.80, 0.78, 0.76, 0.68, 0.68, 0.68, 0.65, 0.58]
p1h = p1h[:6]

# An experiment coordinates interactions between agents and their tasks.
experiment = pyreto.continuous.MarketExperiment([], [], market, p1h)

# Associate each generator in the case with an agent.
for gen in case.generators[:1]:
    # The environment provides market and case sensor values and handles
    # submission of offers/bids to the market.
    env = pyreto.continuous.MarketEnvironment([gen], market, numOffbids=2)
    # Reward is defined as profit.
    task = pyreto.continuous.ProfitTask(env, maxSteps=len(p1h))
    # Build an ANN for policy function approximation.
#    net = buildNetwork(env.outdim, 7, env.indim, bias=True, outputbias=False)
    net = buildNetwork(env.outdim, env.indim, bias=False)
    # Create an agent and select an episodic learner.
    learner = ENAC()
    agent = LearningAgent(net, learner)
    # Name the agent according to its first generator's name.
    agent.name = gen.name

    # Adjust some parameters of the NormalExplorer.
    sigma = [50.0] * env.indim
    learner.explorer.sigma = sigma
    #learner.learningRate = 0.01 # (0.1-0.001, down to 1e-7 for RNNs)

    # Add the task and agent to the experiment.
    experiment.tasks.append(task)
    experiment.agents.append(agent)

takers = case.generators[1:]
for g in takers:
    env = pyreto.continuous.MarketEnvironment([g], market, numOffbids=2)
    task = pyreto.continuous.ProfitTask(env, maxSteps=len(p1h))
    agent = pyreto.continuous.environment.ZeroAgent(env.outdim, env.indim)
    experiment.tasks.append(task)
    experiment.agents.append(agent)

# Prepare for plotting.
pylab.figure(figsize=(16,8))
pylab.ion()
plot = MultilinePlotter(autoscale=1.1, xlim=[0, len(p1h)], ylim=[0, 1])

# Solve an initial OPF.
OPF(case, market.locationalAdjustment=='dc', opt={"verbose": False}).solve()

weeks = 52 # number of roleouts
days = 2 # number of samples per learning step
for week in range(weeks):
    experiment.doEpisodes(days)

    # Scale sigma manually.
    sigma = [(sig * 0.95) - 0.05 for sig in sigma]

    for i, agent in enumerate(experiment.agents):
        state, action, reward = \
            agent.history.getSequence(agent.history.getNumSequences() - 1)
        plot.addData(i, week, scipy.mean(reward))

        agent.learn()
        agent.reset()

        if hasattr(agent, "learner"):
            agent.learner.explorer.sigma = sigma

    plot.update()

pylab.savefig("/tmp/pyreto.png")

#------------------------------------------------------------------------------
# Pylon Tutorial "Optimal Power Flow"
#
# Author: Richard Lincoln, r.w.lincoln@gmail.com
#------------------------------------------------------------------------------

""" This tutorial provides a guide for solving an Optimal Power Flow problem
using Pylon.

First import the necessary components from Pylon. """

from pylon import Case, Bus, Branch, Generator, OPF, REFERENCE

""" Import "sys" for writing to stdout. """
import sys

""" Import the logging module """
import logging

""" and set up a basic configuration. """
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

""" Create two generators, specifying their marginal cost. """
bus1 = Bus(p_demand=100.0, type=REFERENCE)
g1 = Generator(bus1, p_min=0.0, p_max=80.0, p_cost=[(0., 0.), (80., 4800.)])
bus2 = Bus()
g2 = Generator(bus2, p_min=0.0, p_max=60.0, p_cost=[(0., 0.), (60., 4500.)])

""" Connect the two generator buses """
line = Branch(bus1, bus2, r=0.05, x=0.25, b=0.06)

""" and add it all to a case. """
case = Case(buses=[bus1, bus2], branches=[line], generators=[g1, g2])

""" Non-linear AC optimal power flow """
dc = False

""" or linearised DC optimal power flow may be selected. """
dc = True

""" Pass the case to the OPF routine and solve. """
OPF(case, dc).solve()

""" View the results as ReStructuredText. """
case.save_rst(sys.stdout)

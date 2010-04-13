#------------------------------------------------------------------------------
# Pylon Tutorial "Power Flow"
#
# Author: Richard Lincoln, r.w.lincoln@gmail.com
#------------------------------------------------------------------------------

""" Import "sys" so the report can be written to stdout. """
import sys

""" Import the logging module """
import logging

""" and set up a basic configuration. """
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

""" The "pylon" package contains classes for defining a power system model and
power flow solvers. """
from pylon import \
    Case, Bus, Branch, Generator, NewtonPF, FastDecoupledPF, REFERENCE

""" Start by building up a one branch case with two generators """
bus1 = Bus(type=REFERENCE)
g1 = Generator(bus1, p=80.0, q=10.0)

""" and fixed load at the other. """
bus2 = Bus(p_demand=60.0, q_demand=4.0)
g2 = Generator(bus2, p=20.0, q=0.0)

""" Connect the two buses """
line = Branch(bus1, bus2, r=0.05, x=0.01)

""" and add it all to a new case. """
case = Case(buses=[bus1, bus2], branches=[line], generators=[g1, g2])

""" Choose to solve using either Fast Decoupled method """
solver = FastDecoupledPF(case)

""" or Newton's method """
solver = NewtonPF(case)

""" and then call the solver. """
solver.solve()

""" Write the case out to view the results. """
case.save_rst(sys.stdout)

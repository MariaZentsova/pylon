#------------------------------------------------------------------------------
# Copyright (C) 2007 Richard W. Lincoln
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 dated June, 1991.
#
# This software is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANDABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#------------------------------------------------------------------------------

""" Defines Pylon. """

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import sys
import logging
from optparse import OptionParser

from pylon.ui.model_view.swarm_mv import SwarmModelView
from pylon.pyreto.api import MarketEnvironment
from pyqle.api import Swarm

from pylon.readwrite.api import \
    read_matpower, read_psat, read_psse, MATPOWERWriter, ReSTWriter

from pylon.routine.api import \
    DCPFRoutine, DCOPFRoutine, NewtonPFRoutine, ACOPFRoutine

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG)

#------------------------------------------------------------------------------
#  Format detection:
#------------------------------------------------------------------------------

def detect_network_type(input, file_name=""):
    """ Detects the format of a network data file according to the file
    extension and the header. """

    if file_name.endswith(".m"):
        line = input.readline()
        if line.startswith("Bus.con" or line.startswith("%")):
            type = "psat"
            logger.info("Recognised PSAT data file.")
        elif line.startswith("function"):
            type = "matpower"
            logger.info("Recognised MATPOWER data file.")
        else:
            type = "matlab"
    elif file_name.endswith(".raw") or file_name.endswith(".psse"):
        type = "psse"
        logger.info("Recognised PSS/E data file.")
    else:
        type = "unrecognised"

    input.seek(0)

    return type

#------------------------------------------------------------------------------
#  "Pylon" function:
#------------------------------------------------------------------------------

class Pylon:
    """ Solves network problems. """

    # Format in which the network is stored.
    type = "any"

    # Routine type to which the network is passed.
    routine = "acpf"

    # Algorithm to be used in the routine.
    algorithm = "newton"

    # File name of input.
    file_name = ""

    # Configure traits with a portable graphical interface?
    gui = False

    # Output format type.
    output_type = "rst"

    def __init__(self, type="any", routine="acpf", algorithm="newton",
                 file_name="", gui=False, output_type="rst"):
        self.routine = routine
        self.algorithm = algorithm
        self.file_name = file_name
        self.gui = gui
        self.output_type = output_type


    def solve(self, input, output):
        """ Forms a network from the input text, obtains a solution using the
        specified routine and writes a report to the output.

        """

        # Get the network from the input.
        n = self._get_network(input)
        if n is None:
            logger.critical("Unrecognised data file.")
            sys.exit(1)

        if self.gui:
            env = MarketEnvironment(network=n)
            model = Swarm(environment=env)
            mv = SwarmModelView(model=model)
            mv.configure_traits()


        # Pass through routine.
        routine = self.routine
        algorithm = self.algorithm

        if routine == "dcpf":
            r = DCPFRoutine(network=n)
        elif routine == "acpf":
            r = NewtonPFRoutine(network=n, algorithm=algorithm)
        elif routine == "dcopf":
            r = DCOPFRoutine(network=n)
        elif routine == "acopf":
            r = ACOPFRoutine(network=n)
        else:
            logger.critical("Unrecognised routine type.")
            sys.exit(1)

        success = r.solve()

        # Portable graphical interface to Pylon.
        if self.gui:
            env = MarketEnvironment(network=n)
            model = Swarm(environment=env)
            mv = SwarmModelView(model=model)
            mv.configure_traits()
        else:
            # Solution output.
            output_type = self.output_type

            writer = None
            if output_type == "matpower":
                writer = MATPOWERWriter(n, output)
            else:
                writer = ReSTWriter(n, output)

            if writer is not None:
                writer.write()


    def _get_network(self, input):
        """ Returns the network from the input. """

        type = self.type

        if type == "any":
            type = detect_network_type(input, self.file_name)

        if type == "matpower":
            n = read_matpower(input)
        elif type == "psat":
            n = read_psat(input)
        elif type == "psse":
            n = read_psse(input)
        elif type == "matlab":
            try:
                n = read_matpower(input)
            except:
                pass
            try:
                n = read_psat(input)
            except:
                n = input.read()
        elif type == "unrecognised":
            try:
                n = read_matpower(input)
            except:
                pass
            try:
                n = read_psat(input)
            except:
                pass
            try:
                n = read_psse(input)
            except:
                n = input.read()
        else:
            n = input.read()

        return n


    def _get_routine(self):
        """ Returns the routine to which to pass the network. """

        routine = self.routine
        algorithm = self.algorithm

        if routine == "dcpf":
            r = DCPFRoutine(network=None)
        elif routine == "acpf":
            r = NewtonPFRoutine(network=None, algorithm=algorithm)
        elif routine == "dcopf":
            r = DCOPFRoutine(network=None)
        elif routine == "acopf":
            r = ACOPFRoutine(network=None)
        else:
            r = None

        return r

#------------------------------------------------------------------------------
#  "main" function:
#------------------------------------------------------------------------------

def main():
    """ Parse command line and call Pylon with the correct data """

    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-o", "--output", dest="output", metavar="FILE",
        help="Write the solution report to FILE.")

    parser.add_option("-q", "--quiet", action="store_true", dest="quiet",
        default=False, help="Print less information.")

    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
        default=False, help="Print debug information.")

    parser.add_option("-n", "--no-report", action="store_true",
        dest="no_report", default=False, help="Suppress report output.")

    parser.add_option("-d", "--debug", action="store_true", dest="debug",
        default=False, help="Print debug information.")

    parser.add_option("-t", "--input-type", dest="type", metavar="TYPE",
        default="any", help="The argument following the -t is used to "
        "indicate the format type of the input data file. The types which are "
        "currently supported include: matpower, psat, psse, m3.  If not "
        "specified Pylon will try to determine the type according to the "
        "file name extension and the file header.")

    parser.add_option("-r", "--routine", dest="routine", metavar="ROUTINE",
        default="pf", help="The argument following the -r is used to"
        "indicate the type of routine to use in solving. The types which are "
        "currently supported include: pf, opf.")

#    parser.add_option("-f", "--formulation", action="store_true",
#        dest="formulation", default="ac", help="Indicates the algorithm"
#        "formulation type to be used.  The types which are currently "
#        "supported include: dc and ac.")

    parser.add_option("-a", "--algorithm", action="store_true",
        dest="algorithm", default="newton", help="Indicates the algorithm "
    "type to be used.  The types which are currently supported include: "
    "newton, gauss, decoupled.")

    parser.add_option("-g", "--gui", action="store_true", default=False,
        dest="gui", help="A portable graphical interface to Pylon.")

    parser.add_option("-T", "--output-type", dest="otype",
        metavar="OUTPUT_TYPE", default="rst", help="Indicates the output "
        "format type.  The type swhich are currently supported include: rst, "
        "matpower.")

    parser.add_option("-p", "--paginate", action="store_true", default=False,
        dest="paginate", help="Pipe all output into less (or if set, $PAGER).")

#    parser.add_option("-h", "--help", action="store_true", default=False,
#        help="Prints the synopsis and a list of the commands.")

    parser.add_option("-V", "--version", dest="version", default=False,
        help="Output version.")

    (options,args)=parser.parse_args()

    if options.quiet:
        logger.setLevel(logging.CRITICAL)
    elif options.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    filename = ""

    if len(args) == 0 or args[0]=="-":
        filename = ""
        infile = sys.stdin
    elif len(args) > 1:
        logger.critical("Usage: %s file.txt [ -o file.rst ] "
            "[ -r dcpf|acpf|dcopf|acopf ] [ -t matpower|psat|psse ]",
            sys.argv[0]
        )
        sys.exit(1)
    else:
        filename = args[0]
        infile=open(filename)

    if options.output:
        outfile=options.output
        if outfile == "-":
            outfile = sys.stdout
            logger.setLevel(logging.CRITICAL) # we must stay quiet
    else:
        outfile = sys.stdout
        if not options.no_report:
            logger.setLevel(logging.CRITICAL) # we must stay quiet

    # Pagiante output
    if options.paginate:
        raise NotImplementedError("Pagination is not yet implemented.")


    pylon = Pylon(type=options.type, routine=options.routine,
        algorithm=options.algorithm, file_name=filename, gui=options.gui,
        output_type=options.type)
    pylon.solve(input=infile, output=outfile)

#    if filename:
#        infile.close() # Clean-up

if __name__ == "__main__":
    main()

# EOF -------------------------------------------------------------------------

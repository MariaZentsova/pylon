#------------------------------------------------------------------------------
# Copyright (C) 2009 Richard Lincoln
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

""" Defines the entry point for Pylon.
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import os
import sys
import logging
import optparse

from pylon.readwrite import MATPOWERReader, PSSEReader, PSATReader, \
    MATPOWERWriter, ReSTWriter, CSVWriter, PickleReader, PickleWriter

from pylon import DCPF, NewtonRaphson, FastDecoupled, DCOPF, ACOPF, UDOPF

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
    format="%(levelname)s: %(message)s")

logger = logging.getLogger("pylon")

#------------------------------------------------------------------------------
#  Read data file:
#------------------------------------------------------------------------------

def read_case(input, format=None):
    """ Returns a case object from the given input file object. The data
        format may be optionally specified.
    """
    # Map of data file types to readers.
    format_map = {"matpower": MATPOWERReader, "psat": PSATReader,
        "psse": PSSEReader, "pickle": PickleReader}

    # Read case data.
    if format_map.has_key(format):
        reader_klass = format_map[format]
        reader = reader_klass()
        case = reader.read(input)
    else:
        # Try each of the readers at random.
        for reader_klass in format_map.values():
            reader = reader_klass()
            try:
                case = reader.read(input)
                if case is not None:
                    break
            except:
                pass
        else:
            case = None

    return case

#------------------------------------------------------------------------------
#  Format detection:
#------------------------------------------------------------------------------

def detect_data_file(input, file_name=""):
    """ Detects the format of a network data file according to the
        file extension and the header.
    """
    _, ext = os.path.splitext(file_name)

    if ext == ".m":
        line = input.readline() # first line
        if line.startswith("function"):
            type = "matpower"
            logger.info("Recognised MATPOWER data file.")
        elif line.startswith("Bus.con" or line.startswith("%")):
            type = "psat"
            logger.info("Recognised PSAT data file.")
        else:
            type = "unrecognised"
        input.seek(0) # reset buffer for parsing

    elif (ext == ".raw") or (ext == ".psse"):
        type = "psse"
        logger.info("Recognised PSS/E data file.")

    elif (ext == ".pkl") or (ext == ".pickle"):
        type = "pickle"
        logger.info("Recognised pickled case.")

    else:
        type = None

    return type

#------------------------------------------------------------------------------
#  "main" function:
#------------------------------------------------------------------------------

def main():
    """ Parses the command line and call Pylon with the correct data.
    """
    parser = optparse.OptionParser(usage="usage: pylon [options] input_file",
                                   version="%prog 0.3.2")

    parser.add_option("-o", "--output", dest="output", metavar="FILE",
        help="Write the solution report to FILE.")

    parser.add_option("-q", "--quiet", action="store_true", dest="quiet",
        default=False, help="Print less information.")

#    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
#        default=False, help="Print debug information.")

#    parser.add_option("-g", "--gui", action="store_true", dest="gui",
#        default=False, help="Use the portable graphical interface to Pylon.")

    parser.add_option("-n", "--no-report", action="store_true",
        dest="no_report", default=False, help="Suppress report output.")

    parser.add_option("-d", "--debug", action="store_true", dest="debug",
        default=False, help="Print debug information.")

    parser.add_option("-t", "--input-type", dest="type", metavar="TYPE",
        default="any", help="The argument following the -t is used to "
        "indicate the format type of the input data file. The types which are "
        "currently supported include: matpower, psat, psse [default: %default]"
        " If not specified Pylon will try to determine the type according to "
        "the file name extension and the file header.")

    parser.add_option("-r", "--routine", dest="routine", metavar="ROUTINE",
        default="acpf", help="The argument following the -r is used to"
        "indicate the type of routine to use in solving. The types which are "
        "currently supported are: 'dcpf', 'acpf', 'dcopf', 'acopf', 'udopf' "
        "and 'none' [default: %default].")

    parser.add_option("-a", "--algorithm", action="store_true",
        metavar="ALGORITHM", dest="algorithm", default="newton",
        help="Indicates the algorithm type to be used for AC power flow. The "
        "types which are currently supported are: 'newton' and 'decoupled' "
        "[default: %default].")

    parser.add_option("-T", "--output-type", dest="otype",
        metavar="OUTPUT_TYPE", default="rst", help="Indicates the output "
        "format type.  The type swhich are currently supported include: rst, "
        "matpower, csv and excel [default: %default].")

    (options, args) = parser.parse_args()

    if options.quiet:
        logger.setLevel(logging.CRITICAL)
    elif options.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Output.
    if options.output:
        if options.output == "-":
            outfile = sys.stdout
            logger.setLevel(logging.CRITICAL) # must stay quiet
        else:
            outfile = open(options.output, "wb")
    else:
        outfile = sys.stdout
        if not options.no_report:
            logger.setLevel(logging.CRITICAL) # must stay quiet

    # Input.
    if len(args) > 1:
        parser.print_help()
        sys.exit(1)
    elif (len(args) == 0) or (args[0] == "-"):
        filename = ""
        if sys.stdin.isatty():
            # True if the file is connected to a tty device, and False
            # otherwise (pipeline or file redirection).
            parser.print_help()
            sys.exit(1)
        else:
            # Handle piped input ($ cat ehv3.raw | pylon | rst2pdf -o ans.pdf).
            infile = sys.stdin
    else:
        filename = args[0]
        infile = open(filename, "rb")

    if options.type == "any":
        type = detect_data_file(input, filename)
    else:
        type = options.type

    # Get the case from the input file-like object.
    case = read_case(input, type)

    if case is not None:
        # Routine (and algorithm) selection.
        if options.routine == "dcpf":
            routine = DCPF(case)
        elif options.routine == "acpf":
            if options.algorithm == "newton":
                routine = NewtonRaphson(case)
            elif options.algorithm == "decoupled":
                routine = FastDecoupled(case)
            else:
                logger.critical("Invalid algorithm [%s]." % options.algorithm)
                sys.exit(1)
        elif options.routine == "dcopf":
            routine = DCOPF(case)
        elif options.routine == "acopf":
            routine = ACOPF(case)
        elif options.routine == "udopf":
            routine = UDOPF(case)
        else:
            logger.critical("Invalid routine [%s]." % options.routine)
            sys.exit(1)

        # Output writer selection.
        if options.output_type == "matpower":
            writer = MATPOWERWriter(case, outfile)
        elif options.output_type == "rst":
            writer = ReSTWriter(case, outfile)
        elif options.output_type == "csv":
            writer = CSVWriter(case, outfile)
        elif options.output_type == "excel":
            from pylon.readwrite.excel_writer import ExcelWriter
            writer = ExcelWriter(case, outfile)
        elif options.output_type == "pickle":
            writer = PickleWriter(case, outfile)
        else:
            logger.critical("Invalid output type [%s]." % options.output_type)
            sys.exit(1)

        routine.solve()
        writer.write()
    else:
        logger.critical("Unable to read case data.")

    # Don't close stdin or stdout.
    if len(args) == 1:
        infile.close()
    if options.output and not (options.output == "-"):
        outfile.close()

if __name__ == "__main__":
    main()

# EOF -------------------------------------------------------------------------

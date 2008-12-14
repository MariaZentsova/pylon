#------------------------------------------------------------------------------
# Copyright (C) 2008 Richard W. Lincoln
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

""" Defines a routine for solving the power flow problem using full Newton's
method.

References:
    D. Zimmerman, Carlos E. Murillo-Sanchez and Deqiang (David) Gan,
    MATPOWER, version 3.2, http://www.pserc.cornell.edu/matpower/

"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import math
import cmath
import logging, sys
from cvxopt.base import matrix, spmatrix, sparse, spdiag, gemv, exp, mul, div
from cvxopt.umfpack import linsolve
import cvxopt.blas

from pylon.routine.ac_pf import ACPFRoutine

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG)

#------------------------------------------------------------------------------
#  Convenient conjugate function:
#------------------------------------------------------------------------------

def conj(A):
    """ Returns the complex conjugate of A as a new matrix. """

    return A.ctrans().trans()


def atan2(X, Y):

    matrix([math.arctan2(Y, X) for k in xrange(nrows*ncols)], (nrows, ncols), 'd')


def angle(z, deg=0):
    """
    Return the angle of the complex argument.

    Parameters
    ----------
    z : array_like
        A complex number or sequence of complex numbers.
    deg : bool, optional
        Return angle in degrees if True, radians if False (default).

    Returns
    -------
    angle : {ndarray, scalar}
        The counterclockwise angle from the positive real axis on
        the complex plane, with dtype as numpy.float64.

    See Also
    --------
    arctan2

    Examples
    --------
    >>> np.angle([1.0, 1.0j, 1+1j])               # in radians
    array([ 0.        ,  1.57079633,  0.78539816])
    >>> np.angle(1+1j, deg=True)                  # in degrees
    45.0

    """
    if deg:
        fact = 180/pi
    else:
        fact = 1.0
#    z = asarray(z)
    if z.typecode is "z":
        zimag = z.imag()
        zreal = z.real()
    else:
        zimag = 0
        zreal = z
    [math.arctan2(x.imag(), x.real()) for x in z]
    return atan2(zimag, zreal) * fact

#------------------------------------------------------------------------------
#  "NewtonPFRoutine" class:
#------------------------------------------------------------------------------

class NewtonPFRoutine(ACPFRoutine):
    """ Solves the power flow using full Newton's method. """

    #--------------------------------------------------------------------------
    #  Trait definitions:
    #--------------------------------------------------------------------------

    # Sparse Jacobian matrix (updated each iteration)
    J = spmatrix

    # Vector of bus voltages
    v = matrix

    # Function of non-linear differential agebraic equations
    f = matrix

    # Bus indexing for updating v
    pv_idxs = []
    pq_idxs = []
    pvpq_idxs = []
    slack_idx = 0

    #--------------------------------------------------------------------------
    #  Solve power flow using full Newton's method:
    #--------------------------------------------------------------------------

    def solve(self):
        """ Solves the AC power flow for the referenced network using full
        Newton's method.

        """

        self._make_admittance_matrix()
        self._initialise_voltage_vector()
        self._make_apparent_power_injection_vector()
        self._index_buses()

        # Initial evaluation of f(x0) and convergency check
        self.converged = False
        self._evaluate_function()
        self._check_convergence()

        iter = 0
#        while (not self.converged) and (iter < self.iter_max):
#            self.iterate()
#            self._evaluate_function()
#            self._check_convergence()
#            iter += 1

        if self.converged:
            logger.info("Routine converged in %d iterations." % iter)
        else:
            logger.info("Routine failed to converge in %d iterations." % iter)

    #--------------------------------------------------------------------------
    #  Newton iterations:
    #--------------------------------------------------------------------------

    def iterate(self):
        """ Performs Newton iterations. """

        J = self._make_jacobian()
        F = self.f

        Va = angle(self.v)
        Vm = abs(self.v)

        pv_idxs = self.pv_idxs
        pq_idxs = self.pq_idxs

        print "TYPECODE:", J.typecode
        print "TYPECODE:", F.typecode

        # Compute update step.
        #
        # Solves the sparse set of linear equations AX=B where A is a sparse
        # matrix and B is a dense matrix of the same type ("d" or "z") as A. On
        # exit B contains the solution.
        linsolve(J, F)

        dx = -1 * F # Update step.
        logger.debug("dx =\n%s" % dx)

        # Update voltage vector
        if pv_idxs:
            Va[pv_idxs] = Va[pv_idxs] + dx[range(len(pv_idxs))]

        if pq_idxs:
            Va[pq_idxs] = Va[pq_idxs] + dx[
                range(len(pv_idxs), len(pv_idxs)+len(pq_idxs))
            ]

            Vm[pq_idxs] = Vm[pq_idxs] + dx[
                range(
                    len(pv_idxs)+len(pq_idxs),
                    len(pv_idxs)+len(pq_idxs)+len(pq_idxs)
                )
            ]

        self.v = v = Vm * exp(j * Va)
        # Avoid wrapped round negative Vm
        # TODO: check necessity
#        Vm = abs(voltage)
#        Va = angle(voltage)

        return v

    #--------------------------------------------------------------------------
    #  Evaluate Jacobian:
    #--------------------------------------------------------------------------

    def _make_jacobian(self):
        """ Computes partial derivatives of power injection w.r.t. voltage.
        The following explains the expressions used to form the matrices:

        S = diag(V) * conj(Ibus) = diag(conj(Ibus)) * V

        Partials of V & Ibus w.r.t. voltage magnitudes
           dV/dVm = diag(V./abs(V))
           dI/dVm = Ybus * dV/dVm = Ybus * diag(V./abs(V))

        Partials of V & Ibus w.r.t. voltage angles
           dV/dVa = j * diag(V)
           dI/dVa = Ybus * dV/dVa = Ybus * j * diag(V)

        Partials of S w.r.t. voltage magnitudes
           dS/dVm = diag(V) * conj(dI/dVm) + diag(conj(Ibus)) * dV/dVm
                  = diag(V) * conj(Ybus * diag(V./abs(V)))
                                           + conj(diag(Ibus)) * diag(V./abs(V))

        Partials of S w.r.t. voltage angles
           dS/dVa = diag(V) * conj(dI/dVa) + diag(conj(Ibus)) * dV/dVa
                  = diag(V) * conj(Ybus * j * diag(V))
                                           + conj(diag(Ibus)) * j * diag(V)
                  = -j * diag(V) * conj(Ybus * diag(V))
                                           + conj(diag(Ibus)) * j * diag(V)
                  = j * diag(V) * conj(diag(Ibus) - Ybus * diag(V))

        References:
            D. Zimmerman, C. E. Murillo-Sanchez and D. Gan, MATPOWER,
            dSbus_dV.m, version 3.2, http://www.pserc.cornell.edu/matpower/

        """

        j = cmath.sqrt(-1)
        Y = self.Y
        v = self.v
        n = len(self.network.buses)

        pv_idxs = self.pv_idxs
        pq_idxs = self.pq_idxs
        pvpq_idxs = self.pvpq_idxs

#        Ibus = cvxopt.blas.dot(matrix(self.Y), v)
        Ibus = Y * v
#        Ibus = self.Y.trans() * v
        logger.debug("Ibus =\n%s" % Ibus)

        diagV = spmatrix(v, range(n), range(n), tc="z")
        logger.debug("diagV =\n%s" % diagV)

        diagIbus = spmatrix(Ibus, range(n), range(n), tc="z")
        logger.debug("diagIbus =\n%s" % diagIbus)

        # diagVnorm = spdiags(V./abs(V), 0, n, n);
        diagVnorm = spmatrix(div(v, abs(v)), range(n), range(n), tc="z")
        logger.debug("diagVnorm =\n%s" % diagVnorm)

        # From MATPOWER v3.2:
        # dSbus_dVm = diagV * conj(Y * diagVnorm) + conj(diagIbus) * diagVnorm;
        # dSbus_dVa = j * diagV * conj(diagIbus - Y * diagV);

        dS_dVm = diagV * conj(Y * diagVnorm) + conj(diagIbus) * diagVnorm
#        dS_dVm = dot(
#            dot(diagV, conj(dot(Y, diagVnorm))) + conj(diagIbus), diagVnorm
#        )
        #dS_dVm = dot(diagV, conj(dot(Y, diagVnorm))) + dot(conj(diagIbus), diagVnorm)
        logger.debug("dS_dVm =\n%s" % dS_dVm)

        dS_dVa = j * diagV * conj(diagIbus - Y * diagV)
#        dS_dVa = dot(dot(j, diagV), conj(dot(diagIbus - Y, diagV)))
        #dS_dVa = dot(dot(j, diagV), conj(diagIbus - dot(Y, diagV)))
        logger.debug("dS_dVa =\n%s" % dS_dVa)


#        dP_dVm = spmatrix(map(lambda x: x.real, dS_dVm), dS_dVm.I, dS_dVa.J, tc="d")

#        dP_dVm = spmatrix(dS_dVm.real(), dS_dVm.I, dS_dVa.J, tc="d")
#        logger.debug("dP_dVm =\n%s" % dP_dVm)
#
#        dP_dVa = spmatrix(dS_dVa.real(), dS_dVa.I, dS_dVa.J, tc="d")
#        logger.debug("dP_dVa =\n%s" % dP_dVa)
#
#        dQ_dVm = spmatrix(dS_dVm.imag(), dS_dVm.I, dS_dVm.J, tc="d")
#        logger.debug("dQ_dVm =\n%s" % dQ_dVm)
#
#        dQ_dVa = spmatrix(dS_dVa.imag(), dS_dVa.I, dS_dVa.J, tc="d")
#        logger.debug("dQ_dVa" % dQ_dVa)

        # From MATPOWER v3.2:
        #    j11 = real(dSbus_dVa([pv; pq], [pv; pq]));
        #    j12 = real(dSbus_dVm([pv; pq], pq));
        #    j21 = imag(dSbus_dVa(pq, [pv; pq]));
        #    j22 = imag(dSbus_dVm(pq, pq));

#            J11 = dP_dVa[pvpq_idxs, pvpq_idxs]
#            J12 = dP_dVm[pvpq_idxs, pq_idxs]
#            J21 = dQ_dVa[pq_idxs, pvpq_idxs]
#            J22 = dQ_dVm[pq_idxs, pq_idxs]

        J11 = dS_dVa[pvpq_idxs, pvpq_idxs].real()
        J12 = dS_dVm[pvpq_idxs, pq_idxs].real()
        J21 = dS_dVa[pq_idxs, pvpq_idxs].imag()
        J22 = dS_dVm[pq_idxs, pq_idxs].imag()

        logger.debug("J12 =\n%s" % J12)
        logger.debug("J22 =\n%s" % J22)

        # The width and height of one quadrant of the Jacobian.
#        w, h = J11.size
#        print "w, h", J11.size, J12.size, J21.size, J22.size

        # A single-column dense matrix containing the numerical values of
        # the nonzero entries of the four quadrants of the Jacobian in
        # column-major order.
#        values = numpy.vstack((J11.V, J12.V, J21.V, J22.V))

        # A single-column integer matrix with the row indices of the entries
        # in "values" shifted appropriately by the width of one quadrant.
#        row_idxs = numpy.vstack((J11.I, J12.I, J21.I+h, J22.I+h))

        # A single-column integer matrix with the column indices of the
        # entries in "values" shifted appropriately by the width of one
        # quadrant.
#        col_idxs = numpy.vstack((J11.J, J12.J+w, J21.J, J22.J+w))

        # A deep copy of "values" is required for contiguity.
#        J = spmatrix(values.copy(), row_idxs, col_idxs)

        JX1 = sparse([J11, J21])
        JX2 = sparse([J12, J22])
        J = sparse([JX1.T, JX2.T]).T
        logger.debug("J =\n%s" % J)

        return J

    #--------------------------------------------------------------------------
    #  Evaluate F(x):
    #--------------------------------------------------------------------------

    def _evaluate_function(self):
        """ Evaluates F(x). """

        # MATPOWER:
        #   mis = V .* conj(Ybus * V) - Sbus;
        v = self.v
        mismatch = mul(v, conj(self.Y * v)) - self.s_surplus


        real = mismatch[self.pvpq_idxs].real()
        imag = mismatch[self.pq_idxs].imag()

        self.f = f = matrix([real, imag])

        return f

    #--------------------------------------------------------------------------
    #  Check convergence:
    #--------------------------------------------------------------------------

    def _check_convergence(self):
        """ Checks if the solution has converged to within the specified
        tolerance.

        """

        F = self.f

        normF = max(abs(F))

        if normF < self.tolerance:
            self.converged = converged = True
        else:
            self.converged = converged = False
#            logger.info("Difference: %.3f" % normF-self.tolerance)

        return converged

    #--------------------------------------------------------------------------
    #  Index buses for updating v:
    #--------------------------------------------------------------------------

    def _index_buses(self):
        """ Set up indexing for updating v. """

        buses = self.network.non_islanded_buses

        # Indexing for updating v
        pv_idxs = [i for i, v in enumerate(buses) if v.mode is "PV"]
        pq_idxs = [i for i, v in enumerate(buses) if v.mode is "PQ"]
        pvpq_idxs = pv_idxs + pq_idxs

        slack_idxs = [i for i, v in enumerate(buses) if v.mode is "Slack"]
        if len(slack_idxs) > 0:
            slack_idx = slack_idxs[0]
        else:
            logger.error    ("No reference/swing/slack bus specified.")
            slack_idx = 0

        self.slack_idx = matrix(slack_idx)
        self.pv_idxs = matrix(pv_idxs)
        self.pq_idxs = matrix(pq_idxs)
        self.pvpq_idxs = matrix(pvpq_idxs)

#------------------------------------------------------------------------------
#  Standalone call:
#------------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import logging
    from os.path import join, dirname
    from pylon.readwrite.api import read_matpower

    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.DEBUG)

    data_file = join(dirname(__file__), "../test/data/case6ww.m")
    n = read_matpower(data_file)

    routine = NewtonPFRoutine(n).solve()

# EOF -------------------------------------------------------------------------

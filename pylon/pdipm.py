#------------------------------------------------------------------------------
# Copyright (C) 2010 Richard Lincoln
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

""" Primal-dual interior point method for NLP.

    References:
        Ray Zimmerman, "pdipm.m", MATPOWER, PSERC Cornell, version 4.0b1,
        http://www.pserc.cornell.edu/matpower/, December 2009
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import logging

from numpy import nonzero, Inf, any, isnan
from numpy.linalg import norm

from cvxopt import matrix, spmatrix, sparse, div, log
from cvxopt.umfpack import linsolve
#from cvxopt.cholmod import linsolve

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
#  Constants:
#------------------------------------------------------------------------------

EPS = 2**-52

#------------------------------------------------------------------------------
#  "pdipm" function:
#------------------------------------------------------------------------------

def pdipm(ipm_f, ipm_gh, ipm_hess, x0, xmin=None, xmax=None,
          A=None, l=None, u=None, feastol=1e-6, gradtol=1e-6, comptol=1e-6,
          costtol=1e-6, max_it=150, max_red=20, step_control=False,
          cost_mult=1, verbose=False):
    """ [x, f, info, Output, Lambda] = ...
            pdipm(f, gh, hess, x0, xmin, xmax, A, l, u, opt)

        min f(x)
          s.t.
        h(x) = 0
        g(x) <= 0
        l <= A*x <= u
        xmin <= x <= xmax
    """
    if xmin is None:
        xmin = matrix(-Inf, x0.size)
    if xmax is None:
        xmax = matrix(Inf, x0.size)
    if A is None:
        A = spmatrix([], [], [], (0, 0))
        l = matrix()
        u = matrix()

    # constants
    xi = 0.99995
    sigma = 0.1
    z0 = 1
    alpha_min = 1e-8
    rho_min = 0.95
    rho_max = 1.05
    mu_threshold = 1e-5

    # initialize
    i = 0                      # iteration counter
    converged = False          # flag
    nx = x0.size[0]            # number of variables
    nA = A.size[0]             # number of original linear constraints

    # add var limits to linear constraints
    AA = sparse([spmatrix(1., range(nx), range(nx)), A])
    ll = matrix([xmin, l])
    uu = matrix([xmax, u])

    # split up linear constraints
    ieq = matrix([i for i, v in enumerate(abs(uu - ll)) if v < EPS])
    igt = matrix([i for i in range(len(l)) if uu[i] >  1e10 and ll[i] > -1e10])
    ilt = matrix([i for i in range(len(l)) if uu[i] < -1e10 and ll[i] <  1e10])
    ibx = matrix([i for i in range(len(l))
                  if (abs(u[i] - l[i]) > EPS) and
                  (uu[i] < 1e10) and (ll[i] > -1e10)])
    Ae = AA[ieq, :]
    be = uu[ieq, :]
    Ai = sparse([AA[ilt, :], -AA[igt, :], AA[ibx, :], -AA[ibx, :]])
    bi = matrix([uu[ilt], -ll[igt], uu[ibx], -ll[ibx]])

    # evaluate cost f(x0) and constraints g(x0), h(x0)
    x = x0
    f, df = ipm_f(x)             # cost
    f = f * cost_mult;
    df = df * cost_mult;
    gn, hn, dgn, dhn = ipm_gh(x)           # non-linear constraints
    g = matrix([gn, Ai * x - bi])          # inequality constraints
    h = matrix([hn, Ae * x - be])          # equality constraints
    dg = sparse([dgn.T, Ai]).T             # 1st derivative of inequalities
    dh = sparse([dhn.T, Ae]).T             # 1st derivative of equalities

    # some dimensions
    neq = h.size[0]           # number of equality constraints
    niq = g.size[0]           # number of inequality constraints
    neqnln = hn.size[0]       # number of non-linear equality constraints
    niqnln = gn.size[0]       # number of non-linear inequality constraints
    nlt = len(ilt)            # number of upper bounded linear inequalities
    ngt = len(igt)            # number of lower bounded linear inequalities
    nbx = len(ibx)            # number of doubly bounded linear inequalities

    # initialize gamma, lam, mu, z, e
    gamma = 1                  # barrier coefficient
    lam = matrix(0.0, (neq, 1))
    z = z0 * matrix(1.0, (niq, 1))
    mu = z
    k = nonzero(g < -z0)
    z[k] = -g[k]
    k = nonzero(div(gamma, z) > z0);
    mu[k] = div(gamma, z(k))
    e = matrix(1.0, (niq, 1))

    # check tolerance
    f0 = f
    if step_control:
        L = f + lam.T * h + mu.T * (g + z) - gamma * sum(log(z))

    Lx = df + dh * lam + dg * mu
    feascond = max([norm(h, Inf), max(g)]) / (1 + max([ norm(x, Inf), norm(z, Inf) ]))
    gradcond = norm(Lx, Inf) / (1 + max([ norm(lam, Inf), norm(mu, Inf) ]))
    compcond = (z.T * mu) / (1 + norm(x, Inf))
    costcond = abs(f - f0) / (1 + abs(f0))
    if verbose:
        logger.info("\n it    objective   step size   feascond     gradcond     compcond     costcond  ")
        logger.info("\n----  ------------ --------- ------------ ------------ ------------ ------------")
        logger.info("\n%3d  %12.8g %10s %12g %12g %12g %12g" %
            (i, f/cost_mult, "", feascond, gradcond, compcond, costcond))
    if feascond < feastol and gradcond < gradtol and \
                    compcond < comptol and costcond < costtol:
        converged = True
        if verbose:
            logger.info("Converged!\n")

    # do Newton iterations
    while (not converged and i < max_it):
        # update iteration counter
        i += 1

        # compute update step
        lmbda = {"eqnonlin": lam[range(neqnln)],
                 "ineqnonlin": mu[range(niqnln)]}
        Lxx = ipm_hess(x, lmbda)
        zinvdiag = spmatrix(div(1.0, z), range(niq), range(niq), (niq, niq))
        mudiag = spmatrix(mu, range(niq), range(niq), (niq, niq))
        dg_zinv = dg * zinvdiag
        M = Lxx + dg_zinv * mudiag * dg.T
        N = Lx + dg_zinv * (mudiag * g + gamma * e)
        Ab = sparse([sparse([M.T, dh.T]),
                     sparse([dh, spmatrix([], [], [], (neq, neq)).T])])
        dxdlam = linsolve(Ab, [-N, -h])
        dx = dxdlam(range(nx))
        dlam = dxdlam(nx + range(neq))
        dz = -g - z - dg.T * dx
        dmu = -mu + zinvdiag * (gamma * e - mudiag * dz)

        # optional step-size control
        sc = False
        if step_control:
            x1 = x + dx

            # evaluate cost, constraints, derivatives at x1
            f1, df1 = ipm_f(x1)          # cost
            f1 = f1 * cost_mult
            df1 = df1 * cost_mult
            gn1, hn1, dgn1, dhn1 = ipm_gh(x1) # non-linear constraints
            g1 = matrix([gn1, Ai * x1 - bi])  # inequality constraints
            h1 = matrix([hn1, Ae * x1 - be])  # equality constraints
            dg1 = sparse([dgn1.T, Ai]).T      # 1st derivative of inequalities
            dh1 = sparse([dhn1.T, Ae]).T      # 1st derivative of equalities

            # check tolerance
            Lx1 = df1 + dh1 * lam + dg1 * mu
            feascond1 = max([norm(h1, Inf), max(g1)]) / (1 + max([ norm(x1, Inf), norm(z, Inf) ]))
            gradcond1 = norm(Lx1, Inf) / (1 + max([ norm(lam, Inf), norm(mu, Inf) ]))

            if feascond1 > feascond and gradcond1 > gradcond:
                sc = True
        if sc:
            alpha = 1.0
            for j in range(max_red):
                dx1 = alpha * dx
                x1 = x + dx1
                f1 = ipm_f(x1)             # cost
                f1 = f1 * cost_mult
                gn1, hn1 = ipm_gh(x1)              # non-linear constraints
                g1 = matrix([gn1, Ai * x1 - bi])   # inequality constraints
                h1 = matrix([hn1, Ae * x1 - be])   # equality constraints
                L1 = f1 + lam.T * h1 + mu.T * (g1 + z) - gamma * sum(log(z))
                if verbose:
                    logger.info("\n   %3d            %10g" % (-j, norm(dx1)))
                rho = (L1 - L) / (Lx.T * dx1 + 0.5 * dx1.T * Lxx * dx1)
                if rho > rho_min and rho < rho_max:
                    break
                else:
                    alpha = alpha / 2.0
            dx = alpha * dx
            dz = alpha * dz
            dlam = alpha * dlam
            dmu = alpha * dmu

        # do the update
        k = nonzero(dz < 0)
        alphap = min( matrix([xi * min(div(z(k), -dz(k))), 1]) )
        k = nonzero(dmu < 0)
        alphad = min( matrix([xi * min(div(mu(k), -dmu(k))), 1]) )
        x = x + alphap * dx
        z = z + alphap * dz
        lam = lam + alphad * dlam
        mu  = mu  + alphad * dmu
        gamma = sigma * (z.T * mu) / niq

        # evaluate cost, constraints, derivatives
        f, df = ipm_f(x);             # cost
        f = f * cost_mult
        df = df * cost_mult
        gn, hn, dgn, dhn = ipm_gh(x)           # non-linear constraints
        g = matrix([gn, Ai * x - bi])          # inequality constraints
        h = matrix([hn, Ae * x - be])          # equality constraints
        dg = sparse([dgn.T, Ai]).T             # 1st derivative of inequalities
        dh = sparse([dhn.T, Ae]).T             # 1st derivative of equalities

        # check tolerance
        Lx = df + dh * lam + dg * mu
        feascond = max([norm(h, Inf), max(g)]) / (1 + max([ norm(x, Inf), norm(z, Inf) ]))
        gradcond = norm(Lx, Inf) / (1 + max([ norm(lam, Inf), norm(mu, Inf) ]))
        compcond = (z.T * mu) / (1 + norm(x, Inf))
        costcond = abs(f - f0) / (1 + abs(f0))
        if verbose:
            logger.info("\n%3d  %12.8g %10.5g %12g %12g %12g %12g" %
                (i, f/cost_mult, norm(dx), feascond, gradcond, compcond, costcond))
        if feascond < feastol and gradcond < gradtol and \
                        compcond < comptol and costcond < costtol:
            converged = True
            if verbose:
                logger.info("\nConverged!\n")
        else:
            if any(isnan(x)) or alphap < alpha_min or alphad < alpha_min or \
                    gamma < EPS or gamma > 1 / EPS:
                if verbose:
                    logger.info("\nNumerically Failed\n")
                break
            f0 = f
            if step_control:
                L = f + lam.T * h + mu.T * (g + z) - gamma * sum(log(z))

    if verbose:
        if not converged:
            logger.info("\nDid not converge in %d iterations.\n" % i)

    info = converged
    output = {"iterations": i, "feascond": feascond, "gradcond": gradcond,
                    "compcond": compcond, "costcond": costcond}

    # zero out multipliers on non-binding constraints
    mu[g < -feastol and mu < mu_threshold] = 0

    # un-scale cost and prices
    f   = f / cost_mult
    lam = lam / cost_mult
    mu  = mu / cost_mult

    # re-package multipliers into struct
    lam_lin = lam[neqnln:neq]              # lambda for linear constraints
    mu_lin  = mu[niqnln:niq]               # mu for linear constraints
    kl = nonzero(lam_lin < 0)              # lower bound binding
    ku = nonzero(lam_lin > 0)                # upper bound binding

    mu_l = matrix(0.0, (nx + nA, 1))
    mu_l[ieq[kl]] = -lam_lin[kl]
    mu_l[igt] = mu_lin[nlt + range(ngt)]
    mu_l[ibx] = mu_lin[nlt + ngt + nbx + range(nbx)]

    mu_u = matrix(0.0, (nx+nA, 1))
    mu_u[ieq[ku]] = lam_lin[ku]
    mu_u[ilt] = mu_lin[1:nlt]
    mu_u[ibx] = mu_lin[nlt + ngt + range(nbx)]

    lmbda = {"eqnonlin": lam[1:neqnln], 'ineqnonlin': mu[1:niqnln],
        'mu_l': mu_l[nx + 1:], 'mu_u': mu_u[nx + 1:],
        'lower': mu_l[1:nx], 'upper': mu_u[1:nx]}

    return x, f, info, output, lmbda

#------------------------------------------------------------------------------
#  "pdipm_qp" function:
#------------------------------------------------------------------------------

def pdipm_qp(H, c, A, b, VLB=None, VUB=None, x0=None, N=0,
             verbose=True, cost_mult=1):
    """ Wrapper function for a primal-dual interior point QP solver.
    """
    nx = len(c)

    if VLB is None:
        VLB = matrix(-Inf, (nx, 1))

    if VUB is None:
        VUB = matrix(Inf, (nx, 1))

    if x0 is None:
        x0 = matrix(0.0, (nx, 1))
        k = nonzero(VUB < 1e10 and VLB > -1e10)
        x0[k] ((VUB[k] + VLB[k]) / 2)
        k = nonzero(VUB < 1e10 and VLB <= -1e10)
        x0[k] = VUB[k] - 1
        k = nonzero(VUB >= 1e10 and VLB > -1e10)
        x0[k] = VLB[k] + 1

    def qp_f(x, H=None, c=None):
        f = 0.5 * x.T * H * x + c.T * x
        df = H * x + c
        return df, H

    def qp_gh(x):
        g = matrix()
        h = matrix()
        dg = matrix()
        dh = matrix()
        return g, h, dg, dh

    def qp_hessian(x, lmbda, H, cost_mult):
        Lxx = H * cost_mult
        return Lxx


    l = matrix(-Inf, b.size)
    l[:N] = b[:N]

    # run it
    xout, f, info, output, lmbda = \
      pdipm(qp_f, qp_gh, qp_hessian, x0, VLB, VUB, A, l, b)

    success = (info > 0)
    if success:
        howout = 'success'
    else:
        howout = 'failure'

    lmbdaout = matrix([-lmbda["mu_l"] + lmbda["mu_u"], lmbda["lower"],
                       lmbda["upper"]])

    return xout, lmbdaout, howout, success

# EOF -------------------------------------------------------------------------

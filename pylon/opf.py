#------------------------------------------------------------------------------
# Copyright (C) 2010 Richard Lincoln
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#------------------------------------------------------------------------------

""" Defines a generalised OPF solver and an OPF model [1].

    [1] Ray Zimmerman, "opf.m", MATPOWER, PSERC Cornell, version 4.0b1,
        http://www.pserc.cornell.edu/matpower/, December 2009
"""

#------------------------------------------------------------------------------
#  Imports:
#------------------------------------------------------------------------------

import logging

from numpy import \
    array, pi, diff, polyder, polyval, exp, conj, Inf, finfo, ones, r_, \
    float64, zeros, diag

from scipy.sparse import csr_matrix, hstack, vstack

from util import Named
from case import REFERENCE
from generator import POLYNOMIAL, PW_LINEAR
from pdipm import pdipm, pdipm_qp

#------------------------------------------------------------------------------
#  Constants:
#------------------------------------------------------------------------------

EPS = finfo(float).eps
SFLOW = "Sflow"
PFLOW = "Pflow"
IFLOW = "Iflow"

#------------------------------------------------------------------------------
#  Logging:
#------------------------------------------------------------------------------

logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
#  "OPF" class:
#------------------------------------------------------------------------------

class OPF(object):
    """ Defines a generalised OPF solver [1].

        [1] Ray Zimmerman, "opf.m", MATPOWER, PSERC Cornell, version 4.0b1,
            http://www.pserc.cornell.edu/matpower/, December 2009
    """

    def __init__(self, case, dc=True, ignore_ang_lim=True, opts=None):
        """ Initialises a new OPF instance.
        """
        # Case under optimisation.
        self.case = case

        # Use DC power flow formulation.
        self.dc = dc

        # Ignore angle difference limits for branches even if specified.
        self.ignore_ang_lim = ignore_ang_lim

        # Solver options (See pdipm.py for futher details).
        self.opts = {} if opts is None else opts

    #--------------------------------------------------------------------------
    #  Public interface:
    #--------------------------------------------------------------------------

    def solve(self, solver_klass=None):
        """ Solves an optimal power flow and returns a results dictionary.
        """
        # Build an OPF model with variables and constraints.
        om = self._construct_opf_model(self.case)

        # Call the specific solver.
        if solver_klass is not None:
            result = solver_klass(om).solve()
        elif self.dc:
            result = DCOPFSolver(om).solve()
        else:
            result = PDIPMSolver(om, self.opts).solve()

        return result

    #--------------------------------------------------------------------------
    #  Private interface:
    #--------------------------------------------------------------------------

    def _construct_opf_model(self, case):
        """ Returns an OPF model.
        """
        # Zero the case result attributes.
        self.case.reset()

        base_mva = case.base_mva

        # Check for one reference bus.
        oneref, refs = self._ref_check(case)
        if not oneref: return {"status": "error"}

        # Remove isolated components.
        bs, ln, gn = self._remove_isolated(case)

        # Update bus indexes.
        self.case.index_buses(bs)

        # Convert single-block piecewise-linear costs into linear polynomial.
        gn = self._pwl1_to_poly(gn)

        # Set-up initial problem variables.
        Va = self._voltage_angle_var(refs, bs)
        Pg = self._p_gen_var(gn, base_mva)

        if self.dc: # DC model.
            # Get the susceptance matrices and phase shift injection vectors.
            B, Bf, Pbusinj, Pfinj = self.case.makeBdc(bs, ln)

            # Power mismatch constraints (B*Va + Pg = Pd).
            Pmis = self._power_mismatch_dc(bs, gn, B, Pbusinj, base_mva)

            # Branch flow limit constraints.
            Pf, Pt = self._branch_flow_dc(ln, Bf, Pfinj, base_mva)
        else:
            # Set-up additional AC-OPF problem variables.
            Vm = self._voltage_magnitude_var(bs, gn)
            Qg = self._q_gen_var(gn, base_mva)

            Pmis, Qmis, Sf, St = self._nln_constraints(len(bs), len(ln))

            # TODO: Dispatchable load, constant power factor constraints.
#            vl = self._dispatchable_load_constraints(gn)

            # TODO: Generator PQ capability curve constraints.
#            PQh, PQl = self._pq_capability_curve_constraints(gn)

        # Branch voltage angle difference limits.
        ang = self._voltage_angle_diff_limit(bs, ln)

        if self.dc:
            vars = [Va, Pg]
            constraints = [Pmis, Pf, Pt, ang]
        else:
            vars = [Va, Vm, Pg, Qg]
            constraints = [Pmis, Qmis, Sf, St, #PQh, PQL, vl,
                           ang]

        # Piece-wise linear generator cost constraints.
        y, ycon = self._pwl_gen_costs(gn, base_mva)
        if ycon is not None:
            vars.append(y)
            constraints.append(ycon)

        # Add variables and constraints to the OPF model object.
        opf = OPFModel(case)
        opf.add_vars(vars)
        opf.add_constraints(constraints)

        if self.dc: # user data
            opf._Bf = Bf
            opf._Pfinj = Pfinj

        return opf


    def _ref_check(self, case):
        """ Checks that there is only one reference bus.
        """
        refs = [bus.i for bus in case.buses if bus.type == REFERENCE]

        if len(refs) == 1:
            return True, refs
        else:
            logger.error("OPF requires a single reference bus.")
            return False, refs


    def _remove_isolated(self, case):
        """ Returns non-isolated case components.
        """
        case.deactivate_isolated()
        buses = case.connected_buses
        branches = case.online_branches
        gens = case.online_generators

        return buses, branches, gens


    def _pwl1_to_poly(self, generators):
        """ Converts single-block piecewise-linear costs into linear
            polynomial.
        """
        for g in generators:
            if (g.pcost_model == PW_LINEAR) and (len(g.p_cost) == 2):
                g.pwl_to_poly()

        return generators

    #--------------------------------------------------------------------------
    #  Optimisation variables:
    #--------------------------------------------------------------------------

    def _voltage_angle_var(self, refs, buses):
        """ Returns the voltage angle variable set.
        """
        Va = array([b.v_angle_guess * (pi / 180.0) for b in buses])

        Vau = ones(len(buses)) * Inf
        Val = -Vau
        Vau[refs] = Va[refs]
        Val[refs] = Va[refs]

        return Variable("Va", len(buses), Va, Val, Vau)


    def _voltage_magnitude_var(self, buses, generators):
        """ Returns the voltage magnitude variable set.
        """
        Vm = array([b.v_magnitude_guess for b in buses])

        # For buses with generators initialise Vm from gen data.
        for g in generators:
            Vm[buses.index(g.bus)] = g.v_magnitude

        Vmin = array([b.v_min for b in buses])
        Vmax = array([b.v_max for b in buses])

        return Variable("Vm", len(buses), Vm, Vmin, Vmax)


    def _p_gen_var(self, generators, base_mva):
        """ Returns the generator active power set-point variable.
        """
        Pg = array([g.p / base_mva for g in generators])

        Pmin = array([g.p_min / base_mva for g in generators])
        Pmax = array([g.p_max / base_mva for g in generators])

        return Variable("Pg", len(generators), Pg, Pmin, Pmax)


    def _q_gen_var(self, generators, base_mva):
        """ Returns the generator reactive power variable set.
        """
        Qg = array([g.q / base_mva for g in generators])

        Qmin = array([g.q_min / base_mva for g in generators])
        Qmax = array([g.q_max / base_mva for g in generators])

        return Variable("Qg", len(generators), Qg, Qmin, Qmax)

    #--------------------------------------------------------------------------
    #  Constraints:
    #--------------------------------------------------------------------------

    def _nln_constraints(self, nb, nl):
        """ Returns non-linear constraints for OPF.
        """
        Pmis = NonLinearConstraint("Pmis", nb)
        Qmis = NonLinearConstraint("Qmis", nb)
        Sf = NonLinearConstraint("Sf", nl)
        St = NonLinearConstraint("St", nl)

        return Pmis, Qmis, Sf, St


    def _power_mismatch_dc(self, buses, generators, B, Pbusinj, base_mva):
        """ Returns the power mismatch constraint (B*Va + Pg = Pd).
        """
        nb, ng = len(buses), len(generators)
        # Negative bus-generator incidence matrix.
        gen_bus = array([buses.index(g.bus) for g in generators])
        neg_Cg = csr_matrix((-1.0, (gen_bus, range(ng))), (nb, ng))

        Amis = hstack([B, neg_Cg], format="csr")

        Pd = array([bus.p_demand for bus in buses])
        Gs = array([bus.g_shunt for bus in buses])

        bmis = -(Pd - Gs) / base_mva - Pbusinj

        return LinearConstraint("Pmis", Amis, bmis, bmis, ["Va", "Pg"])


    def _branch_flow_dc(self, branches, Bf, Pfinj, base_mva):
        """ Returns the branch flow limit constraint.  The real power flows
            at the from end the lines are related to the bus voltage angles
            by Pf = Bf * Va + Pfinj.
        """
        # Indexes of constrained lines.
        il = array([i for i,l in enumerate(branches) if 0.0 < l.rate_a < 1e10])
        lpf = ones(len(il)) * -Inf
        rate_a = array([l.rate_a / base_mva for l in branches])
        upf = rate_a[il] - Pfinj[il]
        upt = rate_a[il] + Pfinj[il]

        Pf = LinearConstraint("Pf",  Bf[il, :], lpf, upf, ["Va"])
        Pt = LinearConstraint("Pt", -Bf[il, :], lpf, upt, ["Va"])

        return Pf, Pt


    def _voltage_angle_diff_limit(self, buses, branches):
        """ Returns the constraint on the branch voltage angle differences.
        """
        nb = len(buses)

        if not self.ignore_ang_lim:
            iang = [i for i, b in enumerate(branches)
                    if (b.ang_min and (b.ang_min > -360.0))
                    or (b.ang_max and (b.ang_max < 360.0))]
            iangl = array([i for i, b in enumerate(branches)
                     if b.ang_min is not None])[iang]
            iangh = array([i for i, b in enumerate(branches)
                           if b.ang_max is not None])[iang]
            nang = len(iang)

            if nang > 0:
                ii = range(nang) + range(nang)
                jjf = array([b.from_bus.i for b in branches])[iang]
                jjt = array([b.to_bus.i for b in branches])[iang]
                jj = r_[jjf, jjt]
                Aang = csr_matrix(r_[ones(nang), -ones(nang)],
                                        (ii, jj), (nang, nb))
                uang = ones(nang) * Inf
                lang = -uang
                lang[iangl] = array([b.ang_min * (pi / 180.0)
                                    for b in branches])[iangl]
                uang[iangh] = array([b.ang_max * (pi / 180.0)
                                    for b in branches])[iangh]
            else:
                Aang = csr_matrix((0, nb), dtype=float64)
                lang = array([], dtype=float64)
                uang = array([], dtype=float64)
        else:
            Aang = csr_matrix((0, nb), dtype=float64)
            lang = array([], dtype=float64)
            uang = array([], dtype=float64)
            iang = array([], dtype=float64)

        return LinearConstraint("ang", Aang, lang, uang, ["Va"])


    def _pwl_gen_costs(self, generators, base_mva):
        """ Returns the basin constraints for piece-wise linear gen cost
            variables [2].  CCV cost formulation expressed as Ay * x <= by.

            [2] C. E. Murillo-Sanchez, "makeAy.m", MATPOWER, PSERC Cornell,
                version 4.0b1, http://www.pserc.cornell.edu/matpower/, Dec 09
        """
        ng = len(generators)
        gpwl = [g for g in generators if g.pcost_model == PW_LINEAR]
        nq = len([g for g in gpwl if g.qcost_model is not None])

        if self.dc:
            pgbas = 0 # starting index within x for active sources
            qgbas = None
            ybas = ng # starting index within x for y variables
        else:
            pgbas = 0
            qgbas = ng + 1 # index of 1st Qg column in Ay
            ybas = ng + nq

        # Number of extra y variables.
        ny = len(gpwl) + nq
        if ny > 0:
            # Total number of cost points.
            nc = len([co for gn in gpwl for co in gn.p_cost])
            Ay = csr_matrix((nc - ny, ybas + ny -1))
            by = zeros((0, 1))

            k = 0
            for i, g in enumerate(gpwl):
                # Number of cost points: segments = ns-1
                ns = len(g.p_cost)

                p = array([x / base_mva for x, c in g.p_cost])
                c = array([c for x, c in g.p_cost])
                # Slopes for Pg (or Qg).
                m = array(diff(c.T) / diff(p.T))

                if 0.0 in diff(p):
                    logger.error("Bad Pcost data: %s" % p)

                b = m.T * p[:ns-1] - c[:ns-1] # rhs
                by = r_[by, b]

                print "B:\n", by

#                Ay[k:k + ns - 2, pgbas + i]
                Ay[k:k + ns - 2, ybas + i] = m.T#matrix(-1., (ns, 1))
                k += (ns - 1)

                # FIXME: Repeat for Q cost.

            y = Variable("y", ny)

            if self.dc:
                ycon = LinearConstraint("ycon", Ay, None, by, ["Pg", "y"])
            else:
                ycon = LinearConstraint("ycon", Ay, None, by, ["Pg", "Qg","y"])
        else:
#            Ay = spmatrix([], [], [], (ybas + ny, 0))
#            by = matrix()
            y = ycon = None

        return y, ycon

#------------------------------------------------------------------------------
#  "Solver" class:
#------------------------------------------------------------------------------

class Solver(object):
    """ Defines a base class for many solvers.
    """

    def __init__(self, om):
        # Optimal power flow model.
        self.om = om


    def solve(self):
        """ Solves optimal power flow and returns a results dict.
        """
        raise NotImplementedError


    def _unpack_model(self, om):
        """ Returns data from the OPF model.
        """
        buses = om.case.connected_buses
        branches = om.case.online_branches
        gens = om.case.online_generators

        cp = om.get_cost_params()

#        Bf = om._Bf
#        Pfinj = om._Pfinj

        return buses, branches, gens, cp


    def _dimension_data(self, buses, branches, generators):
        """ Returns the problem dimensions.
        """
        ipol = self.ipol = [i for i, g in enumerate(generators)
                            if g.pcost_model == POLYNOMIAL]
        ipwl = self.ipwl = [i for i, g in enumerate(generators)
                            if g.pcost_model == PW_LINEAR]
        nb = len(buses)
        nl = len(branches)
        # Number of general cost vars, w.
        nw = self.om.cost_N
        # Number of piece-wise linear costs.
        if "y" in [v.name for v in self.om.vars]:
            ny = self.om.get_var_N("y")
        else:
            ny = 0
        # Total number of control variables of all types.
        nxyz = self.om.var_N

        return ipol, ipwl, nb, nl, nw, ny, nxyz


    def _split_constraints(self, om):
        """ Returns the linear problem constraints.
        """
        A, l, u = om.linear_constraints() # l <= A*x <= u

        # Indexes for equality, greater than (unbounded above), less than
        # (unbounded below) and doubly-bounded constraints.
        ieq = [i for i, v in enumerate(abs(u - l)) if v < EPS]
        igt = [i for i in range(len(l)) if u[i] >=  1e10 and l[i] > -1e10]
        ilt = [i for i in range(len(l)) if l[i] <= -1e10 and u[i] <  1e10]
        ibx = [i for i in range(len(l))
               if (abs(u[i] - l[i]) > EPS) and (u[i] < 1e10) and (l[i] >-1e10)]

        Aeq = A[ieq, :]
        beq = u[ieq, :]
        Aieq = hstack([A[ilt, :], -A[igt, :], A[ibx, :], -A[ibx, :]])
        bieq = r_[u[ilt], -l[igt], u[ibx], -l[ibx]]

        return Aeq, beq, Aieq, bieq


    def _var_bounds(self):
        """ Returns bounds on the optimisation variables.
        """
        x0 = zeros((0, 1))
        LB = zeros((0, 1))
        UB = zeros((0, 1))

        for var in self.om.vars:
            x0 = r_[x0, var.v0]
            LB = r_[LB, var.vl]
            UB = r_[UB, var.vu]

        return x0, LB, UB


    def _initial_interior_point(self, buses, LB, UB):
        """ Selects an interior initial point for interior point solver.
        """
        Va = self.om.get_var("Va")
        va_refs = [b.v_angle_guess * pi / 180.0 for b in buses
                   if b.type == REFERENCE]
        x0 = (LB + UB) / 2.0
        x0[Va.i1:Va.iN + 1] = va_refs[0] # Angles set to first reference angle.
        # TODO: PWL initial points.
        return x0

#------------------------------------------------------------------------------
#  "DCOPFSolver" class:
#------------------------------------------------------------------------------

class DCOPFSolver(Solver):
    """ Defines a solver for DC optimal power flow [3].

        [3] Ray Zimmerman, "dcopf_solver.m", MATPOWER, PSERC Cornell, v4.0b1,
            http://www.pserc.cornell.edu/matpower/, December 2009
    """

    def __init__(self, om, opts=None):
        """ Initialises a new DCOPFSolver instance.
        """
        super(DCOPFSolver, self).__init__(om)

        # User-defined costs.
        self.N = csr_matrix((0, self.om.var_N))
        self.H = csr_matrix((0, 0))
        self.Cw = zeros((0, 0))
        self.fparm = zeros((0, 0))

        # Solver options (See pdipm.py for futher details).
        self.opts = {} if opts is None else opts


    def solve(self):
        """ Solves DC optimal power flow and returns a results dict.
        """
        base_mva = self.om.case.base_mva
        # Unpack the OPF model.
        buses, branches, generators, cp = self._unpack_model(self.om)
        # Compute problem dimensions.
        ipol, ipwl, nb, nl, nw, ny, nxyz = self._dimension_data(buses,
                                                                branches,
                                                                generators)
        # Split the constraints in equality and inequality.
        Aeq, beq, Aieq, bieq = self._split_constraints(self.om)
        # Piece-wise linear components of the objective function.
        Npwl, Hpwl, Cpwl, fparm_pwl, any_pwl = self._pwl_costs(ny, nxyz)
        # Quadratic components of the objective function.
        Npol, Hpol, Cpol, fparm_pol, polycf, npol = \
            self._quadratic_costs(generators, ipol, nxyz, base_mva)
        # Combine pwl, poly and user costs.
        NN, HHw, CCw, ffparm = \
            self._combine_costs(Npwl, Hpwl, Cpwl, fparm_pwl, any_pwl,
                                Npol, Hpol, Cpol, fparm_pol, npol,
                                self.N, self.H, self.Cw, self.fparm, nw)
        # Transform quadratic coefficients for w into coefficients for X.
        HH, CC, C0 = self._transform_coefficients(NN, HHw, CCw, ffparm, polycf,
                                                  any_pwl, npol, nw)
        # Bounds on the optimisation variables.
        _, LB, UB = self._var_bounds()

        # Select an interior initial point for interior point solver.
        x0 = self._initial_interior_point(buses, LB, UB)

        # Call the quadratic/linear solver.
        s = self._run_opf(HH, CC, Aieq, bieq, Aeq, beq, LB, UB, x0, self.opts)

        return s


    def _pwl_costs(self, ny, nxyz):
        """ Returns the piece-wise linear components of the objective function.
        """
        any_pwl = int(ny > 0)
        if any_pwl:
            Npwl = csr_matrix((ones(ny), ()))
            Hpwl = 0
            Cpwl = 1
            fparm_pwl = array([1, 0, 0, 1])
        else:
            Npwl = csr_matrix((0, nxyz))
            Hpwl = csr_matrix((0, 0))
            Cpwl = array([])
            fparm_pwl = zeros(4)

        return Npwl, Hpwl, Cpwl, fparm_pwl, any_pwl


    def _quadratic_costs(self, generators, ipol, nxyz, base_mva):
        """ Returns the quadratic cost components of the objective function.
        """
        npol = len(ipol)
        rnpol = range(npol)
        gpol = [g for g in generators if g.pcost_model == POLYNOMIAL]

        if [g for g in gpol if len(g.p_cost) > 3]:
            logger.error("Order of polynomial cost greater than quadratic.")

        iqdr = [i for i, g in enumerate(generators)
                if g.pcost_model == POLYNOMIAL and len(g.p_cost) == 3]
        ilin = [i for i, g in enumerate(generators)
                if g.pcost_model == POLYNOMIAL and len(g.p_cost) == 2]

        polycf = zeros((npol, 3))
        if len(iqdr) > 0:
            polycf[iqdr, :] = array([list(g.p_cost)
                                     for g in generators]).T[iqdr, :]

        polycf[ilin, 1:] = array([list(g.p_cost[:2])
                                  for g in generators]).T[ilin, :]

        # Convert to per-unit.
        polycf *= diag([base_mva**2, base_mva, 1])
        Pg = self.om.get_var("Pg")
        Npol = csr_matrix((ones(npol), (rnpol, Pg.i1 + ipol)), (npol, nxyz))
        Hpol = csr_matrix((2 * polycf[:, 0], (rnpol, rnpol)), (npol, npol))
        Cpol = polycf[:, 1]
        fparm_pol = ones(npol) * array([1, 0, 0, 1]).T

        return Npol, Hpol, Cpol, fparm_pol, polycf, npol


    def _combine_costs(self, Npwl, Hpwl, Cpwl, fparm_pwl, any_pwl,
                       Npol, Hpol, Cpol, fparm_pol, npol,
                       N=None, H=None, Cw=None, fparm=None, nw=0):
        NN = vstack([Npwl, Npol])#, N])

        HHw = vstack([
            hstack([Hpwl, csr_matrix((npol, any_pwl))]),
            hstack([csr_matrix((any_pwl, npol)), Hpol])
        ])

#        HHw = sparse([
#            sparse([Hpwl, spmatrix([], [], [], (any_pwl, npol + nw))]).T,
#            sparse([spmatrix([], [], [], (npol, any_pwl)),
#                    Hpol,
#                    spmatrix([], [], [], (npol, nw))]).T,
#            sparse([spmatrix([], [], [], (nw, any_pwl + npol)), H]).T
#        ]).T

        CCw = r_[Cpwl, Cpol]#, Cw]
        ffparm = r_[fparm_pwl, fparm_pol]#, fparm]

        return NN, HHw, CCw, ffparm


    def _transform_coefficients(self, NN, HHw, CCw, ffparm, polycf,
                               any_pwl, npol, nw):
        """ Transforms quadratic coefficients for w into coefficients for X.
        """
        nnw = any_pwl + npol + nw
        M = csr_matrix((ffparm[:, 3], (range(nnw), range(nnw))))
        MR = M * ffparm[:, 2]
        HMR = HHw * MR
        MN = M * NN
        HH = MN.H * HHw * MN
        CC = MN.H * (CCw - HMR)
        # Constant term of cost.
        C0 = 1./2. * MR.H * HMR + sum(polycf[:, 2])

        return HH, CC, C0


    def _run_opf(self, P, q, G, h, A, b, LB, UB, x0, opts):
        """ Solves the either quadratic or linear program.
        """
        AA = vstack([A, G]) # Combined equality and inequality constraints.
        bb = r_[b, h]
        N = A.shape[0]

        if len(P) > 0:
            solution = pdipm_qp(P, q, AA, bb, LB, UB, x0, N, opts)
        else:
            solution = pdipm_qp(None, q, AA, bb, LB, UB, x0, N, opts)

        return solution

#------------------------------------------------------------------------------
#  "PDIPMSolver" class:
#------------------------------------------------------------------------------

class PDIPMSolver(Solver):
    """ Solves AC optimal power flow using a primal-dual interior point method.
    """

    def __init__(self, om, flow_lim=SFLOW, opts=None):
        """ Initialises a new PDIPMSolver instance.
        """
        super(PDIPMSolver, self).__init__(om)

        # Quantity to limit for branch flow constraints ("S", "P" or "I").
        self.flow_lim = flow_lim

        # Options for the PDIPM.
        self.opts = {} if opts is None else opts


    def _ref_bus_angle_constraint(self, buses, Va, xmin, xmax):
        """ Adds a constraint on the reference bus angles.
        """
        refs = [bus.i for bus in buses if bus.type == REFERENCE]
        Varefs = array([b.v_angle_guess for b in buses if b.type == REFERENCE])

        xmin[Va.i1 - 1 + refs] = Varefs
        xmax[Va.iN - 1 + refs] = Varefs

        return xmin, xmax


    def solve(self):
        """ Solves AC optimal power flow.
        """
        case = self.om.case
        base_mva = case.base_mva

        # TODO: Find an explanation for this value.
        self.opt["cost_mult"] = 1e-4

        # Unpack the OPF model.
        bs, ln, gn, cp = self._unpack_model(self.om)

        # Compute problem dimensions.
        ng = len(gn)
        gpol = [g for g in gn if g.pcost_model == POLYNOMIAL]
        ipol, ipwl, nb, nl, nw, ny, nxyz = self._dimension_data(bs, ln, gn)

        # Linear constraints (l <= A*x <= u).
        A, l, u = self.om.linear_constraints()

        _, xmin, xmax = self._var_bounds()

        # Select an interior initial point for interior point solver.
        x0 = self._initial_interior_point(bs, xmin, xmax)

        # Build admittance matrices.
        Ybus, Yf, Yt = case.Y

        # Optimisation variables.
        Va = self.om.get_var("Va")
        Vm = self.om.get_var("Vm")
        Pg = self.om.get_var("Pg")
        Qg = self.om.get_var("Qg")

        # Adds a constraint on the reference bus angles.
#        xmin, xmax = self._ref_bus_angle_constraint(bs, Va, xmin, xmax)

        def ipm_f(x):
            """ Evaluates the objective function, gradient and Hessian for OPF.
            """
            p_gen = x[Pg.i1:Pg.iN + 1] # Active generation in p.u.
            q_gen = x[Qg.i1:Qg.iN + 1] # Reactive generation in p.u.

            #------------------------------------------------------------------
            #  Evaluate the objective function.
            #------------------------------------------------------------------

            # Polynomial cost of P and Q.
            xx = r_[p_gen, q_gen] * base_mva
            if len(ipol) > 0:
                f = sum([g.total_cost(xx[i]) for i,g in enumerate(gn)])
            else:
                f = 0

            # Piecewise linear cost of P and Q.
            if ny:
                y = self.om.get_var("y")
                ccost = csr_matrix((ones(ny), (range(y.i1, i.iN + 1),
                                 ones(1, ny))), (1, nxyz))
                f += ccost * x
            else:
                ccost = zeros(nxyz)

            # TODO: Generalised cost term.

            #------------------------------------------------------------------
            #  Evaluate cost gradient.
            #------------------------------------------------------------------

            iPg = array(range(Pg.i1, Pg.iN + 1))
            iQg = array(range(Qg.i1, Qg.iN + 1))

            # Polynomial cost of P and Q.
            df_dPgQg = zeros(2 * ng)        # w.r.t p.u. Pg and Qg
#            df_dPgQg[ipol] = matrix([g.poly_cost(xx[i], 1) for g in gpol])
            for i, g in enumerate(gn):
                der = polyder(list(g.p_cost))
                df_dPgQg[i] = polyval(der, xx[i]) * base_mva

            df = zeros(nxyz, 1)
            df[iPg] = df_dPgQg[:ng]
            df[iQg] = df_dPgQg[ng:ng + ng]

            # Piecewise linear cost of P and Q.
            df += ccost.T # linear cost row is additive wrt any nonlinear cost

            # TODO: Generalised cost term.

            #------------------------------------------------------------------
            #  Evaluate cost Hessian.
            #------------------------------------------------------------------

            d2f = None

            return f, df, d2f


        def ipm_gh(x):
            """ Evaluates nonlinear constraints and their Jacobian for OPF.
            """
            Pgen = x[Pg.i1:Pg.iN + 1] # Active generation in p.u.
            Qgen = x[Qg.i1:Qg.iN + 1] # Reactive generation in p.u.

            for i, g in enumerate(gn):
                g.p = Pgen[i] * base_mva # active generation in MW
                g.q = Qgen[i] * base_mva # reactive generation in MVAr

            # Rebuild the net complex bus power injection vector in p.u.
            Sbus = case.getSbus(bs)

            Vang = x[Va.i1:Va.iN + 1]
            Vmag = x[Vm.i1:Vm.iN + 1]
            V = Vmag * exp(1j * Vang)

            # Evaluate the power flow equations.
            mis = V * conj(Ybus * V) - Sbus

            #------------------------------------------------------------------
            #  Evaluate constraint function values.
            #------------------------------------------------------------------

            # Equality constraints (power flow).
            h = r_[mis.real,  # active power mismatch for all buses
                   mis.imag]  # reactive power mismatch for all buses

            # Inequality constraints (branch flow limits).
            flow_max = array([(l.rate_a / base_mva)**2 for l in ln])
            # FIXME: There must be a more elegant method for this.
            for i, v in enumerate(flow_max):
                if v == 0.0:
                    flow_max[i] = Inf

            if self.flow_lim == IFLOW:
                If = Yf * V
                It = Yt * V
                # Branch current limits.
                g = r_[(If * conj(If)) - flow_max,
                       (If * conj(It)) - flow_max]
            else:
                i_fbus = [e.from_bus.i for e in ln]
                i_tbus = [e.to_bus.i for e in ln]
                # Complex power injected at "from" bus (p.u.).
                Sf = V[i_fbus] * conj(Yf * V)
                # Complex power injected at "to" bus (p.u.).
                St = V[i_tbus] * conj(Yt * V)
                if self.flow_lim == PFLOW: # active power limit, P (Pan Wei)
                    # Branch real power limits.
                    g = r_[Sf.real()**2 - flow_max,
                           St.real()**2 - flow_max]
                elif self.flow_lim == SFLOW: # apparent power limit, |S|
                    # Branch apparent power limits.
                    g = r_[(Sf * conj(Sf)) - flow_max,
                           (St * conj(St)) - flow_max].real
                else:
                    raise ValueError

            #------------------------------------------------------------------
            #  Evaluate partials of constraints.
            #------------------------------------------------------------------

            iVa = range(Va.i1, Va.iN + 1)
            iVm = range(Vm.i1, Vm.iN + 1)
            iPg = range(Pg.i1, Pg.iN + 1)
            iQg = range(Qg.i1, Qg.iN + 1)
            iVaVmPgQg = r_[iVa, iVm, iPg, iQg].T

            # Compute partials of injected bus powers.
            dSbus_dVm, dSbus_dVa = case.dSbus_dV(Ybus, V)

            i_gbus = [gen.bus.i for gen in gn]
            neg_Cg = csr_matrix((-ones(ng), (i_gbus, range(ng))), (nb, ng))

            # Transposed Jacobian of the power balance equality constraints.
            dh = csr_matrix((nxyz, 2 * nb))

            blank = csr_matrix((nb, ng))
            dh[iVaVmPgQg, :] = vstack([
                hstack([dSbus_dVa.real, dSbus_dVm.real, neg_Cg, blank]),
                hstack([dSbus_dVa.imag, dSbus_dVm.imag, blank, neg_Cg])
            ]).T

            # Compute partials of flows w.r.t V.
            if self.flow_lim == IFLOW:
                dFf_dVa, dFf_dVm, dFt_dVa, dFt_dVm, Ff, Ft = \
                    case.dIbr_dV(Yf, Yt, V)
            else:
                dFf_dVa, dFf_dVm, dFt_dVa, dFt_dVm, Ff, Ft = \
                    case.dSbr_dV(Yf, Yt, V, bs, ln)
            if self.flow_lim == PFLOW:
                dFf_dVa = dFf_dVa.real
                dFf_dVm = dFf_dVm.real
                dFt_dVa = dFt_dVa.real
                dFt_dVm = dFt_dVm.real
                Ff = Ff.real
                Ft = Ft.real

            # Squared magnitude of flow (complex power, current or real power).
            df_dVa, df_dVm, dt_dVa, dt_dVm = \
                case.dAbr_dV(dFf_dVa, dFf_dVm, dFt_dVa, dFt_dVm, Ff, Ft)

            # Construct Jacobian of inequality constraints (branch limits) and
            # transpose it.
            dg = csr_matrix((nxyz, 2 * nl))
            dg[r_[iVa, iVm].T, :] = vstack([
                hstack([df_dVa, df_dVm]),
                hstack([dt_dVa, dt_dVm])
            ]).T

            return g, h, dg, dh


        def ipm_hess(x, lmbda):
            """ Evaluates Hessian of Lagrangian for AC OPF.
            """
            Pgen = x[Pg.i1:Pg.iN + 1] # Active generation in p.u.
            Qgen = x[Qg.i1:Qg.iN + 1] # Reactive generation in p.u.

            for i, g in enumerate(gn):
                g.p = Pgen[i] * base_mva # active generation in MW
                g.q = Qgen[i] * base_mva # reactive generation in MVAr

            Vang = x[Va.i1:Va.iN + 1]
            Vmag = x[Vm.i1:Vm.iN + 1]
            V = Vmag * exp(1j * Vang)
            nxtra = nxyz - 2 * nb

            #------------------------------------------------------------------
            #  Evaluate d2f.
            #------------------------------------------------------------------

            d2f_dPg2 = csr_matrix((ng, 1)) # w.r.t p.u. Pg
            d2f_dQg2 = csr_matrix((ng, 1)) # w.r.t p.u. Qg
#            d2f_dPg2[ipol] = matrix([g.poly_cost(Pg[i] * base_mva, 2)
#                                     for i, g in enumerate(gpol)])
            for i, g in enumerate(gn):
                der = polyder(list(g.p_cost), 2)
                d2f_dPg2[i] = polyval(der, Pgen[i]) * base_mva
#            d2f_dQg2[ipol] = matrix([g.poly_cost(Qg[i] * base_mva, 2)
#                                     for i, g in enumerate(gpol)
#                                     if g.qcost_model is not None])
            for i, g in enumerate(gn):
                if g.qcost_model == POLYNOMIAL:
                    der = polyder(list(g.q_cost), 2)
                    d2f_dQg2[i] = polyval(der, Qgen[i]) * base_mva

            i = r_[array(range(Pg.i1, Pg.iN + 1)),
                   array(range(Qg.i1, Qg.iN + 1))]
            d2f = csr_matrix(r_[d2f_dPg2, d2f_dQg2], i, i, (nxyz, nxyz))

            # TODO: Generalised cost model.

            d2f *= self.opts["cost_mult"]

            #------------------------------------------------------------------
            #  Evaluate Hessian of power balance constraints.
            #------------------------------------------------------------------

            nlam = len(lmbda["eqnonlin"]) / 2
            lamP = lmbda["eqnonlin"][:nlam]
            lamQ = lmbda["eqnonlin"][nlam:nlam + nlam]
            Hpaa, Hpav, Hpva, Hpvv = case.d2Sbus_dV2(Ybus, V, lamP)
            Hqaa, Hqav, Hqva, Hqvv = case.d2Sbus_dV2(Ybus, V, lamQ)

            d2H = vstack([
                hstack([
                    vstack([hstack([Hpaa, Hpav]),
                            hstack([Hpva, Hpvv])]).real +
                    vstack([hstack([Hqaa, Hqav]),
                            hstack([Hpva, Hpvv])]).imag,
                    csr_matrix((2 * nb, nxtra))]),
                hstack([
                    csr_matrix((nxtra, 2 * nb)),
                    csr_matrix((nxtra, nxtra))
                ])
            ])

            #------------------------------------------------------------------
            #  Evaluate Hessian of flow constraints.
            #------------------------------------------------------------------

            nmu = len(lmbda["ineqnonlin"]) / 2
            muF = lmbda["ineqnonlin"][:nmu]
            muT = lmbda["ineqnonlin"][nmu:nmu + nmu]
            if self.flow_lim == "I":
                dIf_dVa, dIf_dVm, dIt_dVa, dIt_dVm, If, It = \
                    case.dIbr_dV(Yf, Yt, V)
                Gfaa, Gfav, Gfva, Gfvv = \
                    case.d2AIbr_dV2(dIf_dVa, dIf_dVm, If, Yf, V, muF)
                Gtaa, Gtav, Gtva, Gtvv = \
                    case.d2AIbr_dV2(dIt_dVa, dIt_dVm, It, Yt, V, muT)
            else:
                f = [e.from_bus.i for e in ln]
                t = [e.to_bus.i for e in ln]
                # Line-bus connection matrices.
                Cf = csr_matrix((ones(nl), (range(nl), f)), (nl, nb))
                Ct = csr_matrix((ones(nl), (range(nl), t)), (nl, nb))
                dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm, Sf, St = \
                    case.dSbr_dV(Yf, Yt, V)
                if self.flow_lim == PFLOW:
                    Gfaa, Gfav, Gfva, Gfvv = \
                        case.d2ASbr_dV2(dSf_dVa.real(), dSf_dVm.real(),
                                        Sf.real(), Cf, Yf, V, muF)
                    Gtaa, Gtav, Gtva, Gtvv = \
                        case.d2ASbr_dV2(dSt_dVa.real(), dSt_dVm.real(),
                                        St.real(), Ct, Yt, V, muT)
                elif self.flow_lim == SFLOW:
                    Gfaa, Gfav, Gfva, Gfvv = \
                        case.d2ASbr_dV2(dSf_dVa, dSf_dVm, Sf, Cf, Yf, V, muF)
                    Gtaa, Gtav, Gtva, Gtvv = \
                        case.d2ASbr_dV2(dSt_dVa, dSt_dVm, St, Ct, Yt, V, muT)
                else:
                    raise ValueError

            d2G = vstack([
                hstack([
                    vstack([hstack([Gfaa, Gfav]),
                            hstack([Gfva, Gfvv])]) +
                    vstack([hstack([Gtaa, Gtav]),
                            hstack([Gtva, Gtvv])]),
                    csr_matrix((2 * nb, nxtra))
                ]),
                hstack([
                    csr_matrix((nxtra, 2 * nb)),
                    csr_matrix((nxtra, nxtra))
                ])
            ])

            return d2f + d2H + d2G

        # Solve using primal-dual interior point method.
#        x, _, info, output, lmbda = \
        s = pdipm(ipm_f, ipm_gh, ipm_hess, x0, xmin, xmax, A, l, u, self.opts)

        return s

#------------------------------------------------------------------------------
#  "OPFModel" class:
#------------------------------------------------------------------------------

class OPFModel(object):
    """ Defines a model for optimal power flow.
    """

    def __init__(self, case):
        self.case = case
        self.vars = []
        self.lin_constraints = []
        self.nln_constraints = []
        self.costs = []


    @property
    def var_N(self):
        return sum([v.N for v in self.vars])


    def add_var(self, var):
        """ Adds a variable to the model.
        """
        if var.name in [v.name for v in self.vars]:
            logger.error("Variable set named '%s' already exists." % var.name)
            return

        var.i1 = self.var_N
        var.iN = self.var_N + var.N - 1
        self.vars.append(var)


    def add_vars(self, vars):
        """ Adds a set of variables to the model.
        """
        for var in vars:
            self.add_var(var)


    def get_var(self, name):
        """ Returns the variable set with the given name.
        """
        for var in self.vars:
            if var.name == name:
                return var
        else:
            raise ValueError



    def get_var_N(self, name):
        """ Return the number of variables in the named set.
        """
        return self.get_var(name).N


    @property
    def nln_N(self):
        return sum([c.N for c in self.nln_constraints])


    @property
    def lin_N(self):
        return sum([c.N for c in self.lin_constraints])


    @property
    def lin_NS(self):
        return len(self.lin_constraints)


    def linear_constraints(self):
        """ Returns the linear constraints.
        """
        A = csr_matrix((self.lin_N, self.var_N), dtype=float64)
        l = ones(self.lin_N) * -Inf
        u = -l

        for lin in self.lin_constraints:
            if lin.N:                   # non-zero number of rows to add
                Ak = lin.A              # A for kth linear constrain set
                i1 = lin.i1             # starting row index
                iN = lin.iN             # ending row index
                vsl = lin.vs            # var set list
                kN = -1                 # initialize last col of Ak used
                Ai = csr_matrix((lin.N, self.var_N))
                for v in vsl:
                    var = self.get_var(v)
                    j1 = var.i1         # starting column in A
                    jN = var.iN         # ending column in A
                    k1 = kN + 1         # starting column in Ak
                    kN = kN + var.N     # ending column in Ak
                    Ai[:, j1:jN + 1] = Ak[:, k1:kN + 1]

                A[i1:iN + 1, :] = Ai
                l[i1:iN + 1] = lin.l
                u[i1:iN + 1] = lin.u

        return A, l, u


    def add_constraint(self, con):
        """ Adds a constraint to the model.
        """
        if isinstance(con, LinearConstraint):
            N, M = con.A.size
            if con.name in [c.name for c in self.lin_constraints]:
                logger.error("Constraint set named '%s' already exists."
                             % con.name)
                return False
            else:
                con.i1 = self.lin_N# + 1
                con.iN = self.lin_N + N - 1

                nv = 0
                for vs in con.vs:
                    nv = nv + self.get_var_N(vs)
                if M != nv:
                    logger.error("Number of columns of A does not match number"
                        " of variables, A is %d x %d, nv = %d", N, M, nv)
                self.lin_constraints.append(con)
        elif isinstance(con, NonLinearConstraint):
            N = con.N
            if con.name in [c.name for c in self.nln_constraints]:
                logger.error("Constraint set named '%s' already exists."
                             % con.name)
                return False
            else:
                con.i1 = self.nln_N# + 1
                con.iN = self.nln_N + N
                self.nln_constraints.append(con)
        else:
            raise ValueError

        return True


    def add_constraints(self, constraints):
        """ Adds constraints to the model.
        """
        for con in constraints:
            self.add_constraint(con)


    @property
    def cost_N(self):
        return sum([c.N for c in self.costs])


    def get_cost_params(self):
        """ Returns the cost parameters.
        """
        return [c.params for c in self.costs]

#------------------------------------------------------------------------------
#  "Indexed" class:
#------------------------------------------------------------------------------

class Set(Named):

    def __init__(self, name, N):

        self.name = name

        # Starting index.
        self.i0 = 0

        # Ending index.
        self.iN = 0

        # Number in set.
        self.N = N

        # Number of sets.
        self.NS = 0

        # Ordered list of sets.
        self.order = []

#------------------------------------------------------------------------------
#  "Variable" class:
#------------------------------------------------------------------------------

class Variable(Set):
    """ Defines a set of variables.
    """

    def __init__(self, name, N, v0=None, vl=None , vu=None):
        """ Initialises a new Variable instance.
        """
        super(Variable, self).__init__(name, N)

        # Initial value of the variables. Zero by default.
        if v0 is None:
            self.v0 = zeros(N)
        else:
            self.v0 = v0

        # Lower bound on the variables. Unbounded below be default.
        if vl is None:
            self.vl = ones(N) * -Inf
        else:
            self.vl = vl

        # Upper bound on the variables. Unbounded above by default.
        if vu is None:
            self.vu = ones(N) * Inf
        else:
            self.vu = vu

#------------------------------------------------------------------------------
#  "LinearConstraint" class:
#------------------------------------------------------------------------------

class LinearConstraint(Set):
    """ Defines a set of linear constraints.
    """

    def __init__(self, name, AorN, l=None, u=None, vs=None):
        N, _ = AorN.size

        super(LinearConstraint, self).__init__(name, N)

        self.A = AorN
        self.l = ones(N) * -Inf if l is None else l
        self.u = ones(N) *  Inf if u is None else u

        # Varsets.
        self.vs = [] if vs is None else vs

        if (self.l.size[0] != N) or (self.u.size[0] != N):
            logger.error("Sizes of A, l and u must match.")

#------------------------------------------------------------------------------
#  "NonLinearConstraint" class:
#------------------------------------------------------------------------------

class NonLinearConstraint(Set):
    """ Defines a set of non-linear constraints.
    """
    pass

#------------------------------------------------------------------------------
#  "Cost" class:
#------------------------------------------------------------------------------

class Cost(Set):
    def __init__(self):
        self.N = None
        self.H = None
        self.Cw = None
        self.dd = None
        self.rh = None
        self.kk = None
        self.mm = None
        self.vs = None
        self.params = None

# EOF -------------------------------------------------------------------------

# Solving the RE problems

The RE problems are a suite of real-world engineering design problems collected and put into a
common form by Tanabe and Ishibuchi. Each one is bound-constrained: where the original design
problem had constraints, the suite folds their total violation into an extra objective, so an
unconstrained solver can be pointed straight at it.

This guide solves the ones DESDEO ships, and checks the result against the approximated Pareto
fronts published with the suite.

## The problems and where they come from

The suite is:

> Tanabe, R., & Ishibuchi, H. (2020). An easy-to-use real-world multi-objective optimization problem
> suite. *Applied Soft Computing*, 89, 106078. <https://doi.org/10.1016/j.asoc.2020.106078>

Each problem is drawn from an earlier paper, which is the reference to cite for the design problem
itself:

| Problem | Design problem | Original source |
|---|---|---|
| `re21` | Four bar truss | Cheng & Li (1999), *Engineering Optimization* 31(5), 641–661. [10.1080/03052159908941390](https://doi.org/10.1080/03052159908941390) |
| `re22` | Reinforced concrete beam | Amir & Hasegawa (1989), *Journal of Structural Engineering* 115(3), 626–646. [10.1061/(ASCE)0733-9445(1989)115:3(626)](https://doi.org/10.1061/%28ASCE%290733-9445%281989%29115%3A3%28626%29) |
| `re23` | Pressure vessel | Kannan & Kramer (1994), *Journal of Mechanical Design* 116(2), 405–411. [10.1115/1.2919393](https://doi.org/10.1115/1.2919393) |
| `re24` | Hatch cover | Amir & Hasegawa (1989), as above. |
| `re31` | Two bar truss | Coello Coello & Pulido (2005), *Structural and Multidisciplinary Optimization* 30(5), 388–403. [10.1007/s00158-005-0527-z](https://doi.org/10.1007/s00158-005-0527-z) |
| `re32` | Welded beam | Ray & Liew (2002), *Engineering Optimization* 34(2), 141–153. [10.1080/03052150210915](https://doi.org/10.1080/03052150210915) |
| `re33` | Disc brake | Ray & Liew (2002), as above. |
| `re34` | Vehicle crashworthiness | Liao, Li, Yang, Zhang & Li (2008), *Structural and Multidisciplinary Optimization* 35(6), 561–569. [10.1007/s00158-007-0163-x](https://doi.org/10.1007/s00158-007-0163-x) |
| `re37` | Rocket injector | Vaidyanathan, Tucker, Papila & Shyy (2003), *41st AIAA Aerospace Sciences Meeting*. [10.2514/6.2003-296](https://doi.org/10.2514/6.2003-296) |
| `re41` | Car side impact | Jain & Deb (2014), *IEEE Transactions on Evolutionary Computation* 18(4), 602–622. [10.1109/TEVC.2013.2281534](https://doi.org/10.1109/TEVC.2013.2281534) |
| `re42` | Conceptual marine design | Parsons & Scott (2004), *Journal of Ship Research* 48(1), 61–76. [10.5957/jsr.2004.48.1.61](https://doi.org/10.5957/jsr.2004.48.1.61) |
| `re61` | Water resource planning | Ray, Tai & Seow (2001), *Engineering Optimization* 33(4), 399–424. [10.1080/03052150108940926](https://doi.org/10.1080/03052150108940926) |

`re22`, `re23` and `re25` have discrete or integer variables and need the mixed-integer algorithm
templates, so they are left out below, as is `re24`, which DESDEO keeps in its constrained form.


## Solving them

One call each. NSGA-III is used throughout because it copes with all of the objective counts here,
from two up to six.

What is plotted below is the **archive** rather than the final population. DESDEO keeps a
non-dominated archive of everything a run has seen, on the object `emo_constructor` returns
alongside the solver, and it holds far more of the front than the last generation does: a few
thousand solutions against a population of about a hundred.

## The reference fronts

The suite publishes an approximated Pareto front for every problem, obtained by pooling long runs of
several algorithms. These are what an implementation should be checked against: if DESDEO's version
of a problem were wrong, its archive would sit somewhere else entirely.

The files are fetched from the suite's repository rather than shipped with DESDEO.

## Comparing the archives against the reference fronts

Two objectives plot directly, three fit in a 3-D scatter, and anything above that goes into
parallel coordinates. The reference front is drawn in grey underneath DESDEO's archive in each case.

Matplotlib has no parallel coordinates plot of its own, so here is a short one. Every axis is scaled
to the range the two fronts cover together, so the lines are directly comparable, and the tick
labels keep the original values. Both sets are thinned to a few hundred lines, which is about as
many as the eye can follow.

The archives track the reference fronts on every problem. Where DESDEO's lines stop short of the
grey ones — the top of `re31`'s and `re33`'s violation axis, for instance — the reference front
reaches extremes that a single 20 000-evaluation run does not, which is a matter of budget rather
than a disagreement about what the problem is.
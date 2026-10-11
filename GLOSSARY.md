# Cartlyf

One configurable scheduling product: each organisation describes its own resources, the work
to be scheduled and the rules, and Cartlyf finds and checks a schedule.

## Configuration

**Organisation**:
A customer of Cartlyf. Owns everything else, and nothing is shared between organisations.
_Avoid_: tenant (in product copy), account, customer

**Resource type**:
An organisation's category of bookable thing, such as Lecturer, Room, Student group or Nurse, with the attributes its resources carry.
_Avoid_: resource class, category

**Resource**:
One bookable person, space, asset or group. Identified to planners by its **code**.
_Avoid_: entity, item

**Code**:
A resource's short, unique, human-chosen identifier within an organisation (e.g. `LT1`, `RN-042`).
_Avoid_: external id, key

**Availability**:
When a resource can be used: weekly rules (available, unavailable, preferred, avoided) plus dated exceptions such as leave and holidays.
_Avoid_: calendar (as a noun for one rule), roster

**Schedule**:
One planning problem: a date range in one timezone, the work to place in it, and the rules in force.
_Avoid_: timetable, roster, plan (for the configuration itself)

**Horizon**:
The span of time a schedule covers, from the start of its first day to the end of its last.
_Avoid_: period, term

**Day part**:
A named stretch of every day, such as morning or afternoon, that rules can refer to.
_Avoid_: session (that word means something else here), shift

**Slot**:
A named start time and length that repeats on chosen weekdays, such as period P1 or the night shift.
_Avoid_: period (unless it is the customer's own word), timeslot

**Slot template**:
A schedule's set of slots.

**Demand**:
A description of work that produces activities: a **session demand** (N sessions a week) or a **coverage demand** (for every date and slot, so many people with given skills).
_Avoid_: course, requirement, shift request

**Activity**:
One thing to place in time: a duration, the starts it may take, and what it needs.
_Avoid_: event, lesson, shift (as the generic word), job

**Series**:
All activities produced by one demand.

**Candidate start**:
A start time an activity is allowed to take.

**Requirement**:
What one activity needs for one **role**: how many resources, which kind, and any that are fixed.
_Avoid_: need, constraint

**Constraint template**:
A kind of rule Cartlyf knows how to enforce, such as maximum load or minimum rest.
_Avoid_: rule type

**Constraint instance**:
One configured rule: a template plus its settings, what it applies to, and whether it is hard or soft.
_Avoid_: rule (acceptable in UI copy), constraint (alone, ambiguous)

**Scope**:
The resources or series a constraint instance applies to.

**Hard / soft**:
A hard rule must never be broken. A soft rule may be broken at a cost (its **weight**).

**Pin**:
A planner's decision that an activity keeps a given start or resources in future solves.
_Avoid_: lock, freeze

**Feasibility check**:
A quick check before solving that reports obvious impossibilities, such as no one qualified or not enough available hours.
_Avoid_: validation (used for inputs), pre-solve

**Import**:
Bringing resources or demands in from a spreadsheet: upload, map columns, dry run, commit.

## Solving

**Score**:
The verdict on a set of placements: how many hard rules are broken, plus the penalty of each soft rule.
_Avoid_: fitness, cost (alone)

**Penalty**:
What a soft rule costs a schedule: its weight times how far the rule is broken.

**Violation**:
One place where a hard rule, or a built-in rule such as no double-booking, is broken.
_Avoid_: error, clash (for anything other than double-booking)

**Conflict**:
A hard rule named as part of the reason no schedule can satisfy all hard rules together.
_Avoid_: blocker

**Checker**:
The part of Cartlyf that scores any set of placements without the solver, so every result can be verified.
_Avoid_: validator

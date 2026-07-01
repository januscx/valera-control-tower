# Architecture Decisions

## Decision 1: Start With Documentation and Simulation

The project starts with architecture docs, task models, and simulated execution before real robot control.

Why:

- simulation lets the task lifecycle and logs be tested without physical risk
- the project can demonstrate architecture before hardware integration is complete
- unknown robot capabilities can be documented instead of guessed
- future hardware work gets a clearer adapter boundary

## Decision 2: Keep Enterprise Integration Separate From Robot Internals

Enterprise integration should model commands, events, and status updates. It should not know how a tracked base or arm adapter performs movement.

Why:

- business workflows need stable contracts, not hardware-specific details
- robot internals will change as simulation and hardware support evolve
- decoupling makes the portfolio story easier to explain
- test data can be created without robot hardware

## Decision 3: Use Small Reviewable Agent Tasks

Codex and other agents should work in small, focused changes.

Why:

- small diffs are easier to review and benchmark
- agent mistakes are easier to find and revert
- architecture stays understandable
- the GitHub workflow remains useful for interviews and portfolio review

## Decision 4: Do Not Invent Hardware Capabilities

Documentation and future code should distinguish planned, simulated, and verified hardware behavior.

Why:

- robotics demos need clear safety and credibility boundaries
- simulated success does not prove physical success
- interview and portfolio readers should be able to trust what the repo claims

## Decision 5: Prefer Plain Local Prototypes First

The first executable prototypes should use plain Python and local files unless a later task explicitly justifies more infrastructure.

Why:

- the roadmap calls for a compact PoC
- local-first work avoids unnecessary cloud or dependency setup
- boring tools keep the architecture easy to inspect

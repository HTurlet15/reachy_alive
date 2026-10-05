"""The robot's brain, one folder per region, sorted by speed.

Each region is named after the part of the brain it imitates. Fast, local
reactions and slow, considered ones live in different regions, so nothing
slow can stall the fast path (see ARCHITECTURE.md, rule 8).
"""
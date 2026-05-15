"""Hand-rolled SAS parser for the CTX-2024-001 modernization MVP.

This parser is sized for the constructs actually present in the synthetic
codebase (DATA, PROC SORT/SQL/SUMMARY/FORMAT, basic %macro/%let/%include
/&var). It is NOT a complete SAS parser. The coverage report
(build/reports/coverage.md) enumerates what is and is not handled.
"""

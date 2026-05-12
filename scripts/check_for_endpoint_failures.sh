#! /usr/bin/env bash

LOGFILE=output.log
ERR_MSGS=()
ERR_COUNT=0
pytest -v tests/*_test.py tests/test_*.py -m "strict_endpoints_test" > $LOGFILE 2>&1 || \
  while read FAIL; do
    ANALYSIS=`echo ${FAIL##*strict\[} | cut -d "]" -f1` # get analysis name from pattern "strict[<ANALYSIS>]"
    ERR_COUNT=$(( ${#ERR_MSGS[@]} + 1 ))
    REASON=`grep "^E       " $LOGFILE | head -n $ERR_COUNT | tail -n 1` # get fail reason
    REASON=${REASON:8} # remove prefix
    ERR_MSGS+=("::warning ::Analyses endpoint '$ANALYSIS' was not available: $REASON") # use GitHub's warning syntax
  done <<< `grep "FAILED.*\[" $LOGFILE | grep -v "%"` # get summary lines with failing tests, ignore progress lines
cat $LOGFILE
for ERR_MSG in "${ERR_MSGS[@]}"; do echo $ERR_MSG; done # flag errors
if [ $ERR_COUNT>0 ]; then; exit 1; fi # fail if there were any errors
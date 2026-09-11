"""Exact paper-tested 0.6R progressive trailing rules, reused by live layer."""
import math
TRAIL_STEP_R=0.6
EXIT_SL="SL"; EXIT_TRAILING_STOP="TRAILING_STOP"; EXIT_TAKE_PROFIT="TAKE_PROFIT"

def is_executable(confidence): return confidence=="HIGH"

def favorable_r(direction, entry, sl, price):
    risk=abs(entry-sl)
    return ((price-entry)/risk) if direction=="BUY" else ((entry-price)/risk)

def locked_level(direction, entry, sl, price):
    r=favorable_r(direction,entry,sl,price)
    return max(0.0, math.floor(r/TRAIL_STEP_R)*TRAIL_STEP_R)

def floor_for_level(direction,entry,sl,level_r):
    risk=abs(entry-sl)
    return entry + level_r*risk if direction=="BUY" else entry-level_r*risk

def next_trailing_state(direction,entry,sl,current_level_r,price):
    new_level=locked_level(direction,entry,sl,price)
    if new_level<=current_level_r: return current_level_r, floor_for_level(direction,entry,sl,current_level_r), False
    return new_level, floor_for_level(direction,entry,sl,new_level), True

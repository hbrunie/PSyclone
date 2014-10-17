from parse import parse
from psyGen import PSyFactory

api="gocean"
ast,invokeInfo=parse("shallow_gocean.f90",api=api)
psy=PSyFactory(api).create(invokeInfo)
print psy.gen

print psy.invokes.names
schedule=psy.invokes.get('invoke_0').schedule
schedule.view()

from psyGen import TransInfo
t=TransInfo()
print t.list
lf=t.get_trans_name('LoopFuse')

# fuse all outer loops
lf1_schedule,memento = lf.apply(schedule.children[0],schedule.children[1])
lf2_schedule,memento = lf.apply(lf1_schedule.children[0],
                                lf1_schedule.children[1])
lf3_schedule,memento = lf.apply(lf2_schedule.children[0],
                                lf2_schedule.children[1])
lf3_schedule.view()

# fuse all inner loops
lf4_schedule,memento = lf.apply(lf3_schedule.children[0].children[0],
                                lf3_schedule.children[0].children[1])
lf5_schedule,memento = lf.apply(lf4_schedule.children[0].children[0],
                                lf4_schedule.children[0].children[1])
lf6_schedule,memento = lf.apply(lf5_schedule.children[0].children[0],
                                lf5_schedule.children[0].children[1])
lf6_schedule.view()

psy.invokes.get('invoke_0')._schedule=lf6_schedule
print psy.gen
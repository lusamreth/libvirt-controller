from time import sleep
import libvirt
from .controller import Console
from threading import Thread, Event, Lock


def spawnTimer(console: Console, execution, timer) -> int:
    ON_START = libvirt.VIR_DOMAIN_EVENT_STARTED
    timer_fn = build_timer(ON_START, execution)
    timer = libvirt.virEventAddTimeout(timer, timer_fn, console)
    return timer


def build_timer(
    target_event: int, execution, debug: bool = False, event_name=""
):
    def timer_fn(timer, console: Console):
        domain_state = console.state[0]
        if domain_state != target_event:
            if debug:
                console.streamline("polling for even " + event_name)
        exit = execution(console)
        if exit:
            console.streamline("execution on exit 1")
            libvirt.virEventRemoveTimeout(timer)

    return timer_fn

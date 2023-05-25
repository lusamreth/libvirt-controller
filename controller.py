import logging
import libvirt
from multiprocessing import Queue, Lock

BufferQueue = Queue()
bufferLock = Lock()


class Console(object):
    def __init__(self, uri, name, lifecyle_hooks=None):
        self.uri = uri
        self.name = name
        self.connection = libvirt.openReadOnly(None)
        self.domain = self.connection.lookupByName(name)
        self.stream = BufferQueue
        self.state = self.domain.state(0)
        self.streamLock = bufferLock
        self.connection.domainEventRegister(
            injectLifeCycleProcess(lifecyle_hooks), self
        )
        self.run_console = True

    def readStream(self, reader):
        if not self.stream.empty():
            self.streamLock.acquire()
            # _print(self.stream.pop())
            reader(self.stream.get())
            self.streamLock.release()

    def streamline(self, item):
        self.streamLock.acquire()
        self.stream.put(item)
        self.streamLock.release()


def injectLifeCycleProcess(state_functions=[]):
    # (state,func)
    # (state,func)
    # (state,func)
    def probing_event(console, event):
        print("EVENT probe", event, state_functions)
        for state_union in state_functions:
            func = state_union["callback"]
            state_event = state_union["event"]
            # libvirt.VIR_DOMAIN_EVENT_STARTED_BOOTED
            name = state_union["name"]
            if event == state_event:
                print("FOUND EVENT [[{}]]".format(name))
                func(console)

    def lifecycle_callback(
        connection, domain, event, detail, console: Console
    ):
        console.state = console.domain.state(0)
        currentState = console.state
        probing_event(console, event)
        # libvirt.VIR_DOMAIN_EVENT_STARTED_WAKEUP
        console.streamline(
            "EVENT CALLBACK HAPPEND -> {} {}".format(event, detail)
        )
        # console.streamline("Current connection : " + connection)
        console.streamline(
            "{} transitioned to state {}, reason {}".format(
                console.name, currentState[0], console.state[1]
            )
        )

    return lifecycle_callback

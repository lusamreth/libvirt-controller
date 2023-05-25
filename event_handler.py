import os
import logging
import sys
import threading
from time import sleep
import libvirt
from subprocess import check_output, Popen, PIPE
from threading import Thread, Event, Lock
from prompt_toolkit import prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.lexers import PygmentsLexer
from .timer import spawnTimer
from .controller import Console, bufferLock, BufferQueue
from .hooks import reset_vnet_ip


def error_handler(unused, error):
    # The console stream errors on VM shutdown; we don't care
    if (
        error[0] == libvirt.VIR_ERR_RPC
        and error[1] == libvirt.VIR_FROM_STREAMS
    ):
        return
    logging.warn(error)


def stdin_callback(watch, fd, events, console: Console):
    readbuf = os.read(fd, 1024)
    input = readbuf.upper().strip().decode()
    console.streamline(input)

    if input.lower() == "exit":
        console.run_console = False
        console.stream.close()
    else:
        console.streamline(input)


def registerLibvirtImpl(console):
    libvirt.registerErrorHandler(error_handler, None)
    libvirt.virEventAddHandle(
        0, libvirt.VIR_EVENT_HANDLE_READABLE, stdin_callback, console
    )


target_ip_net = "172.253.118.102"
full_target_ip = "{}/24".format(target_ip_net)


def report_ids(msg):
    print("uid, gid = %d, %d; %s" % (os.getuid(), os.getgid(), msg))


def demote(user_uid, user_gid):
    def result():
        report_ids("starting demotion")
        os.setgid(user_gid)
        os.setuid(user_uid)
        report_ids("finished demotion")

    return result


def startingLookingGlass(console: Console):
    child = Popen(
        ["pgrep", "-f", "looking-glass-client"],
        stdout=PIPE,
        shell=False,
    )
    pid_result = (
        str(child.communicate()[0], "UTF-8").strip().split("\n")
    )
    first_res = pid_result.pop()
    pid = int(first_res) if first_res != "" else None
    _print = lambda x: console.streamline(x)
    currentState = console.domain.state(0)[0]
    console.streamline(str(console.domain.state(0)[0]))

    if pid is not None:
        _print(
            "Already found looking-glass-client running : {}".format(
                pid
            )
        )
        return

    if (
        currentState is not libvirt.VIR_DOMAIN_EVENT_SHUTDOWN
        or currentState is not libvirt.VIR_DOMAIN_SHUTOFF
    ):
        os.seteuid(1000)
        _print("starting looking-glass-client...")
        Popen(
            "looking-glass-client -m 97 &",
            stdout=PIPE,
            user="lusamreth",
            stderr=PIPE,
            shell=True,
        )
    else:
        print("Cannot launch looking glass while vm is close")


def spawnResetVnetTimer(console: Console):
    console.streamline("spinning a timer spata")
    return spawnTimer(
        console,
        lambda console: reset_vnet_ip(
            target_ip_net, lambda x: console.streamline(x)
        ),
        1000,
    )


class VnetResetter:
    def __init__(self):
        pass


def setupConsole() -> Console:
    libvirt.virEventRegisterDefaultImpl()
    console = Console(
        "qemu:///system",
        "win10-2",
        lifecyle_hooks=[
            # {
            #     "name": "resetting vnet ip",
            #     "callback": spata,
            #     "event": libvirt.VIR_DOMAIN_EVENT_STARTED,
            # },
            {
                "name": "starting looking glass",
                "callback": startingLookingGlass,
                "event": libvirt.VIR_DOMAIN_EVENT_STARTED,
            },
            {
                "name": "resetting vnet",
                "callback": spawnResetVnetTimer,
                "event": libvirt.VIR_DOMAIN_EVENT_STARTED,
            },
            {
                "name": "resetting vnet ip",
                "callback": startingLookingGlass,
                "event": libvirt.VIR_DOMAIN_PAUSED,
            },
        ],
    )

    spawnResetVnetTimer(console)
    registerLibvirtImpl(console)
    return console


def main(console: Console, lock: Lock):
    logging.basicConfig(filename="msg.log", level=logging.DEBUG)
    # spawnTimer(console)
    while console.run_console:
        libvirt.virEventRunDefaultImpl()
        # console.readStream()


def clear():
    os.system("clear")


screen = "\n>>"
screen_template = "\n>>"
prompt = ">>"


def printToScreen(s):
    global screen, prompt
    clear()
    screen += s + "\n"
    screen = "{}{}".format(screen, screen_template)
    # screen += prompt + "\n"
    print(screen)


def promptToScreen(p):
    global prompt
    # clear()
    print(screen)
    s = input(p)
    return s


def PromptLoop(console: Console, lock: Lock):
    isRunning = True
    prefix = "HELLO"
    text = ""

    while isRunning:
        try:
            text = prefix + " > " + "\n"
            sleep(0.1)
            # console.streamline(text)
        except KeyboardInterrupt:
            continue
        except EOFError:
            break

        if text == "exit" or text == "EXIT":
            isRunning = False
        if console.state[0] == libvirt.VIR_DOMAIN_RUNNING:
            prefix = "[[ RUNNING ]]"
        elif console.state[0] == libvirt.VIR_DOMAIN_EVENT_STOPPED:
            prefix = "[[ CLOSED ]]"
        elif console.state[0] == libvirt.VIR_DOMAIN_PAUSED:
            prefix = "[[ PAUSING ]]"
        else:
            prefix = "[[ ACTION ]] " + str(console.state[0])

    print("prompt loop exited")


consoleLock = Lock()
console = setupConsole()


InputThread = Thread(
    target=PromptLoop,
    args=(console, consoleLock),
)


mainThread = Thread(
    target=main,
    args=((console, consoleLock)),
)


def MainRunner():
    mainThread.start()
    while console.run_console:
        console.readStream(lambda st: printToScreen(st))
    mainThread.join()


MainRunner()

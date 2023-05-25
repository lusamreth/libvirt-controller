import netifaces
import os


def reset_vnet_ip(full_target_ip: str, printer=print) -> bool:
    network_ifs = netifaces.interfaces()
    _print = printer
    for interface in network_ifs:
        if interface.startswith("vnet"):
            ips = netifaces.ifaddresses(interface)

            if ips.get(netifaces.AF_INET) is None:
                _print("Still probing for inet ip...")
                return False

            net_ip = ips[netifaces.AF_INET][0]
            _print("VNET information :")
            _print("-KVM VNET : {}".format(interface))
            _print("-ip-address info : {}".format(net_ip))
            target_ip_net = full_target_ip.split("/")[0]

            if net_ip["addr"] != target_ip_net:
                _print(
                    "vnet has different address from the target setting"
                )
                print("reset vnet ip...")
                os.system(
                    "ifconfig {} {}".format(
                        interface, full_target_ip
                    )
                )
                return False
            else:
                _print("Correct vnet ip")
                return True
    return False

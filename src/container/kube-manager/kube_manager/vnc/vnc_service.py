#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#

"""
VNC service management for kubernetes
"""

from vnc_api.vnc_api import *
from config_db import *
from loadbalancer import *
from cfgm_common import importutils

class VncService(object):

    def __init__(self, vnc_lib=None, label_cache=None):
        self._vnc_lib = vnc_lib
        self._label_cache = label_cache

        self.service_lb_mgr = importutils.import_object(
            'kube_manager.vnc.loadbalancer.ServiceLbManager', vnc_lib)
        self.service_ll_mgr = importutils.import_object(
            'kube_manager.vnc.loadbalancer.ServiceLbListenerManager', vnc_lib)
        self.service_lb_pool_mgr = importutils.import_object(
            'kube_manager.vnc.loadbalancer.ServiceLbPoolManager', vnc_lib)
        self.service_lb_member_mgr = importutils.import_object(
            'kube_manager.vnc.loadbalancer.ServiceLbMemberManager', vnc_lib)

    def _get_project(self, service_namespace):
        proj_fq_name = ['default-domain', service_namespace]
        try:
            proj_obj = self._vnc_lib.project_read(fq_name=proj_fq_name)
            return proj_obj
        except NoIdError:
            return None

    def _get_network(self):
        vn_fq_name = ['default-domain', 'default', 'cluster-network']
        try:
            vn_obj = self._vnc_lib.virtual_network_read(fq_name=vn_fq_name)
        except NoIdError:
            return None
        return vn_obj

    def _get_virtualmachine(self, id):
        try:
            vm_obj = self._vnc_lib.virtual_machine_read(id=id)
        except NoIdError:
            return None
        obj = self._vnc_lib.virtual_machine_read(id = id, fields = ['virtual_machine_interface_back_refs'])
        back_refs = getattr(obj, 'virtual_machine_interface_back_refs', None)
        vm_obj.virtual_machine_interface_back_refs = back_refs
        return vm_obj

    def check_service_selectors_actions(self, selectors, service_id, ports):
        for selector in selectors.items():
            key = self._label_cache._get_key(selector)
            self._label_cache._locate_label(key,
                self._label_cache.service_selector_cache, selector, service_id)
            pod_ids = self._label_cache.pod_label_cache.get(key, [])
            if len(pod_ids):
                self.add_pods_to_service(service_id, pod_ids, ports)

    def remove_service_selectors_from_cache(self, selectors, service_id, ports):
        for selector in selectors.items():
            key = self._label_cache._get_key(selector)
            self._label_cache._remove_label(key,
                self._label_cache.service_selector_cache, selector, service_id)

    def add_pod_to_service(self, service_id, pod_id, port=None):
        lb = LoadbalancerKM.get(service_id)
        if not lb:
            return

        listener_found = True
        for ll_id in lb.loadbalancer_listeners:
            ll = LoadbalancerListenerKM.get(ll_id)
            if not ll:
                contine
            if not ll.params['protocol_port']:
                contine

            if port:
                if ll.params['protocol_port'] != port['port'] or \
                   ll.params['protocol'] != port['protocol']:
                    listener_found = False

            if not listener_found:
                contine
            pool_id = ll.loadbalancer_pool
            if not pool_id:
                contine
            pool = LoadbalancerPoolKM.get(pool_id)
            if not pool:
                contine
            vm = VirtualMachineKM.get(pod_id)
            if not vm: 
                continue

            for vmi_id in list(vm.virtual_machine_interfaces):
                vmi = VirtualMachineInterfaceKM.get(vmi_id)
                if not vmi:
                    continue
                member_match = False
                for member_id in pool.members:
                    member = LoadbalancerMemberKM.get(member_id)
                    if member and member.vmi == vmi_id:
                        member_match = True
                        break
                if not member_match:
                    member_obj = self._vnc_create_member(pool, vmi_id,
                                                      ll.params['protocol_port'])
                    LoadbalancerMemberKM.locate(member_obj.uuid)
                

    def remove_pod_from_service(self, service_id, pod_id, port=None):
        lb = LoadbalancerKM.get(service_id)
        if not lb:
            return

        listener_found = True
        for ll_id in lb.loadbalancer_listeners:
            ll = LoadbalancerListenerKM.get(ll_id)
            if not ll:
                contine
            if not ll.params['protocol_port']:
                contine

            if port:
                if ll.params['protocol_port'] != port['port'] or \
                   ll.params['protocol'] != port['protocol']:
                    listener_found = False

            if not listener_found:
                contine
            pool_id = ll.loadbalancer_pool
            if not pool_id:
                contine
            pool = LoadbalancerPoolKM.get(pool_id)
            if not pool:
                contine
            vm = VirtualMachineKM.get(pod_id)
            if not vm: 
                continue

            for vmi_id in list(vm.virtual_machine_interfaces):
                vmi = VirtualMachineInterfaceKM.get(vmi_id)
                if not vmi:
                    continue
                member_match = False
                for member_id in pool.members:
                    member = LoadbalancerMemberKM.get(member_id)
                    if member and member.vmi == vmi_id:
                        member_match = True
                        break
                if member_match:
                    self._vnc_delete_member(member.uuid)
                    LoadbalancerMemberKM.delete(member.uuid)

    def add_pods_to_service(self, service_id, pod_list, ports=None):
        for pod_id in pod_list:
            for port in ports:
                self.add_pod_to_service(service_id, pod_id, port)

    def _vnc_create_member(self, pool, vmi_id, protocol_port):
        pool_obj = self.service_lb_pool_mgr.read(pool.uuid)
        member_obj = self.service_lb_member_mgr.create(pool_obj, vmi_id, protocol_port)
        return member_obj

    def _vnc_create_pool(self, namespace, ll, port):
        proj_obj = self._get_project(namespace)
        ll_obj = self.service_ll_mgr.read(ll.uuid)
        pool_obj = self.service_lb_pool_mgr.create(ll_obj, proj_obj, port)
        return pool_obj

    def _vnc_create_listener(self, namespace, lb, port):
        proj_obj = self._get_project(namespace)
        lb_obj = self.service_lb_mgr.read(lb.uuid)
        ll_obj = self.service_ll_mgr.create(lb_obj, proj_obj, port)
        return ll_obj

    def _create_listeners(self, namespace, lb, ports):
        for port in ports:
            listener_found = False
            for ll_id in lb.loadbalancer_listeners:
                ll = LoadbalancerListenerKM.get(ll_id)
                if not ll:
                    contine
                if not ll.params['protocol_port']:
                    contine
                if not ll.params['protocol']:
                    contine

                if ll.params['protocol_port'] == port['port'] and \
                   ll.params['protocol'] == port['protocol']:
                    listener_found = True
                    break

            if not listener_found:
                ll_obj = self._vnc_create_listener(namespace, lb, port)
                ll = LoadbalancerListenerKM.locate(ll_obj._uuid)

            pool_id = ll.loadbalancer_pool
            if pool_id:
                pool = LoadbalancerPoolKM.get(pool_id)
            # SAS FIXME: If pool_id present, check for targetPort value
            if not pool_id or not pool:
                pool_obj = self._vnc_create_pool(namespace, ll, port)
                LoadbalancerPoolKM.locate(pool_obj._uuid)

    def _vnc_create_lb(self, service_id, service_name,
                       service_namespace, service_ip, selectors):
        proj_obj = self._get_project(service_namespace)
        vn_obj = self._get_network()
        lb_obj = self.service_lb_mgr.create(vn_obj, service_id, service_name, 
                                        proj_obj, service_ip, selectors)
        return lb_obj

    def _lb_create(self, service_id, service_name,
            service_namespace, service_ip, selectors, ports):
        lb = LoadbalancerKM.get(service_id)
        if not lb:
            lb_obj = self._vnc_create_lb( service_id, service_name, 
                                        service_namespace, service_ip, selectors)
            lb = LoadbalancerKM.locate(service_id)

        self._create_listeners(service_namespace, lb, ports)

    def vnc_service_add(self, service_id, service_name,
            service_namespace, service_ip, selectors, ports):
        self._lb_create(service_id, service_name, service_namespace, service_ip,
                        selectors, ports)

        if selectors:
            self.check_service_selectors_actions(selectors, service_id, ports)

    def _vnc_delete_member(self, member_id):
        self.service_lb_member_mgr.delete(member_id)

    def _vnc_delete_pool(self, pool_id):
        self.service_lb_pool_mgr.delete(pool_id)

    def _vnc_delete_listener(self, ll_id):
        self.service_ll_mgr.delete(ll_id)

    def _vnc_delete_listeners(self, lb, ports):
        listeners = lb.loadbalancer_listeners.copy()
        for ll_id in listeners or []:
            ll = LoadbalancerListenerKM.get(ll_id)
            if not ll:
                continue
            pool_id = ll.loadbalancer_pool
            if pool_id:
                pool = LoadbalancerPoolKM.get(pool_id)
                if pool:
                    members = pool.members.copy()
                    for member_id in members or []:
                        member = LoadbalancerMemberKM.get(member_id)
                        if member:
                            self._vnc_delete_member(member_id)
                            LoadbalancerMemberKM.delete(member_id)

                self._vnc_delete_pool(pool_id)
                LoadbalancerPoolKM.delete(pool_id)
            self._vnc_delete_listener(ll_id)
            LoadbalancerListenerKM.delete(ll_id)

    def _vnc_delete_lb(self, lb_id):
        self.service_lb_mgr.delete(lb_id)

    def _lb_delete(self, service_id, service_name,
            service_namespace, service_ip, selectors, ports):
        lb = LoadbalancerKM.get(service_id)
        if not lb:
            return
        self._vnc_delete_listeners(lb, ports)
        self._vnc_delete_lb(service_id)
        LoadbalancerKM.delete(service_id)

    def vnc_service_delete(self, service_id, service_name, 
                           service_namespace, service_ip, selectors, ports):
        self._lb_delete(service_id, service_name, service_namespace, service_ip,
                        selectors, ports)
        if selectors:
            self.remove_service_selectors_from_cache(selectors, service_id, ports)

    def process(self, event):
        service_id = event['object']['metadata'].get('uid')
        service_name = event['object']['metadata'].get('name')
        service_namespace = event['object']['metadata'].get('namespace')
        service_ip = event['object']['spec'].get('clusterIP')
        selectors = event['object']['spec'].get('selector', None)
        ports = event['object']['spec'].get('ports')

        if event['type'] == 'ADDED' or event['type'] == 'MODIFIED':
            self.vnc_service_add(service_id, service_name,
                service_namespace, service_ip, selectors, ports)
        elif event['type'] == 'DELETED':
            self.vnc_service_delete(service_id, service_name, service_namespace,
                                    service_ip, selectors, ports)

#
# Copyright (c) 2025 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import typing
import datetime
import urllib.parse
import logging
import requests
import time
import token
from typing import List, Dict, Any, Tuple


from uds.core.util import security
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached

from . import types, consts, exceptions


logger = logging.getLogger(__name__)

class OpenshiftClient:
    cluster_url: str
    api_url: str
    username: str
    password: str
    namespace: str
    _verify_ssl: bool
    _timeout: int
    _token_expiry: datetime.datetime

    _session: typing.Optional[requests.Session] = None

    cache: typing.Optional['Cache']

    def __init__(
        self,
        cluster_url: str,
        api_url: str,
        username: str,
        password: str,
        namespace: str = 'default',
        timeout: int = 5,
        verify_ssl: bool = False,
        cache: typing.Optional['Cache'] = None,
    ) -> None:
        self.cluster_url = cluster_url
        self.api_url = api_url
        self.username : str = username
        self.password: str = password
        self.namespace: str = namespace

        self._verify_ssl: bool = verify_ssl
        self._timeout: int = timeout

        self.cache = cache

        self._access_token = ''
        self._token_expiry = datetime.datetime.min

    @property
    def session(self) -> requests.Session:
        return self.connect()

    def connect(self, force: bool = False) -> requests.Session:
        # For testing, always use the fixed token
        session = self._session = security.secure_requests_session(verify=self._verify_ssl)
        session.headers.update(
            {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': 'Bearer sha256~82_k2GpPJ4som5Vfy3P6kcQgeeHdxo-_txXR760K_tM',
            }
        )
        return session

    def get_token(self) -> str|None:
        return "sha256~82_k2GpPJ4som5Vfy3P6kcQgeeHdxo-_txXR760K_tM"
        try:
            url = f"{self.cluster_url}/oauth/authorize?client_id=openshift-challenging-client&response_type=token"
            r = requests.get(url, auth=(self.username, self.password), timeout=15, allow_redirects=True, verify=False)
            if "access_token=" not in r.url:
                raise Exception("No se encontró access_token en la URL de respuesta")
            token = r.url.split("access_token=")[1].split("&")[0]
            return token
        except Exception as ex:
            logging.error(f"No se pudo obtener token: {ex}")
            raise

    def get_api_url(self, path: str, *parameters: tuple[str, str]) -> str:
        url = self.api_url + path
        if parameters:
            url += '?' + urllib.parse.urlencode(
                parameters, doseq=True, safe='[]', quote_via=urllib.parse.quote_plus
            )
        return url

    def do_request(
        self,
        method: typing.Literal['GET', 'POST', 'PUT', 'DELETE'],
        path: str,
        *parameters: tuple[str, str],
        data: typing.Any = None,
        check_for_success: bool = False,
    ) -> typing.Any:
        logger.debug(
            'Requesting %s %s with parameters %s and data %s',
            method.upper(),
            path,
            parameters,
            data,
        )
        try:
            match method:
                case 'GET':
                    response = self.session.get(
                        self.get_api_url(path, *parameters),
                        timeout=self._timeout,
                    )
                case 'POST':
                    response = self.session.post(
                        self.get_api_url(path, *parameters),
                        json=data,
                        timeout=self._timeout,
                    )
                case 'PUT':
                    response = self.session.put(
                        self.get_api_url(path, *parameters),
                        json=data,
                        timeout=self._timeout,
                    )
                case 'DELETE':
                    response = self.session.delete(
                        self.get_api_url(path, *parameters),
                        timeout=self._timeout,
                    )
                case _:
                    raise ValueError(f'Unsupported HTTP method: {method}')
        except requests.ConnectionError as e:
            raise exceptions.OpenshiftConnectionError(str(e))
        except requests.RequestException as e:
            raise exceptions.OpenshiftError(f'Error during request: {str(e)}')
        logger.debug('Request result to %s: %s -- %s', path, response.status_code, response.content[:64])

        if not response.ok:
            if response.status_code == 401:
                # Unauthorized, try to refresh the token
                logger.debug('Unauthorized request, refreshing token')
                self._session = None
                raise exceptions.OpenshiftAuthError(
                    'Unauthorized request, please check your credentials or token expiry'
                )
            elif response.status_code == 403:
                # Forbidden, user does not have permissions
                logger.debug('Forbidden request, check your permissions')
                raise exceptions.OpenshiftPermissionError('Forbidden request, please check your permissions')
            elif response.status_code == 404:
                # Not found, resource does not exist
                logger.debug('Resource not found: %s', path)
                raise exceptions.OpenshiftNotFoundError(f'Resource not found: {path}')

            error_message = f'Error on request {method.upper()} {path}: {response.status_code} - {response.content.decode("utf8")[:128]}'
            logger.debug(error_message)
            raise exceptions.OpenshiftError(error_message)

        try:
            data = response.json()
        except Exception as e:
            error_message = f'Error parsing JSON response from {method.upper()} {path}: {str(e)}'
            logger.debug(error_message)
            raise exceptions.OpenshiftError(error_message)

        if check_for_success and not data.get('success', False):
            error_message = f'Error on request {method.upper()} {path}: {data.get("error", "Unknown error")}'
            logger.debug(error_message)
            raise exceptions.OpenshiftError(error_message)

        return data

    def do_paginated_request(
        self,
        method: typing.Literal['GET', 'POST', 'PUT', 'DELETE'],
        path: str,
        key: str,
        *parameters: tuple[str, str],
        data: typing.Any = None,
    ) -> typing.Iterator[typing.Any]:
        """
        Make a paginated request to the Openshift API.
        Args:
            method (str): HTTP method to use (GET, POST, PUT, DELETE)
            path (str): API endpoint path
            *parameters: Additional parameters to include in the request
            data (Any): Data to send with the request (for POST/PUT)
        Yields:
            typing.Any: The JSON response from each page of the request

        Note:
            The responses has also the "meta" key, which contains pagination information:
            offset: int64
            max: int64
            size: int64
            total: int64

            This information is used to determine if there are more pages to fetch.
            If not present, we try our best by counting the number of items returned
            and comparing it with the items requested per page (consts.MAX_ITEMS_PER_REQUEST).
        """
        offset = 0
        while True:
            params: list[tuple[str, str]] = [i for i in parameters] + [
                ('max', str(consts.MAX_ITEMS_PER_REQUEST)),
                ('offset', str(offset)),
            ]
            response = self.do_request(method, path, *params, data=data)
            data = response.get(key, [])
            yield from data

            # Checke meta information to see if we have more pages
            meta = response.get('meta', {})
            if not meta:  # Do our best to avoid errors if meta is not present
                # Check if we have more pages
                if len(data) < consts.MAX_ITEMS_PER_REQUEST:
                    break
            elif meta.get('offset', 0) + meta.get('size', 0) >= meta.get('total', 0):
                # No more pages, as offset is greater than or equal to total
                break

            offset += consts.MAX_ITEMS_PER_REQUEST

    #* --- OpenShift resource Methods ---

    def print_resource_names(self, items: List[Dict[str, Any]], title: str) -> None:
        logging.info("list of %s:", title)
        for idx, item in enumerate(items, start=1):
            name = item.get('metadata', {}).get('name', 'UNKNOWN')
            logging.info("%d - %s", idx, name)

    def get_vm_info_by_name(self, vm_name: str) -> types.VMDefinition | None:
        path = f"apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachines/{vm_name}"
        try:
            response = self.do_request('GET', path)
            return types.VMDefinition.from_dict(response)  # Convertir a VMDefinition aquí
        except exceptions.OpenshiftNotFoundError:
            return None
        except Exception as e:
            logger.info(f"Error getting VM {vm_name}: {e}")
            return None
        
    def get_vm_instance_info_by_name(self, vm_name: str) -> types.VMInstanceInfo | None:
        path = f"apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachineinstances/{vm_name}"
        try:
            response = self.do_request('GET', path)
            return types.VMInstanceInfo.from_dict(response)  # Convertir a VMInstanceInfo aquí
        except exceptions.OpenshiftNotFoundError:
            return None
        except Exception as e:
            logger.info(f"Error getting VM Instance {vm_name}: {e}")
            return None

    def monitor_vm_clone(self, api_url: str, namespace: str, clone_name: str, polling_interval: int = 5) -> None:
        clone_url = f"{api_url}/apis/clone.kubevirt.io/v1alpha1/namespaces/{namespace}/virtualmachineclones/{clone_name}"
        headers = {"Authorization": f"Bearer {self.get_token()}", "Accept": "application/json"}
        logging.info("Monitoring clone process for '%s'...", clone_name)
        while True:
            try:
                response = requests.get(clone_url, headers=headers, verify=False)
                if response.status_code == 200:
                    clone_data = response.json()
                    status = clone_data.get('status', {})
                    phase = status.get('phase', 'Unknown')
                    logging.info("Phase: %s", phase)
                    for condition in status.get('conditions', []):
                        ctype = condition.get('type', '')
                        cstatus = condition.get('status', '')
                        cmsg = condition.get('message', '')
                        logging.info("  %s: %s - %s", ctype, cstatus, cmsg)
                    if phase == 'Succeeded':
                        logging.info("Clone '%s' completed successfully!", clone_name)
                        break
                    elif phase == 'Failed':
                        logging.error("Clone '%s' failed!", clone_name)
                        break
                elif response.status_code == 404:
                    logging.warning("Clone resource '%s' not found. May have been cleaned up.", clone_name)
                    break
                else:
                    logging.error("Error monitoring clone: %d", response.status_code)
            except Exception as e:
                logging.error("Monitoring exception: %s", e)
            logging.info("Waiting %d seconds before next check...", polling_interval)
            time.sleep(polling_interval)

    def get_vm_pvc_or_dv_name(self, api_url: str, namespace: str, vm_name: str) -> Tuple[str, str]:
        vm_url = f"{api_url}/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines/{vm_name}"
        headers = {"Authorization": f"Bearer {self.get_token()}", "Accept": "application/json"}
        response = requests.get(vm_url, headers=headers, verify=False)
        if response.status_code == 200:
            vm_obj = response.json()
            volumes = vm_obj.get("spec", {}).get("template", {}).get("spec", {}).get("volumes", [])
            for vol in volumes:
                pvc = vol.get("persistentVolumeClaim")
                if pvc:
                    return pvc.get("claimName"), "pvc"
                dv = vol.get("dataVolume")
                if dv:
                    return dv.get("name"), "dv"
        raise Exception(f"No PVC or DataVolume found in VM {vm_name}")

    def get_datavolume_size(self, api_url: str, namespace: str, dv_name: str) -> str:
        url = f"{api_url}/apis/cdi.kubevirt.io/v1beta1/namespaces/{namespace}/datavolumes/{dv_name}"
        headers = {"Authorization": f"Bearer {self.get_token()}", "Accept": "application/json"}
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            dv = response.json()
            size = dv.get("status", {}).get("amount", None)
            if size:
                return size
            return dv.get("spec", {}).get("pvc", {}).get("resources", {}).get("requests", {}).get("storage") or ""
        raise Exception(f"No se pudo obtener el tamaño del DataVolume {dv_name}")

    def get_pvc_size(self, api_url: str, namespace: str, pvc_name: str) -> str:
        url = f"{api_url}/api/v1/namespaces/{namespace}/persistentvolumeclaims/{pvc_name}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            pvc = response.json()
            capacity = pvc.get("status", {}).get("capacity", {}).get("storage")
            if capacity:
                return capacity
        raise Exception(f"No se pudo obtener el tamaño del PVC {pvc_name}")

    def clone_pvc_with_datavolume(self, api_url: str, namespace: str, source_pvc_name: str, cloned_pvc_name: str, storage_class: str, storage_size: str) -> bool:
        dv_url = f"{api_url}/apis/cdi.kubevirt.io/v1beta1/namespaces/{namespace}/datavolumes"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        body: Dict[str, Any] = {
            "apiVersion": "cdi.kubevirt.io/v1beta1",
            "kind": "DataVolume",
            "metadata": {"name": cloned_pvc_name, "namespace": namespace},
            "spec": {
                "source": {
                    "pvc": {"name": source_pvc_name, "namespace": namespace}
                },
                "pvc": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": storage_size}},
                    "storageClassName": storage_class
                }
            }
        }
        response = requests.post(dv_url, headers=headers, json=body, verify=False)
        if response.status_code == 201:
            logging.info(f"DataVolume '{cloned_pvc_name}' creado exitosamente")
            return True
        logging.error(f"Fallo al crear DataVolume: {response.status_code} {response.text}")
        return False

    def create_vm_from_pvc(self, api_url: str, namespace: str, source_vm_name: str, new_vm_name: str, new_dv_name: str, source_pvc_name: str) -> bool:
        original_vm_url = f"{api_url}/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines/{source_vm_name}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        resp = requests.get(original_vm_url, headers=headers, verify=False)
        if resp.status_code != 200:
            logging.error(f"No se pudo obtener la VM origen: {resp.status_code} {resp.text}")
            return False

        vm_obj = resp.json()
        vm_obj['metadata']['name'] = new_vm_name

        for k in ['resourceVersion', 'uid', 'selfLink']:
            vm_obj['metadata'].pop(k, None)
        vm_obj.pop('status', None)

        vm_obj['spec'].pop('running', None)
        vm_obj['spec']['runStrategy'] = 'Always'

        for vol in vm_obj['spec']['template']['spec']['volumes']:
            if 'dataVolume' in vol:
                vol['dataVolume']['name'] = new_dv_name
            elif 'persistentVolumeClaim' in vol:
                vol['persistentVolumeClaim']['claimName'] = new_dv_name

        vm_obj['spec']['dataVolumeTemplates'] = [{
            "metadata": {"name": new_dv_name},
            "spec": {
                "source": {"pvc": {"name": source_pvc_name}},
                "pvc": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "399Gi"}},
                    "storageClassName": "crc-csi-hostpath-provisioner"
                }
            }
        }]

        interfaces = vm_obj.get('spec', {}).get('template', {}).get('spec', {}).get('domain', {}).get('devices', {}).get('interfaces', [])
        for iface in interfaces:
            iface.pop('macAddress', None)

        create_url = f"{api_url}/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines"
        headers["Content-Type"] = "application/json"
        resp = requests.post(create_url, headers=headers, json=vm_obj, verify=False)
        if resp.status_code == 201:
            logging.info(f"VM '{new_vm_name}' creada correctamente con DataVolumeTemplate.")
            return True
        logging.error(f"Error creando VM: {resp.status_code} {resp.text}")
        return False

    def wait_for_datavolume_clone_progress(self, api_url: str, namespace: str, datavolume_name: str, timeout: int = 3000, polling_interval: int = 5) -> bool:
        url = f"{api_url}/apis/cdi.kubevirt.io/v1beta1/namespaces/{namespace}/datavolumes/{datavolume_name}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        start = time.time()
        while time.time() - start < timeout:
            response = requests.get(url, headers=headers, verify=False)
            if response.status_code == 200:
                dv = response.json()
                status = dv.get('status', {})
                phase = status.get('phase')
                progress = status.get('progress', 'N/A')
                logging.info(f"DataVolume {datavolume_name} status: {phase}, progress: {progress}")
                if phase == 'Succeeded':
                    logging.info(f"DataVolume {datavolume_name} clonación completada")
                    return True
                elif phase == 'Failed':
                    logging.error(f"DataVolume {datavolume_name} clonación fallida")
                    return False
            else:
                logging.error(f"Error consultando DataVolume {datavolume_name}: {response.status_code}")
            time.sleep(polling_interval)
        logging.error(f"Timeout esperando clonación de DataVolume {datavolume_name}")
        return False

    def start_vm(self, api_url: str, namespace: str, vm_name: str) -> bool:
        url = f"{api_url}/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines/{vm_name}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/merge-patch+json",
            "Accept": "application/json"
        }
        body: Dict[str, Any] = {
            "spec": {
                "runStrategy": "Always"
            }
        }
        response = requests.patch(url, headers=headers, json=body, verify=False)
        if response.status_code in [200, 201]:
            logging.info(f"VM {vm_name} puesta en marcha.")
            return True
        else:
            logging.info(f"Error al arrancar la VM {vm_name}: {response.status_code} - {response.text}")
            return False

    def stop_vm(self, api_url: str, namespace: str, vm_name: str) -> bool:
        url = f"{api_url}/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines/{vm_name}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/merge-patch+json",
            "Accept": "application/json"
        }
        body: Dict[str, Any] = {
            "spec": {
                "runStrategy": "Halted"
            }
        }
        response = requests.patch(url, headers=headers, json=body, verify=False)
        if response.status_code in [200, 201]:
            logging.info(f"VM {vm_name} se apagará.")
            return True
        else:
            logging.info(f"Error al apagar la VM {vm_name}: {response.status_code} - {response.text}")
            return False

    def copy_vm_same_size(self, api_url: str, namespace: str, source_vm_name: str, new_vm_name: str, storage_class: str) -> None:
        source_pvc_name, vol_type = self.get_vm_pvc_or_dv_name(api_url, namespace, source_vm_name) #type: ignore  
        size = self.get_pvc_size(api_url, namespace, source_pvc_name)
        new_pvc_name = f"{new_vm_name}-disk"
        if self.clone_pvc_with_datavolume(api_url, namespace, source_pvc_name, new_pvc_name, storage_class, size):
            self.create_vm_from_pvc(api_url, namespace, source_vm_name, new_vm_name, new_pvc_name, source_pvc_name)
        else:
            logging.error("Error al clonar PVC")


   # @cached('test', consts.CACHE_VM_INFO_DURATION)
    def test(self) -> bool:
        # Simple test: try to enumerate VMs to check connectivity and authentication
        try:
            vm_url = f"{self.api_url}/apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachines"
            headers = {'Authorization': f'Bearer {self.get_token()}', 'Accept': 'application/json'}
            response = requests.get(vm_url, headers=headers, verify=self._verify_ssl, timeout=self._timeout)
            response.raise_for_status()
            logger.debug('Successfully enumerated VMs for test')
            return True
        except Exception as e:
            logger.error(f"Error testing Openshift by enumerating VMs: {e}")
            raise exceptions.OpenshiftConnectionError(str(e)) from e
            return False

    def enumerate_vms(self) -> collections.abc.Iterator[types.VMDefinition]:
        """
        Fetch all VMs from KubeVirt API in the current namespace as VMDefinition objects using do_request.
        """
        response = self.do_request(
            'GET',
            f'/apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachines'
        )
        vms = response.get('items', [])
        yield from (types.VMDefinition.from_dict(vm) for vm in vms)

    @cached('vms', consts.CACHE_INFO_DURATION)
    def list_vms(self) -> list[types.VMDefinition]:
        """
        List all VMs in the current namespace as VMDefinition objects.
        """
        return list(self.enumerate_vms())

    @cached('instance', consts.CACHE_VM_INFO_DURATION)
    def get_vm_info(self, vm_name: str, force: bool = False) -> types.VMDefinition | None:
        """
        Get a specific VM by name in the current namespace.
        Returns the VM dict if found, else None.
        """
        return self.get_vm_info_by_name(vm_name)
    
    @cached('instance_info', consts.CACHE_VM_INFO_DURATION)
    def get_vm_instance_info(self, vm_name: str) -> types.VMInstanceInfo | None:
        """
        Get a specific VM Instance by name in the current namespace.
        Returns the VM Instance info if found, else None.
        """
        return self.get_vm_instance_info_by_name(vm_name)

    def start_instance(self, vm_name: str) -> bool:
        """
        Start a specific VM by name.
        Returns True if started successfully, False otherwise.
        """
        return self.start_vm(self.api_url, self.namespace, vm_name)

    def stop_instance(self, vm_name: str) -> bool:
        """
        Stop a specific VM by name.
        Returns True if stopped successfully, False otherwise.
        """
        return self.stop_vm(self.api_url, self.namespace, vm_name)
    
    def delete_instance(self, vm_name: str) -> bool:
        """
        Delete a specific VM by name.
        Returns True if deleted successfully, False otherwise.
        """
        path = f"apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachines/{vm_name}"
        try:
            self.do_request('DELETE', path)
            return True
        except Exception as e:
            logging.error(f"Error deleting VM: {e}")
            return False

    def clone_instance(self, source_vm_name: str, new_vm_name: str, storage_class: str) -> bool:
        """
        Clone a VM by name, creating a new VM with the same size.
        Returns True if clone succeeded, False otherwise.
        """
        try:
            self.copy_vm_same_size(self.api_url, self.namespace, source_vm_name, new_vm_name, storage_class)
            return True
        except Exception as e:
            logging.error(f"Error cloning VM: {e}")
            return False
        
    @staticmethod
    def validate_vm_id(vm_id: str | int) -> None:
        try:
            int(vm_id)
        except ValueError:
            raise exceptions.OpenshiftNotFoundError(f'VM {vm_id} not found')


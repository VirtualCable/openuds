#
# Copyright (c) 2025 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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

    _session: requests.Session | None = None

    cache: 'Cache | None'

    def __init__(
        self,
        cluster_url: str,
        api_url: str,
        username: str,
        password: str,
        namespace: str = 'default',
        timeout: int = 5,
        verify_ssl: bool = False,
        cache: 'Cache | None' = None,
    ) -> None:
        self.cluster_url = cluster_url
        self.api_url = api_url
        self.username: str = username
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

    def get_token(self) -> str | None:
        try:
            url = (
                f"{self.cluster_url}/oauth/authorize?client_id=openshift-challenging-client&response_type=token"
            )
            r = requests.get(
                url, auth=(self.username, self.password), timeout=15, allow_redirects=True, verify=False
            )
            if "access_token=" not in r.url:
                raise Exception("access_token not found in response URL")
            token = r.url.split("access_token=")[1].split("&")[0]
            return token
        except Exception as ex:
            logging.error(f"Could not obtain token: {ex}")
            raise

    def connect(self, force: bool = False) -> requests.Session:
        # For testing, always use the fixed token
        session = self._session = security.secure_requests_session(verify=self._verify_ssl)
        session.headers.update(
            {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.get_token()}',
            }
        )
        return session

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
    ) -> collections.abc.Iterator[typing.Any]:
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

    # * --- OpenShift resource Methods ---*

    def get_vm_info(self, vm_name: str) -> types.VM:
        """
        Get VM information by name.
        Returns the VM object if found, else None.
        """
        response: dict[str, typing.Any] = {}
        response: dict[str, typing.Any] = self.do_request(
            'GET', f"/apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachines/{vm_name}"
        )

        try:
            response['instance'] = self.do_request(
                'GET', f"/apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachineinstances/{vm_name}"
            )
        except exceptions.OpenshiftNotFoundError:
            pass  # If the VMInstance is not found, we can still return the VM info

        logger.debug(f"VM info for '{vm_name}': {response}")
        return types.VM.from_dict(response)

    def get_vm_interfaces(self, vm_name: str) -> list[types.Interface]:
        """
        Get the interfaces of a VM by name.
        Returns a list of Interface objects.
        """
        try:
            interfaces = self.do_request(
                'GET', f"/apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachineinstances/{vm_name}"
            ).get('status', {}).get('interfaces', [])
        except exceptions.OpenshiftNotFoundError:
            return []  # If the VMInstance is not found, return an empty list
        
        return [types.Interface.from_dict(iface) for iface in interfaces]

    def get_vm_pvc_or_dv_name(self, api_url: str, namespace: str, vm_name: str) -> tuple[str, str]:
        """
        Returns the name of the PVC or DataVolume used by the VM.
        """
        path = f"/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines/{vm_name}"
        response = self.do_request('GET', path)
        volumes = response.get("spec", {}).get("template", {}).get("spec", {}).get("volumes", [])
        for vol in volumes:
            pvc = vol.get("persistentVolumeClaim")
            if pvc:
                return pvc.get("claimName"), "pvc"
            dv = vol.get("dataVolume")
            if dv:
                return dv.get("name"), "dv"
        raise Exception(f"No PVC or DataVolume found in VM {vm_name}")

    def get_datavolume_phase(self, datavolume_name: str) -> types.State:
        """
        Get the phase of a DataVolume.
        Returns the phase as a VMStatus.
        """
        path = f"/apis/cdi.kubevirt.io/v1beta1/namespaces/{self.namespace}/datavolumes/{datavolume_name}"
        try:
            response = self.do_request('GET', path)
            return types.State.from_string(response.get('status', {}).get('phase', ''))
        except Exception:
            pass
        return types.State.UNKNOWN

    def get_datavolume_size(self, namespace: str, datavolume_name: str) -> str:
        """
        Get the size of a DataVolume.
        Returns the size as a string.
        """
        path = f"/apis/cdi.kubevirt.io/v1beta1/namespaces/{namespace}/datavolumes/{datavolume_name}"
        response = self.do_request('GET', path)
        size = response.get("status", {}).get("amount", None)
        if size:
            return size
        return (
            response.get("spec", {}).get("pvc", {}).get("resources", {}).get("requests", {}).get("storage")
            or ""
        )

    def get_pvc_size(self, api_url: str, namespace: str, pvc_name: str) -> str:
        """
        Get the size of a PVC.
        Returns the size as a string.
        """
        path = f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{pvc_name}"
        response = self.do_request('GET', path)
        capacity = response.get("status", {}).get("capacity", {}).get("storage")
        if capacity:
            return capacity
        raise Exception(f"Could not get the size of PVC {pvc_name}")

    def get_pvc_storage_class_and_volume_mode(
        self, api_url: str, namespace: str, source_pvc_name: str
    ) -> tuple[str | None, str | None]:
        # Get the storageClassName and volumeMode of the source PVC
        path = f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{source_pvc_name}"
        response = self.do_request('GET', path)
        source_storage_class = response.get("spec", {}).get("storageClassName", None)
        source_volume_mode = response.get("spec", {}).get("volumeMode", None)
        return source_storage_class, source_volume_mode

    def clone_pvc_with_datavolume(
        self,
        api_url: str,
        namespace: str,
        source_pvc_name: str,
        cloned_pvc_name: str,
        storage_class: str,
        storage_size: str,
    ) -> bool:
        """
        Clone a PVC using a DataVolume.
        Returns True if the DataVolume was created successfully, else False.
        """
        path = f"/apis/cdi.kubevirt.io/v1beta1/namespaces/{namespace}/datavolumes"
        body: dict[str, typing.Any] = {
            "apiVersion": "cdi.kubevirt.io/v1beta1",
            "kind": "DataVolume",
            "metadata": {"name": cloned_pvc_name, "namespace": namespace},
            "spec": {
                "source": {"pvc": {"name": source_pvc_name, "namespace": namespace}},
                "pvc": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": storage_size}},
                    "storageClassName": storage_class,
                },
            },
        }
        try:
            self.do_request('POST', path, data=body)
            logging.info(f"DataVolume '{cloned_pvc_name}' created successfully")
            return True
        except Exception as e:
            logging.error(f"Failed to create DataVolume: {e}")
            return False

    def create_vm_from_pvc(
        self,
        api_url: str,
        namespace: str,
        source_vm_name: str,
        new_vm_name: str,
        new_dv_name: str,
        source_pvc_name: str,
    ):
        """
        Create a new VM from a cloned PVC using DataVolumeTemplates.
        Returns True if the VM was created successfully, else False.
        """
        path = f"/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines/{source_vm_name}"
        vm_obj = self.do_request('GET', path)

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

        # Use the source PVC size and volumeMode for the new DataVolumeTemplate
        pvc_size = self.get_pvc_size(api_url, namespace, source_pvc_name)

        source_storage_class, source_volume_mode = self.get_pvc_storage_class_and_volume_mode(
            api_url, namespace, source_pvc_name
        )

        pvc_spec = {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": pvc_size}},
            "storageClassName": source_storage_class,
        }
        if source_volume_mode:
            pvc_spec["volumeMode"] = source_volume_mode
        vm_obj['spec']['dataVolumeTemplates'] = [
            {
                "metadata": {"name": new_dv_name},
                "spec": {
                    "source": {"pvc": {"name": source_pvc_name}},
                    "pvc": pvc_spec,
                },
            }
        ]

        interfaces = (
            vm_obj.get('spec', {})
            .get('template', {})
            .get('spec', {})
            .get('domain', {})
            .get('devices', {})
            .get('interfaces', [])
        )
        for iface in interfaces:
            iface.pop('macAddress', None)

        logger.info(f"Creating VM '{new_vm_name}' from cloned PVC '{new_dv_name}'.")
        # logger.info(f"VM Object: {vm_obj}")

        create_path = f"/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines"
        self.do_request('POST', create_path, data=vm_obj)

    def delete_vm(self, api_url: str, namespace: str, vm_name: str) -> bool:
        """
        Delete a VM by name.
        Returns True if the VM was deleted successfully, else False.
        Treats 404 (not found) as success (idempotent delete).
        """
        from . import exceptions as oshift_exceptions

        try:
            path = f"/apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachines/{vm_name}"
            self.do_request('DELETE', path)
        except oshift_exceptions.OpenshiftNotFoundError:
            logging.info(f"VM {vm_name} not found when deleting, treating as already deleted.")
            return True
        except Exception as e:
            logging.error(f"Error deleting VM: {e}")
            return False

        # Delete persistent volume
        pv_path = "/api/v1/persistentvolumes"
        try:
            pvs_resp = self.do_request('GET', pv_path)
            if pvs_resp.get("items", []):
                for pv in pvs_resp.get("items", []):
                    claim_ref = pv.get("spec", {}).get("claimRef", {})
                    if (
                        claim_ref.get("name") == f"{vm_name}-disk"
                        and claim_ref.get("namespace") == self.namespace
                        and pv.get('status', {}).get('phase') == 'Released'
                    ):
                        pv_name = pv.get("metadata", {}).get("name")
                        pv_path = f"/api/v1/persistentvolumes/{pv_name}"
                        try:
                            self.do_request('DELETE', pv_path)
                        except oshift_exceptions.OpenshiftNotFoundError:
                            logger.info(f"PV {pv_name} not found when deleting, treating as already deleted.")
        except Exception as e:
            logger.warning(f"Could not delete associated PV for VM {vm_name}: {e}")

        return True

    def start_vm(self, api_url: str, namespace: str, vm_name: str) -> bool:
        """
        Start a VM by name.
        Returns True if the VM was started successfully, else False.
        """

        # Get Vm info
        path = f"/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines/{vm_name}"
        try:
            vm_obj = self.do_request('GET', path)
        except Exception as e:
            logging.error(f"Could not get source VM: {e}")
            return False

        # Update runStrategy to Always
        vm_obj['spec']['runStrategy'] = 'Always'
        try:
            self.do_request('PUT', path, data=vm_obj)
            logging.info(f"VM {vm_name} will be started.")
            return True
        except Exception as e:
            logging.info(f"Error starting VM {vm_name}: {e}")
            return False

    def stop_vm(self, api_url: str, namespace: str, vm_name: str) -> bool:
        """
        Stop a VM by name.
        Returns True if the VM was stopped successfully, else False.
        """
        # Get Vm info
        path = f"/apis/kubevirt.io/v1/namespaces/{namespace}/virtualmachines/{vm_name}"
        try:
            vm_obj = self.do_request('GET', path)
        except Exception as e:
            logging.error(f"Could not get source VM: {e}")
            return False

        # Update runStrategy to Halted
        vm_obj['spec']['runStrategy'] = 'Halted'
        try:
            self.do_request('PUT', path, data=vm_obj)
            logging.info(f"VM {vm_name} will be stopped.")
            return True
        except Exception as e:
            logging.info(f"Error starting VM {vm_name}: {e}")
            return False

    def copy_vm_same_size(
        self, api_url: str, namespace: str, source_vm_name: str, new_vm_name: str, storage_class: str
    ) -> None:
        """
        Copy a VM by name, creating a new VM with the same size.
        """
        source_pvc_name, vol_type = self.get_vm_pvc_or_dv_name(api_url, namespace, source_vm_name)  # type: ignore
        size = self.get_pvc_size(api_url, namespace, source_pvc_name)
        new_pvc_name = f"{new_vm_name}-disk"
        if self.clone_pvc_with_datavolume(
            api_url, namespace, source_pvc_name, new_pvc_name, storage_class, size
        ):
            self.create_vm_from_pvc(
                api_url, namespace, source_vm_name, new_vm_name, new_pvc_name, source_pvc_name
            )
        else:
            logging.error("Error cloning PVC")

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

    def enumerate_vms(self) -> collections.abc.Iterator[types.VM]:
        """
        Fetch all VMs from KubeVirt API in the current namespace as VMDefinition objects using do_request.
        """
        response = self.do_request('GET', f'/apis/kubevirt.io/v1/namespaces/{self.namespace}/virtualmachines')
        vms = response.get('items', [])
        yield from (types.VM.from_dict(vm) for vm in vms)

    @cached('vms', consts.CACHE_INFO_DURATION)
    def list_vms(self) -> list[types.VM]:
        """
        List all VMs in the current namespace as VMDefinition objects.
        """
        return list(self.enumerate_vms())

    def start_vm_instance(self, vm_name: str) -> bool:
        """
        Start a specific VM by name.
        Returns True if started successfully, False otherwise.
        """
        return self.start_vm(self.api_url, self.namespace, vm_name)

    def stop_vm_instance(self, vm_name: str) -> bool:
        """
        Stop a specific VM by name.
        Returns True if stopped successfully, False otherwise.
        """
        return self.stop_vm(self.api_url, self.namespace, vm_name)

    def delete_vm_instance(self, vm_name: str) -> bool:
        """
        Delete a specific VM by name.
        Returns True if deleted successfully, False otherwise.
        Treats 404 (not found) as success (idempotent delete).
        """
        return self.delete_vm(self.api_url, self.namespace, vm_name)

# Copyright: Devon Mar (@devon-mar)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

import json
from urllib.parse import urlencode, urljoin

from ansible.errors import AnsibleError, AnsibleParserError
from ansible.module_utils._text import to_native
from ansible.module_utils.six.moves.urllib.error import HTTPError, URLError
from ansible.module_utils.urls import ConnectionError, SSLValidationError, open_url
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display

__metaclass__ = type

DOCUMENTATION = """
name: list
author: Devon Mar (@devon-mar)
version_added: "0.1.0"
short_description: Returns an array of IPs/prefixes
description:
  - This lookup returns IPs/prefixes from the NetBox lists plugin for NetBox.
options:
  _terms:
    description: The NetBox lists endpoint(s).
    required: True
  url_:
    description: The URL to the NetBox instance with the lists plugin.
    type: str
    required: true
    env:
      - name: NETBOX_API
      - name: NETBOX_URL
  token_:
    description: The NetBox API token.
    type: str
    vars:
      - name: netbox_token
    env:
      - name: NETBOX_TOKEN
      - name: NETBOX_API_TOKEN
  lists_path_:
    description: Path to the Netbox lists API root. To be appended to I(url_).
    type: str
    default: "/api/plugins/lists/"
    env:
      - name: NETBOX_LISTS_PATH
  allow_empty_:
    type: bool
    default: False
    description: If C(false), an exception will be raised if the returned list is empty.
    env:
      - name: NETBOX_LISTS_ALLOW_EMPTY
  key_value:
    description:
      - Arbitrary C(key=value) pairs to be passed to NetBox lists as filters.
      - C(key_value) is not an actual option for this lookup plugin.
    type: dict
"""

RETURN = r"""
_raw:
  type: list
  elements: str
  description:
    - The list of IPs/prefixes.
"""

display = Display()


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        # lookups in general are expected to both take a list as input and output a list
        # this is done so they work with the looping construct 'with_'.
        ret = []

        filters = {k: kwargs.pop(k) for k in list(kwargs) if not k.endswith("_")}

        self.set_options(var_options=variables, direct=kwargs)

        netbox_url = self.get_option("url_")
        netbox_token = self.get_option("token_")
        allow_empty = self.get_option("allow_empty_")
        lists_path = self.get_option("lists_path_")

        headers = {"Accept": "application/json"}
        if netbox_token:
            headers["Authorization"] = "Token %s" % netbox_token

        if any(len(term) == 0 for term in terms):
            raise AnsibleError("Received empty term")

        lists_url = urljoin(netbox_url, lists_path)
        for term in terms:
            url = urljoin(
                lists_url,
                # Prevent unecessary redirect
                term if term[-1] == "/" else term + "/",
            )

            if filters:
                url += "?" + urlencode(filters, doseq=True)

            display.vvvv("nblists: NetBox list url: %s" % url)

            try:
                response = open_url(url, headers=headers)
            except HTTPError as e:
                raise AnsibleError(
                    "Received HTTP error for %s : %s" % (url, to_native(e))
                )
            except URLError as e:
                raise AnsibleError(
                    "Failed lookup url for %s : %s" % (url, to_native(e))
                )
            except SSLValidationError as e:
                raise AnsibleError(
                    "Error validating the server's certificate for %s: %s"
                    % (url, to_native(e))
                )
            except ConnectionError as e:
                raise AnsibleError("Error connecting to %s: %s" % (url, to_native(e)))

            try:
                parsed = json.loads(response.read())
            except Exception as e:
                raise AnsibleParserError(
                    "Could not parse JSON response for %s: %s" % (url, to_native(e))
                )

            if not isinstance(parsed, list):
                raise AnsibleParserError("Response was not a list for %s" % url)

            if not allow_empty and len(parsed) == 0:
                raise AnsibleError("Got empty list for %s" % url)

            ret += parsed

        return ret

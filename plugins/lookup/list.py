# Copyright: Devon Mar (@devon-mar)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
name: list
author: Devon Mar (@devon-mar)
version_added: "0.1.0"
short_description: Returns an array of IPs/prefixes
description:
  - >-
    This lookup returns IPs/prefixes from the L(NetBox lists,https://github.com/devon-mar/netbox-lists) plugin for
    L(NetBox,https://github.com/netbox-community/netbox).
options:
  _terms:
    description:
      - The NetBox lists endpoint(s). For example, C(ip-addresses), C(prefixes), C(tags/<tag-slug>) or C(devices).
      - This is the part that comes after C(https://<your NetBox URL>/api/plugins/lists/).
      - See the plugin section of the API documentation of your NetBox instance for all endpoints.
    required: True
  url_:
    description: The URL to the NetBox instance with the Lists plugin.
    type: str
    required: true
    env:
      - name: NETBOX_API
      - name: NETBOX_URL
  token_:
    description: The NetBox API token.
    type: str
    env:
      - name: NETBOX_TOKEN
      - name: NETBOX_API_TOKEN
  lists_path_:
    description: Path to the Netbox Lists API root. To be appended to I(url_).
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
      - I(key_value) is not an actual option for this lookup plugin.
      - Use a C(list), C(set) or C(tuple) as the value to use a filter more than once. 
    type: dict
"""

RETURN = r"""
_raw:
  type: list
  elements: str
  description:
    - The list of IPs/prefixes.
"""

EXAMPLES = r"""
- name: Get all NetBox IP addresses with the tag 'special'
  ansible.builtin.debug:
    msg: "{{ q('devon_mar.nblists.list', 'ip-addresses', tag='special') }}"

- name: Manually specify a token and URL.
  ansible.builtin.debug:
    msg: "{{ q('devon_mar.nblists.list', 'ip-addresses', tag='special', url_='https://netbox.example.com', token_='abc123') }}"

# Build an ACL using all NetBox prefixes with the role 'data'
- name: Build ACL 10
  ansible.builtin.set_fact:
    acl_10_aces: "{{ acl_10_aces | default([]) + ace }}"
  vars:
    ace:
      - grant: permit
        source:
          address: "{{ item | ansible.utils.ipaddr('network') }}"
          wildcard_bits: "{{ item | ansible.utils.ipaddr('wildcard') }}"
  loop: "{{ q('devon_mar.nblists.list', 'prefixes', role='data') }}"
- name: Ensure ACLs are configured
  cisco.ios.ios_acls:
    config:
      - afi: ipv4
        acls:
          - name: 10
            aces: "{{ acl_10_aces }}"
"""

import json
from urllib.parse import urlencode, urljoin

from ansible.errors import AnsibleError, AnsibleParserError
from ansible.module_utils._text import to_native
from ansible.module_utils.urls import open_url
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display

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

        if any(len(term) == 0 or term == "/" for term in terms):
            raise AnsibleError("Received empty term")

        lists_url = urljoin(netbox_url, lists_path)
        for term in terms:
            url = urljoin(
                lists_url,
                # Prevent unecessary redirect
                term if term[-1] == "/" else term + "/",
            )

            if filters:
                url_filters = []
                for k, v in filters.items():
                    if isinstance(v, (list, set, tuple)):
                        url_filters.extend((k, x) for x in v)
                    else:
                        url_filters.append((k, v))

                url += "?" + urlencode(filters, doseq=True)

            display.vvvv("nblists: NetBox list url: %s" % url)

            try:
                response = open_url(url, headers=headers)
            except Exception as e:
                raise AnsibleError(
                    "Error making request to '%s': %s" % (url, to_native(e))
                )

            try:
                parsed = json.loads(response.read())
            except Exception as e:
                raise AnsibleParserError(
                    "Could not parse JSON response for '%s': %s" % (url, to_native(e))
                )

            if not isinstance(parsed, list):
                raise AnsibleParserError("Response was not a list for %s" % url)

            if not allow_empty and len(parsed) == 0:
                raise AnsibleError("Got empty list for %s" % url)

            ret += parsed

        return ret

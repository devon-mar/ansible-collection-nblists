#!/usr/bin/env bash

cd "${BASH_SOURCE%/*}" || exit
ANSIBLE_ROLES_PATH="../" ansible-playbook "files/${1:-setup}.yml"

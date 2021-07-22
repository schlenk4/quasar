#!/usr/bin/env python3

#TODO authors etc
import os
import argparse

def clone_quasar(test_branch):
    os.system(f'git clone --recursive -b {test_branch} --depth=1 https://github.com/quasar-team/quasar.git')

def prepare_opcua_backend(opcua_backend, open62541_compat_branch):
    if opcua_backend == 'o6':
        os.system(f'./quasar.py enable_module open62541-compat {open62541_compat_branch}')
    pass

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--clone', action='store_true')
    parser.add_argument('--quasar_branch', default='master')
    parser.add_argument('--opcua_backend')
    parser.add_argument('--open62541_compat_branch')

    args = parser.parse_args()

    if args.clone:
        clone_quasar(args.quasar_branch)

    prepare_opcua_backend(args.opcua_backend, args.open62541_compat_branch)

    print('a')
    pass

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# encoding: utf-8
'''
externalToolCheck.py

@author:     Damian Abalo Miron <damian.abalo@cern.ch>
@author:	 Piotr Nikiel

@copyright:  2016 CERN

@license:
Copyright (c) 2016, CERN, Universidad de Oviedo.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted
provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions
   and the following disclaimer in the documentation and/or other materials provided with the
   distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT  HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS  OR
IMPLIED  WARRANTIES, INCLUDING, BUT NOT  LIMITED TO, THE IMPLIED WARRANTIES  OF  MERCHANTABILITY
AND  FITNESS  FOR  A  PARTICULAR  PURPOSE  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,  SPECIAL, EXEMPLARY, OR  CONSEQUENTIAL
DAMAGES (INCLUDING, BUT  NOT LIMITED TO,  PROCUREMENT OF  SUBSTITUTE GOODS OR  SERVICES; LOSS OF
USE, DATA, OR PROFITS; OR BUSINESS  INTERRUPTION) HOWEVER CAUSED AND ON ANY  THEORY  OF  LIABILITY,
WHETHER IN  CONTRACT, STRICT  LIABILITY,  OR  TORT (INCLUDING  NEGLIGENCE OR OTHERWISE)  ARISING IN
ANY WAY OUT OF  THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

@contact:    quasar-developers@cern.ch
'''

import os
import platform
import subprocess
from subprocess import Popen
from commandMap import getCommand
from quasarExceptions import WrongReturnValue
from colorama import Fore, Back, Style

StandardMessage = 'Check the website https://quasar.docs.cern.ch for instructions'

def checkExecutableExists(executableKeyName, doesNotExistErrorMessage, executableArgument='-h'):
    errorMessage = (
        f'executable [key: {executableKeyName}, command: {getCommand(executableKeyName)}]'
        ' cannot be found. Maybe it is not installed, or maybe it is not set in the PATH. \n'
        f'{doesNotExistErrorMessage}')
    try:
        returnCode = subprocess.call([getCommand(executableKeyName), executableArgument],
            stdout=open(os.devnull, 'wb'), stderr=subprocess.STDOUT)
        if returnCode == 0:
            print((
                f"executable [key:{executableKeyName}, command: "
                f"{getCommand(executableKeyName)}] {Fore.GREEN}exists{Style.RESET_ALL}"))
        else:
            raise Exception(errorMessage)
    except:
        raise Exception(errorMessage)

def checkAstyle():
    checkExecutableExists('astyle', StandardMessage)

def checkXsdcxx():
    checkExecutableExists('xsdcxx', StandardMessage, "--version" )

def checkKdiff3():
    if platform.system() == "Linux":
        return checkExecutableExists('diff', StandardMessage, '--version')
    #if the system is a windows machine then:
    errorMessageWindows = "kdiff3 cannot be found. Maybe it is not installed, or maybe it is not set in the PATH. \nkdiff3 can be downloaded in http://kdiff3.sourceforge.net/ "
    try:
        returnCode = subprocess.call(['where', getCommand('diff')],
            stdout=open(os.devnull, 'wb'),
            stderr=subprocess.STDOUT)
        if returnCode == 0:
            print("kdiff3 does exist")
        else:
            raise Exception(errorMessageWindows)
    except:
        raise Exception(errorMessageWindows)

def checkCMake():
    checkExecutableExists('cmake', StandardMessage)

def checkCompiler():
    if platform.system() == "Linux":
        checkExecutableExists('make', 'Please, install the package make using the package manager of your distribution.')
        return checkExecutableExists('gcc', 'Please, install the package gcc using the package manager of your distribution.', '--help')

def checkXMLLint():
    checkExecutableExists('xmllint', StandardMessage, '--version')

#Non compulsory dependancy (Needed for generating graphs, but QUASAR will perfectly work without GraphViz)
def checkGraphViz():
    checkExecutableExists('graphviz', StandardMessage, '-V')

#Non compulsory dependancy (Needed for generating documentation, but QUASAR will perfectly work without DoxyGen)
def checkDoxyGen():
    checkExecutableExists('doxygen', StandardMessage, '--version')

def tryDependency(functionCheck, critical=True):
    try:
        functionCheck()
    except Exception as e:
        if(critical):
            print(f"{Fore.RED}CRITICAL dependency missing: {str(e)}{Style.RESET_ALL}")
        else:
            print("Optional dependency missing: " + str(e))

def checkExternalDependencies():
    """Checks all of QUASAR dependencies to see if everything is setup as expected, and prints apropiate messages to point out what is missing."""
    tryDependency(checkKdiff3)
    tryDependency(checkCMake)
    tryDependency(checkCompiler)
    tryDependency(checkXMLLint)
    tryDependency(checkAstyle)
    tryDependency(checkXsdcxx)
    tryDependency(checkGraphViz, False)
    tryDependency(checkDoxyGen, False)

def subprocessWithImprovedErrors(subprocessCommand, dependencyName, validReturnCodes=[0]):
    """Method that calls subprocess, but print intelligent error messages if there are any exceptions caught.

    Keyword arguments:
    subprocessCommand -- String or list of strings that will be given to subprocess
    dependencyName -- parameterless name of the command, just for error loging purposes
    validReturnCodes -- array of acceptable return codes, only 0 by default. If the return code is not in the list and exception will be thrown
    """
    try:
        returnCode = subprocess.call(subprocessCommand)
    except OSError as e:
        raise Exception("There was an OS error when trying to execute the program [" + dependencyName + "]. This probably means that a dependency is missing or non-accesible; Exception: [" + str(e) + "]. For more details run the command 'quasar.py external_tool_check'.")
    except Exception as e:
        raise Exception("There was an application error when trying to execute the program [" + dependencyName + "]. Exception: [" + str(e) + "]")
    if returnCode not in validReturnCodes:
        raise WrongReturnValue(dependencyName, returnCode)

def subprocessWithImprovedErrorsPipeOutputToFile(subprocessCommand, outputFile, dependencyName, validReturnCodes=[0]):
    """Method that calls subprocess, but print intelligent error messages if there are any exceptions catched, and then pipes the output of the process to the given file

    Keyword arguments:
    subprocessCommand -- String or list of strings that will be given to subprocess
    dependencyName    -- parameterless name of the command, just for error loging purposes
    outputFile        -- file where the std out of the process will be written into
    validReturnCodes  -- array of acceptable return codes, only 0 by default. If the return code is not in the list and exception will be thrown
    """
    print('Calling {tool} with args {args} with output to file {out}'.format(
            tool=dependencyName,
            args=' '.join(subprocessCommand),
            out=outputFile))
    try:
        with open(outputFile,"wb") as out:
            process = subprocess.Popen(subprocessCommand, stdout=out)
            streamdata = process.communicate()
            returnCode = process.returncode
    except OSError as e:
        raise Exception("There was an OS error when trying to execute the program [" + dependencyName + "]. This probably means that a dependency is missing or non-accesible; Exception: [" + str(e) + "]. For more details run the command 'quasar.py external_tool_check'.")
    except Exception as e:
        raise Exception("There was an application error when trying to execute the program [" + dependencyName + "]. Exception: [" + str(e) + "]")
    if returnCode not in validReturnCodes:
        raise WrongReturnValue(dependencyName, returnCode)
